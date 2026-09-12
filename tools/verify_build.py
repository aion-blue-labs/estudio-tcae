#!/usr/bin/env python3
"""Comprobaciones estáticas de la app generada."""

import json
import re
from collections import Counter
from pathlib import Path


root = Path(__file__).resolve().parents[1]
html = (root / "index.html").read_text(encoding="utf-8")
marker = "const DATA  = "
start = html.index(marker) + len(marker)
data, _ = json.JSONDecoder().raw_decode(html[start:])


def hid(text):
    value = 0
    for char in text:
        value = (value * 31 + ord(char)) & 0xFFFFFFFF
    return f"q{value}"


assert len(data) == 2627
assert len({hid(q["q"]) for q in data}) == len(data), "Colisión de identificadores"
assert all(len(q.get("opts", [])) == 4 for q in data)
assert all(len(set(q["opts"])) == 4 for q in data)
assert all(0 <= q.get("correct", -1) <= 3 for q in data)
assert all(q.get("expl", "").strip() for q in data)
assert all(sum(q.get("sim") == f"T{n}" for q in data) == 50 for n in range(1, 32))
assert sum(q.get("sim") == "IR" for q in data) == 12
assert sum(q.get("sim") == "I" for q in data) == 38
assert "const KEY = 'tcae_progress_v3'" in html

html_version = re.search(r'const VERSION = "([^"]+)";', html).group(1)
sw = (root / "sw.js").read_text(encoding="utf-8")
sw_version = re.search(r"const VERSION = '([^']+)';", sw).group(1)
assert html_version == sw_version

new = [q for q in data if re.fullmatch(r"T(?:[2-9]|[12]\d|3[01])|IR", str(q.get("sim", "")))]
answers = Counter(q["correct"] for q in new)
assert max(answers.values()) - min(answers.values()) <= 2

print(f"OK: {len(data)} preguntas, 31 temas x 50, 50 específicas de instrumental")
print(f"IDs únicos: {len(data)}; respuestas nuevas: {dict(sorted(answers.items()))}")
print(f"Versión HTML/SW: {html_version}; progreso: tcae_progress_v3")
