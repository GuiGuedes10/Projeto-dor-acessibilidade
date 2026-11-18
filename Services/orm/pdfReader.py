import fitz

def read_pdf(path: str) -> str:
    text = ""

    with fitz.open(path) as pdf:
        for page in pdf:
            text += page.get_text() + "\n"

    return text.strip()