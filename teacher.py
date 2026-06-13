import os
import re
import json
import certifi
import warnings
import autogen
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Optional
import instructor
from datetime import datetime

warnings.filterwarnings("ignore", category=UserWarning, module="flaml")
warnings.filterwarnings("ignore", category=UserWarning)
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise EnvironmentError("Critical Environment Error: System Key 'GROQ_API_KEY' is missing.")

instructor_client = instructor.from_provider("groq/llama-3.3-70b-versatile", api_key=GROQ_API_KEY)

config_list = [{
    "model": "llama-3.3-70b-versatile", 
    "api_key": GROQ_API_KEY,
    "base_url": "https://api.groq.com/openai/v1",
    "api_type": "openai"
}]
llm_config = {"temperature": 0.2, "config_list": config_list, "timeout": 180, "cache_seed": None}
OUTPUT_DIR = "outputs"

class CoreChapter(BaseModel):
    chapter_number: int = Field(..., description="Legitimate sequential chapter number")
    title: str = Field(..., description="Official text string chapter name")
    core_topics: List[str] = Field(..., description="Conceptual subtopics taught in this framework")

class SubjectSyllabus(BaseModel):
    subject_name: str = Field(..., description="Subject domain name")
    theoretical_marks: int = Field(..., description="Written score ceiling threshold (Max 80)", le=80)
    practical_marks: int = Field(..., description="Practical evaluation matrix (Max 30)", le=30)
    chapters: List[CoreChapter] = Field(..., description="Exhaustive chapter maps")

class CompleteAcademicCurriculum(BaseModel):
    board: str = Field(..., description="Governing body board name")
    class_level: str = Field(..., description="Grade framework level")
    stream: str = Field(..., description="Academic stream sector")
    subjects: List[SubjectSyllabus] = Field(..., description="Verified curriculum subjects lists")

def contains_devanagari(text: str) -> bool:
    return any(0x0900 <= ord(ch) <= 0x097F for ch in text) if text else False

def normalize_language_hint(text: str) -> str:
    if not text: return "English"
    t = text.lower()
    if any(k in t for k in ["marathi", "मराठी"]): return "Marathi"
    if any(k in t for k in ["hindi", "हिंदी"]): return "Hindi"
    return "Hindi" if contains_devanagari(text) else "English"

def safe_pdf_filename(question: str, regenerate_count: int = 0) -> str:
    name = "_".join(question.split()[:6]).lower()
    name = re.sub(r"[^a-zA-Z0-9_]", "", name) or "ai_mentor_output"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{name}_v{regenerate_count}_{ts}.pdf" if regenerate_count > 0 else f"{name}_{ts}.pdf"

def analyze_request(user_question: str) -> dict:
    q = user_question.lower()
    if any(k in q for k in ["syllabus", "curriculum", "chapters", "index", "अभ्यासक्रम", "पाठ्यक्रम"]):
        variety = "official_syllabus"
    elif any(k in q for k in ["paper", "test", "exam", "question paper", "प्रश्नपत्रिका"]):
        variety = "paperset"
    elif any(k in q for k in ["build", "code", "architecture", "algorithm", "app"]):
        variety = "engineering_blueprint"
    else:
        variety = "study_notes"

    lang = normalize_language_hint(user_question)
    board = "Maharashtra State Board" if lang == "Marathi" or "maharashtra" in q else "CBSE"
    
    class_level = "10"
    if "11" in q: class_level = "11"
    elif "12" in q: class_level = "12"
    
    class_match = re.search(r'(\d+)', q)
    if class_match: class_level = class_match.group(1)
        
    return {"output_variety": variety, "class_level": class_level, "board": board, "language": lang}

def get_dynamic_system_message(variety: str, language: str) -> str:
    base = f"You are an expert master educator. Write responses entirely in: {language}."
    if variety == "paperset":
        return base + "\nStyle: Professional Examination Paper. Provide Time, Max Marks, Section A (MCQs), Section B (Short Answers), Section C (Long Essays). Follow with a complete accurate Answer Key section."
    elif variety == "engineering_blueprint":
        return base + "\nStyle: Application Engineering Blueprint. Include ASCII connection diagrams, data pipelines, step-by-step algorithms, and production-ready source code templates."
    return base + "\nStyle: Thorough Masterclass Study Notes. Break down concepts intensely using simple everyday analogies, highlighted key vocabulary terms, clear summaries, and practice checkpoint questions."

