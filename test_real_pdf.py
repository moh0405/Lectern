import os
from pathlib import Path

def extract_pdf_text(pdf_path: str, max_chars: int = 1000) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("Missing dependency 'pypdf'. Install with: pip install pypdf") from e

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found at: {pdf_path}")

    reader = PdfReader(pdf_path)
    texts = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            # Skip pages that cannot be parsed; continue with others
            continue

    full_text = "\n".join(texts)
    return full_text[:max_chars]


def main():
    pdf_path = str(Path("data/uploaded_files/Dsa.pdf").resolve())
    print(f"Using PDF: {pdf_path}")

    try:
        snippet = extract_pdf_text(pdf_path, max_chars=1500)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Tip: Place your PDF under 'data/uploaded_files/' and name it 'Dsa.pdf'.")
        return
    except RuntimeError as e:
        print(f"Error: {e}")
        print("Tip: Run 'pip install -r requirements.txt' to install dependencies.")
        return

    if not snippet.strip():
        print("PDF parsed, but no text was extracted (possibly scanned or image-only PDF).")
    else:
        print("Extracted text preview (first 1500 characters):\n")
        print(snippet)


if __name__ == "__main__":
    main()