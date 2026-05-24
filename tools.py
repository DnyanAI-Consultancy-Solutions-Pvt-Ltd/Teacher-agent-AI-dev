import os
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

    Important:
    - This function returns SEARCH_ERROR_* text for failures.
    - teacher.py should check SEARCH_ERROR before sending results to any agent.
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

        # Handle common Google API errors clearly before raise_for_status()
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
                "Check these points: Custom Search API enabled, billing enabled, valid API key, correct GOOGLE_CSE_ID, "
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
# HELPER: CHECK WHETHER SEARCH FAILED
# ─────────────────────────────────────────

def is_search_error(search_result: str) -> bool:
    """
    Returns True when a search tool result is not usable as valid search data.
    Use this before passing search results to an agent.
    """

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
# OFFICIAL EXAM INFO SEARCH TOOL
# ─────────────────────────────────────────

def search_exam_info_tool(
    exam_query: Annotated[str, "Exam-related query, e.g., NEET 2026 exam date, JEE timetable, SSC board result"],
) -> str:
    """
    Searches latest exam information from official or trusted education sources.
    Use this for:
    - exam dates
    - timetables
    - admit cards
    - results
    - registration dates
    - counselling schedules
    - official notifications
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

    First tries Google Custom Search.
    If Google is not configured or fails, falls back to DuckDuckGo.
    """

    query = (
        f"Maharashtra State Board syllabus standard {class_standard} "
        f"{topic} chapters topics official curriculum"
    )

    print(f"\n[Tool Execution] Searching syllabus for: {query}...\n")

    # First preference: Google Search
    google_result = google_search_tool(query, num_results=3)

    if not is_search_error(google_result):
        return google_result

    # Fallback: DuckDuckGo
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