user_proxy = autogen.UserProxyAgent(name="Admin", human_input_mode="NEVER", code_execution_config={"use_docker": False})
syllabus_agent = autogen.AssistantAgent(name="syllabus_agent", llm_config=llm_config)
concept_agent = autogen.AssistantAgent(name="concept_agent", llm_config=llm_config)
curriculum_agent = autogen.AssistantAgent(name="curriculum_agent", llm_config=llm_config, system_message="Outline core target learning parameters. Do not output raw console code dictionaries.")
learning_outcome_agent = autogen.AssistantAgent(name="learning_outcome_agent", llm_config=llm_config, system_message="Draft descriptive checking outcomes based on the curriculum parameters.")

def run_single_agent(agent, message: str) -> str:
    user_proxy.initiate_chat(agent, message=message, max_turns=1, clear_history=True)
    messages = user_proxy.chat_messages[agent]
    for msg in reversed(messages):
        content = msg.get("content", "")
        if content and content.strip() != message.strip():
            return content.strip()
    return ""

def run_unstructured_education_pipeline(user_question, request_context):
    board, cl, lang, variety = request_context["board"], request_context["class_level"], request_context["language"], request_context["output_variety"]
    
    sys_instruction = get_dynamic_system_message(variety, lang)
    syllabus_agent.update_system_message(sys_instruction)
    concept_agent.update_system_message(sys_instruction)

    from tools import official_web_reader_tool
    web_context = official_web_reader_tool(board=board, class_level=cl, subject="Education", topic=user_question, language=lang)

    syllabus_prompt = f"Query: {user_question}\nParameters: {json.dumps(request_context)}\nSource Ingestion:\n{web_context}"
    syllabus_context = run_single_agent(syllabus_agent, syllabus_prompt)
    
    curriculum_context = run_single_agent(curriculum_agent, f"Syllabus Context:\n{syllabus_context}\nLang: {lang}")
    learning_outcomes = run_single_agent(learning_outcome_agent, f"Curriculum Structure:\n{curriculum_context}\nLang: {lang}")

    base_prompt = f"Grounding: {syllabus_context}\nTarget Goals: {learning_outcomes}\nPrompt: {user_question}\nLang Medium: {lang}"
    draft = run_single_agent(concept_agent, base_prompt)

    if learning_outcomes and len(learning_outcomes.strip()) > 10:
        draft = f"### Cognitive Framework & Learning Outcomes:\n{learning_outcomes}\n\n---\n\n{draft}"
    return draft, "concept_agent"

def run_structured_syllabus_pipeline(user_question: str, ctx: dict) -> CompleteAcademicCurriculum:
    board, cl, lang = ctx["board"], ctx["class_level"], ctx["language"]
    from tools import official_web_reader_tool, google_search_tool
    
    web_context = official_web_reader_tool(board=board, class_level=cl, subject="Syllabus Matrix", topic=user_question, language=lang)
    if not web_context or "error" in web_context.lower() or len(web_context.strip()) < 150:
        search_query = f"{board} Class {cl} official chapters indexing list timeline site:learncbse.in OR site:byjus.com"
        try:
            links = google_search_tool(query=search_query)
            urls = re.findall(r'https?://[^\s\'"\",<>\]\}]+', str(links))
            if urls:
                from crawler import crawl_official_site
                web_context = crawl_official_site(urls[0].strip().rstrip('.)]'))
        except Exception:
            pass

    return instructor_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        response_model=CompleteAcademicCurriculum,
        messages=[
            {"role": "system", "content": "You are a professional academic registrar. Build an exact mapping list of core textbook units and chapter integer indices. Never write decimal index titles like '1.1'. Total theory test scores max out at 80 marks."},
            {"role": "user", "content": f"Syllabus Request: {user_question}\nWeb Reference:\n{web_context}"}
        ],
        temperature=0.0
    )

