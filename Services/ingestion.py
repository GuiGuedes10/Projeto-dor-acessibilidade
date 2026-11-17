import hashlib
from pathlib import Path

from Services.pdfReader import read_pdf
from Services.chunker import split_text
from Services.embedding import generate_embeddings
from Database.chromaDb.chroma import collection


PDF_FOLDER = "../Database/chromaDb/datas"


def load_pdfs() -> list[Path]:
    return list(PDF_FOLDER.glob("*.pdf"))


def save_embeddings(
    chunks: list[str],
    embeddings: list[list[float]],
    ids: list[str]
):
    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings
    )


def process_pdf(path: Path):

    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    file_prefix = hashlib.sha256(
        str(path.resolve()).encode()
    ).hexdigest()[:16]

    chunks = split_text(read_pdf(str(path)))

    if not chunks:
        print(f"Nenhum texto encontrado: {path.name}")
        return

    ids = [
        f"{file_prefix}_{file_hash}_{i}"
        for i in range(len(chunks))
    ]

    existing_ids = collection.get(
        where=None
    )["ids"]

    previous_ids = [
        item for item in existing_ids
        if item.startswith(f"{file_prefix}_")
    ]

    if set(ids).issubset(set(previous_ids)):
        print(f"Documento já carregado: {path.name}")
        return

    if previous_ids:
        collection.delete(ids=previous_ids)

    embeddings = generate_embeddings(chunks)

    save_embeddings(chunks, embeddings, ids)

    print(f"Documento carregado: {path.name}")


def initialize_knowledge_base():

    PDF_FOLDER.mkdir(parents=True, exist_ok=True)

    pdfs = load_pdfs()

    if not pdfs:
        print("Nenhum PDF encontrado.")
        return

    for pdf in pdfs:
        process_pdf(pdf)

    print("Base de conhecimento inicializada.")