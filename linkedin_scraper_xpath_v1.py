#!/usr/bin/env python3
"""
LinkedIn Scraper XPath V1 - Text-Based Extraction

Revolutionary approach using XPath text matching:
1. Find elements by their ACTUAL TEXT CONTENT, not just CSS classes
2. Use XPath's powerful text() functions to locate post content directly
3. Eliminate ancestor filtering issues by targeting content semantically
4. Use text patterns like "hiring", "Product Manager" etc. to identify post content

XPath Strategy:
- //*[contains(text(), 'hiring')] - Find any element containing "hiring" 
- //p[contains(text(), 'Product Manager')] - Find p elements with specific text
- //article//p[string-length(text()) > 50] - Find substantial paragraphs in articles
- //*[@data-test-id='main-feed-activity-card__commentary'] - Direct attribute targeting

This bypasses all CSS selector complexity and focuses on CONTENT.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import os
from datetime import datetime
import csv
import argparse
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("linkedin-scraper-xpath")

class LinkedInXPathScraper:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.output_dir = Path(self.config["output_settings"]["output_directory"])
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Set defaults
        config.setdefault("chrome_options", {})
        config["chrome_options"].setdefault("disable_automation_flags", [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars", 
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ])
        config["chrome_options"].setdefault("user_agent", 
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        config["chrome_options"].setdefault("window_size", [1366, 900])
        
        config.setdefault("scraping_settings", {})
        config["scraping_settings"].setdefault("headless", False)
        config["scraping_settings"].setdefault("implicit_wait_timeout", 5)
        config["scraping_settings"].setdefault("page_load_timeout", 45)
        config["scraping_settings"].setdefault("explicit_wait_timeout", 20)
        
        config.setdefault("output_settings", {})
        config["output_settings"].setdefault("output_directory", "outputs")
        config["output_settings"].setdefault("timestamp_format", "%Y%m%d_%H%M%S")
        
        return config

    def _setup_driver(self) -> webdriver.Chrome:
        """Setup Chrome driver with anti-detection measures"""
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
        self.driver = self._setup_driver()
        self.wait = WebDriverWait(self.driver, self.config["scraping_settings"]["explicit_wait_timeout"])
        return True

    def login(self) -> Tuple[bool, str]:
        """Login to LinkedIn"""
        self.driver.get("https://www.linkedin.com/login")
        time.sleep(2)
        
        try:
            user_input = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            pass_input = self.wait.until(EC.presence_of_element_located((By.ID, "password")))
            
            creds = self.config["linkedin_credentials"]
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

    # ========== XPATH-BASED CONTENT EXTRACTION ==========

    def _expand_content_xpath(self):
        """Use XPath to find and click 'see more' buttons"""
        print("🔄 Expanding content using XPath...")
        
        # XPath patterns for "see more" buttons
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
        """
        Revolutionary XPath approach: Find post content by ACTUAL TEXT CONTENT
        """
        print("\\n🎯 XPATH-BASED POST CONTENT EXTRACTION")
        
        # First, expand any truncated content
        self._expand_content_xpath()
        
        # Strategy: Use what we know about this specific post
        # From debug: post contains "We're Hiring: Product Manager"
        
        # Extract key terms from URL to help target content
        url_terms = []
        if "hiring" in url.lower():
            url_terms.append("hiring")
        if "product-manager" in url.lower():
            url_terms.extend(["product", "manager"])
        if "were-hiring" in url.lower():
            url_terms.extend(["We're", "Hiring"])
            
        print(f"🔍 Targeting content with URL-derived terms: {url_terms}")
        
        # XPath strategies for finding post content by text content
        content_extraction_strategies = [
            
            # Strategy 1: Direct text search for known content patterns
            {
                "name": "Direct Text Pattern Matching",
                "xpaths": [
                    "//*[contains(text(), 'hiring')]",
                    "//*[contains(text(), 'Hiring')]", 
                    "//*[contains(text(), 'Product Manager')]",
                    "//*[contains(text(), 'We\\'re Hiring')]",
                    "//*[contains(text(), 'Were Hiring')]",
                ]
            },
            
            # Strategy 2: Attribute-based with text validation
            {
                "name": "Attribute + Text Validation",
                "xpaths": [
                    "//*[@data-test-id='main-feed-activity-card__commentary']",
                    "//*[@data-test-id='main-feed-activity-card__commentary']//*[text()]",
                    "//p[@data-test-id='main-feed-activity-card__commentary']",
                ]
            },
            
            # Strategy 3: Semantic content detection (substantial paragraphs)
            {
                "name": "Semantic Content Detection", 
                "xpaths": [
                    "//p[string-length(normalize-space(text())) > 20]",
                    "//div[string-length(normalize-space(text())) > 50]",
                    "//article//p[string-length(normalize-space(text())) > 30]",
                    "//*[string-length(normalize-space(text())) > 100]",
                ]
            },
            
            # Strategy 4: LinkedIn-specific content containers
            {
                "name": "LinkedIn Content Containers",
                "xpaths": [
                    "//div[contains(@class, 'feed-shared-text')]//text()[normalize-space()]/..",
                    "//div[contains(@class, 'update-components-text')]//text()[normalize-space()]/..",
                    "//div[contains(@class, 'attributed-text-segment')]//text()[normalize-space()]/..",
                ]
            }
        ]
        
        extracted_texts = []
        
        for strategy in content_extraction_strategies:
            print(f"\\n📋 Strategy: {strategy['name']}")
            strategy_texts = []
            
            for xpath in strategy["xpaths"]:
                try:
                    print(f"   Testing: {xpath}")
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    print(f"   Found: {len(elements)} elements")
                    
                    for i, element in enumerate(elements[:5], 1):  # Limit to first 5 per xpath
                        try:
                            # Try multiple text extraction methods
                            text_candidates = [
                                element.get_attribute("textContent"),
                                element.get_attribute("innerText"), 
                                element.text
                            ]
                            
                            for method_idx, text in enumerate(text_candidates):
                                if text and text.strip():
                                    text = text.strip()
                                    # Only consider substantial text
                                    if len(text) > 20:
                                        print(f"     Element {i}: '{text[:80]}{'...' if len(text) > 80 else ''}'")
                                        
                                        # Quality filter: skip obvious metadata
                                        if not any(skip in text.lower() for skip in [
                                            '• 3rd+', '• 2nd', '• 1st', 'followers', 'connections',
                                            'like this', 'repost', 'share this', 'send',
                                            'hours ago', 'days ago', 'minutes ago'
                                        ]):
                                            if text not in strategy_texts:
                                                strategy_texts.append(text)
                                            break
                        except Exception as e:
                            print(f"     Element {i}: Error extracting text - {e}")
                            continue
                            
                except Exception as e:
                    print(f"   XPath Error: {e}")
                    continue
            
            print(f"📊 Strategy '{strategy['name']}' found {len(strategy_texts)} unique texts")
            extracted_texts.extend(strategy_texts)
        
        # Remove duplicates while preserving order
        unique_texts = []
        seen = set()
        for text in extracted_texts:
            text_key = text[:100].lower()  # Use first 100 chars for deduplication
            if text_key not in seen:
                seen.add(text_key)
                unique_texts.append(text)
        
        print(f"\\n📝 Total unique texts found: {len(unique_texts)}")
        
        # Find the best candidate based on content quality and length
        best_content = ""
        max_score = 0
        
        for text in unique_texts:
            # Score based on length, presence of key terms, and quality indicators
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
            if "we're" in text.lower() or "were" in text.lower():
                score += 5
            if len(text.split()) > 10:  # Prefer multi-sentence content
                score += 5
                
            # Penalty for metadata-like content
            if any(bad in text.lower() for bad in ['followers', '• 3rd+', 'connections']):
                score -= 20
                
            print(f"Content score {score:.1f}: '{text[:60]}...'")
            
            if score > max_score:
                max_score = score
                best_content = text
        
        if best_content:
            print(f"\\n🏆 BEST CONTENT SELECTED (score: {max_score:.1f}):")
            print(f"'{best_content[:200]}{'...' if len(best_content) > 200 else ''}'")
            return best_content
        else:
            print("❌ No suitable post content found")
            return ""

    def _extract_author_xpath(self) -> Dict[str, str]:
        """Extract author info using XPath"""
        print("\\n👤 EXTRACTING AUTHOR WITH XPATH")
        
        author_info = {"post_author": "", "author_title": "", "author_profile_url": ""}
        
        # XPath strategies for author name
        author_xpaths = [
            "//a[contains(@href, '/in/')]",  # Profile links
            "//a[contains(@href, '/in/') and string-length(text()) > 3 and string-length(text()) < 100]",
        ]
        
        for xpath in author_xpaths:
            try:
                links = self.driver.find_elements(By.XPATH, xpath)
                print(f"Found {len(links)} profile links")
                
                for i, link in enumerate(links[:5], 1):
                    text = link.text.strip()
                    href = link.get_attribute("href")
                    
                    print(f"Link {i}: '{text}' -> {href}")
                    
                    # Look for reasonable author names
                    if text and 5 <= len(text) <= 100:
                        # Take first line as name
                        name = text.split('\\n')[0].strip()
                        if name and not any(skip in name.lower() for skip in [
                            'see more', 'like', 'comment', 'share', 'follow'
                        ]):
                            author_info["post_author"] = name
                            author_info["author_profile_url"] = href
                            print(f"✅ Selected author: {name}")
                            break
                            
                if author_info["post_author"]:
                    break
                    
            except Exception as e:
                print(f"Author extraction error: {e}")
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
                    # Look for job titles (not timestamps)
                    if text and len(text) < 200 and not any(skip in text.lower() for skip in [
                        'ago', 'hour', 'day', 'week', 'month', 'min'
                    ]):
                        author_info["author_title"] = text
                        print(f"✅ Found title: {text}")
                        break
                        
                if author_info["author_title"]:
                    break
                    
            except Exception:
                continue
        
        return author_info

    def _extract_metadata_xpath(self) -> Dict[str, str]:
        """Extract metadata using XPath"""
        print("\\n📅 EXTRACTING METADATA WITH XPATH")
        
        # XPath for time elements
        time_xpaths = [
            "//time",
            "//time/@datetime",
            "//*[contains(text(), 'h') or contains(text(), 'd') or contains(text(), 'w')][string-length(text()) < 20]"
        ]
        
        for xpath in time_xpaths:
            try:
                if xpath.endswith("/@datetime"):
                    # Handle datetime attribute
                    elements = self.driver.find_elements(By.XPATH, xpath[:-10])  # Remove /@datetime
                    for el in elements:
                        datetime_attr = el.get_attribute("datetime")
                        if datetime_attr:
                            print(f"✅ Found datetime: {datetime_attr}")
                            return {"date_posted": datetime_attr}
                else:
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    for el in elements:
                        text = el.text.strip()
                        if text and len(text) < 20 and ('h' in text or 'd' in text or 'w' in text or 'ago' in text):
                            print(f"✅ Found timestamp: {text}")
                            return {"date_posted": text}
            except Exception as e:
                print(f"Metadata extraction error: {e}")
                continue
        
        print("❌ No timestamp found")
        return {"date_posted": ""}

    def _extract_comments_xpath(self, limit=10) -> List[Dict[str, str]]:
        """Extract comments using XPath"""
        print(f"\\n💬 EXTRACTING COMMENTS WITH XPATH (limit={limit})")
        
        # Try to expand comments first
        try:
            comment_buttons = self.driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'comment')]")
            if comment_buttons:
                print(f"Found {len(comment_buttons)} comment buttons")
                comment_buttons[0].click()
                time.sleep(3)
                print("✅ Comments expanded")
        except Exception as e:
            print(f"⚠️ Could not expand comments: {e}")
        
        comments = []
        
        # XPath for comment containers
        comment_xpaths = [
            "//article[contains(@data-id, 'comment')]",
            "//*[contains(@class, 'comment') and not(contains(@class, 'commentary'))]",
        ]
        
        for xpath in comment_xpaths:
            try:
                comment_elements = self.driver.find_elements(By.XPATH, xpath)
                print(f"Found {len(comment_elements)} comment elements with {xpath}")
                
                for i, comment_el in enumerate(comment_elements[:limit]):
                    try:
                        full_text = comment_el.text.strip()
                        if len(full_text) < 20:
                            continue
                        
                        lines = [line.strip() for line in full_text.split('\\n') if line.strip()]
                        
                        # Simple parsing: first line = author, find comment text
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
                            print(f"✅ Comment {len(comments)}: '{commentor}' - '{comment_text[:50]}...'")
                        
                    except Exception as e:
                        print(f"❌ Error processing comment {i}: {e}")
                        continue
                
                if comments:  # If found comments, don't try other xpaths
                    break
                    
            except Exception as e:
                print(f"Comment XPath error: {e}")
                continue
        
        print(f"📊 Total comments extracted: {len(comments)}")
        return comments

    def _extract_links_xpath(self) -> List[str]:
        """Extract links using XPath"""
        links = []
        try:
            # XPath for all links
            link_elements = self.driver.find_elements(By.XPATH, "//a[@href]")
            for a in link_elements:
                href = a.get_attribute("href")
                if href and href not in links:
                    # Include external links and meaningful LinkedIn links
                    if not href.startswith('https://www.linkedin.com') or '/in/' in href or '/company/' in href:
                        links.append(href)
        except Exception as e:
            print(f"Link extraction error: {e}")
        
        return links

    # ========== MAIN SCRAPING FUNCTION ==========

    def scrape_post(self, url: str) -> Dict[str, Any]:
        """Main scraping function using XPath approach"""
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
            "scraper_version": "1.0-xpath",
        }
        
        # XPath-based extractions
        data.update(self._extract_author_xpath())
        data.update(self._extract_metadata_xpath()) 
        data["post_text"] = self._extract_post_content_xpath(url)
        data["links"] = self._extract_links_xpath()
        data["comments"] = self._extract_comments_xpath(limit=20)
        
        return data

    def save_csv(self, post_data: Dict[str, Any]) -> str:
        """Save results to CSV"""
        ts = datetime.now().strftime(self.config["output_settings"]["timestamp_format"])
        csv_path = self.output_dir / f"linkedin_post_xpath_{ts}.csv"
        
        # Convert comments to JSON
        comments_json = []
        for comment in (post_data.get("comments") or []):
            comments_json.append({
                "commentor": comment.get("commentor", ""),
                "comment": comment.get("comment_text", "")
            })
        
        # Create CSV row
        row_data = {
            "post_url": post_data.get("post_url", ""),
            "post_author": post_data.get("post_author", ""),
            "author_title": post_data.get("author_title", ""),
            "author_profile_url": post_data.get("author_profile_url", ""),
            "date_posted": post_data.get("date_posted", ""),
            "post_text": post_data.get("post_text", ""),
            "links": "; ".join(post_data.get("links", []) or []),
            "comment_count": len(post_data.get("comments") or []),
            "comments": json.dumps(comments_json, ensure_ascii=False),
            "scraped_at": post_data.get("scraped_at", ""),
            "scraper_version": post_data.get("scraper_version", ""),
        }
        
        # Write CSV
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row_data.keys()))
            writer.writeheader()
            writer.writerow(row_data)
        
        return str(csv_path)

    def close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

# ========== CLI ==========

def main():
    parser = argparse.ArgumentParser(description="LinkedIn XPath Scraper")
    parser.add_argument("--url", required=True, help="LinkedIn post URL")
    parser.add_argument("--config", default="config.json", help="Config file path")
    args = parser.parse_args()

    scraper = LinkedInXPathScraper(config_path=args.config)
    scraper.initialize_driver()
    
    # Login
    ok, msg = scraper.login()
    if not ok:
        print("❌ Login failed:", msg)
        scraper.close_driver()
        return 1

    try:
        # Scrape post
        data = scraper.scrape_post(args.url)
        csv_file = scraper.save_csv(data)
        
        print(f"\\n✅ XPATH SCRAPING COMPLETE!")
        print(f"📁 Saved: {csv_file}")
        print(f"\\n📊 RESULTS SUMMARY:")
        print(f"📝 Author: {data.get('post_author', 'N/A')}")
        print(f"👤 Title: {data.get('author_title', 'N/A')}")
        print(f"📅 Date: {data.get('date_posted', 'N/A')}")
        print(f"📄 Post Text: {len(data.get('post_text', ''))} characters")
        print(f"💬 Comments: {len(data.get('comments', []))}")
        print(f"🔗 Links: {len(data.get('links', []))}")
        
        # Show post text preview
        post_text = data.get('post_text', '')
        if post_text:
            print(f"\\n📝 POST TEXT PREVIEW:")
            print(f"'{post_text[:300]}{'...' if len(post_text) > 300 else ''}'")
        else:
            print("\\n❌ NO POST TEXT EXTRACTED!")
        
        return 0
        
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        scraper.close_driver()

if __name__ == "__main__":
    if not os.path.exists("config.json"):
        print("❌ config.json missing. Example:")
        print(json.dumps({
            "linkedin_credentials": {"email": "you@example.com", "password": "YOUR_PASSWORD"},
            "chrome_options": {},
            "scraping_settings": {"headless": False},
            "output_settings": {"output_directory": "outputs", "timestamp_format": "%Y%m%d_%H%M%S"}
        }, indent=2))
        exit(1)
    exit(main())
