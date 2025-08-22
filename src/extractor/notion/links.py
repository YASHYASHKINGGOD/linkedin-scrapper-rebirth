import re
from typing import List, Dict, Set, Optional
from bs4 import BeautifulSoup
from datetime import datetime
from .client import SyncNotionScraper, NotionConfig

def is_linkedin_url(url: str) -> bool:
    """Check if a URL is a LinkedIn URL."""
    if not url:
        return False
    return "linkedin.com" in url.lower()

def normalize_linkedin_url(url: str) -> str:
    """Normalize LinkedIn URL by removing tracking parameters."""
    # Remove common tracking parameters but keep essential ones
    if '?' in url:
        base_url, params = url.split('?', 1)
        
        # For LinkedIn job URLs, we want to keep the basic structure
        if '/jobs/view/' in base_url or '/posts/' in base_url:
            return base_url
        
        # For other URLs, remove tracking but keep view parameters
        essential_params = []
        for param in params.split('&'):
            if param.startswith('v=') or param.startswith('gid='):
                essential_params.append(param)
        
        if essential_params:
            return base_url + '?' + '&'.join(essential_params)
        else:
            return base_url
    
    return url

def extract_linkedin_links_from_html(html_content: str, source_url: str, limit: Optional[int] = 10) -> List[Dict[str, str]]:
    """Extract LinkedIn links from HTML content."""
    soup = BeautifulSoup(html_content, 'lxml')
    links = []
    seen_urls: Set[str] = set()
    
    # Find all anchor tags with href attributes
    for link_tag in soup.find_all('a', href=True):
        href = link_tag.get('href', '').strip()
        
        if not href or not is_linkedin_url(href):
            continue
        
        # Handle relative URLs
        if href.startswith('//'):
            href = 'https:' + href
        elif href.startswith('/'):
            href = 'https://linkedin.com' + href
        
        # Normalize the URL
        normalized_url = normalize_linkedin_url(href)
        
        # Skip if we've already seen this URL
        if normalized_url in seen_urls:
            continue
        
        seen_urls.add(normalized_url)
        
        # Get anchor text and surrounding context
        anchor_text = link_tag.get_text(strip=True)
        
        # Try to get better context - look for table row or list item
        context = ""
        for parent_tag in ['tr', 'li', 'div']:
            parent = link_tag.find_parent(parent_tag)
            if parent:
                context = parent.get_text(strip=True)[:300]  # Increased context length
                break
        
        if not context:
            # Fallback to immediate parent
            parent = link_tag.parent
            if parent:
                context = parent.get_text(strip=True)[:300]
        
        link_data = {
            "url": normalized_url,
            "source": "notion",
            "source_page_url": source_url,
            "anchor_text": anchor_text,
            "row_context": context,
            "captured_at": datetime.now().isoformat(),
        }
        
        links.append(link_data)
        
        # Stop if we've reached the limit (if limit is set)
        if limit is not None and len(links) >= limit:
            break
    
    return links

def extract_linkedin_links_from_notion_page(page_url: str, limit: int = 10) -> List[Dict[str, str]]:
    """Extract LinkedIn links from a Notion page using Playwright."""
    config = NotionConfig(
        headless=True,  # Run in headless mode for production
        wait_for_content=8000,  # Wait longer for Notion content to load
        delay_between_requests=2.0  # Respectful delay
    )
    
    with SyncNotionScraper(config) as scraper:
        try:
            print(f"   🔍 Fetching page with Playwright...")
            html_content = scraper.fetch_page(page_url)
            
            print(f"   📄 Got {len(html_content)} characters of HTML")
            
            # Save HTML for debugging
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_file = f"./storage/debug_notion_{timestamp}.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"   💾 Saved debug HTML to {debug_file}")
            
            # Extract links
            links = extract_linkedin_links_from_html(html_content, page_url, limit)
            return links
            
        except Exception as e:
            print(f"   ❌ Error extracting links from {page_url}: {e}")
            return []