def process_question(user_question: str, regenerate_count: int = 0) -> dict:
    ctx = analyze_request(user_question)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if ctx.get("output_variety") == "official_syllabus":
        curriculum_data = run_structured_syllabus_pipeline(user_question, ctx)
        output_filename = f"syllabus_class_{ctx['class_level']}_{datetime.now().strftime('%M%S')}.pdf"
        
        from pdf_compiler import compile_curriculum_object_to_pdf
        compiled_pdf = compile_curriculum_object_to_pdf(curriculum_data, output_filename)
        
        text_preview = f"## Verified Curriculum Structure: {curriculum_data.board} {curriculum_data.class_level}\n"
        for sub in curriculum_data.subjects:
            text_preview += f"\n### Subject: {sub.subject_name} [Theory Ceil: {sub.theoretical_marks} Marks | Practical Allot: {sub.practical_marks} Marks]\n"
            # Fixed: Directly targets sub.chapters without referencing a non-existent sub.subjects array attribute
            for ch in sub.chapters:
                text_preview += f"- **Chapter {ch.chapter_number}: {ch.title}**\n  *Concepts: {', '.join(ch.core_topics)}*\n"
        return {"type": "syllabus", "pdf": compiled_pdf, "direct_response": text_preview, "request_context": ctx}
        
    else:
        final_output, agent_name = run_unstructured_education_pipeline(user_question, ctx)
        output_filename = safe_pdf_filename(user_question, regenerate_count)
        
        from pdf_compiler import compile_chat_history_to_pdf
        from tools import get_minimal_citation
        compiled_pdf = compile_chat_history_to_pdf(
            chat_history=[{"name": agent_name, "role": "assistant", "content": final_output}],
            user_query=user_question,
            llm_config=llm_config,
            output_dir=OUTPUT_DIR,
            output_filename=output_filename,
            report_title=f"Academic Artifact: {ctx['output_variety'].replace('_',' ').title()}",
            citation_hint=get_minimal_citation(user_question)
        )
        return {"type": "concept", "pdf": compiled_pdf, "direct_response": final_output, "request_context": ctx}

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  AI ALL-ROUNDER MASTER CLASS ENGINE v3.6 - ACTIVE")
    print("  Enter custom academic queries, blueprint tasks, or syllabus trackers.")
    print("=" * 70 + "\n")

    while True:
        try:
            user_q = input("Ask your learning mentor (or type 'exit'): ").strip()
            if user_q.lower() in ["exit", "quit"]: break
            if not user_q: continue

            ctx = analyze_request(user_q)
            q_low = user_q.lower()

            if ctx.get("output_variety") == "official_syllabus":
                print("\n[Verification Hub] Dynamic parameter adjustment required for target tables:")
                if not any(s in q_low for s in ["science", "commerce", "arts", "humanities"]):
                    print("[1] Science   [2] Commerce   [3] Arts")
                    choice = input("Select stream (1-3): ").strip()
                    ctx["stream"] = "Commerce" if choice == "2" else ("Arts" if choice == "3" else "Science")
                else:
                    ctx["stream"] = "Science" if "science" in q_low else ("Commerce" if "commerce" in q_low else "Arts")

                if ctx["language"] == "English" and not "english" in q_low:
                    print("[1] English Medium   [2] Marathi Medium   [3] Hindi Medium")
                    l_choice = input("Select layout language (1-3): ").strip()
                    if l_choice == "2": ctx["language"] = "Marathi"; ctx["board"] = "Maharashtra State Board"
                    elif l_choice == "3": ctx["language"] = "Hindi"

                if not any(s in q_low for s in ["math", "physics", "chemistry", "biology", "history", "accounts", "economics"]):
                    sub_focus = input("Target a specific subject file lookup (e.g., Physics) or enter for global grid: ").strip()
                    if sub_focus: user_q += f" for {sub_focus}"

                print(f"\n[System Lock] Setup context verified. Handing over to engine sequence...\n")

            print(f"[System Monitor] Running deep educational orchestration loops...")
            res = process_question(user_q)
            
            print(f"\n[Success] Execution complete!")
            print(f"📄 Generated Document Asset Link: {res.get('pdf')}\n")
            print("-" * 70)
            print(res.get("direct_response"))
            print("-" * 70 + "\n")
            
        except KeyboardInterrupt:
            print("\n\\nSession terminated.")
            break
        except Exception as e:
            print(f"\n[Pipeline Critical Exception Anomaly]: {str(e)}\n")