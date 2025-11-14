#!/usr/bin/env python3
import sys
from pathlib import Path
from PyPDF2 import PdfReader

def pdf_to_text(pdf_path: str):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text.strip()

def main():
    if len(sys.argv) < 2:
        print("Error: Missing PDF file path", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print("Error: File not found", file=sys.stderr)
        sys.exit(1)

    text = pdf_to_text(pdf_path)
    print(text)

if __name__ == "__main__":
    main()