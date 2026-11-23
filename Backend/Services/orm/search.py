"""Busca híbrida com deduplicação, evidência lexical e fontes."""
import math
import os
import re
import unicodedata

from Database.chromaDb.chroma import collection
from Models.embedding_model import embedding_model

_STOPWORDS = set("a o as os de da do das dos e em na no nas nos para por um uma quais qual que preciso precisa realizar como meu minha eu se ao os sao ser com fazer faco posso necessarios necessario necessarias necessaria quero gostaria saber".split())


def _terms(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+", normalized)
    # Reúne flexões comuns sem depender de outro modelo.
    return {word[:-1] if word.endswith("s") else word
            for word in words if len(word) > 2 and word not in _STOPWORDS}


def _proximity(text: str, query_terms: set[str]) -> float:
    """Favorece termos juntos (ex.: documentos para matrícula), não menções dispersas."""
    tokens = [term for word in text.split() for term in sorted(_terms(word))]
    best = float("inf")
    counts = {}
    left = 0
    for right, term in enumerate(tokens):
        if term in query_terms:
            counts[term] = counts.get(term, 0) + 1
        while query_terms and len(counts) == len(query_terms):
            best = min(best, right - left + 1)
            previous = tokens[left]
            if previous in counts:
                counts[previous] -= 1
                if not counts[previous]:
                    del counts[previous]
            left += 1
    return 1 / (1 + best - len(query_terms)) if math.isfinite(best) else 0.0


def search_evidence(query: str, top_k: int = 5) -> list[dict]:
    if not query.strip() or top_k <= 0:
        return []
    count = collection.count()
    if not count:
        return []
    query_terms = _terms(query)
    query_embedding = embedding_model.encode(query, normalize_embeddings=True).tolist()
    results = collection.query(
        query_embeddings=[query_embedding], n_results=min(count, max(30, top_k * 6)),
        include=["documents", "metadatas", "distances"],
    )
    candidates = {}
    for identifier, text, metadata, distance in zip(
        results["ids"][0], results["documents"][0],
        results["metadatas"][0], results["distances"][0],
    ):
        candidates[identifier] = (text, metadata or {}, float(distance))

    # A busca textual também alcança listas exatas fora dos vizinhos semânticos.
    # Paginação evita carregar todos os documentos em uma única resposta do Chroma.
    lexical = []
    for offset in range(0, count, 500):
        batch = collection.get(limit=500, offset=offset, include=["documents", "metadatas"])
        for identifier, text, metadata in zip(batch["ids"], batch["documents"], batch["metadatas"]):
            coverage = len(query_terms & _terms(text or "")) / max(1, len(query_terms))
            if query_terms and coverage == 1:
                lexical.append((identifier, text, metadata or {}))
    for identifier, text, metadata in lexical:
        if identifier not in candidates:
            candidates[identifier] = (text, metadata, None)

    max_distance = float(os.getenv("RAG_MAX_DISTANCE", "0.65"))
    ranked = []
    for text, metadata, distance in candidates.values():
        if not text:
            continue
        coverage = len(query_terms & _terms(text)) / max(1, len(query_terms))
        # Exige evidência dos termos centrais, além da proximidade semântica.
        if query_terms and coverage < min(1.0, 2 / len(query_terms)):
            continue
        if distance is not None and (not math.isfinite(distance) or distance > max_distance) and coverage < 1:
            continue
        similarity = max(0.0, 1 - distance) if distance is not None else 0.0
        ranked.append((0.35 * coverage + 0.15 * similarity + 0.5 * _proximity(text, query_terms), {
            "text": text, "source": metadata.get("source", "Fonte não identificada (índice antigo)"),
            "page": metadata.get("page"), "distance": distance,
        }))
    ranked.sort(key=lambda item: item[0], reverse=True)
    seen = set()
    evidence = []
    for _, item in ranked:
        fingerprint = " ".join(item["text"].casefold().split())
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        evidence.append(item)
        if len(evidence) == top_k:
            break
    return evidence


def search_knowledge_base(query: str, top_k: int = 5):
    # Mantém o contrato do endpoint /searchData: uma lista de textos.
    return [item["text"] for item in search_evidence(query, top_k)]
