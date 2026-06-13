import os
import logging
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional

from teacher import process_question

# Configure high-performance logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AI_Mentor_API")

OUTPUTS_DIR = os.path.abspath("outputs")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Guarantees output directory availability at boot."""
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    logger.info("Advanced AI Pedagogical Engine initialized successfully.")
    yield
    logger.info("Shutting down AI Pedagogical Engine application context.")

app = FastAPI(
    title="AI Learning & Career Mentor API",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QuestionRequest(BaseModel):
    question: str = Field(..., description="The direct question or prompt from the student.")
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

@app.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "healthy", "service": "AI Learning & Career Mentor API running"}

@app.post("/ask", status_code=status.HTTP_201_CREATED)
async def ask_question(payload: QuestionRequest):
    logger.info(f"Received pedagogical query for student: {payload.student_id}")
    try:
        # Non-blocking handoff to pipeline logic
        result = process_question(
            user_question=payload.question,
            regenerate_count=payload.regenerate_count
        )

        pdf_url = None
        if result.get("pdf"):
            filename = os.path.basename(result["pdf"])
            # dynamic host identification fallback template
            pdf_url = f"http://localhost:8000/download/{filename}"

        return {
            "type": result.get("type"),
            "answer": result.get("direct_response"),
            "pdf_url": pdf_url,
            "request_context": result.get("request_context"),
            "success": True
        }

    except Exception as e:
        logger.error(f"Execution trace breakdown anomaly: {str(e)}")
        return {
            "type": "error",
            "answer": "An optimization failure occurred inside the orchestration layer.",
            "error": str(e),
            "trace": traceback.format_exc(),
            "pdf_url": None,
            "success": False
        }

@app.get("/download/{filename}")
async def download_pdf(filename: str):
    # Security Sandbox: Mitigate directory path traversal attempts
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(OUTPUTS_DIR, safe_filename)

    if not os.path.exists(file_path):
        logger.warning(f"Malicious or missing file retrieval attempt intercepted: {safe_filename}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="The requested academic document could not be resolved or found."
        )

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="application/pdf"
    )