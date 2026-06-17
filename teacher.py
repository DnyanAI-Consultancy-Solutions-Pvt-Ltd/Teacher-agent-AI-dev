import os
import re
import warnings
from dotenv import load_dotenv
import autogen
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
from pdf_compiler import compile_exam_paper_to_pdf
from datetime import datetime

warnings.filterwarnings("ignore", category=UserWarning)

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise EnvironmentError("Critical Environment Error: GROQ_API_KEY is missing from environment configuration.")

ACTIVE_MODEL = "llama-3.1-8b-instant"
llm_config = {
    "config_list": [
        {
            "model": ACTIVE_MODEL,
            "api_key": GROQ_API_KEY,
            "base_url": "https://api.groq.com/openai/v1",
        }
    ],
    "temperature": 0.1,
}

OUTPUT_DIR = "outputs"

def contains_devanagari(text: str) -> bool:
    return any(0x0900 <= ord(ch) <= 0x097F for ch in text) if text else False

def normalize_language_hint(text: str) -> str:
    if not text: return "English"
    t = text.lower()
    if any(k in t for k in ["marathi", "मराठी"]): return "Marathi"
    if any(k in t for k in ["hindi", "हिंदी"]): return "Hindi"
    return "Hindi" if contains_devanagari(text) else "English"

def analyze_request(user_question: str) -> dict:
    q = user_question.lower().strip()
    
    non_edu_signals = [
        "recipe", "how to cook", "movie gossip", "bollywood", "hollywood", 
        "song lyrics", "cricket score", "ipl score", "gaming cheat", "video game stream"
    ]
    if any(junk in q for junk in non_edu_signals):
        return {"output_variety": "non_educational_reject", "generate_pdf": False}

    with_answers = False
    if any(ans in q for ans in ["with answers", "answer key", "solutions", "उत्तरांसह", "उत्तरपत्रिका"]):
        with_answers = True

    if any(k in q for k in ["syllabus", "curriculum", "chapters", "index", "अभ्यासक्रम"]):
        variety = "official_syllabus"
    elif any(k in q for k in ["paper", "test", "exam", "question paper", "प्रश्नपत्रिका", "mock"]):
        variety = "paperset"
    elif any(k in q for k in ["gk", "general knowledge", "who is", "fact", "history of", "gk questions", "capital of"]):
        variety = "general_knowledge"
    elif any(k in q for k in ["notes", "explain", "study material", "tutorial", "chapter summary"]):
        variety = "study_notes"
    else:
        variety = "educational_query"

    lang = normalize_language_hint(user_question)
    
    class_level = None
    class_match = re.search(r'(\d+)', q)
    if class_match:
        class_level = class_match.group(1)
    else:
        if "eleven" in q or "11th" in q or "hsc" in q: class_level = "11"
        elif "twelve" in q or "12th" in q: class_level = "12"
        elif "ten" in q or "10th" in q or "ssc" in q: class_level = "10"
        elif "ninth" in q or "9th" in q: class_level = "9"

    is_higher_secondary = False
    if class_level and class_level.isdigit():
        if int(class_level) in [11, 12]:
            is_higher_secondary = True

    board = "Maharashtra State Board" if lang == "Marathi" or "maharashtra" in q else "CBSE"

    subject = None
    subject_map = {
        "physics": "Physics", "chemistry": "Chemistry", "biology": "Biology", 
        "science": "Science", "math": "Mathematics", "history": "History",
        "geography": "Geography", "social science": "Social Science", "marathi": "Marathi",
        "civics": "Political Science", "economics": "Economics", "accounts": "Accountancy"
    }
    
    found_subjects = []
    for key, sub_val in subject_map.items():
        if key in q:
            found_subjects.append(sub_val)
            
    if found_subjects:
        subject = ", ".join(list(set(found_subjects)))
        is_generic_paper = False
    else:
        subject = "All Core Disciplines" if variety == "paperset" else "General Academic Inquiries"
        is_generic_paper = True if variety == "paperset" else False
        
    return {
        "output_variety": variety,
        "class_level": class_level if class_level else "9",
        "is_higher_secondary": is_higher_secondary,
        "board": board,
        "language": lang,
        "subject": subject,
        "is_generic_paper": is_generic_paper,
        "with_answers": with_answers,
        "time_allowed": "3 Hours",
        "max_marks": 100 if variety == "paperset" else 80
    }

