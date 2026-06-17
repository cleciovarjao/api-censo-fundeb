"""Script de teste isolado para um unico PDF."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pdf_processor import processar_pdfs


def main() -> int:
    resultado = processar_pdfs(limit=1)
    print(f"Status: {resultado.get('status')}")
    print(f"PDFs processados: {resultado.get('processados', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
