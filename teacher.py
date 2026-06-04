import os
import re
import json
import certifi
import warnings
import hashlib
import autogen
from dotenv import load_dotenv
from datetime import datetime

from pdf_compiler import compile_chat_history_to_pdf
from tools import (
    search_syllabus_tool,
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
        "model": "llama-3.3-70b-versatile",
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
    "extra_body": {},
}

OUTPUT_DIR = "outputs"
MEMORY_FILE = "student_memory.json"
REFERENCE_CACHE_FILE = "reference_cache.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─────────────────────────────────────────
# MEMORY + CACHE
# ─────────────────────────────────────────

def load_json_file(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


student_memory = load_json_file(MEMORY_FILE, {"students": {}})
reference_cache = load_json_file(REFERENCE_CACHE_FILE, {})


def update_student_history(student_id, question, output_type, pdf_path=None):
    student_id = student_id or "default_student"

    if student_id not in student_memory["students"]:
        student_memory["students"][student_id] = {
            "questions": [],
            "topics_learned": [],
            "generated_pdfs": [],
            "last_updated": "",
        }

    record = {
        "question": question,
        "output_type": output_type,
        "pdf": pdf_path,
        "timestamp": datetime.now().isoformat(),
    }

    student_memory["students"][student_id]["questions"].append(record)

    if question not in student_memory["students"][student_id]["topics_learned"]:
        student_memory["students"][student_id]["topics_learned"].append(question)

    if pdf_path:
        student_memory["students"][student_id]["generated_pdfs"].append(pdf_path)

    student_memory["students"][student_id]["last_updated"] = datetime.now().isoformat()

    save_json_file(MEMORY_FILE, student_memory)


def cache_key(text):
    return hashlib.sha256(text.lower().strip().encode("utf-8")).hexdigest()


def get_cached_references(query):
    key = cache_key(query)

    if key in reference_cache:
        return reference_cache[key]

    return None


def save_cached_references(query, references):
    key = cache_key(query)
    reference_cache[key] = {
        "query": query,
        "references": references,
        "cached_at": datetime.now().isoformat(),
    }
    save_json_file(REFERENCE_CACHE_FILE, reference_cache)


def safe_pdf_filename(question: str, regenerate_count: int = 0) -> str:
    name = "_".join(question.split()[:6]).lower()
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)

    if not name:
        name = "ai_mentor_output"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if regenerate_count > 0:
        return f"{name}_v{regenerate_count}_{timestamp}.pdf"

    return f"{name}_{timestamp}.pdf"


# ─────────────────────────────────────────
# USER PROXY
# ─────────────────────────────────────────

user_proxy = autogen.UserProxyAgent(
    name="Admin",
    human_input_mode="NEVER",
    code_execution_config={"use_docker": False},
)


def run_single_agent(agent, message: str) -> str:
    user_proxy.initiate_chat(
        agent,
        message=message,
        max_turns=1,
        clear_history=True,
    )

    messages = user_proxy.chat_messages[agent]

    for msg in reversed(messages):
        content = msg.get("content", "")
        if content and content.strip() != message.strip():
            return content.strip()

    return ""


# ─────────────────────────────────────────
# REQUEST ANALYZER
# ─────────────────────────────────────────

