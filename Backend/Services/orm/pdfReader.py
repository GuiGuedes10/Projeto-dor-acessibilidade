import pymupdf

def read_pdf_pages(path: str) -> list[tuple[int, str]]:
    with pymupdf.open(path) as pdf:
        return [(number, page.get_text().strip()) for number, page in enumerate(pdf, 1)]

def read_pdf(path: str) -> str:
    text = ""

    with pymupdf.open(path) as pdf:
        for page in pdf:
            text += page.get_text() + "\n"

    return text.strip()
