#!/usr/bin/env python3
"""Extrae las preguntas tipo examen incluidas en los PDF de Cristina.

No copia ni publica los PDF. Solo genera un banco JSON trazable con las
preguntas, opciones, respuesta marcada y explicación de cada tema.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
MEDIA = WORKSPACE / "media" / "inbound"
OUTPUT = ROOT / "topic-banks" / "pdf-resumenes.json"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def pdfs_by_topic() -> dict[int, Path]:
    found: dict[int, list[Path]] = {}
    for path in MEDIA.glob("**/*.pdf"):
        match = re.search(r"TEMA[_ ](\d+)", path.name, flags=re.IGNORECASE)
        if match:
            found.setdefault(int(match.group(1)), []).append(path)

    missing = sorted(set(range(1, 31)) - set(found))
    if missing:
        raise ValueError(f"Faltan PDF dos temas: {missing}")

    selected: dict[int, Path] = {}
    for number, paths in found.items():
        # Telegram pode reempaquetar dúas copias do mesmo PDF con metadatos
        # binarios distintos. Comparamos o texto real, non os bytes do contedor.
        text_hashes = {
            hashlib.sha256(
                "\n".join((page.extract_text() or "") for page in PdfReader(p).pages)
                .encode("utf-8")
            ).hexdigest()
            for p in paths
        }
        if len(text_hashes) != 1:
            raise ValueError(f"Tema {number}: hai copias PDF con texto distinto")
        selected[number] = sorted(paths)[0]
    return selected


def parse_topic(number: int, path: Path) -> list[dict]:
    text = "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)
    start = text.lower().rfind("preguntas tipo examen")
    if start < 0:
        raise ValueError(f"Tema {number}: non se atopou a sección de preguntas")
    section = text[start:]
    end = section.lower().find("resumen: lo esencial")
    if end > 0:
        section = section[:end]

    pattern = re.compile(
        r"(?ms)^\s*(\d{1,2})\s+(.+?)\n"
        r"A\)\s*(.+?)\nB\)\s*(.+?)\nC\)\s*(.+?)\nD\)\s*(.+?)\n"
        r"(.+?)(?=^\s*\d{1,2}\s+|\Z)"
    )
    out: list[dict] = []
    for match in pattern.finditer(section):
        qnum = int(match.group(1))
        stem = clean(match.group(2))
        raw_options = [clean(match.group(i)) for i in range(3, 7)]
        marked = [i for i, option in enumerate(raw_options) if "✓" in option]
        if len(marked) != 1:
            raise ValueError(f"Tema {number}, pregunta {qnum}: resposta marcada ambigua")
        options = [clean(option.replace("✓", "")) for option in raw_options]
        explanation = clean(match.group(7))
        out.append(
            {
                "sim": f"PDF{number}",
                "tag": f"PDF · TEMA {number}",
                "n": f"PDF{number}-{qnum}",
                "q": stem,
                "caso": "",
                "opts": options,
                "correct": marked[0],
                "expl": explanation,
                "source_topic": number,
            }
        )

    if len(out) < 10:
        raise ValueError(f"Tema {number}: só se extraeron {len(out)} preguntas")
    if [q["n"] for q in out] != [f"PDF{number}-{i}" for i in range(1, len(out) + 1)]:
        raise ValueError(f"Tema {number}: numeración inesperada")
    return out


def main() -> None:
    selected = pdfs_by_topic()
    questions: list[dict] = []
    for number in range(1, 31):
        questions.extend(parse_topic(number, selected[number]))

    OUTPUT.write_text(
        json.dumps(questions, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"PDF únicos: {len(selected)}")
    print(f"Preguntas extraídas: {len(questions)}")
    print(f"Saída: {OUTPUT}")


if __name__ == "__main__":
    main()
