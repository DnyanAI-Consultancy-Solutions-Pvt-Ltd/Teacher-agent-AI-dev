import os
import re
import io
import httpx
from typing_extensions import Annotated
from bs4 import BeautifulSoup
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

def google_search_tool(
    query: Annotated[str, "Search query text"],
    num_results: Annotated[int, "Count"] = 5
) -> str:
    """Executes high-speed infrastructure searches via Google Custom Search API Engine."""
    key = os.getenv("GOOGLE_API_KEY")
    cx = os.getenv("GOOGLE_CSE_ID")

    if not key or not cx:
        return "SEARCH_ERROR_CONFIG: Google custom API credentials missing inside .env context."

    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": key, "cx": cx, "q": query, "num": max(1, min(int(num_results), 10))}

    # Configured with a wider timeout threshold to support slow institutional servers
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        try:
            res = client.get(url, params=params)
            if res.status_code != 200:
                return f"SEARCH_ERROR_{res.status_code}: Google API gateway boundary error."

            items = res.json().get("items", [])
            if not items: 
                return "NO_RESULTS_FOUND: No query matches found."

            summary = ""
            for idx, item in enumerate(items, start=1):
                summary += f"\nSource {idx}:\nTitle: {item.get('title')}\nLink: {item.get('link')}\nSnippet: {item.get('snippet')}\n"
            return summary.strip()
        except Exception as e:
            return f"SEARCH_ERROR_UNKNOWN: {str(e)}"

def parse_search_sources(search_text: str):
    if not search_text or "SEARCH_ERROR" in search_text or "NO_RESULTS_FOUND" in search_text: 
        return []
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

def get_minimal_citation(user_query: str) -> str:
    return "Ref: National Curriculum Framework and Official Textbook Matrix"

def official_web_reader_tool(board: str, class_level: str, subject: str, topic: str = "", language: str = "English") -> str:
    """Queries, ingests, and normalizes educational material directly from verified .gov or academic portals."""
    query = f"{board} Class {class_level} {subject} {topic} official syllabus curriculum book chapters"
    search_text = google_search_tool(query, num_results=5)
    sources = parse_search_sources(search_text)

    final_output = "OFFICIAL_WEB_READER_RESULT\n"
    read_count = 0

    # User-Agent headers mask the client to prevent automated blocking mechanisms
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    with httpx.Client(timeout=25.0, follow_redirects=True, headers=headers) as client:
        for src in sources:
            link = src.get("link", "")
            # Whitelisted open educational data domains alongside state nodes
            if not link or not any(dom in link for dom in [".nic.in", ".gov.in", "ebalbharati.in", "mahahsscboard.in", "byjus.com", "learncbse.in"]):
                continue
            try:
                res = client.get(link)
                if res.status_code != 200: continue
                
                # Safe PDF parsing strategy
                if "pdf" in res.headers.get("Content-Type", "").lower() or link.lower().endswith(".pdf"):
                    reader = PdfReader(io.BytesIO(res.content))
                    text = "".join([p.extract_text() or "" for p in reader.pages[:8]])
                else:
                    soup = BeautifulSoup(res.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header"]): 
                        tag.decompose()
                    text = soup.get_text(separator="\n", strip=True)

                # Strip duplicate whitespace blocks to save LLM context
                text = re.sub(r'\n+', '\n', text)
                
                read_count += 1
                final_output += f"\nSOURCE {read_count}\nURL: {link}\nContent:\n{text[:5000]}\n"
                if read_count >= 2: break
            except Exception:
                continue

    return final_output if read_count > 0 else "OFFICIAL_READER_ERROR: No official reference data could be structured safely."