request_analyzer_agent = autogen.AssistantAgent(
    name="request_analyzer_agent",
    llm_config=llm_config,
    system_message="""
You are request_analyzer_agent.

Analyze the request and return ONLY valid JSON.

Return this structure:

{
  "is_supported": true,
  "domain": "education | coding | career | project | general_learning | unknown",
  "output_type": "concept | notes | quiz | paper | roadmap | exam_info | example | code | code_review | debugging | architecture | interview | certification | project_plan | system_design | implementation | unknown",
  "class_level": "string",
  "subject": "string",
  "topic": "string",
  "chapter": "string",
  "board": "NCERT | CBSE | Maharashtra State Board | State Board | Unknown",
  "difficulty": "easy | medium | hard",
  "marks": 0,
  "language": "English | Hindi | Marathi",
  "include_answer_key": true,
  "needs_current_info": false,
  "detail_level": "normal | detailed | very_detailed",
  "bloom_level": "remember | understand | apply | analyze | evaluate | create | mixed",
  "reason": "short reason"
}

Rules:
- Education includes school/college subjects, syllabus, notes, quiz, paper, concepts, exam info.
- Coding includes programming, debugging, code review, APIs, frontend/backend, database.
- Career includes roadmap, interview, certification, job preparation.
- Project includes app building, architecture, implementation, system design.
- paper = paper set, model paper, question paper, assessment.
- quiz = MCQ, worksheet, practice questions.
- notes = revision notes, summary, formula sheet.
- exam_info = exam date, notification, admit card, result.
- If question asks detailed/full/complete/blueprint/end-to-end/from scratch, set detail_level very_detailed.
- If Bloom level is not mentioned, use mixed.
- If language not mentioned, use English.
- If harmful/illegal, set is_supported false.
Return only JSON.
"""
)


def analyze_request(user_question: str) -> dict:
    fallback = {
        "is_supported": True,
        "domain": "general_learning",
        "output_type": "concept",
        "class_level": "Unknown",
        "subject": "Unknown",
        "topic": user_question,
        "chapter": "Unknown",
        "board": "Unknown",
        "difficulty": "medium",
        "marks": 0,
        "language": "English",
        "include_answer_key": True,
        "needs_current_info": False,
        "detail_level": "normal",
        "bloom_level": "mixed",
        "reason": "Fallback analyzer used.",
    }

    try:
        raw = run_single_agent(request_analyzer_agent, user_question)
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)

        for key, value in fallback.items():
            parsed.setdefault(key, value)

        return parsed

    except Exception:
        q = user_question.lower()

        if any(w in q for w in ["complete", "detailed", "blueprint", "full setup", "end-to-end", "from scratch"]):
            fallback["detail_level"] = "very_detailed"

        if "hindi" in q:
            fallback["language"] = "Hindi"
        elif "marathi" in q:
            fallback["language"] = "Marathi"

        if "cbse" in q:
            fallback["board"] = "CBSE"
        elif "ncert" in q:
            fallback["board"] = "NCERT"
        elif "maharashtra" in q or "state board" in q:
            fallback["board"] = "Maharashtra State Board"

        if any(w in q for w in ["python", "java", "javascript", "react", "node", "fastapi", "api", "code", "error", "bug", "debug"]):
            fallback["domain"] = "coding"
            fallback["output_type"] = "debugging" if any(w in q for w in ["error", "bug", "fix"]) else "code"

        elif any(w in q for w in ["career", "interview", "certification", "resume", "job", "roadmap"]):
            fallback["domain"] = "career"
            fallback["output_type"] = "interview" if "interview" in q else "roadmap"

        elif any(w in q for w in ["project", "system design", "architecture", "implementation", "platform", "build app"]):
            fallback["domain"] = "project"
            if "system design" in q or "architecture" in q:
                fallback["output_type"] = "system_design"
            elif "implementation" in q:
                fallback["output_type"] = "implementation"
            else:
                fallback["output_type"] = "project_plan"

        elif any(w in q for w in ["class", "math", "science", "biology", "physics", "chemistry", "notes", "quiz", "paper", "exam"]):
            fallback["domain"] = "education"

            if any(w in q for w in ["paper", "question paper", "model paper"]):
                fallback["output_type"] = "paper"
                fallback["marks"] = 50
            elif any(w in q for w in ["quiz", "mcq", "worksheet"]):
                fallback["output_type"] = "quiz"
                fallback["marks"] = 20
            elif any(w in q for w in ["notes", "summary", "revision"]):
                fallback["output_type"] = "notes"
            elif any(w in q for w in ["exam date", "admit card", "result", "notification", "neet", "jee"]):
                fallback["output_type"] = "exam_info"
                fallback["needs_current_info"] = True
            else:
                fallback["output_type"] = "concept"

        marks_match = re.search(r"(\d+)\s*marks?", q)
        if marks_match:
            fallback["marks"] = int(marks_match.group(1))

        chapter_match = re.search(r"chapter\s*(\d+|[a-zA-Z ]+)", q)
        if chapter_match:
            fallback["chapter"] = chapter_match.group(1).strip()

        return fallback


