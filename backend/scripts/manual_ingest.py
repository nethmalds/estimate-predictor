#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def select_python_bin(root: Path) -> str:
    windows_python = root / "venv" / "Scripts" / "python.exe"
    posix_python = root / "venv" / "bin" / "python"
    if windows_python.is_file():
        return str(windows_python)
    if posix_python.is_file():
        return str(posix_python)
    return sys.executable or "python"


def resolve_pdf_path(pdf_arg: str, root: Path) -> Path:
    pdf_path = Path(pdf_arg)
    if pdf_path.is_absolute():
        return pdf_path

    cwd_candidate = Path.cwd() / pdf_path
    if cwd_candidate.is_file():
        return cwd_candidate

    root_candidate = root / pdf_path
    if root_candidate.is_file():
        return root_candidate

    return cwd_candidate


def run_cmd(python_bin: str, args: list, cwd: Path) -> None:
    subprocess.run([python_bin, *args], check=True, cwd=str(cwd))


def main() -> int:
    root = project_root()
    default_pdf = "data_layer/storage/bsr_wp_2025.pdf"

    parser = argparse.ArgumentParser(description="Run manual ingest for a PDF file.")
    parser.add_argument("pdf_path", nargs="?", default=default_pdf)
    args = parser.parse_args()

    pdf_path = resolve_pdf_path(args.pdf_path, root)
    if not pdf_path.is_file():
        print(f"PDF not found: {pdf_path}")
        print("Usage: python scripts/manual_ingest.py [pdf_path]")
        return 1

    python_bin = select_python_bin(root)

    if os.getenv("SKIP_MIGRATIONS") != "1":
        run_cmd(python_bin, ["-m", "alembic", "upgrade", "head"], root)

    run_cmd(
        python_bin,
        ["-m", "services.rag_process.manual_ingest", "--pdf-path", str(pdf_path)],
        root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
