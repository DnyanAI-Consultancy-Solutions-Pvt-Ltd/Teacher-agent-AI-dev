from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from teacher import process_question

app = FastAPI(title="AI Education Teacher Agent API")

# Allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def health():
    return {"status": "running"}


@app.post("/ask")
def ask_question(payload: QuestionRequest):
    result = process_question(payload.question)

    pdf_url = None

    if result.get("pdf"):
        filename = os.path.basename(result["pdf"])
        pdf_url = f"http://localhost:8000/download/{filename}"

    return {
        "type": result.get("type"),
        "answer": result.get("answer"),
        "pdf_url": pdf_url,
    }


@app.get("/download/{filename}")
def download_pdf(filename: str):
    file_path = os.path.join("outputs", filename)

    if not os.path.exists(file_path):
        return {"error": "File not found"}

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/pdf",
    )