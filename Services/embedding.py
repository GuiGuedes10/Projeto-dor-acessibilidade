from Models.embedding_model import embedding_model


def generate_embeddings(chunks: list[str]) -> list[list[float]]:
    embeddings = embedding_model.encode(
        chunks,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    return embeddings.tolist()