from fastapi import Request
from pydantic import BaseModel, Field

from Agents.ragAgent import rag_agent
from Utils.errors import ApiError


class RagRequest(BaseModel):
    search: str = Field(min_length=1)


def test_rag(body: RagRequest, request: Request):

    query = body.search.strip()

    if not query:
        raise ApiError(
            400,
            "invalid_search",
            "A pergunta não pode estar vazia."
        )

    llm = request.app.state.llm

    response = rag_agent(
        llm=llm,
        query=query
    )

    return {
        "query": query,
        "response": response
    }