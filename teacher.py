import os
import re
import json
import certifi
import urllib.request
import urllib.parse
import autogen
from datetime import datetime

from pdf_compiler import compile_chat_history_to_pdf
from tools import search_syllabus_tool

# Ensure secure SSL certificate handling across all network fetch scopes
os.environ["SSL_CERT_FILE"] = certifi.where()
load_dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(load_dotenv_path):
    from dotenv import load_dotenv
    load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing in .env file")

config_list = [
    {
        "model": "llama-3.3-70b-versatile",
        "api_key": GROQ_API_KEY,
        "base_url": "https://api.groq.com/openai/v1",
        "api_type": "groq",
    }
]

llm_config = {
    "temperature": 0,
    "config_list": config_list,
    "timeout": 120,
    "cache_seed": None,
}

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =====================================================================
# STEP 1: DEFINE AGENTS & USER PROXY FIRST TO PREVENT SCOPING NameErrors
# =====================================================================
user_proxy = autogen.UserProxyAgent(
    name="Admin", 
    human_input_mode="NEVER", 
    max_consecutive_auto_reply=1, 
    code_execution_config={"use_docker": False}
)

concept_agent = autogen.AssistantAgent(
    name="concept_agent", 
    llm_config=llm_config, 
    system_message="""You are concept_agent. Explain academic topics clearly, concisely, and step-by-step.
    
    CRITICAL RESEARCH-STYLE CITATION DIRECTIONS:
    1. Do NOT put your citations or references at the very top or in a single isolated block at the very bottom of the entire document.
    2. Instead, use a clean inline parenthetical style:
       - Place precise, academic parenthetical citations directly inside the sentences/paragraphs right next to the specific concepts, definitions, or equations.
       - Format: (Chapter {Number}: {Chapter Name}, Page {Number}, {Book Name}, {Board Name})
       - Example: "According to the fundamental theorem of calculus, integration is the reverse process of differentiation (Chapter 3: Indefinite Integration, Page 104, Mathematics Part II, Maharashtra State Board)."
    3. Strictly do NOT append any separate 'Section References' or trailing reference footnotes at the bottom of your output."""
)

example_agent = autogen.AssistantAgent(
    name="example_agent", 
    llm_config=llm_config, 
    system_message="""You are example_agent. Provide step-by-step solved problems, experiments, or diagrams based on the concept introduced.
    
    CRITICAL RESEARCH-STYLE CITATION DIRECTIONS:
    1. Integrate inline parenthetical reference markers directly inside the text adjacent to relevant problem steps.
       - Format: (Chapter {Number}: {Chapter Name}, Exercise {Number}, Page {Number}, {Book Name}, {Board Name})
    2. Strictly do NOT append any separate lists of references or section summary blocks at the bottom."""
)

notes_agent = autogen.AssistantAgent(
    name="notes_agent", 
    llm_config=llm_config, 
    system_message="""You are notes_agent. Compile quick summary revision notes, bullet points, and core formulas.
    
    CRITICAL RESEARCH-STYLE CITATION DIRECTIONS:
    1. Place parenthetical references directly inline right next to core formulas or summary headers.
       - Format: (Chapter {Number}: {Chapter Name}, Page {Number}, {Book Name}, {Board Name})
       - Example: "Integration by Parts: ∫ u v dx = u ∫ v dx - ∫ [u' * ∫ v dx] dx (Chapter 3: Indefinite Integration, Page 120, Mathematics Part II, Maharashtra State Board)."
    2. Keep citations integrated and localized. Do not create any trailing reference tables or lists at the bottom."""
)

