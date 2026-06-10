import os
import re
import json
import certifi
import time
import warnings
import autogen
from dotenv import load_dotenv
from datetime import datetime

from pdf_compiler import compile_chat_history_to_pdf
from tools import (
    official_web_reader_tool,
    google_search_tool,
    build_learning_references,
    get_minimal_citation,
)

warnings.filterwarnings("ignore", category=UserWarning, module="flaml")

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise EnvironmentError("GROQ_API_KEY not found. Please check your .env file.")

config_list = [
    {
        "model": "llama-3.1-8b-instant",
        "api_key": GROQ_API_KEY,
        "base_url": "https://api.groq.com/openai/v1",
        "api_type": "openai",
        "price": [0.0, 0.0],
    }
]

llm_config = {
    "temperature": 0,
    "config_list": config_list,
    "timeout": 180,
    "cache_seed": None,
}

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DEVANAGARI_RANGE = (0x0900, 0x097F)

def contains_devanagari(text: str) -> bool:
    if not text: return False
    return any(DEVANAGARI_RANGE[0] <= ord(ch) <= DEVANAGARI_RANGE[1] for ch in text)

def normalize_language_hint(text: str) -> str:
    if not text: return "English"
    t = text.lower()
    if any(k in t for k in ["marathi", "मराठी", "मराठीमध्ये", "in marathi"]): return "Marathi"
    if any(k in t for k in ["hindi", "हिंदी", "हिन्दी", "in hindi"]): return "Hindi"
    return "Hindi" if contains_devanagari(text) else "English"

def enforce_language_flags(ctx: dict) -> dict:
    lang = ctx.get("language") or "English"
    ctx["language"] = normalize_language_hint(lang)
    return ctx

def safe_pdf_filename(question: str, regenerate_count: int = 0) -> str:
    name = "_".join(question.split()[:6]).lower()
    name = re.sub(r"[^a-zA-Z0-9_]", "", name) or "ai_mentor_output"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{name}_v{regenerate_count}_{timestamp}.pdf" if regenerate_count > 0 else f"{name}_{timestamp}.pdf"

user_proxy = autogen.UserProxyAgent(name="Admin", human_input_mode="NEVER", code_execution_config={"use_docker": False})

def run_single_agent(agent, message: str) -> str:
    time.sleep(1)
    user_proxy.initiate_chat(agent, message=message, max_turns=1, clear_history=True)
    messages = user_proxy.chat_messages[agent]
    for msg in reversed(messages):
        content = msg.get("content", "")
        if content and content.strip() != message.strip():
            return content.strip()
    return ""

def analyze_request(user_question: str) -> dict:
    q = user_question.lower()
    inferred_lang = normalize_language_hint(user_question)
    
    class_level = "10"  # Sensible default fallback for secondary schooling queries
    for lvl in ["10", "12", "5", "6", "7", "8", "9", "11"]:
        if f"class {lvl}" in q or f"std {lvl}" in q or f"इयत्ता {lvl}" in q or f"कक्षा {lvl}" in q or f" {lvl} " in q:
            class_level = lvl
            break
            
    # FIXED: Extended keywords to map Algebra & Geometry to Mathematics to stop verification false alarms
    subject = "Mathematics"
    if "science" in q or "विज्ञान" in q or "chemical" in q or "physics" in q or "chemistry" in q: 
        subject = "Science"
    elif "math" in q or "geometry" in q or "algebra" in q or "गणित" in q or "भूमिती" in q: 
        subject = "Mathematics"
    elif "history" in q or "इतिहास" in q: 
        subject = "History"
    elif "geography" in q or "भूगोल" in q: 
        subject = "Geography"

    board = "CBSE"
    if "maharashtra" in q or "state board" in q or "ssc" in q or "hsc" in q or "बालभारती" in q:
        board = "Maharashtra State Board"

    return {
        "is_supported": True, 
        "domain": "education", 
        "output_type": "syllabus" if "syllabus" in q or "अभ्यासक्रम" in q else "concept",
        "class_level": class_level,
        "subject": subject,
        "topic": user_question, 
        "chapter": "Unknown",
        "board": board,
        "difficulty": "medium", 
        "marks": 0, 
        "language": inferred_lang, 
        "include_answer_key": True,
        "needs_current_info": False, 
        "detail_level": "normal", 
        "bloom_level": "mixed", 
        "reason": "Script context tracking."
    }

def route_request(request_context: dict) -> str:
    if "syllabus" in request_context.get("topic", "").lower() or "syllabus" in request_context.get("output_type", ""):
        return "education_syllabus"
    return "education_concept"


# ──────────────────────────────────────────────────────────────────────────────
# SYSTEM AGENTS INTERFACE
# ──────────────────────────────────────────────────────────────────────────────

