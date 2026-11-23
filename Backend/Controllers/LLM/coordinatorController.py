from fastapi import Request
from pydantic import BaseModel, Field, field_validator

from Agents.coordinatorAgent import coordinator_agent


class ChatRequest(BaseModel):
    search: str = Field(min_length=1)

    @field_validator('search')
    @classmethod
    def validate_search(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('A pergunta não pode estar vazia.')
        return value.strip()


def chat(body: ChatRequest, request: Request):
    query = body.search.strip()
    response = coordinator_agent(llm=request.app.state.llm, query=query)
    return {'query': query, 'response': response}
