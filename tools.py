import os
import re
import requests
import io
from bs4 import BeautifulSoup
from pypdf import PdfReader
from duckduckgo_search import DDGS

# ──────────────────────────────────────────────────────────────────────────────
# KEYLESS REPLACEMENT SEARCH TOOL (DUCKDUCKGO)
# ──────────────────────────────────────────────────────────────────────────────

def google_search_tool(query: str, num_results: int = 5) -> str:
    """
    Acts as a drop-in replacement for the old Google Search API.
    Uses DuckDuckGo Search under the hood. Requires ZERO API keys or credentials.
    """
    print(f"\n[Tool Execution] Searching via Free Web Infrastructure for: {query}...\n")
    try:
        summary = ""
        # Context-managed DuckDuckGo scraper connection matrix
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max(1, min(int(num_results), 10))))
            
            if not results:
                return "NO_RESULTS_FOUND: No queries matched across web indexes."
                
            for idx, result in enumerate(results, start=1):
                title = result.get("title", "Resource Asset")
                link = result.get("href", "")
                snippet = result.get("body", "")
                summary += f"\nSource {idx}:\nTitle: {title}\nLink: {link}\nSnippet: {snippet}\n"
                
        return summary.strip()
    except Exception as e:
        return f"SEARCH_ERROR_UNKNOWN: Web index query failure: {str(e)}"

def is_search_error(search_result: str) -> bool:
    if not search_result: return True
    return any(marker in search_result.lower() for marker in ["search_error", "no_results_found", "failed"])

def parse_search_sources(search_text: str):
    if not search_text or is_search_error(search_text): return []
    sources = []
    blocks = re.split(r"\nSource\s+\d+:\n", "\n" + search_text)
    for block in blocks:
        block = block.strip()
        if not block: continue
        t = re.search(r"Title:\s*(.*)", block)
        l = re.search(r"Link:\s*(.*)", block)
        s = re.search(r"Snippet:\s*(.*)", block, re.DOTALL)
        if l:
            sources.append({
                "title": t.group(1).strip() if t else "Resource Asset",
                "link": l.group(1).strip(),
                "snippet": s.group(1).strip() if s else ""
            })
    return sources

def infer_subject_from_query(query: str) -> str:
    q = query.lower()
    subject_map = {
        "biology": "Biology", "botany": "Biology", "zoology": "Biology",
        "math": "Mathematics", "maths": "Mathematics", "algebra": "Mathematics",
        "geometry": "Mathematics", "physics": "Physics", "chemistry": "Chemistry",
        "science": "Science", "history": "History", "geography": "Geography",
        "english": "English", "marathi": "Marathi"
    }
    for keyword, subject in subject_map.items():
        if keyword in q: return subject
    return "General Education"

def infer_class_from_query(query: str) -> str:
    q = query.lower()
    patterns = [r"class\s*(\d+)", r"(\d+)(st|nd|rd|th)\s*class", r"standard\s*(\d+)", r"std\s*(\d+)"]
    for pattern in patterns:
        match = re.search(pattern, q)
        if match: return f"Class {match.group(1)}"
    return "Class not specified"

def infer_board_from_query(query: str) -> str:
    q = query.lower()
    if "cbse" in q: return "CBSE"
    if "ncert" in q: return "NCERT"
    if "maharashtra" in q or "state board" in q or "ssc" in q or "hsc" in q: return "Maharashtra State Board"
    return "NCERT / State Board"

def build_learning_references(user_query: str, num_results: int = 4) -> str:
    subject = infer_subject_from_query(user_query)
    class_name = infer_class_from_query(user_query)
    board = infer_board_from_query(user_query)
    citation_hint = f"Ref: {board} {subject} {class_name}"

    search_query = f"{board} {class_name} {subject} syllabus textbook official index links"
    search_result = google_search_tool(search_query, num_results=num_results)
    sources = parse_search_sources(search_result)

    output = "\n\n---REFERENCE_METADATA_START---\n"
    output += f"Citation Hint: {citation_hint}\nBoard/Book: {board}\nClass: {class_name}\nSubject: {subject}\n"
    output += "Explore More:\n"
    if sources:
        for idx, ref in enumerate(sources[:num_results], start=1):
            output += f"{idx}. {ref['title']}\n   Link: {ref['link']}\n"
    else:
        output += f"1. {board} {subject} {class_name} official reference\n"
    output += "---REFERENCE_METADATA_END---\n"
    return output.strip()

def get_minimal_citation(user_query: str) -> str:
    return f"Ref: {infer_board_from_query(user_query)} Curriculum Framework Map"

OFFICIAL_DOMAINS = ["ncert.nic.in", "cbseacademic.nic.in", "ebalbharati.in", "mahahsscboard.in", "learncbse.in", "byjus.com", ".gov.in", ".nic.in"]

def read_url_text(url: str) -> str:
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()

        if "pdf" in content_type or url.lower().endswith(".pdf"):
            reader = PdfReader(io.BytesIO(response.content))
            text = ""
            for page_no, page in enumerate(reader.pages[:15], start=1):
                text += f"\n--- Page {page_no} ---\n" + (page.extract_text() or "")
            return text.strip()

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]): tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except Exception as e:
        return f"READ_ERROR: {str(e)}"

def official_web_reader_tool(board: str, class_level: str, subject: str, topic: str = "", language: str = "English") -> str:
    lang_keyword = "मराठी माध्यम अभ्यासक्रम पाठ्यक्रम" if language == "Marathi" else ""
    query = f"{board} Class {class_level} {subject} {topic} {lang_keyword} official syllabus textbook index"

    search_result = google_search_tool(query, num_results=5)
    if is_search_error(search_result):
        return "OFFICIAL_READER_ERROR: Could not query fallback web indices safely."

    sources = parse_search_sources(search_result)
    final_output = "OFFICIAL_WEB_READER_RESULT\n"
    read_count = 0

    for source in sources:
        link = source.get("link", "")
        if not link or not any(domain in link for domain in OFFICIAL_DOMAINS): 
            continue

        page_text = read_url_text(link)
        if not page_text or page_text.startswith("READ_ERROR"): 
            continue

        # FIXED INDENTATION BLOCK: Re-aligned loop properties to match loop lifecycle
        read_count += 1
        final_output += f"\n\nSOURCE {read_count}\nTitle: {source.get('title')}\nURL: {link}\nExtracted Content:\n{page_text[:1200]}\n"
        if read_count >= 2: 
            break

    return final_output if read_count > 0 else "OFFICIAL_READER_ERROR: Verified indices were found but timed out during extraction."