syllabus_agent = autogen.AssistantAgent(
    name="syllabus_agent",
    llm_config=llm_config,
    system_message="""You are an expert curriculum syllabus developer.
Your layout response must exclusively be clean, human-readable textbook outlines or course chapters.
CRITICAL PROHIBITION: Do NOT output code blocks, dictionary scripts, or tracking definitions. Write content directly using bullet points and clear plaintext headings."""
)

curriculum_agent = autogen.AssistantAgent(name="curriculum_agent", llm_config=llm_config, system_message="Map out educational objectives. Do not write code or embed dictionary logs.")
learning_outcome_agent = autogen.AssistantAgent(name="learning_outcome_agent", llm_config=llm_config, system_message="Draft descriptive learning outcome points. Write only text explanations.")
concept_agent = autogen.AssistantAgent(
    name="concept_agent", 
    llm_config=llm_config, 
    system_message="You are a senior school teacher. Provide a detailed topic textbook study guide explanation. Do not write python metadata or configurations."
)
reference_agent = autogen.AssistantAgent(name="reference_agent", llm_config=llm_config, system_message="Append validation references. Do not use code variables.")
motivator_agent = autogen.AssistantAgent(name="motivator_agent", llm_config=llm_config, system_message="Inject brief student notes. Output text headers directly without code.")
curator_agent = autogen.AssistantAgent(name="curator_agent", llm_config=llm_config, system_message="Clean text layouts. Strip out system syntax assignments, dict keys, or brace maps completely.")
quality_checker_agent = autogen.AssistantAgent(name="quality_checker_agent", llm_config=llm_config, system_message="Audit clarity. Ensure no script logs remain in the output text fields.")

def clean_agent_output(text: str) -> str:
    if not text: return ""
    for tag in ["PLAY_DONE", "PLAN_DONE", "SYLLABUS_DONE", "CURRICULUM_DONE", "OUTCOME_DONE", "CONCEPT_DONE", "REFERENCE_DONE", "MOTIVATION_DONE", "CURATOR_DONE", "QUALITY_DONE"]:
        text = re.sub(rf"\[{tag}\]", "", text, flags=re.IGNORECASE)
    return text.strip()

def build_context_prompt(request_context, syllabus_context="", curriculum_context="", learning_outcomes="", draft="", references="", regenerate_count=0):
    request_context = enforce_language_flags(dict(request_context))
    return f"REQUEST_CONTEXT:\n{json.dumps(request_context, indent=2, ensure_ascii=False)}\n\nSYLLABUS_CONTEXT:\n{syllabus_context}\nDRAFT:\n{draft}\nStrictly write in language layout medium: {request_context.get('language')}"

