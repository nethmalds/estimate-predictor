import argparse
import json

from src.ai.rag.service import service


def main() -> None:
    parser = argparse.ArgumentParser(description="Manually ingest BSR PDF into PostgreSQL and Chroma")
    parser.add_argument("--pdf-path", required=True, help="Absolute or relative path to BSR PDF")
    args = parser.parse_args()

    service.bootstrap()
    result = service.ingest_bsr_pdf(args.pdf_path)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