# ─────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────

domain_router_agent = autogen.AssistantAgent(
    name="domain_router_agent",
    llm_config=llm_config,
    system_message="""
You are domain_router_agent.

Return only one route:

education_concept
education_notes
education_quiz
education_paper
education_roadmap
education_exam_info
coding_tutor
code_reviewer
debugging
architecture
career_roadmap
interview
certification
project_planner
system_design
implementation

Use REQUEST_CONTEXT only.
Return route only.
"""
)


def route_request(request_context: dict) -> str:
    try:
        route = run_single_agent(domain_router_agent, json.dumps(request_context, indent=2)).strip().lower()

        valid_routes = {
            "education_concept", "education_notes", "education_quiz", "education_paper",
            "education_roadmap", "education_exam_info", "coding_tutor", "code_reviewer",
            "debugging", "architecture", "career_roadmap", "interview", "certification",
            "project_planner", "system_design", "implementation",
        }

        if route in valid_routes:
            return route

    except Exception:
        pass

    domain = request_context.get("domain", "general_learning")
    output_type = request_context.get("output_type", "concept")

    if domain == "education":
        return {
            "paper": "education_paper",
            "quiz": "education_quiz",
            "notes": "education_notes",
            "roadmap": "education_roadmap",
            "exam_info": "education_exam_info",
        }.get(output_type, "education_concept")

    if domain == "coding":
        return {
            "code_review": "code_reviewer",
            "debugging": "debugging",
            "architecture": "architecture",
        }.get(output_type, "coding_tutor")

    if domain == "career":
        return {
            "interview": "interview",
            "certification": "certification",
        }.get(output_type, "career_roadmap")

    if domain == "project":
        return {
            "system_design": "system_design",
            "implementation": "implementation",
        }.get(output_type, "project_planner")

    return "education_concept"


# ─────────────────────────────────────────
# AGENTS
# ─────────────────────────────────────────

syllabus_agent = autogen.AssistantAgent(
    name="syllabus_agent",
    llm_config=llm_config,
    system_message="""
You are syllabus_agent.
Identify syllabus/chapter scope.
Include board, class, subject, chapter, subtopics.
Do not invent exact page numbers.
End with [SYLLABUS_DONE].
"""
)

curriculum_agent = autogen.AssistantAgent(
    name="curriculum_agent",
    llm_config=llm_config,
    system_message="""
You are curriculum_agent.
Make education content board-aware and curriculum-aligned.
Ensure chapter-wise and class-wise suitability.
End with [CURRICULUM_DONE].
"""
)

learning_outcome_agent = autogen.AssistantAgent(
    name="learning_outcome_agent",
    llm_config=llm_config,
    system_message="""
You are learning_outcome_agent.
Add 3-5 learning outcomes.
Use action words: Understand, Explain, Apply, Analyze, Evaluate, Create.
End with [OUTCOME_DONE].
"""
)

concept_agent = autogen.AssistantAgent(
    name="concept_agent",
    llm_config=llm_config,
    system_message="""
You are concept_agent.
Teach step-by-step.
Respect language, board, class, difficulty, Bloom level.
Include examples, common mistakes, quick revision.
End with [CONCEPT_DONE].
"""
)

notes_agent = autogen.AssistantAgent(
    name="notes_agent",
    llm_config=llm_config,
    system_message="""
You are notes_agent.
Create structured notes.
Include learning outcomes, definitions, formulas, key points, examples, common mistakes, quick revision, practice questions.
Respect requested language.
End with [NOTES_DONE].
"""
)

