#!/usr/bin/env python3
"""Genera 50 preguntas por tema a partir de 25 hechos revisados y las integra.

El script es idempotente: elimina de ``index.html`` las preguntas temáticas
generadas previamente (sim T2..T31) y vuelve a crearlas desde ``topic-banks``.
No cambia los identificadores ni la clave de progreso de la PWA.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
BANK_DIR = ROOT / "topic-banks"

THEME_LABELS = {
    "higiene": "Higiene y unidad del paciente",
    "movilizacion": "Movilización y posiciones",
    "upp": "Úlceras por presión",
    "constantes": "Constantes vitales y balance",
    "eliminacion": "Eliminación, sondajes y ostomías",
    "alimentacion": "Alimentación y nutrición",
    "medicacion": "Medicación y oxigenoterapia",
    "instrumental": "Instrumental quirúrgico",
    "infeccion": "Asepsia, esterilización y aislamientos",
    "muestras": "Muestras, residuos y seguridad",
    "urgencias": "Urgencias, RCP y primeros auxilios",
    "geriatria": "Geriatría, terminal y comunicación",
    "calidad": "Calidad, organización y documentación",
    "legislacion": "Legislación y parte común",
}

DIRECT_TEMPLATES = (
    "Señale la afirmación correcta sobre «{term}»:",
    "¿Qué opción describe correctamente «{term}»?",
    "En relación con «{term}», indique la respuesta correcta:",
    "¿Cuál es la característica correcta de «{term}»?",
)
REVERSE_TEMPLATES = (
    "¿A qué concepto corresponde esta descripción: «{definition}»?",
    "Identifique el concepto descrito: «{definition}».",
    "La descripción «{definition}» se refiere a:",
    "¿Qué término se ajusta a la siguiente definición: «{definition}»?",
)


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\W+", " ", text).strip()


def place(correct: str, distractors: list[str], position: int) -> tuple[list[str], int]:
    options = list(distractors)
    options.insert(position, correct)
    if len(options) != 4 or len(set(options)) != 4:
        raise ValueError(f"Opciones no únicas: {options}")
    return options, position


def generate_bank(spec: dict) -> list[dict]:
    number = int(spec["tema_num"])
    facts = spec["facts"]
    if len(facts) != 25:
        raise ValueError(f"Tema {number}: se esperaban 25 hechos, hay {len(facts)}")

    terms = [f["term"].strip() for f in facts]
    definitions = [f["definition"].strip() for f in facts]
    if len({norm(x) for x in terms}) != 25:
        raise ValueError(f"Tema {number}: términos repetidos")
    if len({norm(x) for x in definitions}) != 25:
        raise ValueError(f"Tema {number}: definiciones repetidas")

    out = []
    for i, fact in enumerate(facts):
        term, definition = terms[i], definitions[i]
        offsets = (1, 7, 13)
        other_defs = [definitions[(i + off) % 25] for off in offsets]
        other_terms = [terms[(i + off) % 25] for off in offsets]
        broad_theme = fact.get("tema", spec["tema_default"])
        if broad_theme not in THEME_LABELS:
            raise ValueError(f"Tema {number}, hecho {i + 1}: categoría inválida {broad_theme}")

        opts, correct = place(definition, other_defs, (number + 2 * i) % 4)
        out.append({
            "sim": f"T{number}",
            "tag": spec["tag"],
            "n": f"T{number}-{2 * i + 1}",
            "q": DIRECT_TEMPLATES[i % len(DIRECT_TEMPLATES)].format(term=term),
            "caso": "",
            "opts": opts,
            "correct": correct,
            "expl": f"{term}: {definition}",
            "tema": broad_theme,
            "bloque": THEME_LABELS[broad_theme],
        })

        opts, correct = place(term, other_terms, (number + 2 * i + 1) % 4)
        out.append({
            "sim": f"T{number}",
            "tag": spec["tag"],
            "n": f"T{number}-{2 * i + 2}",
            "q": REVERSE_TEMPLATES[i % len(REVERSE_TEMPLATES)].format(definition=definition),
            "caso": "",
            "opts": opts,
            "correct": correct,
            "expl": f"La descripción corresponde a {term}. {definition}",
            "tema": broad_theme,
            "bloque": THEME_LABELS[broad_theme],
        })
    return out


def decode_after(source: str, marker: str):
    start = source.index(marker) + len(marker)
    value, consumed = json.JSONDecoder().raw_decode(source[start:])
    return value, start, start + consumed


def main() -> None:
    html = INDEX.read_text(encoding="utf-8")
    data, data_start, data_end = decode_after(html, "const DATA  = ")
    topic_sim = re.compile(r"T(?:[2-9]|[12]\d|3[01])|IR")
    existing = [q for q in data if not topic_sim.fullmatch(str(q.get("sim", "")))]

    generated = []
    specs = []
    for path in sorted(BANK_DIR.glob("tema-*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        specs.append(spec)
        generated.extend(generate_bank(spec))

    reinforcement_path = BANK_DIR / "instrumental-refuerzo.json"
    reinforcement = json.loads(reinforcement_path.read_text(encoding="utf-8"))
    if len(reinforcement) != 12:
        raise ValueError(f"Refuerzo instrumental: se esperaban 12 preguntas, hay {len(reinforcement)}")
    for i, q in enumerate(reinforcement, 1):
        item = dict(q)
        item.update({
            "sim": "IR",
            "tag": "INSTRUMENTAL · REFUERZO",
            "n": f"IR{i}",
            "caso": item.get("caso", ""),
            "tema": "instrumental",
            "bloque": THEME_LABELS["instrumental"],
        })
        generated.append(item)

    expected_numbers = {int(s["tema_num"]) for s in specs}
    if expected_numbers != set(range(2, 32)):
        missing = sorted(set(range(2, 32)) - expected_numbers)
        raise ValueError(f"Faltan bancos temáticos: {missing}")

    seen = {norm(q["q"]) for q in existing}
    duplicates = [q["q"] for q in generated if norm(q["q"]) in seen]
    if duplicates:
        raise ValueError(f"Preguntas duplicadas con el banco previo: {duplicates[:5]}")
    stems = [norm(q["q"]) for q in generated]
    if len(stems) != len(set(stems)):
        raise ValueError("Hay enunciados duplicados entre los nuevos temas")

    for q in generated:
        if len(q["opts"]) != 4 or len(set(q["opts"])) != 4:
            raise ValueError(f"Opciones inválidas en {q['n']}")
        if not 0 <= q["correct"] <= 3 or not q["expl"].strip():
            raise ValueError(f"Respuesta o explicación inválida en {q['n']}")

    merged = existing + generated
    encoded = json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
    html = html[:data_start] + encoded + html[data_end:]

    version = time.strftime("%Y%m%d-%H%M")
    html = re.sub(r'const VERSION = "[^"]+";', f'const VERSION = "{version}";', html, count=1)
    INDEX.write_text(html, encoding="utf-8")

    sw_path = ROOT / "sw.js"
    sw = sw_path.read_text(encoding="utf-8")
    sw = re.sub(r"const VERSION = '[^']+';", f"const VERSION = '{version}';", sw, count=1)
    sw_path.write_text(sw, encoding="utf-8")

    manifest_path = ROOT / "manifest.webmanifest"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["description"] = (
        f"Practica el examen TCAE del SERGAS: {len(merged)} preguntas con "
        "corrección al momento, repaso espaciado y simulacros cronometrados."
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts = Counter(q["sim"] for q in generated)
    print(f"Banco previo conservado: {len(existing)}")
    print(f"Preguntas nuevas: {len(generated)}")
    print(f"Total app: {len(merged)}")
    print(f"Distribución respuestas: {dict(sorted(Counter(q['correct'] for q in generated).items()))}")
    print(f"Temas: {dict(sorted(counts.items()))}")


if __name__ == "__main__":
    main()
