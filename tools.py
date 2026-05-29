import os
import re
import json
import requests
from typing_extensions import Annotated
from duckduckgo_search import DDGS
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

    Required .env values:
    GOOGLE_API_KEY=your_google_api_key
    GOOGLE_CSE_ID=your_google_custom_search_engine_id
    """

    google_api_key = os.getenv("GOOGLE_API_KEY")
    google_cse_id = os.getenv("GOOGLE_CSE_ID")

    if not google_api_key:
        return (
            "SEARCH_ERROR_CONFIG: GOOGLE_API_KEY is missing in .env file. "
            "Add GOOGLE_API_KEY before using Google Search."
        )

    if not google_cse_id:
        return (
            "SEARCH_ERROR_CONFIG: GOOGLE_CSE_ID is missing in .env file. "
            "Add GOOGLE_CSE_ID before using Google Search."
        )

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
            return (
                "SEARCH_ERROR_400_GOOGLE_BAD_REQUEST: Google rejected the request. "
                "Possible reasons: invalid GOOGLE_CSE_ID, invalid query format, or wrong API parameters."
            )

        if response.status_code == 401:
            return (
                "SEARCH_ERROR_401_GOOGLE_UNAUTHORIZED: Google API key is invalid or unauthorized. "
                "Check GOOGLE_API_KEY in .env file."
            )

        if response.status_code == 403:
            return (
                "SEARCH_ERROR_403_GOOGLE_API_FORBIDDEN: Google Custom Search API rejected the request. "
                "Check: Custom Search API enabled, billing enabled, valid API key, correct GOOGLE_CSE_ID, "
                "and API key restrictions allow Custom Search JSON API."
            )

        if response.status_code == 429:
            return (
                "SEARCH_ERROR_429_GOOGLE_QUOTA_EXCEEDED: Google Search quota/rate limit exceeded. "
                "Check Google Cloud quota and billing."
            )

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

            summary += (
                f"\nSource {idx}:\n"
                f"Title: {title}\n"
                f"Link: {link}\n"
                f"Snippet: {snippet}\n"
            )

        return summary.strip()

    except requests.exceptions.Timeout:
        return "SEARCH_ERROR_TIMEOUT: Google Search request timed out."

    except requests.exceptions.HTTPError as e:
        return f"SEARCH_ERROR_HTTP: Google Search HTTP error: {str(e)}"

    except requests.exceptions.RequestException as e:
        return f"SEARCH_ERROR_REQUEST: Google Search network/request error: {str(e)}"

    except Exception as e:
        return f"SEARCH_ERROR_UNKNOWN: Google Search unexpected error: {str(e)}"


# ─────────────────────────────────────────
# SEARCH ERROR CHECK
# ─────────────────────────────────────────

def is_search_error(search_result: str) -> bool:
    if not search_result:
        return True

    error_markers = [
        "SEARCH_ERROR",
        "NO_RESULTS_FOUND",
        "Google Search is not configured",
        "Google Search failed",
        "Google Search HTTP error",
        "403",
        "Forbidden",
    ]

    return any(marker.lower() in search_result.lower() for marker in error_markers)


# ─────────────────────────────────────────
# SEARCH RESULT PARSING
# ─────────────────────────────────────────

def parse_search_sources(search_text: str):
    """
    Converts plain search output into structured source list.
    """
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

        sources.append(
            {
                "title": title,
                "link": link,
                "snippet": snippet,
            }
        )

    return sources


def infer_subject_from_query(query: str) -> str:
    q = query.lower()

    subject_map = {
        "biology": "Biology",
        "botany": "Biology",
        "zoology": "Biology",
        "math": "Mathematics",
        "maths": "Mathematics",
        "algebra": "Mathematics",
        "geometry": "Mathematics",
        "physics": "Physics",
        "chemistry": "Chemistry",
        "science": "Science",
        "history": "History",
        "geography": "Geography",
        "english": "English",
        "python": "Computer Science",
        "coding": "Computer Science",
        "computer": "Computer Science",
    }

    for keyword, subject in subject_map.items():
        if keyword in q:
            return subject

    return "General Education"


def infer_class_from_query(query: str) -> str:
    q = query.lower()

    patterns = [
        r"class\s*(\d+)",
        r"(\d+)(st|nd|rd|th)\s*class",
        r"standard\s*(\d+)",
        r"std\s*(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            return f"Class {match.group(1)}"

    if "ssc" in q:
        return "SSC"
    if "hsc" in q:
        return "HSC"

    return "Class not specified"


def infer_board_from_query(query: str) -> str:
    q = query.lower()

    if "cbse" in q:
        return "CBSE"
    if "ncert" in q:
        return "NCERT"
    if "maharashtra" in q or "state board" in q or "ssc" in q or "hsc" in q:
        return "Maharashtra State Board"

    return "NCERT / State Board"


def infer_reference_hint(query: str) -> str:
    """
    Creates a short, safe citation hint.
    Page numbers are intentionally shown as 'verify from textbook'
    unless an official source explicitly gives pages.
    """
    subject = infer_subject_from_query(query)
    class_name = infer_class_from_query(query)
    board = infer_board_from_query(query)

    return f"Ref: {board} {subject} {class_name}, chapter/page as per official textbook"


# ─────────────────────────────────────────
# EXPLORE MORE / CITATION BUILDER
# ─────────────────────────────────────────

def build_learning_references(
    user_query: Annotated[str, "User's education-related query"],
    num_results: Annotated[int, "Number of references/resources to return"] = 4,
) -> str:
    """
    Builds a compact 'Explore More' section with:
    - textbook/board reference hint
    - likely chapters/resources
    - official links from Google results where available

    This is meant to be appended by teacher agents or PDF compiler.
    """

    subject = infer_subject_from_query(user_query)
    class_name = infer_class_from_query(user_query)
    board = infer_board_from_query(user_query)
    citation_hint = infer_reference_hint(user_query)

    search_query = (
        f"{board} {class_name} {subject} syllabus textbook chapter "
        f"{user_query} official"
    )

    search_result = google_search_tool(search_query, num_results=num_results)

    references = []
    sources = parse_search_sources(search_result)

    for source in sources[:num_results]:
        title = source.get("title", "")
        link = source.get("link", "")
        snippet = source.get("snippet", "")

        if title and link:
            references.append(
                {
                    "title": title,
                    "link": link,
                    "snippet": snippet,
                }
            )

    output = ""
    output += "\n\n---REFERENCE_METADATA_START---\n"
    output += f"Citation Hint: {citation_hint}\n"
    output += f"Board/Book: {board}\n"
    output += f"Class: {class_name}\n"
    output += f"Subject: {subject}\n"
    output += "Chapter/Page: Use the matching official textbook chapter; page number may vary by edition.\n"

    if references:
        output += "Explore More:\n"
        for idx, ref in enumerate(references, start=1):
            output += f"{idx}. {ref['title']}\n"
            output += f"   Link: {ref['link']}\n"
    else:
        output += "Explore More:\n"
        output += f"1. {board} {subject} {class_name} official textbook\n"
        output += f"2. {board} {subject} {class_name} syllabus\n"
        output += "3. NCERT / State Board textbook exercises\n"

    output += "---REFERENCE_METADATA_END---\n"

    return output.strip()


def get_minimal_citation(
    user_query: Annotated[str, "User's education-related query"],
) -> str:
    """
    Returns one-line minimal citation suitable for PDF footer/corner.
    """
    return infer_reference_hint(user_query)


# ─────────────────────────────────────────
# OFFICIAL EXAM INFO SEARCH TOOL
# ─────────────────────────────────────────

def search_exam_info_tool(
    exam_query: Annotated[str, "Exam-related query, e.g., NEET 2026 exam date, JEE timetable, SSC board result"],
) -> str:
    """
    Searches latest exam information from official or trusted education sources.
    """

    official_query = (
        f"{exam_query} official notification latest exam date schedule "
        f"site:.gov.in OR site:.nic.in OR site:nta.ac.in OR site:cbse.gov.in OR site:mahahsscboard.in"
    )

    result = google_search_tool(official_query, num_results=5)

    if is_search_error(result):
        return (
            f"{result}\n\n"
            "Official exam information could not be verified because search failed or returned no results. "
            "Do not guess exam dates. Ask user to check the official exam authority website manually."
        )

    return result


# ─────────────────────────────────────────
# SYLLABUS SEARCH TOOL
# ─────────────────────────────────────────

def search_syllabus_tool(
    class_standard: Annotated[str, "The class or standard of the student, e.g., '12th class', 'class 9'"],
    topic: Annotated[str, "The math/science topic being researched, e.g., 'integration', 'linear equations'"]
) -> str:
    """
    Searches dynamically for Maharashtra State Board syllabus matching
    the student's exact class and learning topic.
    """

    query = (
        f"Maharashtra State Board syllabus standard {class_standard} "
        f"{topic} chapters topics official curriculum"
    )

    print(f"\n[Tool Execution] Searching syllabus for: {query}...\n")

    google_result = google_search_tool(query, num_results=3)

    if not is_search_error(google_result):
        return google_result

    print("\n[Tool Execution] Google search unavailable. Trying DuckDuckGo fallback...\n")

    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=3)]

            if results:
                summary = (
                    "Google search was unavailable or failed. "
                    "DuckDuckGo fallback results are provided below:\n"
                )

                for idx, r in enumerate(results, start=1):
                    title = r.get("title", "No title")
                    link = r.get("href", "No link")
                    body = r.get("body", "No snippet")

                    summary += (
                        f"\nSource {idx}:\n"
                        f"Title: {title}\n"
                        f"Link: {link}\n"
                        f"Snippet: {body}\n"
                    )

                return summary.strip()

        return (
            "NO_RESULTS_FOUND: No specific syllabus details found from Google or DuckDuckGo. "
            "Proceed with general textbook scope only, and clearly mention that official syllabus could not be verified."
        )

    except Exception as e:
        return (
            f"SEARCH_ERROR_DUCKDUCKGO: Syllabus search failed due to an error: {str(e)}. "
            "Proceed with general textbook scope only, and clearly mention that official syllabus could not be verified."
        )


# ─────────────────────────────────────────
# STRUCTURED REFERENCE JSON HELPER
# ─────────────────────────────────────────

def build_reference_json(user_query: str) -> str:
    """
    Optional helper if you want structured references later.
    Returns JSON string so AutoGen tools can pass it safely.
    """
    metadata = {
        "citation_hint": infer_reference_hint(user_query),
        "board": infer_board_from_query(user_query),
        "class": infer_class_from_query(user_query),
        "subject": infer_subject_from_query(user_query),
        "chapter_page_note": "Chapter/page should be verified from the exact textbook edition.",
    }

    return json.dumps(metadata, indent=2)