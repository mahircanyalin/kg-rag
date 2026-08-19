import sys
from pathlib import Path
# retrieval/ klasörünü import yoluna ekle
sys.path.insert(0, str(Path(__file__).parent.parent / "retrieval"))

from fastapi import FastAPI
from pydantic import BaseModel
from pipeline import ask

app = FastAPI(title="Knowledge Graph RAG", version="1.0")


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    question: str
    route: str
    route_reason: str
    answer: str
    citations: list[str]
    invalid_citations: list[str]


@app.get("/")
def health():
    return {"status": "ok", "message": "KG-RAG API çalışıyor"}


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(request: AskRequest):
    result = ask(request.question)
    return AskResponse(**result)