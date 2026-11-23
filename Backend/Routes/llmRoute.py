from fastapi import APIRouter, Request

from Controllers.LLM.ragController import RagRequest, test_rag

router = APIRouter()


@router.post("/rag")
def rag_test(body: RagRequest, request: Request):
    return test_rag(body, request)