def run_pure_autogen_pipeline(user_query: str, ctx: dict):
    print(f"\n[AutoGen Setup] Spawning academic group conversation room...")

    user_proxy = UserProxyAgent(
        name="Admin_Proxy",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=2,
        is_termination_msg=lambda x: "TERMINATE" in x.get("content", "").upper(),
        code_execution_config=False
    )

    format_blueprint = ""
    if ctx["output_variety"] == "paperset":
        if ctx["is_generic_paper"]:
            subject_distribution_rule = (
                "This is a comprehensive full-grade exam. You MUST distribute the 100 marks equally "
                "across ALL core subjects for this class (e.g., Science, Mathematics, Social Science, and Language). "
                "Create distinct subheadings within each section for each subject so they are fully covered."
            )
        else:
            subject_distribution_rule = f"This exam is strictly focused on {ctx['subject']}. All questions must target the detailed curriculum of this subject."

        if ctx["with_answers"]:
            answer_handling_rule = (
                "The user explicitly requested answers. You MUST compile a clean question paper layout first, "
                "and append '### EXAM_ANSWER_KEY_SECTION' at the absolute bottom followed by the clean answers."
            )
        else:
            answer_handling_rule = (
                "CRITICAL BLANK EXAM RULE: The user wants a standard test paper ONLY. "
                "Do NOT write words like 'Answer:', 'Solution:', or expose the correct keys anywhere in the text layout. "
                "Every single section must contain clean, unanswered evaluation items for a student to answer."
            )

        format_blueprint = f"""
        LAYOUT FORMAT: RIGOROUS 100-MARK QUESTION PAPER
        - TOTAL WEIGHTAGE: 100 Marks.
        - {subject_distribution_rule}
        - Use strict structural headers:
          SECTION A: MULTIPLE CHOICE QUESTIONS (25 Marks)
          SECTION B: SHORT ANSWER QUESTIONS (35 Marks)
          SECTION C: LONG ANSWER QUESTIONS (40 Marks)
        - {answer_handling_rule}
        """
    elif ctx["output_variety"] == "official_syllabus":
        format_blueprint = """
        LAYOUT FORMAT: SYLLABUS UNIT OUTLINE
        - Every syllabus line item must use a single colon formatting pattern: [Unit/Chapter Module] : [Subtopics, content definitions, and weightage].
        - Do NOT include mock question sets or scoring guidelines.
        """
    elif ctx["output_variety"] == "study_notes":
        # TOKEN-OPTIMIZED CONTEXT-PACKED PROMPT FOR STUDY NOTES
        format_blueprint = """
        LAYOUT FORMAT: TEXTBOOK-STYLE STUDY NOTES WITH MULTI-DISCIPLINARY DIAGRAM ANCHORS
        - Structure contents using clear headers: 'CHAPTER [X]: [CHAPTER TITLE]'.
        - Organize text logically using subheadings: '1. CORE THEORY ANALYSIS', '2. KEY TERMINOLOGY DEFINITIONS', and '3. CONCEPTUAL SCENARIO EXAMPLES'.
        
        CRITICAL TOKEN CONSTRAINT SECURITY RULE:
        To prevent API Rate Limit Errors, be concise and dense. Write elite textbook definitions without long conversational words.
        
        VISUAL DIAGRAM ADVANCEMENT RULE:
        Whenever you introduce a vital conceptual mechanism (e.g., cellular division checkpoints, circuit loops, flowcharts, geometric proofs), insert a dedicated diagram placeholder anchor using this literal formatting token syntax on a standalone new line:
        

[Image of X]

        Where X is a comprehensive description of what the graphic or structural illustration should visualize for a child.
        """
    else:
        format_blueprint = "LAYOUT FORMAT: Provide an elegant educational composition directly matching the query targets."

    orchestrator_agent = AssistantAgent(
        name="Dynamic_Orchestrator",
        llm_config=llm_config,
        system_message=f"""You are the Master Educational Director. Your task is to design explicit layout commands for the agents.
        
        CRITICAL OPERATIONAL CONSTRAINT:
        The text generation token limit is restricted to 6,000 tokens. Instruct the creator to compress explanation prose, avoid repetitive phrasing, and write dense, high-quality, actionable content.

        Current Scope Context:
        - EDUCATION LEVEL: {"Higher Secondary (11-12)" if ctx['is_higher_secondary'] else "Secondary (1-10)"}
        - TARGET BOARD: {ctx['board']}
        - GRADE INFRASTRUCTURE: Standard {ctx['class_level']}
        - FOCUS SUBJECT(S): {ctx['subject']}
        - FORMAT TARGET VARIETY: {ctx['output_variety']}
        - WORKING LANGUAGE MEDIUM: {ctx['language']}

        Instructions for Specialist_Creator:
        1. Blueprint Execution: Follow this structural framework layout exactly:
        {format_blueprint}
        2. Multi-Subject Handling: If the user asked for a broad class level framework without naming a specific subject, generate content for all core subjects combined.
        3. Language Constraint: Write entirely in {ctx['language']} (Devanagari script if Marathi).
        4. Links: Always append '### EXT_LINK_PORTAL_TRIGGER' followed by official textbook repository anchors at the bottom.
        
        Issue your instruction card to Specialist_Creator now."""
    )

    creator_agent = AssistantAgent(
        name="Specialist_Creator",
        llm_config=llm_config,
        system_message="""You are the Content Setter and Research Teacher. Listen to the instruction card from Dynamic_Orchestrator.
        Generate the full text body matching the specified layout format blueprint exactly.
        CRITICAL COMPRESSION RESTRAINT: Write high-density summaries. Do NOT print progress updates, chat checklists, formatting notes, or long descriptions. 
        Print ONLY the actual final academic text directly to keep the message size safe and under token limits."""
    )

    critic_agent = AssistantAgent(
        name="Board_Reviewer",
        llm_config=llm_config,
        system_message="""You are the Quality Control Moderator. Review the text block printed by Specialist_Creator.
        Verify that it satisfies the marks weightage, subject distribution, and answer-key inclusion boundaries ordered by Dynamic_Orchestrator perfectly.
        If it contains the correct text, reprint that full text block exactly as it is, and append the string 'TERMINATE' at the absolute bottom of your message.
        Do NOT wrap the output inside progress check timelines or formatting templates."""
    )

    agent_team = [user_proxy, orchestrator_agent, creator_agent, critic_agent]
    groupchat = GroupChat(agents=agent_team, messages=[], max_round=6, speaker_selection_method="round_robin")
    manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)

    chat_history_log = user_proxy.initiate_chat(
        recipient=manager,
        message=f"User Query Target: {user_query}. Dynamic_Orchestrator, parse the intent requirements and issue the dynamic instruction card.",
        clear_history=True
    )

    final_raw_content = ""
    for message in reversed(chat_history_log.chat_history):
        msg_content = message.get("content", "")
        if "TERMINATE" in msg_content.upper() and "BOARD_REVIEWER" in message.get("name", "").upper():
            clean_text = re.sub(r'(?i)TERMINATE', '', msg_content).strip()
            if "Task Review" not in clean_text and len(clean_text) > 150:
                final_raw_content = clean_text
                break
                
    if not final_raw_content:
        for message in reversed(chat_history_log.chat_history):
            if "SPECIALIST_CREATOR" in message.get("name", "").upper():
                final_raw_content = message.get("content", "").replace("TERMINATE", "").strip()
                break

    if not final_raw_content:
        final_raw_content = chat_history_log.chat_history[-1]['content'].replace("TERMINATE", "").strip()

    return final_raw_content