quiz_agent = autogen.AssistantAgent(
    name="quiz_agent", 
    llm_config=llm_config, 
    system_message="""You are quiz_agent. You are an expert examination board specialist. You do NOT generate simple, flat lists of basic questions. Instead, you design professional, highly structured, and authentic Model Question Papers modeled exactly after official board examination layouts.

    CRITICAL BOARD QUESTION PAPER FORMATTING DIRECTIONS:
    1. EXAMINATION HEADER (Must be centered beautifully using HTML tags):
       - Do NOT include any large, raw State Board Names (e.g. "MAHARASHTRA STATE BOARD...") at the very top of the question paper.
       - Directly start with the centered and bolded Exam Type and Session:
         <center><b>MOCK / MODEL QUESTION PAPER (2025-2026 Session)</b></center>
       - Follow immediately with the centered and bolded Grade Level & Subject:
         <center><b>CLASS [STANDARD] - [SUBJECT]</b></center>
    2. EXAM PARAMETERS ROW:
       - Place the Time Allowed and Maximum Marks in a clean, space-separated single-line layout directly underneath the header block:
         `Time Allowed: 2 Hours 30 Minutes`                                   `Maximum Marks: 60`
       - Add a solid horizontal rule (---) immediately underneath this parameters row to divide it from the instructions.
    3. GENERAL INSTRUCTIONS:
       - Provide a clean, numbered list of standard exam instructions (e.g., "1. All questions are compulsory.", "2. Figures to the right indicate full marks.", "3. Candidates are allowed 15 minutes of reading time before starting.").
    4. STRUCTURAL PARTS & SECTIONS:
       - PART A (Objective Type MCQs): "I. Answer all the questions. Each question carries ONE mark. [1 x 10 = 10 Marks]"
         - Group options cleanly on a single horizontal row or column:
           a) [Option A]       b) [Option B]       c) [Option C]       d) [Option D]
       - PART B (Short Answer Questions): "II. Answer any FIVE questions. Each question carries TWO marks. [2 x 5 = 10 Marks]"
       - PART C (Medium Answer Questions): "III. Answer any FIVE questions. Each question carries THREE marks. [3 x 5 = 15 Marks]"
       - PART D (Long Answer / Detailed Problems): "IV. Answer any SEVEN questions. Each question carries FIVE marks. [5 x 7 = 35 Marks]"
    5. STRICT NO-CITATION RULE FOR PAPERS:
       - Question papers must look authentic and realistic. Do NOT include any textbook page references or curriculum citations (neither parenthetical nor footnotes) inside the exam paper itself.
       - Place the question marks right-aligned on the same line as the question (e.g., `[5 Marks]`).
    6. BILINGUAL MULTI-MEDIUM RULE (For non-English language papers):
       - If generating papers for Marathi, Hindi, or non-Latin scripts, you must provide clean parallel English translations or transliterated subtitles next to the native text so standard PDF engines can compile without displaying '????' blocks."""
)

web_summary_agent = autogen.AssistantAgent(
    name="web_summary_agent", 
    llm_config=llm_config, 
    system_message="""You are web_summary_agent, an expert researcher. Synthesize raw web search records into a highly accurate, direct, textbook response.
    
    CRITICAL DIRECTIONS:
    1. Resolve exam and result scheduling queries by deeply analyzing titles, snippets, and deep content provided.
    2. You MUST strictly list your sources. Always append a formal 'Verified Sources & Citations' section at the end of your response. Use markdown formats like:
       - [Source Title](URL) - Key extracted details
       - If no direct URL is present in the context, cite the Source Node metadata clearly.
    3. Use your extensive, verified academic knowledge base to double-check and resolve specific state exam and competitive examination schedules (such as Maharashtra SSC/HSC exam dates, CBSE declarations, or NTA NEET announcements) when raw search data snippets are incomplete, always citing the official board or portal as the benchmark authority (e.g., 'mahresult.nic.in' or 'cbseresults.nic.in')."""
)