quiz_agent = autogen.AssistantAgent(
    name="quiz_agent",
    llm_config=llm_config,
    system_message="""
You are quiz_agent.
Create exactly ONE quiz/worksheet.
Respect marks, difficulty, Bloom level, chapter, language.
Include answer key only if include_answer_key is true.
Do not repeat questions.
End with [QUIZ_DONE].
"""
)

paper_agent = autogen.AssistantAgent(
    name="paper_agent",
    llm_config=llm_config,
    system_message="""
You are paper_agent.
Create exactly ONE professional paper.
Include:
- title
- board
- class
- subject
- chapter/topic
- time
- marks
- instructions
- marks distribution table
- Bloom's level table
- sections
- questions
- answer key only if include_answer_key is true

Respect 20/50/80/100 marks.
Respect language.
Do not repeat paper.
End with [PAPER_DONE].
"""
)

coding_tutor_agent = autogen.AssistantAgent(
    name="coding_tutor_agent",
    llm_config=llm_config,
    system_message="""
You are coding_tutor_agent.
Teach coding with explanation, commands, code snippets, folder structure, testing, deployment notes.
End with [CODING_TUTOR_DONE].
"""
)

code_reviewer_agent = autogen.AssistantAgent(
    name="code_reviewer_agent",
    llm_config=llm_config,
    system_message="""
You are code_reviewer_agent.
Review code for bugs, security, readability, performance.
Give fixed code and issue table.
End with [CODE_REVIEW_DONE].
"""
)

debugging_agent = autogen.AssistantAgent(
    name="debugging_agent",
    llm_config=llm_config,
    system_message="""
You are debugging_agent.
Explain error, root cause, fix, commands, verification, prevention.
End with [DEBUGGING_DONE].
"""
)

architecture_agent = autogen.AssistantAgent(
    name="architecture_agent",
    llm_config=llm_config,
    system_message="""
You are architecture_agent.
Create detailed architecture with components, data flow, APIs, DB, security, deployment, monitoring, scaling.
End with [ARCHITECTURE_DONE].
"""
)

roadmap_agent = autogen.AssistantAgent(
    name="roadmap_agent",
    llm_config=llm_config,
    system_message="""
You are roadmap_agent.
Create learning/career roadmap with phases, weekly plan, resources, projects, checkpoints.
End with [ROADMAP_DONE].
"""
)

interview_agent = autogen.AssistantAgent(
    name="interview_agent",
    llm_config=llm_config,
    system_message="""
You are interview_agent.
Create interview preparation plan, questions, answers, scenarios, hands-on tasks.
End with [INTERVIEW_DONE].
"""
)

certification_agent = autogen.AssistantAgent(
    name="certification_agent",
    llm_config=llm_config,
    system_message="""
You are certification_agent.
Create certification preparation plan with resources, timeline, practice strategy.
End with [CERTIFICATION_DONE].
"""
)

project_planner_agent = autogen.AssistantAgent(
    name="project_planner_agent",
    llm_config=llm_config,
    system_message="""
You are project_planner_agent.
Create detailed project blueprint:
requirements, features, modules, tech stack, folder structure, timeline, risks, milestones.
Do not summarize detailed requests.
End with [PROJECT_PLAN_DONE].
"""
)

system_design_agent = autogen.AssistantAgent(
    name="system_design_agent",
    llm_config=llm_config,
    system_message="""
You are system_design_agent.
Create detailed system design:
HLD, LLD, APIs, DB, auth, security, scaling, deployment, monitoring, failure handling.
Do not summarize detailed requests.
End with [SYSTEM_DESIGN_DONE].
"""
)

implementation_agent = autogen.AssistantAgent(
    name="implementation_agent",
    llm_config=llm_config,
    system_message="""
You are implementation_agent.
Give step-by-step implementation:
setup, backend, frontend, DB, APIs, auth, testing, Docker, CI/CD, deployment, verification.
Do not summarize detailed requests.
End with [IMPLEMENTATION_DONE].
"""
)

