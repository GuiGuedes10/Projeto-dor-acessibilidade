from Database.chromaDb.chroma import collection
from Models.embedding_model import embedding_model


def search_knowledge_base(query: str, top_k: int = 5):

    query_embedding = embedding_model.encode(
        query,
        normalize_embeddings=True
    ).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    print("Resultado da busca:", results)

    return results["documents"][0] if results["documents"] else []