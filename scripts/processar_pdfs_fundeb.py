"""Script para processar PDFs do Fundeb com limitacao segura."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pdf_processor import processar_pdfs


def main() -> int:
    parser = argparse.ArgumentParser(description="Processa PDFs do Fundeb.")
    parser.add_argument("--limit", type=int, default=1, help="Quantidade de PDFs para processar.")
    args = parser.parse_args()

    if args.limit < 1:
        print("O limite precisa ser maior ou igual a 1.")
        return 1

    print(f"Iniciando processamento seguro com limite {args.limit}...")
    resultado = processar_pdfs(limit=args.limit)
    print(f"Status: {resultado.get('status')}")
    print(f"PDFs processados: {resultado.get('processados', 0)}")
    print(f"PDFs pulados: {resultado.get('pulados', 0)}")
    print(f"Trechos criados: {resultado.get('trechos_criados', 0)}")

    avisos = resultado.get("avisos") or []
    if avisos:
        print("Avisos:")
        for aviso in avisos:
            print(f"- {aviso}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