assessment_agent = autogen.AssistantAgent(
    name="assessment_agent",
    llm_config=llm_config,
    system_message="""
You are assessment_agent.
For quiz/paper check marks distribution, answer key, difficulty balance, Bloom levels, chapter coverage.
Do not shorten.
End with [ASSESSMENT_DONE].
"""
)

difficulty_agent = autogen.AssistantAgent(
    name="difficulty_agent",
    llm_config=llm_config,
    system_message="""
You are difficulty_agent.
Adjust difficulty and Bloom levels:
remember, understand, apply, analyze, evaluate, create.
Do not remove sections.
End with [DIFFICULTY_DONE].
"""
)

reference_agent = autogen.AssistantAgent(
    name="reference_agent",
    llm_config=llm_config,
    system_message="""
You are reference_agent.
Add compact references and Explore More.
For education include chapter/book/page hints if safe.
For coding/career/project include official docs/resources.
Do not invent exact page numbers.
End with [REFERENCE_DONE].
"""
)

motivator_agent = autogen.AssistantAgent(
    name="motivator_agent",
    llm_config=llm_config,
    system_message="""
You are motivator_agent.
Add short confidence-building message.
Keep it 2-4 lines.
End with [MOTIVATION_DONE].
"""
)

curator_agent = autogen.AssistantAgent(
    name="curator_agent",
    llm_config=llm_config,
    system_message="""
You are curator_agent.
Organize and polish content.
Do NOT shorten.
Preserve headings, details, code, tables, roadmap, architecture, implementation steps.
Remove only repetition/irrelevant text.
End with [CURATOR_DONE].
"""
)

quality_checker_agent = autogen.AssistantAgent(
    name="quality_checker_agent",
    llm_config=llm_config,
    system_message="""
You are quality_checker_agent.
Final cleanup only.
Do NOT shorten.
Remove duplicate content, agent names, internal tags.
Preserve all useful detail.
Return PDF-ready output.
End with [QUALITY_DONE].
"""
)

exam_info_agent = autogen.AssistantAgent(
    name="exam_info_agent",
    llm_config=llm_config,
    system_message="""
You are exam_info_agent.
Answer using provided search results only.
Prefer official sources.
Never guess.
Include links.
"""
)

autogen.agentchat.register_function(
    search_syllabus_tool,
    caller=syllabus_agent,
    executor=user_proxy,
    name="search_syllabus_tool",
    description="Search syllabus/curriculum context.",
)


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def clean_agent_output(text: str) -> str:
    if not text:
        return ""

    tags = [
        "SYLLABUS_DONE", "CURRICULUM_DONE", "OUTCOME_DONE", "CONCEPT_DONE",
        "NOTES_DONE", "QUIZ_DONE", "PAPER_DONE", "CODING_TUTOR_DONE",
        "CODE_REVIEW_DONE", "DEBUGGING_DONE", "ARCHITECTURE_DONE",
        "ROADMAP_DONE", "INTERVIEW_DONE", "CERTIFICATION_DONE",
        "PROJECT_PLAN_DONE", "SYSTEM_DESIGN_DONE", "IMPLEMENTATION_DONE",
        "ASSESSMENT_DONE", "DIFFICULTY_DONE", "REFERENCE_DONE",
        "MOTIVATION_DONE", "CURATOR_DONE", "QUALITY_DONE",
    ]

    for tag in tags:
        text = re.sub(rf"\[{tag}\]", "", text, flags=re.IGNORECASE)

    text = re.sub(r"^.*?_agent\s*$", "", text, flags=re.IGNORECASE | re.MULTILINE)

    return text.strip()


