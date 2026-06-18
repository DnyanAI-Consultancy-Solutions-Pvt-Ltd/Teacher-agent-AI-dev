import os
import base64
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from teacher import agentic_analyze_request, run_pure_autogen_pipeline
from pdf_compiler import compile_exam_paper_to_pdf

app = FastAPI(
    title="AI Multi-Agent Academic API Portal",
    description="Production-ready REST API layout backing the Agentic Education Domain Workspace",
    version="1.0.0"
)

# Enable Cross-Origin Resource Sharing (CORS) so external frontends can call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to specific domains for deployment security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REQUEST AND RESPONSE SCHEMAS ---
class AcademicRequest(BaseModel):
    query: str
    compile_pdf: bool = True
    language_override: str = None  # Optional: "English" or "Marathi"
    stream_override: str = None    # Optional: "Science", "Commerce", or "Arts"

class GenerationResponse(BaseModel):
    status: str
    variety: str
    grade_level: str
    subject: str
    board: str
    markdown_content: str
    pdf_filename: str = None
    pdf_download_url: str = None

# --- API ENDPOINTS ---

@app.get("/", tags=["Health Check"])
async def root():
    """Simple status check verifying that the API engine layer is alive."""
    return {"status": "operational", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/v1/generate", response_model=GenerationResponse, tags=["Academic Generation"])
async def generate_academic_content(payload: AcademicRequest):
    """
    Submits an education domain query to the Agentic Layer.
    Automatically parses intent parameters via the Query_Analyzer agent and triggers the compilation workspace loop.
    """
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query text input tray cannot be empty.")
        
    try:
        # 1. Run the pure LLM-driven query analysis configuration step
        ctx = agentic_analyze_request(payload.query)
        
        # Out-of-scope filtering safeguard activation
        if ctx.get("output_variety") == "non_educational_reject":
            raise HTTPException(
                status_code=422, 
                detail="Request Rejected: Out of Scope. Please enter a valid educational curriculum query."
            )
            
        # Apply explicit layout overrides if passed through the API parameters
        if payload.language_override:
            ctx["language"] = payload.language_override
            if payload.language_override == "Marathi":
                ctx["board"] = "Maharashtra State Board"
        if payload.stream_override:
            ctx["stream"] = payload.stream_override

        # 2. Fire off the pure instruction-driven AutoGen system multi-agent group chat
        markdown_result = run_pure_autogen_pipeline(payload.query, ctx)
        
        # 3. Dynamic PDF compilation block execution path
        pdf_filename = None
        pdf_url = None
        
        if payload.compile_pdf:
            final_payload = markdown_result
            if "Official Board Reference" not in final_payload and "Official Textbook" not in final_payload:
                final_payload += f"\n\n### EXT_LINK_PORTAL_TRIGGER\n- Official Textbook Repository Portal: https://ebalbharati.in\n"
                
            pdf_filename = f"{ctx['subject'].lower().replace(', ', '_')}_{ctx['output_variety']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            # The compiler writes the document binary to disk inside the /outputs directory folder
            compile_exam_paper_to_pdf(
                main_text=final_payload,
                ctx=ctx,
                filename=pdf_filename,
                output_dir="outputs",
                include_answer_key=ctx["with_answers"]
            )
            pdf_url = f"/api/v1/download/{pdf_filename}"

        return GenerationResponse(
            status="success",
            variety=ctx["output_variety"],
            grade_level=ctx["class_level"],
            subject=ctx["subject"],
            board=ctx["board"],
            markdown_content=markdown_result,
            pdf_filename=pdf_filename,
            pdf_download_url=pdf_url
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline Core Server Error: {str(e)}")


@app.get("/api/v1/download/{filename}", tags=["File Operations"])
async def download_pdf_asset(filename: str):
    """Retrieves and downloads the compiled PDF asset binary directly by filename."""
    file_path = os.path.join("outputs", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested compiled asset file was not found on server storage.")
    return FileResponse(file_path, media_type="application/pdf", filename=filename)


def remove_file_safely(path: str):
    """Background cleaner target callback utility helper."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

@app.delete("/api/v1/cleanup/{filename}", tags=["File Operations"])
async def delete_pdf_asset(filename: str, background_tasks: BackgroundTasks):
    """Schedules a temporary server file disk storage deletion pass to keep workspace memory clean."""
    file_path = os.path.join("outputs", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Target asset file does not exist.")
    background_tasks.add_task(remove_file_safely, file_path)
    return {"status": "cleanup_scheduled", "target_file": filename}