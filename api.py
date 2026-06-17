import os
import logging
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
from fastapi.concurrency import run_in_threadpool

from teacher import analyze_request, process_question

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AI_Mentor_API")

OUTPUTS_DIR = os.path.abspath("outputs")

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    logger.info("Advanced AI Pedagogical Engine initialized successfully.")
    yield
    logger.info("Shutting down AI Pedagogical Engine application context.")

app = FastAPI(
    title="AI Learning & Career Mentor API",
    version="2.1.0",
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
    question: str = Field(..., description="The user question or target base prompt.")
    student_id: Optional[str] = "default_student"
    generate_pdf: Optional[bool] = None  
    board: Optional[str] = None         # 'CBSE' or 'Maharashtra State Board'
    class_level: Optional[str] = None   # '9', '10', '12'
    subject: Optional[str] = None       # 'Science', 'Mathematics', etc.
    language: Optional[str] = None      # 'English' or 'Marathi'
    max_marks: Optional[int] = None     # 40, 80, 100
    time_allowed: Optional[str] = None  # '2 Hours', '3 Hours'

@app.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "healthy", "service": "AI Board-Aligned Question Paper Factory Active"}

@app.post("/ask", status_code=status.HTTP_201_CREATED)
async def ask_question(payload: QuestionRequest):
    logger.info(f"Received API operational payload request for: {payload.student_id}")
    try:
        # Parse baseline question profiles
        ctx = analyze_request(payload.question)
        
        # Merge input fields sent directly from UI Form fields
        if payload.generate_pdf is not None: ctx["generate_pdf"] = payload.generate_pdf
        if payload.board: ctx["board"] = payload.board
        if payload.class_level: ctx["class_level"] = payload.class_level
        if payload.subject: ctx["subject"] = payload.subject
        if payload.language: ctx["language"] = payload.language
        if payload.max_marks: ctx["max_marks"] = payload.max_marks
        if payload.time_allowed: ctx["time_allowed"] = payload.time_allowed

        logger.info(f"Routing Matrix Parameters Engine Unified -> Subject: {ctx.get('subject')} | Language: {ctx.get('language')} | PDF Generation Flag: {ctx.get('generate_pdf')}")

        # Async non-blocking thread-pool handoff
        result = await run_in_threadpool(
            process_question,
            user_question=payload.question,
            ctx=ctx
        )

        # Mirror output data straight to terminal terminal output logs
        print("\n" + "="*60)
        print(f" LIVE WEB UI GENERATION STREAM FOR ID: {payload.student_id}")
        print("="*60)
        print(result.get("direct_response", "").replace("### EXT_LINK_PORTAL_TRIGGER", ""))
        print("="*60)

        pdf_url = None
        if result.get("pdf_generated") and result.get("pdf"):
            filename = os.path.basename(result["pdf"])
            pdf_url = f"http://localhost:8000/download/{filename}"

        return {
            "type": ctx.get("output_variety"),
            "subject": ctx.get("subject"),
            "answer": result.get("direct_response"),
            "pdf_url": pdf_url,
            "pdf_generated": result.get("pdf_generated"),
            "request_context": ctx,
            "success": True
        }

    except Exception as e:
        logger.error(f"Pipeline failure: {str(e)}")
        return {
            "type": "error",
            "answer": "An optimization failure occurred inside the orchestration layer.",
            "error": str(e),
            "trace": traceback.format_exc(),
            "pdf_url": None,
            "pdf_generated": False,
            "success": False
        }

@app.get("/download/{filename}")
async def download_pdf(filename: str):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(OUTPUTS_DIR, safe_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested file asset missing on storage volumes.")

    return FileResponse(path=file_path, filename=safe_filename, media_type="application/pdf")