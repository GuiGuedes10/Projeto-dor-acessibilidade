import os
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from Services.orm.ingestion import initialize_knowledge_base
from Models.llm import load_llm
from Routes import chromaRoute, llmRoute

load_dotenv()

PORT = int(os.getenv("PORT", 8080))

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_knowledge_base()
    app.state.llm = load_llm()

    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {f"Backend is running, listening in port: " + str(PORT)}

app.include_router(chromaRoute.router)
app.include_router(llmRoute.router, prefix = "/llm")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=PORT, reload=True)