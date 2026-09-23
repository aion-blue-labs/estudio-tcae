#!/usr/bin/env python3
"""Valida estrutura e detecta duplicados das preguntas extraídas dos PDF."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PDF_BANK = ROOT / "topic-banks" / "pdf-resumenes.json"
INDEX = ROOT / "index.html"


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\W+", " ", value).strip()


def app_data() -> list[dict]:
    html = INDEX.read_text(encoding="utf-8")
    marker = "const DATA  = "
    start = html.index(marker) + len(marker)
    return json.JSONDecoder().raw_decode(html[start:])[0]


def main() -> None:
    incoming = json.loads(PDF_BANK.read_text(encoding="utf-8"))
    existing = app_data()

    assert all(len(q["opts"]) == 4 for q in incoming)
    assert all(len(set(q["opts"])) == 4 for q in incoming)
    assert all(0 <= q["correct"] <= 3 for q in incoming)
    assert all(q["expl"].strip() for q in incoming)
    assert len({q["n"] for q in incoming}) == len(incoming)
    assert len({norm(q["q"]) for q in incoming}) == len(incoming)

    existing_norm = {norm(q["q"]): q for q in existing}
    exact = [q["n"] for q in incoming if norm(q["q"]) in existing_norm]
    print(f"Preguntas PDF: {len(incoming)}")
    print(f"Estrutura válida: {len(incoming)}")
    print(f"Duplicados literais normalizados: {len(exact)} {exact}")
    print(f"Respostas marcadas: {dict(sorted(Counter(q['correct'] for q in incoming).items()))}")

    # Busca conservadora de case-duplicados. Só imprime coincidencias moi altas;
    # a decisión final de excluír faise no integrador.
    candidates = []
    existing_pairs = [
        (set(norm(q["q"]).split()), q.get("n", "?"), q["q"]) for q in existing
    ]
    for q in incoming:
        nq = set(norm(q["q"]).split())
        best = max(
            (
                (
                    len(nq & old_tokens) / len(nq | old_tokens),
                    old_n,
                    old_q,
                )
                for old_tokens, old_n, old_q in existing_pairs
            ),
            key=lambda item: item[0],
        )
        if best[0] >= 0.78:
            candidates.append((q["n"], *best))
    print(f"Candidatos semellantes (Jaccard >= 0.78): {len(candidates)}")
    for new_n, ratio, old_n, old_q in candidates:
        print(f"{new_n} | {ratio:.3f} | {old_n} | {old_q}")


if __name__ == "__main__":
    main()