def run_education_pipeline(user_question, request_context, route, regenerate_count):
    request_context = enforce_language_flags(dict(request_context))
    
    board_param = request_context.get("board", "")
    class_lvl = request_context.get("class_level", "")
    subj_name = request_context.get("subject", "")
    topic_name = request_context.get("topic", "")
    target_lang = request_context.get("language", "English")

    official_reader_result = official_web_reader_tool(
        board=board_param,
        class_level=class_lvl,
        subject=subj_name,
        topic=topic_name,
        language=target_lang
    )

    is_missing = False
    missing_reason = []

    if not official_reader_result or "official_reader_error" in official_reader_result.lower():
        is_missing = True
        missing_reason.append("Could not establish a connection to verified national or state database directories.")
    else:
        layout_cleanup = official_reader_result
        noise_filters = ["मुखपृष्ठ", "संपर्क", "महाराष्ट्र", "मंडळ", "लॉगिन", "येथे", "क्लिक", "navigation", "search", "home"]
        for word in noise_filters:
            layout_cleanup = layout_cleanup.replace(word, "")

        if target_lang in ["Hindi", "Marathi"]:
            if not contains_devanagari(layout_cleanup.strip()):
                is_missing = True
                missing_reason.append(f"Official server links matched, but no verified textbook matrix was indexed in {target_lang} medium script.")
            elif len(layout_cleanup.strip()) < 100:
                is_missing = True
                missing_reason.append(f"Insufficient curriculum data. The webpage structure for {target_lang} medium does not contain a full chapter table layout.")
        else:
            if len(layout_cleanup.strip()) < 100:
                is_missing = True
                missing_reason.append("The repository link returned text fields that are too short to compile an authentic curriculum index.")

    if is_missing:
        if target_lang == "Marathi":
            report = f"""
अधिकृत अभ्यासक्रम माहिती उपलब्ध नाही (Verification Failed)

शिक्षक एजंटला खोटा किंवा अंदाज लावलेला अभ्यासक्रम तयार करण्याची परवानगी नाही. अधिकृत डेटाबेस तपासताना खालील त्रुटी आढळल्या आहेत:

- मंडळ/बोर्ड: {board_param}
- इयत्ता / माध्यम: इयत्ता {class_lvl} ({target_lang} माध्यम)
- विषय: {subj_name}
- स्थिती: {', '.join(missing_reason)}

कृती आवश्यक: कृपया आपले इनपुट तपासा किंवा थेट ई-बालभारती/अधिकृत पाठ्यपुस्तक पडताळणी पर्याय वापरा.
"""
        elif target_lang == "Hindi":
            report = f"""
आधिकारिक पाठ्यक्रम डेटा अनुपलब्ध (Verification Failed)

शिक्षक एजेंट को मनगढ़ंत या अनुमानित पाठ्यक्रम जानकारी प्रदर्शित करने की अनुमति नहीं है। आधिकारिक रिपोजिटरी में निम्नलिखित विसंगतियां पाई गईं:

- बोर्ड/प्राधिकरण: {board_param}
- कक्षा / माध्यम: कक्षा {class_lvl} ({target_lang} माध्यम)
- विषय: {subj_name}
- स्थिति: {', '.join(missing_reason)}

समाधान: कृपया विषय प्रविष्टि की जांच करें या सीधे आधिकारिक पाठ्यपुस्तक सूची संदर्भ से मिलान करें।
"""
        else:
            report = f"""
Official Curriculum Verification Failed

The teacher agent is strictly configured not to guess or hallucinate text matrices. Official directories were reached but verified structures were missing.

- Board: {board_param}
- Class / Medium: Class {class_lvl} ({target_lang} Medium)
- Subject: {subj_name}
- Reason: {', '.join(missing_reason)}

**Action Required:** Please verify your input parameters.
"""
        return report.strip(), "curator_agent", True

    syllabus_prompt = f"REQUEST_CONTEXT:\n{json.dumps(request_context, ensure_ascii=False)}\n\nOFFICIAL_WEB_READER_RESULT:\n{official_web_reader_tool}"
    
    syllabus_context = run_single_agent(syllabus_agent, syllabus_prompt)
    curriculum_context = run_single_agent(curriculum_agent, build_context_prompt(request_context, syllabus_context=syllabus_context))
    learning_outcomes = run_single_agent(learning_outcome_agent, build_context_prompt(request_context, syllabus_context=syllabus_context, curriculum_context=curriculum_context))

    base_prompt = build_context_prompt(request_context, syllabus_context=syllabus_context, curriculum_context=curriculum_context, learning_outcomes=learning_outcomes, regenerate_count=regenerate_count)

    if route == "education_syllabus":
        draft = syllabus_context
        specialist_name = "syllabus_agent"
    else:
        draft = run_single_agent(concept_agent, base_prompt)
        specialist_name = "concept_agent"

    if learning_outcomes and len(learning_outcomes.strip()) > 10:
        draft = f"Learning Outcomes / अध्ययन निष्पत्ती:\n{learning_outcomes}\n\n{draft}"

    return draft, specialist_name, False

def process_question(user_question: str, regenerate_count: int = 0) -> dict:
    request_context = analyze_request(user_question)
    request_context = enforce_language_flags(request_context)
    route = route_request(request_context)

    final_output, specialist_name, failed_verification = run_education_pipeline(
        user_question, request_context, route, regenerate_count
    )

    if failed_verification:
        print("[System Monitor] Verification failed notice generated. Bypassing downstream optimization agent tracks.")
    else:
        try:
            shared_context = build_context_prompt(request_context, draft=final_output)
            final_output = run_single_agent(reference_agent, shared_context)
            final_output = run_single_agent(motivator_agent, build_context_prompt(request_context, draft=final_output))
            final_output = run_single_agent(curator_agent, build_context_prompt(request_context, draft=final_output))
            final_output = run_single_agent(quality_checker_agent, build_context_prompt(request_context, draft=final_output))
        except Exception as mix_err:
            print(f"[Warning] Optimization loop turn bypassed: {mix_err}")

    final_output = clean_agent_output(final_output)

    output_filename = safe_pdf_filename(user_question, regenerate_count)
    compiled_pdf = compile_chat_history_to_pdf(
        chat_history=[{"name": specialist_name, "role": "assistant", "content": final_output}],
        user_query=user_question,
        llm_config=llm_config,
        output_dir=OUTPUT_DIR,
        output_filename=output_filename,
        report_title="AI Curriculum Report",
        citation_hint=get_minimal_citation(user_question),
    )

    return {"type": route, "pdf": compiled_pdf, "direct_response": final_output, "request_context": request_context}

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("AI Learning Mentor - Final Balanced Multilingual Core Active")
    print("Supports: English, Hindi, Marathi Mediums | Auto Font Fallbacks Running")
    print("=" * 70 + "\n")

    while True:
        user_q = input("Enter your query (or type exit): ").strip()
        if user_q.lower() in ["exit", "quit"]: 
            print("\nShutting down. Keep learning!\n")
            break
        if not user_q: continue
        try:
            res = process_question(user_q)
            print(f"\nResponse Generated Successfully!")
            print(f"PDF Location: {res.get('pdf')}")
            print(f"\n[Generated Report Preview]:\n{res.get('direct_response')}\n")
        except Exception as e:
            print(f"Pipeline Exception: {e}")