def build_context_prompt(
    request_context,
    syllabus_context="",
    curriculum_context="",
    learning_outcomes="",
    draft="",
    references="",
    student_history="",
    regenerate_count=0,
):
    return f"""
REQUEST_CONTEXT:
{json.dumps(request_context, indent=2, ensure_ascii=False)}

STUDENT_HISTORY:
{student_history}

REGENERATION_VERSION:
{regenerate_count}

SYLLABUS_OR_CONTEXT:
{syllabus_context}

CURRICULUM_OR_DOMAIN_CONTEXT:
{curriculum_context}

LEARNING_OUTCOMES:
{learning_outcomes}

DRAFT_OUTPUT:
{draft}

REFERENCE_CONTEXT:
{references}

IMPORTANT:
- Respect language.
- Respect difficulty.
- Respect marks.
- Respect answer key toggle.
- Respect Bloom level.
- If regeneration version is greater than 0, create a different variation.
"""


def get_student_history(student_id):
    student_id = student_id or "default_student"
    return json.dumps(
        student_memory.get("students", {}).get(student_id, {}),
        indent=2,
        ensure_ascii=False,
    )


def build_reference_text(user_question, domain="education"):
    cached = get_cached_references(user_question)
    if cached:
        return cached["references"]

    if domain == "education":
        try:
            refs = build_learning_references(user_question)
            save_cached_references(user_question, refs)
            return refs
        except Exception:
            pass

    refs = (
        "---REFERENCE_METADATA_START---\n"
        f"Citation Hint: {get_minimal_citation(user_question) if domain == 'education' else 'Ref: official docs / trusted learning resources'}\n"
        "Explore More:\n"
        "1. Official documentation or textbook/resource for this topic\n"
        "2. Practical examples and exercises\n"
        "3. Best-practice guides or reference material\n"
        "---REFERENCE_METADATA_END---"
    )

    save_cached_references(user_question, refs)
    return refs


def normalize_final_log(final_content, agent_name="final_agent"):
    return [{"name": agent_name, "role": "assistant", "content": final_content}]


def answer_exam_info_question(question):
    search_results = google_search_tool(
        f"{question} official latest notification exam date schedule",
        num_results=5,
    )

    prompt = f"""
User Question:
{question}

Google Search Results:
{search_results}

Answer only from these results.
"""

    return clean_agent_output(run_single_agent(exam_info_agent, prompt))


# ─────────────────────────────────────────
# PIPELINES
# ─────────────────────────────────────────

def run_education_pipeline(user_question, request_context, route, student_history, regenerate_count):
    syllabus_context = clean_agent_output(
        run_single_agent(
            syllabus_agent,
            build_context_prompt(request_context, student_history=student_history),
        )
    )

    curriculum_context = clean_agent_output(
        run_single_agent(
            curriculum_agent,
            build_context_prompt(request_context, syllabus_context=syllabus_context, student_history=student_history),
        )
    )

    learning_outcomes = clean_agent_output(
        run_single_agent(
            learning_outcome_agent,
            build_context_prompt(
                request_context,
                syllabus_context=syllabus_context,
                curriculum_context=curriculum_context,
                student_history=student_history,
            ),
        )
    )

    base_prompt = build_context_prompt(
        request_context,
        syllabus_context=syllabus_context,
        curriculum_context=curriculum_context,
        learning_outcomes=learning_outcomes,
        student_history=student_history,
        regenerate_count=regenerate_count,
    )

    if route == "education_paper":
        draft = run_single_agent(paper_agent, base_prompt)
        specialist_name = "paper_agent"
    elif route == "education_quiz":
        draft = run_single_agent(quiz_agent, base_prompt)
        specialist_name = "quiz_agent"
    elif route == "education_notes":
        draft = run_single_agent(notes_agent, base_prompt)
        specialist_name = "notes_agent"
    elif route == "education_roadmap":
        draft = run_single_agent(roadmap_agent, base_prompt)
        specialist_name = "roadmap_agent"
    else:
        draft = run_single_agent(concept_agent, base_prompt)
        specialist_name = "concept_agent"

    draft = clean_agent_output(draft)

    if learning_outcomes and route not in ["education_paper", "education_quiz"]:
        draft = "Learning Outcomes\n" + learning_outcomes + "\n\n" + draft

    if route in ["education_paper", "education_quiz"]:
        draft = clean_agent_output(
            run_single_agent(
                assessment_agent,
                build_context_prompt(request_context, draft=draft, student_history=student_history),
            )
        )

        draft = clean_agent_output(
            run_single_agent(
                difficulty_agent,
                build_context_prompt(request_context, draft=draft, student_history=student_history),
            )
        )

    return draft, specialist_name


