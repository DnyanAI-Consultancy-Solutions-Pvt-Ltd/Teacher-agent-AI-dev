import os
import traceback
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from teacher import process_question

app = FastAPI(title="AI Learning & Career Mentor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str
    student_id: Optional[str] = "default_student"
    board: Optional[str] = None
    difficulty: Optional[str] = None
    marks: Optional[int] = None
    language: Optional[str] = None
    include_answer_key: Optional[bool] = None
    output_type: Optional[str] = None
    chapter: Optional[str] = None
    bloom_level: Optional[str] = None
    regenerate: Optional[bool] = False
    regenerate_count: Optional[int] = 0


@app.get("/")
def health():
    return {"status": "AI Learning & Career Mentor API running"}


@app.post("/ask")
def ask_question(payload: QuestionRequest):
    try:
        result = process_question(
            user_question=payload.question,
            student_id=payload.student_id,
            board=payload.board,
            difficulty=payload.difficulty,
            marks=payload.marks,
            language=payload.language,
            include_answer_key=payload.include_answer_key,
            output_type=payload.output_type,
            chapter=payload.chapter,
            bloom_level=payload.bloom_level,
            regenerate=payload.regenerate,
            regenerate_count=payload.regenerate_count,
        )

        pdf_url = None

        if result.get("pdf"):
            filename = os.path.basename(result["pdf"])
            pdf_url = f"http://localhost:8000/download/{filename}"

        return {
            "type": result.get("type"),
            "answer": result.get("answer"),
            "direct_response": result.get("direct_response"),
            "pdf_url": pdf_url,
            "request_context": result.get("request_context"),
        }

    except Exception as e:
        return {
            "type": "error",
            "answer": "Something went wrong while generating the response.",
            "error": str(e),
            "trace": traceback.format_exc(),
            "pdf_url": None,
        }


@app.get("/download/{filename}")
def download_pdf(filename: str):
    file_path = os.path.join("outputs", filename)

    if os.path.exists(file_path):
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/pdf",
        )

    return {"error": "File not found"}