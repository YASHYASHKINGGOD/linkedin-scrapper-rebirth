#!/usr/bin/env python3
"""
Database-Integrated LinkedIn XPath Scraper

Integrates the existing Selenium XPath scraper with PostgreSQL database.
Converts CSV output to database storage in linkedin_posts_raw table.

Based on: linkedin_scraper_xpath_v1.py
Modified to: Save to PostgreSQL instead of CSV files

Usage:
    from apps.scraper_playwright.posts.selenium_scraper import DatabaseLinkedInScraper
    
    scraper = DatabaseLinkedInScraper(database_url, config_path)
    result = await scraper.scrape_post_to_db(url, link_id)
"""

import json
import logging
import time
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import asyncio

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager

try:
    import psycopg
except ImportError:
    print("❌ psycopg is required. Install with: pip install 'psycopg[binary]'")
    psycopg = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database-linkedin-scraper")


class DatabaseLinkedInScraper:
    """LinkedIn XPath Scraper with PostgreSQL integration"""
    
    def __init__(self, database_url: str, config_path: str = "config.json", storage_base: str = "./storage"):
        self.database_url = database_url
        self.storage_base = Path(storage_base)
        self.posts_storage = self.storage_base / "posts"
        self.posts_storage.mkdir(parents=True, exist_ok=True)
        
        self.config = self._load_config(config_path)
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration with defaults"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except FileNotFoundError:
            print(f"⚠️  Config file {config_path} not found. Using defaults.")
            config = {}
        
        # Set defaults (same as original scraper)
        config.setdefault("chrome_options", {})
        config["chrome_options"].setdefault("disable_automation_flags", [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars", 
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ])
        config["chrome_options"].setdefault("user_agent", 
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        config["chrome_options"].setdefault("window_size", [1920, 1080])
        
        config.setdefault("scraping_settings", {})
        config["scraping_settings"].setdefault("headless", False)
        config["scraping_settings"].setdefault("implicit_wait_timeout", 5)
        config["scraping_settings"].setdefault("page_load_timeout", 45)
        config["scraping_settings"].setdefault("explicit_wait_timeout", 20)
        
        return config

    def _setup_driver(self) -> webdriver.Chrome:
        """Setup Chrome driver with anti-detection measures (same as original)"""
        chrome_options = Options()
        for flag in self.config["chrome_options"]["disable_automation_flags"]:
            chrome_options.add_argument(flag)
        
        chrome_options.add_argument(f"--user-agent={self.config['chrome_options']['user_agent']}")
        w, h = self.config["chrome_options"]["window_size"]
        chrome_options.add_argument(f"--window-size={w},{h}")
        
        if self.config["scraping_settings"]["headless"]:
            chrome_options.add_argument("--headless=new")

        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.implicitly_wait(self.config["scraping_settings"]["implicit_wait_timeout"])
        driver.set_page_load_timeout(self.config["scraping_settings"]["page_load_timeout"])
        return driver

    def initialize_driver(self):
        """Initialize the webdriver"""
        self.driver = self._setup_driver()
        self.wait = WebDriverWait(self.driver, self.config["scraping_settings"]["explicit_wait_timeout"])
        return True

    def login(self) -> Tuple[bool, str]:
        """Login to LinkedIn (same as original)"""
        self.driver.get("https://www.linkedin.com/login")
        time.sleep(2)
        
        try:
            user_input = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            pass_input = self.wait.until(EC.presence_of_element_located((By.ID, "password")))
            
            creds = self.config.get("linkedin_credentials", {})
            if not creds.get("email") or not creds.get("password"):
                return False, "LinkedIn credentials not found in config"
            
            user_input.clear()
            user_input.send_keys(creds["email"])
            pass_input.clear()
            pass_input.send_keys(creds["password"])
            
            submit_btn = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            submit_btn.click()
            time.sleep(3)
            
            # Check if login was successful
            if any(k in self.driver.current_url for k in ("feed", "mynetwork", "jobs", "/in/", "messaging")):
                return True, "Login successful"
            else:
                return False, f"Login may have failed: {self.driver.current_url}"
                
        except Exception as e:
            return False, f"Login error: {str(e)}"

    # ========== XPath Content Extraction (from original scraper) ==========
    
    def _expand_content_xpath(self):
        """Use XPath to find and click 'see more' buttons"""
        print("🔄 Expanding content using XPath...")
        
        see_more_xpaths = [
            "//button[contains(@aria-label, 'more')]",
            "//button[contains(text(), 'see more')]",
            "//button[contains(text(), 'See more')]", 
            "//button[@data-test-id='see-more-button']",
            "//*[contains(text(), '...see more')]",
        ]
        
        for xpath in see_more_xpaths:
            try:
                buttons = self.driver.find_elements(By.XPATH, xpath)
                if buttons:
                    for btn in buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            btn.click()
                            print(f"✅ Clicked see more button: {xpath}")
                            time.sleep(2)
                            return  # Only click the first working button
            except Exception as e:
                print(f"⚠️ Failed with xpath {xpath}: {e}")
                continue

    def _extract_post_content_xpath(self, url: str) -> str:
        """Extract post content using XPath (simplified from original)"""
        print("\\n🎯 XPATH-BASED POST CONTENT EXTRACTION")
        
        # Expand truncated content first
        self._expand_content_xpath()
        
        # Extract key terms from URL to help target content
        url_terms = []
        if "hiring" in url.lower():
            url_terms.append("hiring")
        if "product-manager" in url.lower():
            url_terms.extend(["product", "manager"])
        
        # XPath strategies for finding post content by text content
        content_extraction_xpaths = [
            # Direct text search for known content patterns
            "//*[contains(text(), 'hiring')]",
            "//*[contains(text(), 'Hiring')]", 
            "//*[contains(text(), 'Product Manager')]",
            "//*[contains(text(), 'We\\'re Hiring')]",
            
            # Attribute-based with text validation
            "//*[@data-test-id='main-feed-activity-card__commentary']",
            "//*[@data-test-id='main-feed-activity-card__commentary']//*[text()]",
            
            # Semantic content detection (substantial paragraphs)
            "//p[string-length(normalize-space(text())) > 20]",
            "//div[string-length(normalize-space(text())) > 50]",
            "//article//p[string-length(normalize-space(text())) > 30]",
            
            # LinkedIn-specific content containers
            "//div[contains(@class, 'feed-shared-text')]//text()[normalize-space()]/..",
            "//div[contains(@class, 'update-components-text')]//text()[normalize-space()]/..",
        ]
        
        extracted_texts = []
        
        for xpath in content_extraction_xpaths:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                for element in elements[:5]:  # Limit to first 5 per xpath
                    try:
                        text_candidates = [
                            element.get_attribute("textContent"),
                            element.get_attribute("innerText"), 
                            element.text
                        ]
                        
                        for text in text_candidates:
                            if text and text.strip() and len(text.strip()) > 20:
                                text = text.strip()
                                # Quality filter: skip obvious metadata
                                if not any(skip in text.lower() for skip in [
                                    '• 3rd+', '• 2nd', '• 1st', 'followers', 'connections',
                                    'like this', 'repost', 'share this', 'send',
                                    'hours ago', 'days ago', 'minutes ago'
                                ]):
                                    if text not in extracted_texts:
                                        extracted_texts.append(text)
                                    break
                    except Exception:
                        continue
            except Exception:
                continue
        
        # Find the best candidate based on content quality and length
        best_content = ""
        max_score = 0
        
        for text in extracted_texts:
            score = 0
            
            # Length score (prefer substantial content, but not too long)
            length_score = min(len(text) / 100, 10)  # Max 10 points for length
            score += length_score
            
            # Keyword relevance score  
            for term in url_terms:
                if term.lower() in text.lower():
                    score += 5
            
            # Content quality indicators
            if "hiring" in text.lower():
                score += 10
            if "product manager" in text.lower():
                score += 10
            if len(text.split()) > 10:  # Prefer multi-sentence content
                score += 5
                
            # Penalty for metadata-like content
            if any(bad in text.lower() for bad in ['followers', '• 3rd+', 'connections']):
                score -= 20
            
            if score > max_score:
                max_score = score
                best_content = text
        
        return best_content

    def _extract_author_xpath(self) -> Dict[str, str]:
        """Extract author info using XPath"""
        author_info = {"post_author": "", "author_title": "", "author_profile_url": ""}
        
        # XPath strategies for author name
        author_xpaths = [
            "//a[contains(@href, '/in/')][string-length(text()) > 3 and string-length(text()) < 100]",
        ]
        
        for xpath in author_xpaths:
            try:
                links = self.driver.find_elements(By.XPATH, xpath)
                for link in links[:5]:
                    text = link.text.strip()
                    href = link.get_attribute("href")
                    
                    if text and 5 <= len(text) <= 100:
                        name = text.split('\\n')[0].strip()
                        if name and not any(skip in name.lower() for skip in [
                            'see more', 'like', 'comment', 'share', 'follow'
                        ]):
                            author_info["post_author"] = name
                            author_info["author_profile_url"] = href
                            break
                            
                if author_info["post_author"]:
                    break
            except Exception:
                continue
        
        # XPath for author title/description  
        title_xpaths = [
            "//p[contains(@class, 'text-color-text-low-emphasis')]",
            "//*[contains(@class, 'feed-shared-actor__description')]",
            "//*[contains(@class, 'feed-shared-actor__sub-description')]"
        ]
        
        for xpath in title_xpaths:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    text = el.text.strip()
                    if text and len(text) < 200 and not any(skip in text.lower() for skip in [
                        'ago', 'hour', 'day', 'week', 'month', 'min'
                    ]):
                        author_info["author_title"] = text
                        break
                        
                if author_info["author_title"]:
                    break
            except Exception:
                continue
        
        return author_info

    def _extract_metadata_xpath(self) -> Dict[str, str]:
        """Extract metadata using XPath"""
        # XPath for time elements
        time_xpaths = [
            "//time",
            "//*[contains(text(), 'h') or contains(text(), 'd') or contains(text(), 'w')][string-length(text()) < 20]"
        ]
        
        for xpath in time_xpaths:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    # Try datetime attribute first
                    datetime_attr = el.get_attribute("datetime")
                    if datetime_attr:
                        return {"date_posted": datetime_attr}
                    
                    # Fall back to text content
                    text = el.text.strip()
                    if text and len(text) < 20 and ('h' in text or 'd' in text or 'w' in text or 'ago' in text):
                        return {"date_posted": text}
            except Exception:
                continue
        
        return {"date_posted": ""}

    def _extract_comments_xpath(self, limit=10) -> List[Dict[str, str]]:
        """Extract comments using XPath"""
        comments = []
        
        # Try to expand comments first
        try:
            comment_buttons = self.driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'comment')]")
            if comment_buttons:
                comment_buttons[0].click()
                time.sleep(3)
        except Exception:
            pass
        
        # XPath for comment containers
        comment_xpaths = [
            "//article[contains(@data-id, 'comment')]",
            "//*[contains(@class, 'comment') and not(contains(@class, 'commentary'))]",
        ]
        
        for xpath in comment_xpaths:
            try:
                comment_elements = self.driver.find_elements(By.XPATH, xpath)
                
                for comment_el in comment_elements[:limit]:
                    try:
                        full_text = comment_el.text.strip()
                        if len(full_text) < 20:
                            continue
                        
                        lines = [line.strip() for line in full_text.split('\\n') if line.strip()]
                        
                        commentor = ""
                        comment_text = ""
                        
                        if lines:
                            # First reasonable line as author
                            potential_author = lines[0]
                            if len(potential_author) < 100:
                                commentor = potential_author
                        
                            # Look for actual comment content
                            for line in lines[1:]:
                                if (len(line) > 5 and 
                                    not any(skip in line.lower() for skip in [
                                        '• 1st', '• 2nd', '• 3rd', 'followers', 'connections',
                                        'like', 'reply', 'share'
                                    ]) and
                                    not (len(line) < 15 and any(char in line for char in ['h', 'd', 'w', 'm']))):
                                    comment_text = line
                                    break
                        
                        if commentor or comment_text:
                            comments.append({
                                "commentor": commentor,
                                "comment_text": comment_text[:300]
                            })
                    except Exception:
                        continue
                
                if comments:  # If found comments, don't try other xpaths
                    break
            except Exception:
                continue
        
        return comments

    def _extract_links_xpath(self) -> List[str]:
        """Extract links using XPath"""
        links = []
        try:
            link_elements = self.driver.find_elements(By.XPATH, "//a[@href]")
            for a in link_elements:
                href = a.get_attribute("href")
                if href and href not in links:
                    # Include external links and meaningful LinkedIn links
                    if not href.startswith('https://www.linkedin.com') or '/in/' in href or '/company/' in href:
                        links.append(href)
        except Exception:
            pass
        
        return links

    # ========== Main scraping function ==========

    def scrape_post(self, url: str) -> Dict[str, Any]:
        """Main scraping function using XPath approach (same structure as original)"""
        print(f"\\n🚀 SCRAPING POST WITH XPATH APPROACH: {url}")
        
        self.driver.get(url)
        time.sleep(3)
        
        # Wait for page to load
        self.wait.until(EC.any_of(
            EC.presence_of_element_located((By.XPATH, "//article")),
            EC.presence_of_element_located((By.XPATH, "//main"))
        ))
        
        # Extract all data
        data = {
            "post_url": url,
            "scraped_at": datetime.now().isoformat(),
            "scraper_version": "1.0-xpath-db",
        }
        
        # XPath-based extractions
        data.update(self._extract_author_xpath())
        data.update(self._extract_metadata_xpath()) 
        data["post_text"] = self._extract_post_content_xpath(url)
        data["links"] = self._extract_links_xpath()
        data["comments"] = self._extract_comments_xpath(limit=20)
        
        return data

    # ========== Database Integration ==========

    def _get_storage_paths(self, link_id: int, url: str) -> Dict[str, Path]:
        """Get organized storage paths for scraped content"""
        today = datetime.now().strftime("%Y%m%d")
        base_dir = self.posts_storage / today / f"link_{link_id}"
        base_dir.mkdir(parents=True, exist_ok=True)
        
        return {
            "html": base_dir / "content.html",
            "screenshot": base_dir / "screenshot.png", 
            "metadata": base_dir / "metadata.json",
            "base_dir": base_dir
        }

    def _save_scraped_files(self, link_id: int, url: str, scraped_data: Dict[str, Any]) -> Dict[str, str]:
        """Save HTML, screenshot, and metadata files to storage"""
        storage_paths = self._get_storage_paths(link_id, url)
        result_paths = {}
        
        try:
            # Save HTML content
            html_content = self.driver.page_source
            with open(storage_paths["html"], 'w', encoding='utf-8') as f:
                f.write(html_content)
            result_paths["html_path"] = str(storage_paths["html"].relative_to(self.storage_base))
            
            # Take screenshot
            self.driver.save_screenshot(str(storage_paths["screenshot"]))
            result_paths["screenshot_path"] = str(storage_paths["screenshot"].relative_to(self.storage_base))
            
            # Save metadata JSON
            with open(storage_paths["metadata"], 'w', encoding='utf-8') as f:
                json.dump(scraped_data, f, indent=2, ensure_ascii=False)
            result_paths["metadata_path"] = str(storage_paths["metadata"].relative_to(self.storage_base))
            
        except Exception as e:
            print(f"⚠️ Error saving files: {e}")
        
        return result_paths

    async def scrape_post_to_db(self, url: str, link_id: int, trace_id: str = None) -> Dict[str, Any]:
        """
        Scrape a LinkedIn post and save to PostgreSQL database
        
        Returns:
            Dict with success status and scraped data
        """
        if not psycopg:
            return {
                "success": False,
                "error": "psycopg not available",
                "link_id": link_id,
                "url": url
            }
        
        scrape_start = datetime.now()
        trace_id = trace_id or f"scrape_{int(time.time())}"
        
        print(f"🕷️ [trace:{trace_id}] Scraping LinkedIn post for link_id={link_id}")
        
        try:
            # Scrape the post using original XPath logic
            scraped_data = self.scrape_post(url)
            
            # Save files to storage
            file_paths = self._save_scraped_files(link_id, url, scraped_data)
            
            # Prepare data for database
            scrape_metadata = {
                "scrape_timestamp": scrape_start.isoformat(),
                "html_length": len(self.driver.page_source) if self.driver else 0,
                "screenshot_taken": bool(file_paths.get("screenshot_path")),
                "scraper_version": scraped_data.get("scraper_version", "1.0-xpath-db"),
                "trace_id": trace_id,
                "browser_user_agent": self.config["chrome_options"]["user_agent"]
            }
            
            # Prepare extracted data (same structure as CSV but in JSON)
            extracted_data = {
                "post_author": scraped_data.get("post_author", ""),
                "author_title": scraped_data.get("author_title", ""),
                "author_profile_url": scraped_data.get("author_profile_url", ""),
                "date_posted": scraped_data.get("date_posted", ""),
                "post_text": scraped_data.get("post_text", ""),
                "links": scraped_data.get("links", []),
                "comment_count": len(scraped_data.get("comments", [])),
                "comments": scraped_data.get("comments", [])
            }
            
            # Update database
            with psycopg.connect(self.database_url) as conn:
                conn.execute("SET TIME ZONE 'UTC'")
                
                # Update the linkedin_posts_raw table
                conn.execute("""
                    UPDATE public.linkedin_posts_raw
                    SET 
                        status = 'completed',
                        scraped_at = now(),
                        raw_html_path = %s,
                        screenshot_path = %s,
                        metadata_json_path = %s,
                        scrape_metadata = %s::jsonb,
                        extracted_data = %s::jsonb,
                        trace_id = %s,
                        scraper_version = %s,
                        updated_at = now()
                    WHERE link_id = %s
                """, [
                    file_paths.get("html_path"),
                    file_paths.get("screenshot_path"),
                    file_paths.get("metadata_path"),
                    json.dumps(scrape_metadata),
                    json.dumps(extracted_data),
                    trace_id,
                    scraped_data.get("scraper_version", "1.0-xpath-db"),
                    link_id
                ])
                
                # Also update linkedin_links status
                conn.execute("""
                    UPDATE public.linkedin_links
                    SET status = 'scraped', updated_at = now()
                    WHERE id = %s
                """, [link_id])
            
            duration = (datetime.now() - scrape_start).total_seconds()
            print(f"✅ [trace:{trace_id}] Successfully scraped and saved to database in {duration:.1f}s")
            
            return {
                "success": True,
                "link_id": link_id,
                "url": url,
                "trace_id": trace_id,
                "duration_seconds": duration,
                "scraped_data": extracted_data,
                "file_paths": file_paths
            }
            
        except Exception as e:
            print(f"❌ [trace:{trace_id}] Scraping failed: {e}")
            
            # Update database with error
            try:
                with psycopg.connect(self.database_url) as conn:
                    conn.execute("""
                        UPDATE public.linkedin_posts_raw
                        SET 
                            status = 'failed',
                            error_message = %s,
                            attempt_count = attempt_count + 1,
                            updated_at = now()
                        WHERE link_id = %s
                    """, [str(e), link_id])
            except Exception as db_error:
                print(f"❌ Database error update failed: {db_error}")
            
            return {
                "success": False,
                "link_id": link_id,
                "url": url,
                "trace_id": trace_id,
                "error": str(e)
            }

    def close_driver(self):
        """Clean up webdriver"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

# ========== Async wrapper for integration ==========

class AsyncDatabaseLinkedInScraper:
    """Async wrapper for the Selenium scraper to integrate with async pipeline"""
    
    def __init__(self, database_url: str, config_path: str = "config.json", storage_base: str = "./storage"):
        self.database_url = database_url
        self.config_path = config_path
        self.storage_base = storage_base
        self._scraper = None
        self._logged_in = False

    async def initialize(self):
        """Initialize the scraper and login"""
        self._scraper = DatabaseLinkedInScraper(self.database_url, self.config_path, self.storage_base)
        self._scraper.initialize_driver()
        
        # Login
        success, msg = self._scraper.login()
        if not success:
            raise RuntimeError(f"LinkedIn login failed: {msg}")
        
        self._logged_in = True
        print("✅ LinkedIn scraper initialized and logged in")

    async def scrape_post(self, url: str, link_id: int, trace_id: str = None) -> Dict[str, Any]:
        """Async interface for scraping posts"""
        if not self._scraper or not self._logged_in:
            await self.initialize()
        
        # Run the scraping in a thread to avoid blocking
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await asyncio.get_event_loop().run_in_executor(
                executor, 
                lambda: asyncio.run(self._scraper.scrape_post_to_db(url, link_id, trace_id))
            )
        
        return result

    async def close(self):
        """Clean up resources"""
        if self._scraper:
            self._scraper.close_driver()


# ========== CLI for testing ==========

async def main():
    """CLI entry point for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database LinkedIn XPath Scraper")
    parser.add_argument("--url", required=True, help="LinkedIn post URL")
    parser.add_argument("--link-id", type=int, required=True, help="Database link ID")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--database-url", help="PostgreSQL connection string")
    
    args = parser.parse_args()
    
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL is required")
        return 1
    
    scraper = AsyncDatabaseLinkedInScraper(database_url, args.config)
    
    try:
        result = await scraper.scrape_post(args.url, args.link_id)
        
        if result["success"]:
            print(f"\\n✅ SCRAPING COMPLETE!")
            print(f"📊 Results for link_id {result['link_id']}:")
            print(f"   Author: {result['scraped_data'].get('post_author', 'N/A')}")
            print(f"   Text length: {len(result['scraped_data'].get('post_text', ''))}")
            print(f"   Comments: {result['scraped_data'].get('comment_count', 0)}")
            print(f"   Duration: {result.get('duration_seconds', 0):.1f}s")
        else:
            print(f"❌ Scraping failed: {result.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        await scraper.close()
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
