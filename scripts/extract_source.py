"""One-time source extraction. Output is a review draft, never official answers."""

import argparse
import json
from pathlib import Path
import fitz

parser = argparse.ArgumentParser()
parser.add_argument("pdf", type=Path)
parser.add_argument("--output", type=Path, default=Path("tmp/pdfs"))
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
doc = fitz.open(args.pdf)
pages = [{"page": i + 1, "text": p.get_text(sort=True)} for i, p in enumerate(doc)]
(args.output / "pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")
(args.output / "source.txt").write_text("\n\n".join(p["text"] for p in pages), encoding="utf-8")
for index in (0, len(doc) - 1):
    doc[index].get_pixmap(matrix=fitz.Matrix(1.3, 1.3)).save(str(args.output / f"page-{index + 1}.png"))
print(json.dumps({"pages": len(doc), "characters": sum(len(p["text"]) for p in pages)}, ensure_ascii=False))
