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
    else:
        subject = "All Core Streams" if variety == "paperset" else "General Academic Inquiries"
        
    return {
        "output_variety": variety,
        "class_level": class_level if class_level else "9",
        "is_higher_secondary": is_higher_secondary,
        "board": board,
        "language": lang,
        "subject": subject,
        "time_allowed": "3 Hours",
        "max_marks": 80
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
        format_blueprint = """
        LAYOUT FORMAT: QUESTION PAPER SET
        - Use strict headers: 'SECTION A: MULTIPLE CHOICE QUESTIONS (20 Marks)', 'SECTION B: SHORT ANSWER QUESTIONS (30 Marks)', and 'SECTION C: LONG ANSWER QUESTIONS (30 Marks)'.
        - For Section A, print 10 MCQs. Print each option (a, b, c, d) strictly on a NEW line.
        - Append question weights dynamically at the end of text lines using brackets, e.g., (5 Marks).
        - Append '### EXAM_ANSWER_KEY_SECTION' at the absolute bottom followed by evaluation guidelines.
        """
    elif ctx["output_variety"] == "official_syllabus":
        format_blueprint = """
        LAYOUT FORMAT: SYLLABUS UNIT OUTLINE
        - CRITICAL SPLIT CONFIGURATION: Every single syllabus line item must be written in a key-value format using a SINGLE colon string character.
        - Syntax rule: [Unit or Chapter Name] : [Complete Subtopics list, Chapter Core Content descriptions, and weightage tokens].
        - Example line: Chapter 1: Matter in our Surroundings - Particle nature, states of matter, and evaporation properties.
        - Do NOT include question sections, bullet blocks without colons, or mock grading templates.
        """
    elif ctx["output_variety"] == "study_notes":
        format_blueprint = """
        LAYOUT FORMAT: ACADEMIC REPOSITORY STUDY NOTES
        - Structure content text using clear headers: 'CHAPTER [X]: [CHAPTER TITLE]'.
        - Break up text details: '1. CORE THEORY ANALYSIS', '2. KEY TERMINOLOGY DEFINITIONS', and '3. CONCEPTUAL SCENARIO EXAMPLES'.
        - Ensure explanations provide high academic depth.
        """
    else:
        format_blueprint = """
        LAYOUT FORMAT: COMPREHENSIVE COMPOSITION
        - Provide a clean, deep explanatory overview matching the educational query directly.
        """

    orchestrator_agent = AssistantAgent(
        name="Dynamic_Orchestrator",
        llm_config=llm_config,
        system_message=f"""You are the Master Educational Director. Your task is to design explicit operational commands for the agents.
        
        Current Scope Context:
        - EDUCATION INFRASTRUCTURE: {"Higher Secondary (11-12)" if ctx['is_higher_secondary'] else "Secondary (1-10)"}
        - RECOGNIZED BOARD FRAMEWORK: {ctx['board']}
        - TARGET STANDARD: {ctx['class_level']}
        - FOCUS SUBJECT(S): {ctx['subject']}
        - INTENT FORMAT VARIETY: {ctx['output_variety']}
        - SPECIFIED STREAM LAYER: {ctx.get('stream', 'General Track')}
        - WORKING MEDIUM: {ctx['language']}

        Instructions for Specialist_Creator:
        1. Context Blueprint Mandate: You MUST follow this blueprint layout style exactly:
        {format_blueprint}
        2. Multi-Subject Handling: If the user asked for a broad class level framework without naming a specific subject, generate content for all core subjects combined.
        3. Language Constraint: Write entirely in {ctx['language']} (Devanagari if Marathi medium).
        4. Links: Always append '### EXT_LINK_PORTAL_TRIGGER' followed by verified textbook repository URLs at the absolute bottom.
        
        Issue your instruction card to Specialist_Creator now."""
    )

    creator_agent = AssistantAgent(
        name="Specialist_Creator",
        llm_config=llm_config,
        system_message="""You are the Content Setter. Listen to the instruction card from Dynamic_Orchestrator.
        Generate the full text body matching the specified layout format blueprint exactly.
        CRITICAL: Do NOT print progress updates, checklists, markdown status summaries, or meta-commentary. 
        Print ONLY the actual final academic text directly."""
    )

    critic_agent = AssistantAgent(
        name="Board_Reviewer",
        llm_config=llm_config,
        system_message="""You are the Quality Control Moderator. Review the content text printed by Specialist_Creator.
        Verify that it matches the layout format blueprint ordered by Dynamic_Orchestrator perfectly.
        If it contains the correct academic text, reprint that full text block exactly as it is, and append the string 'TERMINATE' at the absolute bottom of your message.
        Do NOT wrap the output inside metadata summaries, status timelines, or bulleted checklists."""
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

if __name__ == "__main__":
    while True:
        try:
            user_q = input("Ask your learning mentor (or type 'exit'): ").strip()
            if user_q.lower() in ["exit", "quit"]: break
            if not user_q: continue

            ctx = analyze_request(user_q)

            if ctx.get("output_variety") == "non_educational_reject":
                print(f"\n🛑 Sorry, this is a non-educational query. Please submit academic, curriculum, or general knowledge requests only.\n")
                continue

            if ctx["is_higher_secondary"]:
                print("\n[High School Academic Stream Selection Required]")
                print("[1] Science Track (PCM/PCB)   [2] Commerce Track   [3] Arts & Humanities")
                stream_choice = input("Select Academic Stream (1-3): ").strip()
                ctx["stream"] = "Commerce" if stream_choice == "2" else ("Arts" if stream_choice == "3" else "Science")
            else:
                print("\n[Academic Layout Medium Selection Required]")
                print("[1] English Medium Instruction Layer")
                print("[2] Marathi Medium Instruction Layer (मराठी भाषा माध्यम)")
                medium_choice = input("Select Medium (1-2): ").strip()
                if medium_choice == "2":
                    ctx["language"] = "Marathi"
                    ctx["board"] = "Maharashtra State Board"
                else:
                    ctx["language"] = "English"

            print("\n[Document Export Format Selection]")
            pdf_choice = input("Do you want to compile a downloadable PDF for this response? (y/n): ").strip().lower()
            should_pdf = True if pdf_choice in ["y", "yes"] else False

            final_response_text = run_pure_autogen_pipeline(user_q, ctx)
            
            print(f"\n" + "-" * 75)
            print(final_response_text)
            print("-" * 75)
            
            if should_pdf:
                final_notes_payload = final_response_text
                if "Official Board Reference" not in final_notes_payload and "Official Textbook" not in final_notes_payload:
                    final_notes_payload += f"\n\n### EXT_LINK_PORTAL_TRIGGER\n- Official Textbook Repository Portal: https://ebalbharati.in\n"
                
                output_filename = f"{ctx['subject'].lower().replace(', ', '_')}_{ctx['output_variety']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                
                include_key = False
                if ctx["output_variety"] == "paperset":
                    print("\n[Evaluation Key Display Configuration]")
                    ans_choice = input("Would you like to embed the Answer Key Appendix inside the PDF? (y/n): ").strip().lower()
                    include_key = True if ans_choice in ["y", "yes"] else False
                
                compiled_pdf = compile_exam_paper_to_pdf(
                    main_text=final_notes_payload, 
                    ctx=ctx, 
                    filename=output_filename, 
                    output_dir=OUTPUT_DIR, 
                    include_answer_key=include_key
                )
                print(f"Here is the PDF file for your output: {compiled_pdf}\n")
            else:
                print("⚡ Process complete. No PDF requested or generated.\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[Pipeline Critical Error]: {str(e)}\n")