import time
import asyncio
from typing import Optional
from dataclasses import dataclass

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
except ImportError:
    async_playwright = None  # type: ignore
    Browser = object  # type: ignore
    BrowserContext = object  # type: ignore
    Page = object  # type: ignore

@dataclass
class NotionConfig:
    """Configuration for Notion scraping."""
    timeout: int = 30000  # Playwright timeout in milliseconds
    headless: bool = True
    delay_between_requests: float = 2.0  # Respectful delay between pages
    wait_for_content: int = 5000  # Wait for content to load (ms)

class NotionScraper:
    """Playwright-based Notion page scraper with stealth mode."""
    
    def __init__(self, config: Optional[NotionConfig] = None):
        if async_playwright is None:
            raise RuntimeError("Playwright not installed. Install with: pip install playwright")
        
        self.config = config or NotionConfig()
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def start(self):
        """Start the browser and create context."""
        self.playwright = await async_playwright().start()
        
        # Launch browser with stealth settings
        self.browser = await self.playwright.chromium.launch(
            headless=self.config.headless,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-default-apps',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
        # Create context with realistic settings
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
            }
        )
        
        # Create page
        self.page = await self.context.new_page()
        
        # Add stealth scripts
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)
    
    async def fetch_page(self, url: str) -> str:
        """Fetch a Notion page and return the HTML content after JS execution."""
        if not self.page:
            raise RuntimeError("Browser not started. Use async with NotionScraper():")
        
        try:
            # Navigate to page
            await self.page.goto(url, timeout=self.config.timeout, wait_until='networkidle')
            
            # Wait for content to load
            await self.page.wait_for_timeout(self.config.wait_for_content)
            
            # Try to wait for any LinkedIn links to appear
            try:
                await self.page.wait_for_selector('a[href*="linkedin.com"]', timeout=5000)
            except:
                # If no LinkedIn links found immediately, that's ok
                pass
            
            # Get the full HTML after JS execution
            html_content = await self.page.content()
            
            # Add respectful delay
            await asyncio.sleep(self.config.delay_between_requests)
            
            return html_content
            
        except Exception as e:
            raise RuntimeError(f"Failed to fetch Notion page {url}: {e}")
    
    async def close(self):
        """Close the browser and cleanup."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

# Synchronous wrapper for backwards compatibility
class SyncNotionScraper:
    """Synchronous wrapper around the async NotionScraper."""
    
    def __init__(self, config: Optional[NotionConfig] = None):
        self.config = config
        self._scraper = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._scraper:
            asyncio.run(self._scraper.close())
    
    def fetch_page(self, url: str) -> str:
        """Fetch a page synchronously."""
        return asyncio.run(self._fetch_page_async(url))
    
    async def _fetch_page_async(self, url: str) -> str:
        """Internal async method."""
        if not self._scraper:
            self._scraper = NotionScraper(self.config)
            await self._scraper.start()
        
        return await self._scraper.fetch_page(url)