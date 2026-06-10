# maha_scraper.py
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def get_maharashtra_board_syllabus(base_url="https://www.mahahsscboard.in"):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    target_urls = [base_url, urljoin(base_url, "subjects.htm")]
    discovered_pdfs = []
    seen_urls = set()
    
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
                        if any(k in link_text.lower() or k in href.lower() for k in ['syllabus', 'subject', 'curriculum', 'hsc', 'ssc', 'std']):
                            seen_urls.add(absolute_url)
                            discovered_pdfs.append(f"- {link_text if link_text.strip() else 'Syllabus Doc'}: {absolute_url}")
            except Exception:
                pass
    return "\n".join(discovered_pdfs) if discovered_pdfs else "No direct PDF files resolved from the main page mapping."