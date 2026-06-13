import os
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("Crawl_Engine")

def crawl_official_site(url: str) -> str:
    """
    Crawls educational pages or open curriculum directories via Jina AI Reader,
    converting raw asset structures into pristine markdown strings.
    """
    jina_url = f"https://r.jina.ai/{url}"
    token = os.getenv("JINA_READER_KEY")
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    logger.info(f"Initiating clean markdown crawl capture for URL: {url}")
    
    # Context-managed connection multiplexer
    with httpx.Client(headers=headers, timeout=20.0, follow_redirects=True) as client:
        try:
            response = client.get(jina_url)
            
            if response.status_code == 200:
                return response.text
            
            logger.warning(f"Jina proxy returned validation anomaly code: {response.status_code}")
            return f"Error: Crawl extraction process failed with code {response.status_code}"
            
        except httpx.ConnectTimeout:
            logger.error("Target edge platform timing threshold breached (Timeout).")
            return "Exception occurred during crawling: Connection timed out."
        except Exception as e:
            logger.critical(f"Unhandled crawling abstraction crash: {str(e)}")
            return f"Exception occurred during crawling: {str(e)}"