def run_simple_domain_pipeline(request_context, route, student_history, regenerate_count):
    prompt = build_context_prompt(
        request_context,
        student_history=student_history,
        regenerate_count=regenerate_count,
    )

    route_map = {
        "coding_tutor": coding_tutor_agent,
        "code_reviewer": code_reviewer_agent,
        "debugging": debugging_agent,
        "architecture": architecture_agent,
        "career_roadmap": roadmap_agent,
        "interview": interview_agent,
        "certification": certification_agent,
        "project_planner": project_planner_agent,
        "system_design": system_design_agent,
        "implementation": implementation_agent,
    }

    agent = route_map.get(route, coding_tutor_agent)
    draft = clean_agent_output(run_single_agent(agent, prompt))

    return draft, agent.name


def run_project_full_blueprint_pipeline(request_context, student_history, regenerate_count):
    base_prompt = build_context_prompt(
        request_context,
        student_history=student_history,
        regenerate_count=regenerate_count,
    )

    project_plan = clean_agent_output(run_single_agent(project_planner_agent, base_prompt))

    system_design = clean_agent_output(
        run_single_agent(
            system_design_agent,
            build_context_prompt(request_context, draft=project_plan, student_history=student_history),
        )
    )

    implementation_plan = clean_agent_output(
        run_single_agent(
            implementation_agent,
            build_context_prompt(
                request_context,
                draft=project_plan + "\n\n" + system_design,
                student_history=student_history,
            ),
        )
    )

    career_roadmap = clean_agent_output(
        run_single_agent(
            roadmap_agent,
            build_context_prompt(
                request_context,
                draft=project_plan + "\n\n" + system_design + "\n\n" + implementation_plan,
                student_history=student_history,
            ),
        )
    )

    combined = f"""
# Complete Project Blueprint

## 1. Project Plan
{project_plan}

## 2. System Design and Architecture
{system_design}

## 3. Implementation Guide
{implementation_plan}

## 4. Learning and Career Roadmap
{career_roadmap}
"""

    return combined.strip(), "project_planner_agent"


def finalize_output(user_question, request_context, draft):
    domain = request_context.get("domain", "education")
    reference_metadata = build_reference_text(user_question, domain)

    reference_output = clean_agent_output(
        run_single_agent(
            reference_agent,
            build_context_prompt(request_context, draft=draft, references=reference_metadata),
        )
    )

    combined_output = draft.strip()

    if reference_output:
        combined_output += "\n\n" + reference_output.strip()

    combined_output += "\n\n" + reference_metadata.strip()

    motivation_output = clean_agent_output(
        run_single_agent(
            motivator_agent,
            build_context_prompt(request_context, draft=combined_output, references=reference_metadata),
        )
    )

    if motivation_output:
        combined_output += "\n\n" + motivation_output.strip()

    curated_output = clean_agent_output(
        run_single_agent(
            curator_agent,
            build_context_prompt(request_context, draft=combined_output, references=reference_metadata),
        )
    )

    if not curated_output:
        curated_output = combined_output

    final_output = clean_agent_output(
        run_single_agent(
            quality_checker_agent,
            build_context_prompt(request_context, draft=curated_output, references=reference_metadata),
        )
    )

    if not final_output:
        final_output = curated_output

    if "---REFERENCE_METADATA_START---" not in final_output:
        final_output += "\n\n" + reference_metadata.strip()

    return final_output


