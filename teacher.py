import os
import re
import json
import time
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
    "timeout": 30,
}

OUTPUT_DIR = "outputs"

# ──────────────────────────────────────────────────────────────────────────────
# PURE AGENTIC ROUTING LAYER (NO IF-ELSE BLOCK CHAINS)
# ──────────────────────────────────────────────────────────────────────────────
def agentic_analyze_request(user_question: str) -> dict:
    """Uses a specialized analyzer agent to parse context using natural language instructions."""
    print(f"[Agentic Analysis] Parsing user query properties...")
    
    analyzer_proxy = UserProxyAgent(
        name="Analyzer_Proxy",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=0,
        code_execution_config=False
    )
    
    analyzer_agent = AssistantAgent(
        name="Query_Analyzer",
        llm_config=llm_config,
        system_message="""You are an expert Educational Metadata Parser. Analyze the incoming user query and return a valid JSON object matching the schema below.
        
        CRITICAL RULES:
        1. If the query is completely non-educational (e.g., cooking recipes, movie gossip, pop music), set "output_variety" to "non_educational_reject".
        2. Categorize the request format ("output_variety") as one of: "paperset", "official_syllabus", "study_notes", "general_knowledge", or "educational_query".
        3. Identify the target class/standard as a string integer (e.g., "9", "11"). Default to "9" if missing.
        4. Set "is_higher_secondary" to true if the grade is 11 or 12, otherwise false.
        5. Identify the subject(s) mentioned. If it is a broad exam paper request with no subject specified, label it "All Core Disciplines" and set "is_generic_paper" to true.
        6. Sniff out if the user wants an answer key/solutions included. Set "with_answers" to true or false.
        7. Determine the board ("CBSE" or "Maharashtra State Board") based on text cues or medium.
        8. Set "max_marks" to 100 for paper sets, and 80 for other outputs.
        
        OUTPUT FORMAT: Return ONLY a raw JSON code block matching this schema. Do not write markdown or conversational introductions:
        {
            "output_variety": "string",
            "class_level": "string",
            "is_higher_secondary": boolean,
            "board": "string",
            "language": "string",
            "subject": "string",
            "is_generic_paper": boolean,
            "with_answers": boolean,
            "time_allowed": "3 Hours",
            "max_marks": integer
        }"""
    )
    
    chat_result = analyzer_proxy.initiate_chat(
        recipient=analyzer_agent,
        message=f"Analyze this user query: '{user_question}'",
        clear_history=True
    )
    
    raw_json_response = chat_result.chat_history[-1]['content']
    clean_json = re.sub(r"```json|```", "", raw_json_response).strip()
    
    try:
        return json.loads(clean_json)
    except Exception:
        return {
            "output_variety": "educational_query", "class_level": "9", "is_higher_secondary": False,
            "board": "CBSE", "language": "English", "subject": "General Studies",
            "is_generic_paper": False, "with_answers": False, "time_allowed": "3 Hours", "max_marks": 80
        }

# ──────────────────────────────────────────────────────────────────────────────
# MAIN AUTOGEN SYSTEM ORCHESTRATION PIPELINE (WITH 429 RETRY INTERCEPTOR)
# ──────────────────────────────────────────────────────────────────────────────
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
        format_blueprint = """
        LAYOUT FORMAT: TEXTBOOK-STYLE STUDY NOTES WITH MULTI-DISCIPLINARY DIAGRAM ANCHORS
        - Structure contents using clear headers: 'CHAPTER [X]: [CHAPTER TITLE]'.
        - Organize text logically using subheadings: '1. CORE THEORY ANALYSIS', '2. KEY TERMINOLOGY DEFINITIONS', and '3. CONCEPTUAL SCENARIO EXAMPLES'.
        
        CRITICAL TOKEN CONSTRAINT SECURITY RULE:
        To prevent API Rate Limit Errors, be concise and dense. Write elite textbook definitions without long conversational words.
        
        VISUAL DIAGRAM ADVANCEMENT RULE:
        Whenever you introduce a vital conceptual mechanism, insert a dedicated diagram placeholder anchor using this literal formatting token syntax on a standalone new line:

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

    # ──────────────────────────────────────────────────────────────────────────
    # SELF-HEALING RATE LIMIT (429) RETRY GUARDRAIL LOOP
    # ──────────────────────────────────────────────────────────────────────────
    max_retries = 3
    retry_delay = 16
    chat_history_log = None
    
    for attempt in range(max_retries):
        try:
            chat_history_log = user_proxy.initiate_chat(
                recipient=manager,
                message=f"User Query Target: {user_query}. Dynamic_Orchestrator, parse the intent requirements and issue the dynamic instruction card.",
                clear_history=True
            )
            break
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate_limit" in error_str:
                if attempt < max_retries - 1:
                    print(f"\n⚠️ [Groq TPM Rate Limit Hit]: Sleeping for {retry_delay} seconds to allow token window reset (Attempt {attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                    continue
            raise e

    if not chat_history_log:
        raise RuntimeError("Pipeline failed to generate log tree output due to critical timeout limits.")

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

# ──────────────────────────────────────────────────────────────────────────────
# RECONFIGURED INTERACTIVE EXECUTION FRAME
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 75)
    print("  🤖 PURE AUTOGEN MULTI-AGENT COMPILER ENVIRONMENT")
    print("  Fully Agentic Intent Routing | Instructions-Driven Core Pipeline")
    print("=" * 75 + "\n")

    while True:
        try:
            user_q = input("Ask your learning mentor (or type 'exit'): ").strip()
            if user_q.lower() in ["exit", "quit"]: break
            if not user_q: continue

            ctx = agentic_analyze_request(user_q)

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
            if ctx["output_variety"] == "paperset":
                print("here is the question paper")
            else:
                print(final_response_text)
            print("-" * 75)
            
            if should_pdf:
                final_notes_payload = final_response_text
                if "Official Board Reference" not in final_notes_payload and "Official Textbook" not in final_notes_payload:
                    final_notes_payload += f"\n\n### EXT_LINK_PORTAL_TRIGGER\n- Official Textbook Repository Portal: https://ebalbharati.in\n"
                
                output_filename = f"{ctx['subject'].lower().replace(', ', '_')}_{ctx['output_variety']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                
                compiled_pdf = compile_exam_paper_to_pdf(
                    main_text=final_notes_payload, 
                    ctx=ctx, 
                    filename=output_filename, 
                    output_dir=OUTPUT_DIR, 
                    include_answer_key=ctx["with_answers"]
                )
                print(f"Here is the PDF file for your output: {compiled_pdf}\n")
            else:
                print("⚡ Process complete. No PDF requested or generated.\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[Pipeline Critical Error]: {str(e)}\n")