from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import os
from teacher import process_question

app = FastAPI(title="Teacher Agent API")

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
def home():
    return {"status": "Teacher Agent Running"}


@app.post("/ask")
def ask_question(request: QuestionRequest):

    result = process_question(request.question)

    pdf_url = None

    if result.get("pdf"):
        filename = os.path.basename(result["pdf"])
        pdf_url = f"http://localhost:8000/download/{filename}"

    return {
        "type": result.get("type"),
        "answer": result.get("answer"),
        "pdf_url": pdf_url
    }


@app.get("/download/{filename}")
def download_pdf(filename: str):

    file_path = os.path.join("outputs", filename)

    if os.path.exists(file_path):
        return FileResponse(
            file_path,
            media_type="application/pdf",
            filename=filename
        )

    return {"error": "File not found"}