# ─────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────

def process_question(
    user_question: str,
    student_id: str = "default_student",
    board: str = None,
    difficulty: str = None,
    marks: int = None,
    language: str = None,
    include_answer_key: bool = None,
    output_type: str = None,
    chapter: str = None,
    bloom_level: str = None,
    regenerate: bool = False,
    regenerate_count: int = 0,
):
    user_question = user_question.strip()

    if not user_question:
        return {
            "type": "error",
            "answer": "Please type a valid question.",
            "pdf": None,
            "direct_response": "",
        }

    request_context = analyze_request(user_question)

    # Override analyzer with API/UI values if provided
    if board:
        request_context["board"] = board
    if difficulty:
        request_context["difficulty"] = difficulty
    if marks is not None:
        request_context["marks"] = marks
    if language:
        request_context["language"] = language
    if include_answer_key is not None:
        request_context["include_answer_key"] = include_answer_key
    if output_type:
        request_context["output_type"] = output_type
    if chapter:
        request_context["chapter"] = chapter
    if bloom_level:
        request_context["bloom_level"] = bloom_level

    if regenerate:
        regenerate_count = regenerate_count or 1

    request_context["regenerate"] = regenerate
    request_context["regenerate_count"] = regenerate_count

    if not request_context.get("is_supported", True):
        return {
            "type": "blocked",
            "answer": "Sorry, I cannot help with this request.",
            "pdf": None,
            "direct_response": "",
        }

    route = route_request(request_context)

    if route == "education_exam_info" or request_context.get("needs_current_info", False):
        answer = answer_exam_info_question(user_question)
        return {
            "type": "exam_info",
            "answer": answer,
            "pdf": None,
            "direct_response": answer,
        }

    domain = request_context.get("domain", "education")
    detail_level = request_context.get("detail_level", "normal")
    student_history = get_student_history(student_id)

    if domain == "project" and detail_level in ["detailed", "very_detailed"]:
        draft, specialist_name = run_project_full_blueprint_pipeline(
            request_context,
            student_history,
            regenerate_count,
        )
    elif route.startswith("education"):
        draft, specialist_name = run_education_pipeline(
            user_question,
            request_context,
            route,
            student_history,
            regenerate_count,
        )
    else:
        draft, specialist_name = run_simple_domain_pipeline(
            request_context,
            route,
            student_history,
            regenerate_count,
        )

    final_output = finalize_output(user_question, request_context, draft)

    chat_logs = normalize_final_log(final_output, specialist_name)
    output_filename = safe_pdf_filename(user_question, regenerate_count)

    citation_hint = (
        get_minimal_citation(user_question)
        if domain == "education"
        else "Ref: official docs / trusted learning resources"
    )

    compiled_pdf = compile_chat_history_to_pdf(
        chat_history=chat_logs,
        user_query=user_question,
        llm_config=llm_config,
        output_dir=OUTPUT_DIR,
        output_filename=output_filename,
        report_title="AI Learning & Career Mentor Report",
        citation_hint=citation_hint,
    )

    update_student_history(student_id, user_question, route, compiled_pdf)

    return {
        "type": route,
        "answer": "Your response has been generated successfully. Please download the PDF.",
        "pdf": compiled_pdf,
        "direct_response": final_output,
        "request_context": request_context,
    }


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("AI Learning & Career Mentor - Final Backend")
    print("Supports: Education, Coding, Career, Project Planning")
    print("=" * 70 + "\n")

    while True:
        user_question = input("What would you like to ask/learn today? ").strip()

        if user_question.lower() in ["exit", "quit"]:
            print("\nShutting down. Keep learning!\n")
            break

        result = process_question(user_question)

        print("\n" + "=" * 70)
        print(result["answer"])

        if result.get("pdf"):
            print(f"\nPDF generated: {result['pdf']}")

        print("=" * 70 + "\n")