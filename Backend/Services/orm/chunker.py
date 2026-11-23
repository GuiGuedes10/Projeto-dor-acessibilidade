def split_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200
) -> list[str]:

    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Parâmetros de chunk inválidos.")

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks