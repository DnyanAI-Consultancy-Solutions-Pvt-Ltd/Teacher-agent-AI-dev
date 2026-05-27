import os
import re
import json
import certifi
import warnings
import autogen
from dotenv import load_dotenv
from datetime import datetime

from pdf_compiler import compile_chat_history_to_pdf
from tools import search_syllabus_tool, google_search_tool

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
    "timeout": 120,
    "cache_seed": None,
    "extra_body": {},
}

OUTPUT_DIR = "outputs"
MEMORY_FILE = "student_memory.json"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_student_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"topics_learned": []}


student_memory = load_student_memory()


def save_memory():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(student_memory, f, indent=4)


def update_student_memory(query):
    if query not in student_memory["topics_learned"]:
        student_memory["topics_learned"].append(query)
        save_memory()


QUERY_RULES = {
    "blocked": [
        "movie", "song", "weather", "recipe", "stock", "share market",
        "celebrity", "shopping", "restaurant", "joke", "cricket score",
        "sports score", "politics", "travel"
    ],
    "exam_info": [
        "neet", "jee", "cet", "gate", "upsc", "mpsc", "exam date",
        "when will", "timetable", "schedule", "admit card", "hall ticket",
        "result", "registration", "application form", "notification",
        "counselling", "counseling", "board exam"
    ],
    "quiz": [
        "quiz", "mcq", "mock test", "test paper", "question paper",
        "practice paper", "paper set", "paperset", "sample paper",
        "worksheet", "generate questions", "create questions", "model paper"
    ],
    "study": [
        "teach", "explain", "learn", "understand", "concept", "chapter",
        "topic", "formula", "solve", "notes", "summary", "revision",
        "syllabus", "curriculum", "roadmap", "class", "standard",
        "ssc", "hsc", "math", "maths", "science", "physics", "chemistry",
        "biology", "history", "geography", "english", "python", "coding",
        "probability", "algebra", "geometry", "grammar"
    ],
}


def classify_query(question: str) -> str:
    q = question.lower().strip()

    for category, keywords in QUERY_RULES.items():
        if any(keyword in q for keyword in keywords):
            return category

    return "unknown"


def answer_exam_info_question(question: str) -> str:
    search_query = f"{question} official latest notification exam date schedule"
    search_results = google_search_tool(search_query, num_results=5)

    exam_info_agent = autogen.AssistantAgent(
        name="exam_info_agent",
        llm_config=llm_config,
        system_message="""
You are an education exam information assistant.

Rules:
- Answer only using the provided Google search results.
- Prefer official sources like NTA, CBSE, Maharashtra Board, State CET Cell, official exam portals.
- If exact date is not officially confirmed in search results, clearly say it is not officially confirmed.
- Never guess exam dates.
- Never create quiz, notes, or study plan for exam date/schedule questions.
- Include source links from search results.
- Keep the response concise.
"""
    )

    temp_user = autogen.UserProxyAgent(
        name="Admin",
        human_input_mode="NEVER",
        code_execution_config={"use_docker": False},
    )

    prompt = f"""
User Question:
{question}

Google Search Results:
{search_results}

Prepare final answer using only the search results above.
"""

    temp_user.initiate_chat(exam_info_agent, message=prompt, max_turns=1)
    messages = temp_user.chat_messages[exam_info_agent]
    return messages[-1]["content"]


orchestrator_agent = autogen.AssistantAgent(
    name="orchestrator_agent",
    llm_config=llm_config,
    system_message="""
You are the Orchestrator for an education-only AI teacher system.

Select only ONE next agent.

Routing:
- teaching/explanation/concept/understanding -> concept_agent
- examples/solved problems/practical steps/coding examples -> example_agent
- notes/revision/summary/formulas/key points -> notes_agent
- syllabus/curriculum/roadmap/study plan -> planner_agent
- quiz/MCQ/mock test/question paper/practice paper/sample paper/worksheet/paper set -> quiz_agent

Important:
- Output only the agent name.
- Do not explain routing.
- Do not select quiz_agent unless the user clearly asks for quiz/test/paper/questions.
"""
)

planner_agent = autogen.AssistantAgent(
    name="planner_agent",
    llm_config=llm_config,
    system_message="""
You are planner_agent.

Create syllabus-based learning plans, roadmaps, curriculum guidance, and study plans.

Rules:
- If class/standard/board is mentioned, use syllabus context where available.
- Keep the plan suitable for the student's level.
- Do not create quiz unless explicitly requested.
- Add one minimal reference line only near the end, like: Ref: NCERT / State Board syllabus.
- End with [PLAN_DONE].
"""
)

concept_agent = autogen.AssistantAgent(
    name="concept_agent",
    llm_config=llm_config,
    system_message="""
You are concept_agent.

Teach educational concepts step by step.

Rules:
- Explain in simple language.
- Match student's class/standard if provided.
- Use examples only where useful.
- Use LaTeX notation for math where needed.
- Do not generate quiz unless explicitly requested.
- Add minimal citation/reference only once, not after every paragraph.
- Citation format must be short, like: Ref: NCERT / State Board textbook.
- End with [CONCEPT_DONE].
"""
)

example_agent = autogen.AssistantAgent(
    name="example_agent",
    llm_config=llm_config,
    system_message="""
You are example_agent.

Give examples, solved problems, practical steps, coding examples, and real-world educational use cases.

Rules:
- Match difficulty to student's level.
- Format as Problem, Step-by-Step Solution, Final Answer where useful.
- Use LaTeX notation for math where needed.
- Do not create full paper sets unless explicitly requested.
- Add one minimal reference line only, like: Ref: NCERT / State Board textbook.
- End with [EXAMPLE_DONE].
"""
)

notes_agent = autogen.AssistantAgent(
    name="notes_agent",
    llm_config=llm_config,
    system_message="""
You are notes_agent.

Create short notes, revision points, formulas, and summaries.

Rules:
- Keep notes exam-friendly and easy to revise.
- Use LaTeX notation for formulas where needed.
- Do not create quiz unless explicitly requested.
- Add minimal citation/reference only once near the top or bottom.
- Citation format must be short, like: Ref: NCERT / State Board textbook.
- End with [NOTES_DONE].
"""
)

quiz_agent = autogen.AssistantAgent(
    name="quiz_agent",
    llm_config=llm_config,
    system_message="""
You are quiz_agent.

Create exactly ONE final question paper, quiz, worksheet, mock test, or practice paper.

Strict Rules:
- Do NOT repeat the paper.
- Do NOT generate multiple versions.
- Do NOT include your agent name.
- Respond only when the user asks for quiz/test/question paper/practice questions.
- Include a professional header.
- Include class, subject, time, maximum marks, sections, questions, and answer key.
- Match class, subject, topic, and difficulty if provided.
- Do not put citation after every question.
- Add only one minimal reference line near the top-right or near the title, like:
  Ref: NCERT / State Board syllabus
- Keep reference very short.
- No long source list.
- End with [QUIZ_DONE].
"""
)

user_proxy = autogen.UserProxyAgent(
    name="Admin",
    human_input_mode="NEVER",
    code_execution_config={"use_docker": False},
)

autogen.agentchat.register_function(
    search_syllabus_tool,
    caller=planner_agent,
    executor=user_proxy,
    name="search_syllabus_tool",
    description="Searches official syllabus/curriculum context for class, board, and topic.",
)


def safe_pdf_filename(question: str) -> str:
    name = "_".join(question.split()[:5]).lower()
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)

    if not name:
        name = "education_output"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{name}_{timestamp}.pdf"


def normalize_chat_logs(messages, agent_name="assistant", user_question=""):
    normalized = []

    for msg in messages:
        content = msg.get("content", "")

        if not content:
            continue

        if user_question and content.strip() == user_question.strip():
            continue

        sender = msg.get("name") or msg.get("role") or agent_name

        if sender in ["Admin", "user"]:
            continue

        if sender == "assistant":
            sender = agent_name

        normalized.append(
            {
                "name": sender,
                "role": "assistant",
                "content": content,
            }
        )

    return normalized


def run_direct_agent(agent, question):
    user_proxy.initiate_chat(
        agent,
        message=question,
        max_turns=1,
        clear_history=True,
    )

    messages = user_proxy.chat_messages[agent]

    logs = normalize_chat_logs(
        messages=messages,
        agent_name=agent.name,
        user_question=question,
    )

    # Keep only final useful response to avoid repeated PDF content
    if logs:
        return [logs[-1]]

    return []


def run_group_agent_flow(question):
    agents = [
        user_proxy,
        orchestrator_agent,
        planner_agent,
        concept_agent,
        example_agent,
        notes_agent,
        quiz_agent,
    ]

    def custom_speaker_selection(last_speaker: autogen.Agent, groupchat: autogen.GroupChat):
        messages = groupchat.messages

        if not messages:
            return orchestrator_agent

        content = messages[-1].get("content") or ""

        done_tags = [
            "[PLAN_DONE]",
            "[CONCEPT_DONE]",
            "[EXAMPLE_DONE]",
            "[NOTES_DONE]",
            "[QUIZ_DONE]",
        ]

        completed_count = sum(
            1 for tag in done_tags
            if any(tag in (m.get("content") or "") for m in messages)
        )

        if completed_count >= 1:
            return None

        if any(tag in content for tag in done_tags):
            return None

        if last_speaker == user_proxy:
            return orchestrator_agent

        if last_speaker == orchestrator_agent:
            available_agents = {agent.name: agent for agent in groupchat.agents}

            for agent_name, agent_obj in available_agents.items():
                if agent_name in content:
                    return agent_obj

            return None

        return None

    groupchat = autogen.GroupChat(
        agents=agents,
        messages=[],
        max_round=4,
        speaker_selection_method=custom_speaker_selection,
        enable_clear_history=True,
    )

    manager = autogen.GroupChatManager(
        groupchat=groupchat,
        llm_config=None,
    )

    user_proxy.initiate_chat(
        manager,
        message=question,
        clear_history=True,
    )

    logs = normalize_chat_logs(
        messages=groupchat.messages,
        agent_name="education_agent",
        user_question=question,
    )

    # Keep only final useful response
    if logs:
        return [logs[-1]]

    return []


def process_question(user_question: str):
    user_question = user_question.strip()

    if not user_question:
        return {
            "type": "error",
            "answer": "Please type a valid education-related question.",
            "pdf": None,
        }

    query_type = classify_query(user_question)

    if query_type in ["blocked", "unknown"]:
        return {
            "type": "blocked",
            "answer": (
                "Sorry, I can answer only education-related questions. "
                "Please ask about studies, syllabus, exams, concepts, notes, or practice questions."
            ),
            "pdf": None,
        }

    if query_type == "exam_info":
        answer = answer_exam_info_question(user_question)

        return {
            "type": "exam_info",
            "answer": answer,
            "pdf": None,
        }

    if query_type == "quiz":
        chat_logs = run_direct_agent(quiz_agent, user_question)
    else:
        chat_logs = run_group_agent_flow(user_question)

    output_filename = safe_pdf_filename(user_question)

    compiled_pdf = compile_chat_history_to_pdf(
        chat_history=chat_logs,
        user_query=user_question,
        llm_config=llm_config,
        output_dir=OUTPUT_DIR,
        output_filename=output_filename,
        report_title="AI Education Report",
    )

    update_student_memory(user_question)

    return {
        "type": query_type,
        "answer": "Your educational response has been generated successfully. Please download the PDF.",
        "pdf": compiled_pdf,
    }


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("AI Education Teacher Agent")
    print("Education-only mode enabled")
    print("Type 'exit' or 'quit' to stop")
    print("=" * 70 + "\n")

    while True:
        user_question = input("What would you like to learn today? ").strip()

        if user_question.lower() in ["exit", "quit"]:
            print("\nShutting down AI Education Teacher Agent. Happy studying!\n")
            break

        result = process_question(user_question)

        print("\n" + "=" * 70)
        print(result["answer"])

        if result.get("pdf"):
            print(f"\nPDF generated: {result['pdf']}")

        print("=" * 70 + "\n")