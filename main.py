from fastapi import FastAPI
import uvicorn

from Services.ingestion import initialize_knowledge_base

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_knowledge_base()

    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"Hello": "World"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)