# =====================================================================
# STEP 2: DEEP-PAGE SCRAPER WITH STRUCTURAL LINK & SNIPPET CAPTURE (GENERIC)
# =====================================================================
def fetch_live_web_content(query: str) -> str:
    """
    Two-Stage Deep Scraper:
    Stage 1: Searches the web index and extracts target links using highly resilient splitting.
    Stage 2: Visits and scrapes the text content of the primary target site.
    Fallback: Uses robust metadata collection and search result details.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }

    try:
        print(f"\n[Stage 1] Querying search index for: '{query}'...")
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        req = urllib.request.Request(search_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            search_html = response.read().decode('utf-8', errors='ignore')

        # Split search result page dynamically by result wrapper tags for absolute resilience
        parts = search_html.split('<div class="result__body">')[1:]
        
        if not parts:
            return "No text snippets found in search index cache."

        target_url = None
        snippets_context = []
        metadata_pool = []

        for i, part in enumerate(parts[:8], 1):
            # Extract target absolute URL by scanning all href parameters in the block
            href_matches = re.findall(r'href=["\']([^"\']+)["\']', part)
            current_url = None
            
            for href in href_matches:
                # Bypass internal navigation and capture the target outbound redirect parameters
                if "duckduckgo.com" in href and "uddg=" in href:
                    parsed_href = urllib.parse.urlparse(href)
                    query_params = urllib.parse.parse_qs(parsed_href.query)
                    if "uddg" in query_params:
                        current_url = query_params["uddg"][0]
                        break
                elif not href.startswith("/") and "duckduckgo.com" not in href:
                    current_url = href
                    break
            
            if current_url and not target_url:
                # Prioritize educational resources or reputable news channels
                if any(domain in current_url for domain in ["gov.in", "nic.in", "ndtv", "timesofindia", "jagranjosh", "indianexpress"]):
                    target_url = current_url
                elif i == 1:
                    target_url = current_url

            # Extract Headline Title
            title_match = re.search(r'<a class="result__url"[^>]*>(.*?)</a>', part, re.DOTALL)
            title = re.sub(r'<[^>]*>', '', title_match.group(1)).strip() if title_match else "Archive Reference"
            
            # Extract Text Snippet
            snippet_match = re.search(r'<[^>]+class="[^"]*snippet[^"]*"[^>]*>(.*?)</[^>]+>', part, re.DOTALL)
            if not snippet_match:
                snippet_match = re.search(r'<a class="result__snippet"[^>]*>(.*?)</a>', part, re.DOTALL)
            
            snippet = re.sub(r'<[^>]*>', '', snippet_match.group(1)).strip() if snippet_match else ""
            
            # Sanitize typical encoding artifacts
            title = title.replace('&amp;', '&').replace('&quot;', '"').replace('&#x27;', "'")
            snippet = snippet.replace('&amp;', '&').replace('&quot;', '"').replace('&#x27;', "'")
            
            if snippet:
                snippets_context.append(snippet)
                metadata_pool.append(f"Result Node [{i}]: Title: {title} | Snippet: {snippet} | Link: {current_url or 'N/A'}")

        deep_text_pool = []
        # Stage 2: Click the primary target link and extract deep page content
        if target_url:
            print(f"[Stage 2] Deep-scraping target page text from: {target_url}...")
            try:
                page_req = urllib.request.Request(target_url, headers=headers)
                with urllib.request.urlopen(page_req, timeout=8) as page_response:
                    page_html = page_response.read().decode('utf-8', errors='ignore')
                
                # Clean structural page scripts & stylesheets
                page_text = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', page_html, flags=re.I)
                page_text = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', page_text, flags=re.I)
                paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', page_text, re.DOTALL)
                
                for p in paragraphs:
                    clean_p = re.sub(r'<[^>]*>', '', p).strip()
                    if len(clean_p) > 30 and any(keyword in clean_p.lower() for keyword in ["result", "declared", "exam", "syllabus", "date", "may", "june", "timetable", "chapters"]):
                        deep_text_pool.append(clean_p)
                
                if deep_text_pool:
                    print("[System] Deep-page text successfully harvested.")
                    return "--- SEARCH RESULTS SUMMARY ---\n" + "\n".join(snippets_context) + f"\n\n--- LIVE DEEP CONTENT FROM ({target_url}) ---\n" + "\n".join(deep_text_pool[:4])
            except Exception as page_err:
                print(f"[Warning] Couldn't read deep page content directly ({str(page_err)}). Falling back.")

        print("[System Routing] Merging structural result metadata parameters...")
        return "--- SEARCH RESULTS SUMMARY ---\n" + "\n".join(snippets_context) + "\n\n--- METADATA ENGINE FALLBACK CONTEXT ---\n" + "\n".join(metadata_pool)

    except Exception as e:
        return f"Web search processing failed: {str(e)}"

# =====================================================================
# STEP 3: PATH A SYLLABUS GATEWAY INTERCEPTOR
# =====================================================================
def fetch_live_board_syllabus(standard: str, subject: str, medium: str = "English") -> str:
    """
    Constructs a highly optimized state board index search lookup 
    and harvests curriculum blueprints before any study materials are built.
    """
    search_query = f"site:ebalbharati.in OR site:mahahsscboard.in Maharashtra State Board {standard} {subject} {medium} medium chapters syllabus index blueprint"
    return fetch_live_web_content(search_query)

# =====================================================================
# STEP 4: HYBRID METADATA EXTRACTOR (STANDARD, SUBJECT, MEDIUM)
# =====================================================================
def extract_educational_metadata(user_sentence: str) -> dict:
    """
    Extracts structural standard numbers via regex patterns first, 
    then uses an instantaneous LLM pass to clean and normalize subjects and mediums.
    """
    print(f"[Parser] Analyzing metadata variables...")
    metadata = {"standard": "10th", "subject": "Science", "medium": "English"}
    lowered_input = user_sentence.lower()
    
    std_match = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s*(?:std|standard|class|gr|grade)\b', lowered_input)
    if not std_match:
        std_match = re.search(r'\b(?:std|standard|class|grade|std\.)\s*(\d{1,2})\b', lowered_input)
    if std_match:
        metadata["standard"] = f"{int(std_match.group(1))}th"

    roman_map = {"ix": "9th", "x": "10th", "xi": "11th", "xii": "12th"}
    for roman, std_str in roman_map.items():
        if re.search(rf'\b{roman}\b', lowered_input):
            metadata["standard"] = std_str
            break

    parsing_prompt = f"""
    You are an automated code parsing script. Analyze this sentence and extract exactly 3 variables:
    1. Standard: Must be formatted exactly like [1th, 2th... 10th, 11th, 12th]. 
    2. Subject: Map the subject name (e.g., Geometry -> 'Mathematics', Biology/Photosynthesis/Chemistry -> 'Science', Civics -> 'Social Sciences').
    3. Medium: 'English', 'Marathi', or 'Hindi'. (Default to 'English').

    User Sentence: "{user_sentence}"
    Regex Guess: {json.dumps(metadata)}

    Output your response STRICTLY as a valid JSON object. No markdown backticks, no text preamble outside the JSON string boundaries.
    """
    try:
        parser_agent = autogen.AssistantAgent(name="parser_agent", llm_config=llm_config, system_message="Output pure raw JSON strings only.")
        user_proxy.clear_history()
        parser_agent.clear_history()
        user_proxy.initiate_chat(recipient=parser_agent, message=parsing_prompt, max_turns=1)
        
        # Cross-version safe history fetch logic to bypass NoneType ChatResult bugs
        chat_history = user_proxy.chat_messages.get(parser_agent, [])
        raw_json = str(chat_history[-1].get("content", "")).strip() if chat_history else ""
        
        if "```json" in raw_json: 
            raw_json = raw_json.split("```json")[-1].split("```")[0].strip()
        elif "```" in raw_json: 
            raw_json = raw_json.split("```")[1].strip()

        llm_metadata = json.loads(raw_json)
        if all(k in llm_metadata for k in ["standard", "subject", "medium"]):
            metadata.update(llm_metadata)
    except Exception:
        pass
    
    print(f"[Parser] Extracted Context Parameters -> CLASS: {metadata['standard']} | SUBJECT: {metadata['subject']} | MEDIUM: {metadata['medium']}")
    return metadata

# =====================================================================
# STEP 5: INTENT CLASSIFIER RETAINED FROM DYNAMIC MODELLING
# =====================================================================
def classify_query_with_llm(question: str) -> str:
    """ Uses the LLM to understand semantic intent without brittle keyword strings. """
    print(f"[System] Determining routing lane via LLM evaluation...")
    routing_prompt = f"""
    Classify the incoming student question into exactly ONE of these categories:
    - 'blocked': Irrelevant to school, educational tracks, or learning (e.g. pop music, recipes, jokes, stocks). Note that core scientific topics like 'photosynthesis', 'cellular respiration', 'gravity', 'algebra', 'chemistry', etc. are strictly educational and must NEVER be blocked.
    - 'exam_info': Questions about dates, results, timetables, or announcements for ANY exam or board.
    - 'quiz': Explicitly asking to generate a test, multiple-choice questions, or worksheets.
    - 'study': Wanting a topic explained, taught, summarized, or demonstrated with notes (e.g., "create notes on photosynthesis").
    
    Question: "{question}"
    Respond with exactly ONE word: blocked, exam_info, quiz, or study. No punctuation, no intro text.
    """
    try:
        router_agent = autogen.AssistantAgent(name="router_agent", llm_config=llm_config, system_message="Output a single word category only.")
        user_proxy.clear_history()
        router_agent.clear_history()
        user_proxy.initiate_chat(recipient=router_agent, message=routing_prompt, max_turns=1)
        
        # Safe history fetch
        chat_history = user_proxy.chat_messages.get(router_agent, [])
        raw_content = str(chat_history[-1].get("content", "")).lower().strip() if chat_history else "study"
        intent = re.sub(r"[^a-z_]", "", raw_content)
        return intent if intent in ["blocked", "exam_info", "quiz", "study"] else "study"
    except Exception:
        return "study"


def normalize_chat_logs(messages, agent_name="assistant", user_question=""):
    """
    Standardizes chat lists into readable blocks for the PDF.
    Strips raw code dictionary outputs and duplicates.
    """
    normalized = []
    seen_contents = set()
    for msg in messages:
        content = str(msg.get("content", "")).strip()
        name = msg.get("name") or msg.get("role") or agent_name
        if not content or isinstance(msg.get("content"), dict) or content == user_question.strip() or "--- SEARCH RESULTS SUMMARY ---" in content or "--- METADATA ENGINE FALLBACK CONTEXT ---" in content or content in seen_contents:
            continue
        
        # Beautifully normalize Agent Senders for PDF Layout
        display_name = str(name).replace("_agent", "").capitalize()
        if "Quiz" in display_name:
            display_name = "Model Question Paper"
        elif "Concept" in display_name:
            display_name = "Conceptual Explanation"
        elif "Example" in display_name:
            display_name = "Solved Examples"
        elif "Notes" in display_name:
            display_name = "Revision Notes"
        elif "Web" in display_name or "Summary" in display_name:
            display_name = "Verified Search Summary"

        normalized.append({"name": display_name, "role": "assistant", "content": content})
        seen_contents.add(content)
    return normalized

# =====================================================================
# STEP 6: ISOLATED WORKFLOW EXECUTION LAYOUTS
# =====================================================================
def execute_deterministic_study_flow(question: str):
    """ Executes a clean sequential multi-agent chain (Path A Blueprint). """
    pipeline_history = []
    
    print("[Pipeline] Dispatching tasks to Concept Agent...")
    user_proxy.clear_history()
    concept_agent.clear_history()
    user_proxy.initiate_chat(recipient=concept_agent, message=question, max_turns=1)
    
    concept_messages = user_proxy.chat_messages.get(concept_agent, [])
    concept_output = concept_messages[-1].get("content", "") if concept_messages else ""
    pipeline_history.extend(normalize_chat_logs(concept_messages, "concept_agent", question))

    print("[Pipeline] Dispatching tasks to Example Agent...")
    ex_prompt = f"Based on this topic foundation:\n\n{concept_output}\n\nPlease generate a practical solved sample problem, scientific demonstration, or real-life scenario."
    user_proxy.clear_history()
    example_agent.clear_history()
    user_proxy.initiate_chat(recipient=example_agent, message=ex_prompt, max_turns=1)
    
    example_messages = user_proxy.chat_messages.get(example_agent, [])
    example_output = example_messages[-1].get("content", "") if example_messages else ""
    pipeline_history.extend(normalize_chat_logs(example_messages, "example_agent", ex_prompt))

    print("[Pipeline] Dispatching tasks to Notes Agent...")
    nt_prompt = f"Based on this demonstration output:\n\n{example_output}\n\nPlease extract concise revision notes and key learning points."
    user_proxy.clear_history()
    notes_agent.clear_history()
    user_proxy.initiate_chat(recipient=notes_agent, message=nt_prompt, max_turns=1)
    
    notes_messages = user_proxy.chat_messages.get(notes_agent, [])
    pipeline_history.extend(normalize_chat_logs(notes_messages, "notes_agent", nt_prompt))

    return pipeline_history

def run_web_search_flow(question: str):
    web_intelligence = fetch_live_web_content(question)
    enriched_prompt = f"Question: {question}\n\nWeb Data Context:\n{web_intelligence}\n\nSummarize the exact final answer below safely with strict clickable citations:"
    user_proxy.clear_history()
    web_summary_agent.clear_history()
    user_proxy.initiate_chat(recipient=web_summary_agent, message=enriched_prompt, max_turns=1)
    
    web_messages = user_proxy.chat_messages.get(web_summary_agent, [])
    return normalize_chat_logs(web_messages, "web_summary_agent", enriched_prompt)

def run_quiz_flow(question: str):
    user_proxy.clear_history()
    quiz_agent.clear_history()
    user_proxy.initiate_chat(recipient=quiz_agent, message=question, max_turns=1)
    
    quiz_messages = user_proxy.chat_messages.get(quiz_agent, [])
    return normalize_chat_logs(quiz_messages, "quiz_agent", question)

# =====================================================================
# STEP 7: MAIN PROCESS ROUTER & LOOP RUNTIME
# =====================================================================
def process_question(user_question: str):
    user_question = user_question.strip()
    if not user_question:
        return {"answer": "Empty query description received.", "pdf": None}

    # FIX: Maintain the original raw user query to generate a clean custom slug/filename
    original_query = user_question

    query_type = classify_query_with_llm(user_question)

    if query_type == "blocked":
        return {"answer": "I can only process educational queries regarding concepts, notes, syllabus updates, and exam records.", "pdf": None}

    # Extract metadata metrics dynamically (Standard, Subject, Medium)
    meta = extract_educational_metadata(user_sentence=user_question)

    # Intercept with Path A Core Curriculum Safeguards
    # (Fetches the syllabus before generating any tests, quizzes, or explanations)
    if query_type in ["study", "quiz"]:
        raw_syllabus = fetch_live_board_syllabus(meta["standard"], meta["subject"], meta["medium"])
        
        # Intercept and clean empty scraper logs so we do not pass raw error strings to the LLM
        if not raw_syllabus or "no text snippets" in raw_syllabus.lower() or "failed" in raw_syllabus.lower():
            syllabus_context = f"Standard core study syllabus outline guidelines for Maharashtra State Board {meta['standard']} {meta['subject']} ({meta['medium']} Medium)."
            ref_status = "Default Guidelines (Active)"
        else:
            syllabus_context = raw_syllabus
            ref_status = "Live Portal Sync (Verified)"
        
        # =============================================================
        # ELEGANT TERMINAL VERIFICATION DASHBOARD (unicode boxed logs)
        # =============================================================
        print("\n┌" + "─"*78 + "┐")
        print(f"│ {'VERIFICATION ENGINE SYSTEM STATUS'.center(76)} │")
        print("├" + "─"*78 + "┤")
        print(f"│  [✓] Classified Intent : {query_type.upper().ljust(50)} │")
        print(f"│  [✓] Standard Class    : {meta['standard'].ljust(50)} │")
        print(f"│  [✓] Subject Domain    : {meta['subject'].ljust(50)} │")
        print(f"│  [✓] Target Medium     : {meta['medium'].ljust(50)} │")
        print("├" + "─"*78 + "┤")
        print(f"│  [⇄] Board Syllabus Target Query:".ljust(79) + "│")
        print(f"│      \"Maharashtra State Board {meta['standard']} {meta['subject']} chapters syllabus\"".ljust(79) + "│")
        print("├" + "─"*78 + "┤")
        print(f"│  [i] Reference Status  : {ref_status.ljust(50)} │")
        preview = (syllabus_context[:65] + "...").replace("\n", " ").strip()
        print(f"│  [i] Context Snippet   : {preview.ljust(50)} │")
        print("└" + "─"*78 + "┘\n")

        # Create structural XML-like markdown wrapper instead of messy bracket blocks
        user_question = f"""
