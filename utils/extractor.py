from pathlib import Path
import fitz
from docx import Document

def clean_text(text):
    return " ".join((text or "").split())

def extract_text(path):
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        doc = fitz.open(path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return clean_text(text)

    if ext == ".docx":
        doc = Document(path)
        return clean_text("\n".join(p.text for p in doc.paragraphs))

    if ext == ".txt":
        return clean_text(path.read_text(encoding="utf-8", errors="ignore"))

    raise ValueError("Unsupported file format.")
