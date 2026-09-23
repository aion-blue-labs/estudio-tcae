#!/usr/bin/env python3
"""Integra na PWA as preguntas fiables dos resumos PDF de Cristina.

O proceso é idempotente, non publica os PDF e conserva a clave de progreso.
As preguntas ambiguas, obsoletas ou inseguras quedan explicitamente excluídas.
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
PDF_BANK = ROOT / "topic-banks" / "pdf-resumenes.json"

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

TOPIC_THEME = {
    **{n: "legislacion" for n in range(1, 9)},
    9: "calidad",
    10: "calidad",
    11: "calidad",
    12: "infeccion",
    13: "geriatria",
    14: "calidad",
    15: "higiene",
    16: "movilizacion",
    17: "instrumental",
    18: "constantes",
    19: "eliminacion",
    20: "muestras",
    21: "alimentacion",
    22: "medicacion",
    23: "infeccion",
    24: "infeccion",
    25: "geriatria",
    26: "upp",
    27: "urgencias",
    28: "geriatria",
    29: "geriatria",
    30: "movilizacion",
}

# Non se integran preguntas con premisa falsa, dato obsoleto, protocolo local
# non universal ou recomendación clínica insegura/ambigua.
EXCLUDED = {
    "PDF2-2", "PDF3-5", "PDF5-7", "PDF6-1", "PDF6-5",
    "PDF10-9", "PDF11-7", "PDF12-2", "PDF12-7", "PDF13-1",
    "PDF14-10", "PDF15-7", "PDF15-8", "PDF16-3", "PDF16-9",
    "PDF17-1", "PDF17-9", "PDF20-8", "PDF22-4", "PDF23-6",
    "PDF24-8", "PDF24-10", "PDF25-2", "PDF25-4", "PDF25-5",
    "PDF25-9", "PDF26-1", "PDF28-2", "PDF28-3", "PDF28-5",
    "PDF28-7", "PDF28-10", "PDF29-6", "PDF30-2", "PDF30-3",
    "PDF30-5",
}

CORRECTIONS = {
    "PDF2-11": {
        "q": "¿Cuál es la capital de Galicia, fijada por la Ley 1/1982, de 24 de junio?",
        "expl": "Santiago de Compostela es la capital de Galicia conforme a la Ley gallega 1/1982. El Estatuto, en su artículo 8, remite la fijación de la sede a una ley de Galicia.",
    },
    "PDF4-3": {
        "q": "¿Cuántas áreas sanitarias existen en Galicia?",
        "opts": [
            "4, correspondientes a las cuatro provincias gallegas.",
            "8 áreas sanitarias.",
            "7 áreas sanitarias.",
            "12 áreas sanitarias.",
        ],
        "correct": 2,
        "expl": "Galicia se organiza en 7 áreas sanitarias. El Decreto 134/2019 sustituyó la denominación de las antiguas EOXI por áreas sanitarias.",
    },
    "PDF4-7": {
        "q": "¿Qué complejo hospitalario de referencia corresponde al Área Sanitaria de Vigo?",
        "expl": "El Complexo Hospitalario Universitario de Vigo (CHUVI) es el complejo hospitalario de referencia del Área Sanitaria de Vigo.",
    },
    "PDF4-9": {
        "q": "La organización actual por áreas sanitarias en Galicia supone, respecto al modelo anterior:",
        "expl": "Las áreas sanitarias gestionan de forma integrada la atención primaria y hospitalaria, con una gerencia común y sistemas de información compartidos.",
    },
    "PDF5-9": {
        "q": "¿Cuántos días hábiles de permiso corresponden por fallecimiento del cónyuge, pareja de hecho o familiar de primer grado?",
        "opts": [
            "1 día hábil.",
            "2 días hábiles, siempre.",
            "3 días hábiles en la misma localidad y 5 si es en distinta localidad.",
            "7 días naturales.",
        ],
        "correct": 2,
        "expl": "El TREBEP reconoce 3 días hábiles cuando el suceso se produce en la misma localidad y 5 días hábiles cuando es en distinta localidad.",
    },
    "PDF6-6": {
        "opts": [
            "El ejercicio de lengua gallega es obligatorio, salvo exención por acreditar el nivel exigido en la convocatoria.",
            "Solo se exige después del nombramiento.",
            "Se valora únicamente como mérito en la fase de concurso.",
            "No se comprueba en el proceso selectivo.",
        ],
        "correct": 0,
        "expl": "Las convocatorias del SERGAS incluyen un ejercicio obligatorio de lengua gallega; quedan exentas las personas que acreditan el nivel exigido en las bases.",
    },
    "PDF9-7": {
        "opts": [
            "5 criterios agentes y 5 de resultados.",
            "7 criterios organizados en dirección, ejecución y resultados.",
            "14 principios de gestión de la calidad de Deming.",
            "7 normas de la serie ISO 9000.",
        ],
        "correct": 1,
        "expl": "El modelo EFQM 2020 se estructura en 7 criterios agrupados en tres bloques: dirección, ejecución y resultados. El esquema de 9 criterios correspondía a versiones anteriores.",
    },
    "PDF19-2": {
        "opts": [
            "Aire estéril.",
            "Agua estéril, en el volumen indicado por el fabricante.",
            "Glicerina al 5%.",
            "Heparina sódica diluida.",
        ],
        "correct": 1,
        "expl": "El balón de una sonda Foley se infla con agua estéril y con el volumen indicado por el fabricante. El suero salino puede cristalizar y dificultar el desinflado.",
    },
    "PDF22-2": {
        "q": "¿Qué vías no parenterales puede administrar el TCAE cuando están pautadas y bajo la supervisión de enfermería, conforme al protocolo del centro?",
        "expl": "El TCAE puede colaborar en la administración por vías oral, rectal y tópica cuando existe pauta y supervisión de enfermería. No se trata de una actuación autónoma ni incluye vías parenterales.",
    },
    "PDF23-8": {
        "opts": [
            "La quirúrgica actúa principalmente como control de fuente y frente a gotas; la FFP2 filtra aerosoles inhalados y requiere buen ajuste facial.",
            "Ambas protegen exactamente igual frente a aerosoles.",
            "La FFP2 solo protege al paciente y la quirúrgica solo al profesional.",
            "Ninguna necesita cubrir nariz y boca simultáneamente.",
        ],
        "correct": 0,
        "expl": "La mascarilla quirúrgica se usa principalmente para control de fuente y protección frente a gotas; una FFP2 ajustada filtra aerosoles y protege al portador.",
    },
}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\W+", " ", text).strip()


def decode_after(source: str, marker: str):
    start = source.index(marker) + len(marker)
    value, consumed = json.JSONDecoder().raw_decode(source[start:])
    return value, start, start + consumed


def balanced_options(item: dict, target: int) -> dict:
    answer = item["opts"][item["correct"]]
    distractors = [o for i, o in enumerate(item["opts"]) if i != item["correct"]]
    options = list(distractors)
    options.insert(target, answer)
    item["opts"] = options
    item["correct"] = target
    return item


def main() -> None:
    html = INDEX.read_text(encoding="utf-8")
    data, data_start, data_end = decode_after(html, "const DATA  = ")
    existing = [q for q in data if not re.fullmatch(r"PDF(?:[1-9]|[12]\d|30)", str(q.get("sim", "")))]
    incoming = json.loads(PDF_BANK.read_text(encoding="utf-8"))

    approved = []
    for source in incoming:
        if source["n"] in EXCLUDED:
            continue
        item = dict(source)
        item.update(CORRECTIONS.get(item["n"], {}))
        topic = int(item.pop("source_topic"))
        theme = TOPIC_THEME[topic]
        item["tema"] = theme
        item["bloque"] = THEME_LABELS[theme]
        item["fuente"] = f"Resumen PDF Tema {topic} (revisado)"
        approved.append(item)

    seen = {norm(q["q"]) for q in existing}
    duplicates = [q["n"] for q in approved if norm(q["q"]) in seen]
    if duplicates:
        raise ValueError(f"Duplicados co banco existente: {duplicates}")
    if len({norm(q["q"]) for q in approved}) != len(approved):
        raise ValueError("Hai enunciados duplicados entre as preguntas PDF aprobadas")

    # A fonte concentraba case todas as respostas na opción C. Reordénanse de
    # forma determinista para evitar aprender o patrón sen cambiar o contido.
    approved = [balanced_options(q, i % 4) for i, q in enumerate(approved)]
    for q in approved:
        if len(q["opts"]) != 4 or len(set(q["opts"])) != 4:
            raise ValueError(f"Opcións inválidas en {q['n']}")
        if not 0 <= q["correct"] <= 3 or not q["expl"].strip():
            raise ValueError(f"Resposta ou explicación inválida en {q['n']}")

    merged = existing + approved
    encoded = json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
    html = html[:data_start] + encoded + html[data_end:]
    version = time.strftime("%Y%m%d-%H%M")
    html = re.sub(r'const VERSION = "[^"]+";', f'const VERSION = "{version}";', html, count=1)
    if "const KEY = 'tcae_progress_v3'" not in html:
        raise ValueError("A clave de progreso cambiou ou non aparece")
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

    print(f"Preguntas extraídas dos PDF: {len(incoming)}")
    print(f"Excluídas tras revisión: {len(EXCLUDED)}")
    print(f"Corrixidas/actualizadas: {len(CORRECTIONS)}")
    print(f"Engadidas: {len(approved)}")
    print(f"Total app: {len(merged)}")
    print(f"Respostas: {dict(sorted(Counter(q['correct'] for q in approved).items()))}")
    print(f"Versión: {version}; progreso: tcae_progress_v3")


if __name__ == "__main__":
    main()
