import os
import re
import json
import requests
import io
from typing_extensions import Annotated
from bs4 import BeautifulSoup
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# GOOGLE SEARCH TOOL
# ─────────────────────────────────────────

def google_search_tool(
    query: Annotated[str, "Search query for latest exam, syllabus, or education-related information"],
    num_results: Annotated[int, "Number of search results to return"] = 5,
) -> str:
    """
    Searches Google using Google Custom Search JSON API.
    """
    google_api_key = os.getenv("GOOGLE_API_KEY")
    google_cse_id = os.getenv("GOOGLE_CSE_ID")

    if not google_api_key:
        return "SEARCH_ERROR_CONFIG: GOOGLE_API_KEY is missing in .env file."

    if not google_cse_id:
        return "SEARCH_ERROR_CONFIG: GOOGLE_CSE_ID is missing in .env file."

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": google_api_key,
        "cx": google_cse_id,
        "q": query,
        "num": max(1, min(int(num_results), 10)),
    }

    print(f"\n[Tool Execution] Google searching for: {query}...\n")

    try:
        response = requests.get(url, params=params, timeout=20)
        if response.status_code == 400:
            return "SEARCH_ERROR_400_GOOGLE_BAD_REQUEST: Google rejected the request."
        if response.status_code == 401:
            return "SEARCH_ERROR_401_GOOGLE_UNAUTHORIZED: Google API key is invalid."
        if response.status_code == 403:
            return "SEARCH_ERROR_403_GOOGLE_API_FORBIDDEN: Custom Search API rejected the request."
        if response.status_code == 429:
            return "SEARCH_ERROR_429_GOOGLE_QUOTA_EXCEEDED: Quota exceeded."

        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])

        if not items:
            return "NO_RESULTS_FOUND: Google returned no results for this query."

        summary = ""
        for idx, item in enumerate(items, start=1):
            title = item.get("title", "No title")
            link = item.get("link", "No link")
            snippet = item.get("snippet", "No snippet")
            summary += f"\nSource {idx}:\nTitle: {title}\nLink: {link}\nSnippet: {snippet}\n"

        return summary.strip()
    except Exception as e:
        return f"SEARCH_ERROR_UNKNOWN: {str(e)}"

def is_search_error(search_result: str) -> bool:
    if not search_result:
        return True
    error_markers = ["SEARCH_ERROR", "NO_RESULTS_FOUND", "failed", "403", "Forbidden"]
    return any(marker.lower() in search_result.lower() for marker in error_markers)