<curriculum_directive>
  <source_board>Maharashtra State Board of Secondary and Higher Secondary Education (MSBSHSE)</source_board>
  <grade_level>{meta['standard']}</grade_level>
  <subject_domain>{meta['subject']}</subject_domain>
  <instructional_medium>{meta['medium']}</instructional_medium>
  <verified_chapters_context>
    {syllabus_context}
  </verified_chapters_context>
</curriculum_directive>

<student_request>
  {user_question}
</student_request>

<alignment_constraints>
  1. Your educational explanation must align strictly with the official Maharashtra State Board standards for {meta['standard']} {meta['subject']}.
  2. Accept standard academic sub-concepts (like 'integration' under 'Mathematics', or 'photosynthesis' under 'Life Processes') as fully valid even if the syllabus context above only lists parent chapters. Do not block valid science, math, or humanities sub-topics.
</alignment_constraints>
"""

    # Direct routing across execution channels
    if query_type == "quiz":
        chat_logs = run_quiz_flow(user_question)
    elif query_type == "exam_info":
        chat_logs = run_web_search_flow(user_question)
    else:
        chat_logs = execute_deterministic_study_flow(user_question)

    if not chat_logs:
        chat_logs = [{"name": "Teacher", "role": "assistant", "content": "Process loop finished execution cleanly."}]

    # Format file naming outputs securely (Using original_query instead of modified wrapped question)
    name_slug = "_".join(original_query.split()[:4]).lower()
    name_slug = re.sub(r"[^a-zA-Z0-9_]", "", name_slug) or "study_material"
    output_filename = f"{name_slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    # DYNAMIC DOCUMENT TITLE GENERATOR: Resolves the "AI Educational Framework Report" issue by creating an elegant title based on standard and subject
    clean_subj = meta.get("subject", "Academic study")
    clean_std = meta.get("standard", "")
    if query_type == "quiz":
        dynamic_title = f"Model Question Paper - Class {clean_std} {clean_subj}"
    elif query_type == "exam_info":
        dynamic_title = f"Academic Schedule Report - Class {clean_std} {clean_subj}"
    else:
        dynamic_title = f"Curriculum Study Notes - Class {clean_std} {clean_subj}"

    # Pass the beautifully polished dynamic title to avoid dry query strings or messy generic headers at the top
    compiled_pdf = compile_chat_history_to_pdf(
        chat_history=chat_logs,
        user_query=dynamic_title,
        llm_config=llm_config,
        output_dir=OUTPUT_DIR,
        output_filename=output_filename,
    )

    # Compiles the actual markdown conversation logs from the agents so that your Web UI can display them directly!
    compiled_text_answer = ""
    for log in chat_logs:
        sender = log.get("name", "Teacher")
        content = log.get("content", "")
        compiled_text_answer += f"### {sender}\n{content}\n\n"
        
    if not compiled_text_answer.strip():
        compiled_text_answer = "The process completed, but no visible textual responses were captured."

    return {"answer": compiled_text_answer, "pdf": compiled_pdf}

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("AI Teacher Agent: Combined Two-Stage Scraper & Path A Curriculum Check")
    print("=" * 70 + "\n")

    while True:
        user_q = input("What would you like to ask? ").strip()
        if user_q.lower() in ["exit", "quit"]:
            break

        result = process_question(user_q)
        print(f"\nStatus: {result['answer']}")
        if result.get("pdf"):
            print(f"File Output Path: {result['pdf']}\n")