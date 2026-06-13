import logging
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

logger = logging.getLogger("Maha_Scraper")

def get_maharashtra_board_syllabus(base_url: str = "https://www.mahahsscboard.in") -> str:
    """Scrapes the Maharashtra Board portal for core academic curriculum documents."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Apple/...",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    
    target_urls = [base_url, urljoin(base_url, "subjects.htm")]
    discovered_pdfs = []
    seen_urls = set()
    
    # Content tokens matching genuine state framework documents
    valid_keys = {"syllabus", "subject", "curriculum", "hsc", "ssc", "std", "अभ्यासक्रम", "पाठ्यक्रम"}

    with httpx.Client(headers=headers, follow_redirects=True, timeout=15.0) as client:
        for url in target_urls:
            try:
                response = client.get(url)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                for link in soup.find_all('a', href=True):
                    href = link['href'].strip()
                    link_text = link.get_text().strip()
                    absolute_url = urljoin(base_url, href)

                    if absolute_url.lower().endswith('.pdf') and absolute_url not in seen_urls:
                        combined_text = (link_text + " " + href).lower()
                        
                        if any(keyword in combined_text for keyword in valid_keys):
                            seen_urls.add(absolute_url)
                            doc_title = link_text if link_text else "Syllabus Resource Document"
                            discovered_pdfs.append(f"- {doc_title}: {absolute_url}")
            except Exception as e:
                logger.error(f"Encountered non-breaking scraping issue on target endpoint {url}: {str(e)}")
                
    return "\n".join(discovered_pdfs) if discovered_pdfs else "No direct PDF files resolved from the main page mapping."