def parse_search_sources(search_text: str):
    if not search_text or is_search_error(search_text):
        return []
    sources = []
    blocks = re.split(r"\nSource\s+\d+:\n", "\n" + search_text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        title_match = re.search(r"Title:\s*(.*)", block)
        link_match = re.search(r"Link:\s*(.*)", block)
        snippet_match = re.search(r"Snippet:\s*(.*)", block, re.DOTALL)

        title = title_match.group(1).strip() if title_match else "Unknown source"
        link = link_match.group(1).strip() if link_match else ""
        snippet = snippet_match.group(1).strip() if snippet_match else ""
        sources.append({"title": title, "link": link, "snippet": snippet})
    return sources

def infer_subject_from_query(query: str) -> str:
    q = query.lower()
    subject_map = {
        "biology": "Biology", "botany": "Biology", "zoology": "Biology",
        "math": "Mathematics", "maths": "Mathematics", "algebra": "Mathematics",
        "geometry": "Mathematics", "physics": "Physics", "chemistry": "Chemistry",
        "science": "Science", "history": "History", "geography": "Geography",
        "english": "English", "python": "Computer Science", "coding": "Computer Science"
    }
    for keyword, subject in subject_map.items():
        if keyword in q:
            return subject
    return "General Education"

def infer_class_from_query(query: str) -> str:
    q = query.lower()
    patterns = [r"class\s*(\d+)", r"(\d+)(st|nd|rd|th)\s*class", r"standard\s*(\d+)", r"std\s*(\d+)"]
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            return f"Class {match.group(1)}"
    if "ssc" in q: return "SSC"
    if "hsc" in q: return "HSC"
    return "Class not specified"

def infer_board_from_query(query: str) -> str:
    q = query.lower()
    if "cbse" in q: return "CBSE"
    if "ncert" in q: return "NCERT"
    if "maharashtra" in q or "state board" in q or "ssc" in q or "hsc" in q:
        return "Maharashtra State Board"
    return "NCERT / State Board"

def infer_reference_hint(query: str) -> str:
    subject = infer_subject_from_query(query)
    class_name = infer_class_from_query(query)
    board = infer_board_from_query(query)
    return f"Ref: {board} {subject} {class_name}, chapter/page as per official textbook"

def build_learning_references(user_query: str, num_results: int = 4) -> str:
    subject = infer_subject_from_query(user_query)
    class_name = infer_class_from_query(user_query)
    board = infer_board_from_query(user_query)
    citation_hint = infer_reference_hint(user_query)

    search_query = f"{board} {class_name} {subject} syllabus textbook {user_query} official"
    search_result = google_search_tool(search_query, num_results=num_results)
    sources = parse_search_sources(search_result)

    output = "\n\n---REFERENCE_METADATA_START---\n"
    output += f"Citation Hint: {citation_hint}\nBoard/Book: {board}\nClass: {class_name}\nSubject: {subject}\n"
    output += "Explore More:\n"
    if sources:
        for idx, ref in enumerate(sources[:num_results], start=1):
            output += f"{idx}. {ref['title']}\n   Link: {ref['link']}\n"
    else:
        output += f"1. {board} {subject} {class_name} official textbook\n"
    output += "---REFERENCE_METADATA_END---\n"
    return output.strip()

def get_minimal_citation(user_query: str) -> str:
    return infer_reference_hint(user_query)

OFFICIAL_DOMAINS = ["ncert.nic.in", "cbseacademic.nic.in", "ebalbharati.in", "mahahsscboard.in", "maa.ac.in", ".gov.in", ".nic.in"]

def is_official_url(url: str) -> bool:
    return any(domain in url for domain in OFFICIAL_DOMAINS)

def read_url_text(url: str) -> str:
    try:
        response = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()

        if "pdf" in content_type or url.lower().endswith(".pdf"):
            pdf_file = io.BytesIO(response.content)
            reader = PdfReader(pdf_file)
            text = ""
            for page_no, page in enumerate(reader.pages[:20], start=1):
                text += f"\n--- Page {page_no} ---\n" + (page.extract_text() or "")
            return text.strip()

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except Exception as e:
        return f"READ_ERROR: {str(e)}"

def official_web_reader_tool(board: str, class_level: str, subject: str, topic: str = "", language: str = "English") -> str:
    """
    Searches official education sites, reads official pages/PDFs, and returns verified content.
    Optimized to inject language-medium anchors for multilingual curriculum parsing.
    """
    board = board or ""
    class_level = class_level or ""
    subject = subject or ""
    topic = topic or ""
    
    # Construct localized translation triggers for search indexing
    lang_keyword = ""
    if language == "Marathi":
        lang_keyword = "मराठी माध्यम इयत्ता अभ्यासक्रम पाठ्यक्रम"
    elif language == "Hindi":
        lang_keyword = "हिंदी माध्यम पाठ्यक्रम सिलेबस"

    if "CBSE" in board.upper() or "NCERT" in board.upper():
        query = f"{class_level} {subject} {topic} {lang_keyword} syllabus textbook official site:ncert.nic.in OR site:cbseacademic.nic.in"
    elif "MAHARASHTRA" in board.upper():
        query = f"Maharashtra State Board {class_level} {subject} {topic} {lang_keyword} syllabus textbook official site:ebalbharati.in OR site:mahahsscboard.in OR site:maa.ac.in"
    else:
        query = f"{board} {class_level} {subject} {topic} {lang_keyword} syllabus textbook official site:ncert.nic.in OR site:cbseacademic.nic.in OR site:.gov.in OR site:.nic.in"

    search_result = google_search_tool(query, num_results=5)
    if is_search_error(search_result):
        return "OFFICIAL_READER_ERROR: Could not search official sources."

    sources = parse_search_sources(search_result)
    final_output = "OFFICIAL_WEB_READER_RESULT\n"
    read_count = 0

    for source in sources:
        link = source.get("link", "")
        if not link or not is_official_url(link):
            continue

        page_text = read_url_text(link)
        if not page_text or page_text.startswith("READ_ERROR"):
            continue

        read_count += 1
        final_output += f"\n\nSOURCE {read_count}\nTitle: {source.get('title')}\nURL: {link}\nExtracted Content:\n{page_text[:6000]}\n"
        if read_count >= 3:
            break

    if read_count == 0:
        return "OFFICIAL_READER_ERROR: Official sources found but could not be read."

    return final_output