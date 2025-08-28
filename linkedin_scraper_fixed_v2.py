#!/usr/bin/env python3
"""
LinkedIn Selenium Scraper (Fixed v2, single file)

Key fixes for your case:
- Author/Title/Content are now located with selectors that match your CSS dump,
  and everything is *scoped to the same post root* to avoid cross-capture.
- Post content handles the case where data-test-id="main-feed-activity-card__commentary"
  is on the <p> itself (as in your file).
- Links are collected from commentary (including LinkedIn URLs).
- Comments are reliably loaded by clicking the "Comments" social action and
  then reading <section class="comment"> blocks; supports "More comments".
- Outputs TWO CSVs: one for the post (summary) and one for comments (detail).

Usage:
  1) Create config.json with your credentials and output dir.
  2) python linkedin_scraper_fixed_v2.py --url "<post permalink>"
"""

import json
import logging
import random
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import os
from datetime import datetime
import csv
import argparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager

# ---------------- Logging ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("scraper.log"), logging.StreamHandler()],
)
logger = logging.getLogger("linkedin-scraper-fixed-v2")


class LinkedInSeleniumScraper:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None

        self.output_dir = Path(self.config["output_settings"]["output_directory"])
        self.output_dir.mkdir(exist_ok=True, parents=True)

    # ---------- Setup ----------
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # defaults
        config.setdefault("chrome_options", {})
        config["chrome_options"].setdefault(
            "disable_automation_flags",
            [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        config["chrome_options"].setdefault(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        )
        config["chrome_options"].setdefault("window_size", [1366, 900])

        config.setdefault("scraping_settings", {})
        config["scraping_settings"].setdefault("headless", False)
        config["scraping_settings"].setdefault("implicit_wait_timeout", 5)
        config["scraping_settings"].setdefault("page_load_timeout", 45)
        config["scraping_settings"].setdefault("explicit_wait_timeout", 20)
        config["scraping_settings"].setdefault("random_delay_range", [0.7, 1.4])

        config.setdefault("output_settings", {})
        config["output_settings"].setdefault("output_directory", "outputs")
        config["output_settings"].setdefault("timestamp_format", "%Y%m%d_%H%M%S")
        return config

    def _setup_chrome_driver(self) -> webdriver.Chrome:
        chrome_options = Options()
        for flag in self.config["chrome_options"]["disable_automation_flags"]:
            chrome_options.add_argument(flag)
        ua = self.config["chrome_options"]["user_agent"]
        chrome_options.add_argument(f"--user-agent={ua}")
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

    def _random_delay(self, lo=None, hi=None):
        if lo is None or hi is None:
            lo, hi = self.config["scraping_settings"]["random_delay_range"]
        time.sleep(random.uniform(lo, hi))

    def initialize_driver(self):
        self.driver = self._setup_chrome_driver()
        self.wait = WebDriverWait(self.driver, self.config["scraping_settings"]["explicit_wait_timeout"])
        return True

    def login(self) -> Tuple[bool, str]:
        self.driver.get("https://www.linkedin.com/login")
        self._random_delay()
        user = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
        pw = self.wait.until(EC.presence_of_element_located((By.ID, "password")))
        creds = self.config["linkedin_credentials"]
        user.clear(); user.send_keys(creds["email"])
        pw.clear(); pw.send_keys(creds["password"])
        self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
        self._random_delay(2, 3.2)
        if any(k in self.driver.current_url for k in ("feed", "mynetwork", "jobs", "/in/", "messaging")):
            return True, "Login successful"
        return False, f"Login failed or verification needed: {self.driver.current_url}"

    def verify_login_status(self):
        return any(k in self.driver.current_url for k in ("feed", "mynetwork", "jobs", "/in/", "messaging"))

    # ---------- Post helpers ----------
    def _get_post_root(self):
        # Try multiple root selectors based on different LinkedIn post page structures
        root_selectors = [
            ".feed-shared-update-v2",  # Standard feed post
            "article",                    # Fallback article elements
            "main",                       # Main content container
            "[data-test-id*='main-feed']", # Any main feed element
            "body"                        # Ultimate fallback - entire body
        ]
        
        for selector in root_selectors:
            roots = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if roots:
                print(f"✅ Using post root: {selector}")
                return roots[0]
                
        raise NoSuchElementException("Post root element not found")

    def _scroll_into_view(self, el):
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
        except Exception:
            pass

    def _expand_post_content(self):
        # Click common 'show more' for post text - improved for different post types
        show_more_selectors = [
            "[data-test-id='main-feed-activity-card__commentary'] button[aria-label*='more']",
            ".update-components-text .inline-show-more-text__button",
            ".feed-shared-inline-show-more-text button",
            "button[aria-label*='see more']",
            "button[aria-label*='more']",
        ]
        
        for sel in show_more_selectors:
            btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
            if btns:
                try:
                    self._scroll_into_view(btns[0])
                    btns[0].click()
                    time.sleep(0.5)  # Give slightly more time for content to load
                    print(f"✅ Expanded post content using selector: {sel}")
                    break
                except Exception as e:
                    print(f"⚠️ Failed to click show more with {sel}: {e}")
                    continue

    def _open_comments(self, root):
        # Click the "Comments" social action if present to load the thread
        try:
            comments_link = root.find_element(By.CSS_SELECTOR, "[data-test-id='social-actions__comments']")
            self._scroll_into_view(comments_link)
            try:
                comments_link.click()
            except (ElementClickInterceptedException, StaleElementReferenceException):
                self.driver.execute_script("arguments[0].click();", comments_link)
            time.sleep(0.6)
        except NoSuchElementException:
            pass

    def _load_more_comments_if_any(self, max_clicks=3):
        # Try to click "More comments" a few times
        for _ in range(max_clicks):
            expanded = False
            for sel in [
                "button[aria-label*='more comments']",
                "a[data-test-id*='see-more-comments']",
                "button[aria-label*='Load more comments']",
            ]:
                btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if btns:
                    try:
                        self._scroll_into_view(btns[0])
                        btns[0].click()
                        time.sleep(0.8)
                        expanded = True
                        break
                    except Exception:
                        continue
            if not expanded:
                break

    # ---------- Extraction ----------
    def _extract_post_author(self) -> Dict[str, str]:
        root = self._get_post_root()
        info = {"post_author": "", "author_title": "", "author_profile_url": ""}
        
        # Look for author info within the post root using broader selectors
        # Based on debug: a[href*='/in/'] elements exist
        try:
            # Try to find profile links within the post (not comments)
            profile_links = root.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
            for link in profile_links:
                text = (link.text or "").strip()
                # Look for meaningful author text (not empty, has actual name)
                if text and len(text.split()) >= 1 and len(text) > 3:
                    # Extract just the name (first line)
                    author_name = text.split('\n')[0].strip()
                    if author_name and not any(skip in author_name.lower() for skip in ['student', 'see more', 'like', 'comment']):
                        info["post_author"] = author_name
                        info["author_profile_url"] = link.get_attribute("href") or ""
                        break
        except Exception:
            pass
        
        # Fix: Use the exact selector you provided for author title
        try:
            # Use simpler selectors that will work with CSS escaping
            title_selectors = [
                "p.text-color-text-low-emphasis.truncate",
                "p.text-color-text-low-emphasis",
                ".feed-shared-actor__description",
                ".feed-shared-actor__sub-description",
                "p[class*='text-color-text-low-emphasis']"
            ]
            
            for sel in title_selectors:
                elements = root.find_elements(By.CSS_SELECTOR, sel)
                for el in elements:
                    text = (el.text or "").strip()
                    # Filter out timestamps and other non-title text
                    if text and len(text) < 200 and not any(skip in text.lower() for skip in ['ago', 'hour', 'day', 'week', 'month']):
                        info["author_title"] = text
                        break
                if info["author_title"]:
                    break
        except Exception:
            pass

        return info

    def _extract_post_metadata(self) -> Dict[str, str]:
        root = self._get_post_root()
        try:
            # Look for time elements anywhere in the post
            t = root.find_element(By.CSS_SELECTOR, "time")
            return {"date_posted": t.get_attribute("datetime") or (t.text or "").strip()}
        except NoSuchElementException:
            # Fallback: look for text that looks like timestamps
            try:
                # Look for patterns like "16h", "2d", "1w" in spans
                for span in root.find_elements(By.CSS_SELECTOR, "span"):
                    text = (span.text or "").strip()
                    if text and ('h' in text or 'd' in text or 'w' in text or 'ago' in text) and len(text) < 20:
                        return {"date_posted": text}
                return {"date_posted": ""}
            except Exception:
                return {"date_posted": ""}

    def _extract_post_content(self) -> Dict[str, str]:
        root = self._get_post_root()
        self._expand_post_content()

        # Fix: Extract ONLY the main post content, excluding comments
        texts = []
        
        # Look for the main post content area - exclude comment areas
        # Updated selectors to handle different LinkedIn DOM variants
        content_selectors = [
            # Specific selector for posts like Artika's - highest priority
            "p[data-test-id='main-feed-activity-card__commentary']",
            ".feed-shared-text",
            "[data-test-id='main-feed-activity-card__commentary']",
            "[data-test-id*='commentary'] .attributed-text-segment-list__content", 
            ".update-components-text span.break-words",
            ".update-components-text",
            ".feed-shared-update-v2__commentary",
            ".feed-shared-update-v2__description .attributed-text-segment-list__content",
            ".feed-shared-update-v2__description",
            # Additional specific selector that was working in debug
            "p.attributed-text-segment-list__content"
        ]
        
        for selector in content_selectors:
            elements = root.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                # Check if this element is inside a comment section (not main post commentary)
                try:
                    # Be more specific - look for actual comment containers, not just "comment" in class
                    parent_comment = el.find_element(By.XPATH, "./ancestor::*[contains(@class, 'comment') and not(contains(@class, 'commentary'))]")
                    # Also check for specific comment container patterns
                    comment_containers = [
                        "./ancestor::article[contains(@data-id, 'comment')]",
                        "./ancestor::*[contains(@class, 'comments-post-meta')]",
                        "./ancestor::section[contains(@class, 'comment')]"
                    ]
                    is_in_comment = False
                    for xpath in comment_containers:
                        try:
                            comment_container = el.find_element(By.XPATH, xpath)
                            if comment_container:
                                is_in_comment = True
                                break
                        except:
                            continue
                    
                    if parent_comment or is_in_comment:  # Skip if inside a comment
                        continue
                except NoSuchElementException:
                    pass  # Not inside a comment, continue processing
                    
                text = (el.get_attribute("innerText") or el.text or "").strip()
                # Filter out short texts, author names, timestamps, etc.
                if text and len(text) > 15:
                    # Remove common non-content patterns
                    if not any(skip in text.lower() for skip in [
                        '• 3rd+', 'hours ago', 'minutes ago', 'days ago', 'weeks ago',
                        'like this', 'comment', 'repost', 'share', 'send',
                        'thanks for posting', 'cfbr', 'commenting for'
                    ]):
                        if text not in texts:
                            texts.append(text)
        
        # Clean up and join the post text
        post_text = "\n\n".join(texts).strip()
        
        # Remove hashtag sections and everything after them if they appear at the end
        lines = post_text.split('\n')
        clean_lines = []
        hashtag_started = False
        
        for line in lines:
            line = line.strip()
            # If we hit a line that's just "hashtag" or starts with hashtags, stop including content
            if line == 'hashtag' or (line.startswith('#') and len(line.split()) == 1):
                hashtag_started = True
                break
            if not hashtag_started:
                clean_lines.append(line)
        
        return {"post_text": "\n".join(clean_lines).strip()}

    def _extract_links(self) -> List[str]:
        root = self._get_post_root()
        links = []
        # Look for all links in the post content area
        for a in root.find_elements(By.CSS_SELECTOR, "a[href]"):
            href = (a.get_attribute("href") or "").strip()
            # Filter out LinkedIn internal links that aren't profile links
            if href and href not in links:
                # Include external links and meaningful LinkedIn links
                if not href.startswith('https://www.linkedin.com') or '/in/' in href or '/company/' in href:
                    links.append(href)
        return links

    def _extract_images(self) -> List[Dict[str, str]]:
        root = self._get_post_root()
        out = []
        for img in root.find_elements(By.CSS_SELECTOR, "ul[data-test-id='feed-images-content'] img"):
            src = img.get_attribute("src") or ""
            alt = img.get_attribute("alt") or ""
            if src and not any(i["url"] == src for i in out):
                out.append({"url": src, "alt": alt})
        return out

    def _extract_comments(self, limit=5) -> List[Dict[str, str]]:
        # Fix: Extract comments using correct selectors from debug findings
        root = self._get_post_root()
        
        # Click on comments to expand them
        try:
            comment_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='comment']")
            if comment_buttons:
                print(f"Found {len(comment_buttons)} comment buttons, clicking first one...")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", comment_buttons[0])
                time.sleep(1)
                comment_buttons[0].click()
                time.sleep(4)  # Wait for comments to load
                print("✅ Comments button clicked successfully")
            else:
                print("❌ No comment buttons found")
                return []
        except Exception as e:
            print(f"❌ Failed to click comments button: {e}")
            return []
        
        comments = []
        
        # Use the correct selector found in debug: article[data-id*='comment']
        print("Looking for comment containers with correct selector...")
        comment_elements = self.driver.find_elements(By.CSS_SELECTOR, "article[data-id*='comment']")
        print(f"Found {len(comment_elements)} real comment containers")
        
        for i, comment_el in enumerate(comment_elements[:limit]):
            try:
                # Get the full text content of the comment
                full_text = comment_el.text.strip()
                
                if not full_text or len(full_text) < 10:
                    continue
                
                print(f"\nProcessing comment {i+1}:")
                print(f"Full text: {full_text[:100]}...")
                
                # Extract author name and comment text using line-by-line parsing
                # Based on debug: LinkedIn structure is predictable
                # Line 1: Author Name
                # Line 2: Connection info (• 3rd+)
                # Line 3: Job Title (long)
                # Line 4: Time (4h, 2d, etc.)
                # Line 5: ACTUAL COMMENT TEXT
                # Line 6+: Like, Reply buttons
                
                lines = full_text.split('\n')
                lines = [line.strip() for line in lines if line.strip()]  # Remove empty lines
                
                commentor = ""
                comment_text = ""
                
                if len(lines) >= 5:  # Need at least 5 lines for standard structure
                    # Line 1 should be the author name
                    potential_author = lines[0]
                    if potential_author and len(potential_author) < 50 and not potential_author.isdigit():
                        commentor = potential_author
                    
                    # Find the time indicator line (usually line 4, but could vary)
                    time_line_index = -1
                    for line_idx, line in enumerate(lines):
                        # Time indicators are short and contain h, d, w, m
                        if (len(line) <= 15 and 
                            any(time_char in line for time_char in ['h', 'd', 'w', 'm']) and
                            any(char.isdigit() for char in line)):
                            time_line_index = line_idx
                            break
                    
                    # Comment text should be the line immediately after time
                    if time_line_index != -1 and time_line_index + 1 < len(lines):
                        potential_comment = lines[time_line_index + 1]
                        
                        # Validate this is actually comment text (not action buttons)
                        if (potential_comment and 
                            potential_comment.lower() not in ['like', 'reply', 'share', 'send'] and
                            not potential_comment.isdigit() and
                            len(potential_comment) > 1):
                            comment_text = potential_comment
                
                # Fallback: If structured parsing failed, use simpler approach
                if not commentor or not comment_text:
                    print(f"Fallback parsing for comment {i+1}")
                    
                    # Try to get author from first meaningful line
                    if not commentor and lines:
                        first_line = lines[0]
                        if (first_line and len(first_line) < 50 and 
                            not any(skip in first_line.lower() for skip in ['•', 'followers', 'like', 'reply'])):
                            commentor = first_line
                    
                    # Better comment text detection - find the shortest meaningful line that's not metadata
                    if not comment_text:
                        # Look for short, simple comments first (like "CFBR", "Interested", etc.)
                        short_comments = []
                        long_comments = []
                        
                        for line_idx, line in enumerate(lines[1:], 1):  # Skip first line (author)
                            if (line and len(line) > 1 and len(line) < 500 and
                                not any(skip in line.lower() for skip in [
                                    '• 3rd+', '• 2nd', '• 1st', 'followers', 'connections',
                                    'like', 'reply', 'share', 'send'
                                ]) and
                                not line.isdigit() and
                                not (len(line) <= 15 and any(char in line for char in ['h', 'd', 'w', 'm']))):
                                
                                # Categorize by length and content
                                if len(line) <= 50:  # Short lines more likely to be actual comments
                                    if not (any(job_word in line.lower() for job_word in [
                                        'manager', 'analyst', 'director', 'engineer', 'specialist',
                                        'executive', 'coordinator', 'associate', 'lead', 'head', 'founder'
                                    ]) and len(line) > 20):  # Skip job titles
                                        short_comments.append((line_idx, line))
                                else:  # Longer lines could be detailed comments
                                    if not any(job_word in line.lower() for job_word in [
                                        'manager', 'analyst', 'director', 'engineer', 'specialist'
                                    ]):
                                        long_comments.append((line_idx, line))
                        
                        # Prefer short comments first, then long ones
                        if short_comments:
                            # Take the first short comment that comes after typical metadata
                            comment_text = short_comments[0][1]
                        elif long_comments:
                            # If no short comments, take the first long comment
                            comment_text = long_comments[0][1]
                
                # Final cleanup
                if not commentor:
                    commentor = ""
                if not comment_text:
                    comment_text = ""
                
                print(f"Extracted author: '{commentor}'")
                print(f"Extracted comment: '{comment_text}'")
                
                # Only add if we have either author or meaningful comment
                if commentor or (comment_text and len(comment_text) > 3):
                    comments.append({
                        "commentor": commentor,
                        "comment_text": comment_text[:500]  # Limit comment length
                    })
                    print(f"✅ Added comment #{len(comments)}")
                else:
                    print("❌ Skipped - insufficient data")
                    
            except Exception as e:
                print(f"❌ Failed to extract comment {i+1}: {e}")
                continue
        
        print(f"\nTotal comments extracted: {len(comments)}")
        return comments

    # ---------- Main ----------
    def scrape_post(self, url: str):
        self.driver.get(url)
        self._random_delay(1, 2)
        self.wait.until(EC.any_of(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".feed-shared-update-v2")),
            EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
        ))
        data = {
            "post_url": url,
            "scraped_at": datetime.now().isoformat(),
            "scraper_version": "1.2",
        }
        data.update(self._extract_post_author())
        data.update(self._extract_post_metadata())
        data.update(self._extract_post_content())
        data["links"] = self._extract_links()
        data["images"] = self._extract_images()
        data["comments"] = self._extract_comments(limit=50)
        return data

    # ---------- Save ----------
    def save_csvs(self, post_data: Dict[str, Any]):
        ts = datetime.now().strftime(self.config["output_settings"]["timestamp_format"])
        
        # Fix: Save everything in a single CSV with comments as JSON column
        single_fp = self.output_dir / f"linkedin_post_{ts}.csv"
        
        # Convert comments to JSON format as requested
        comments_json = []
        for comment in (post_data.get("comments") or []):
            comments_json.append({
                "commentor": comment.get("commentor", ""),
                "comment": comment.get("comment_text", "")
            })
        
        # Single CSV with all data including comments as JSON
        post_row = {
            "post_url": post_data.get("post_url", ""),
            "post_author": post_data.get("post_author", ""),
            "author_title": post_data.get("author_title", ""),
            "author_profile_url": post_data.get("author_profile_url", ""),
            "date_posted": post_data.get("date_posted", ""),
            "post_text": post_data.get("post_text", ""),
            "links": "; ".join(post_data.get("links", []) or []),
            "image_urls": "; ".join([img.get("url","") for img in (post_data.get("images") or [])]),
            "comment_count": len(post_data.get("comments") or []),
            "comments": json.dumps(comments_json, ensure_ascii=False),  # Comments as JSON string
            "scraped_at": post_data.get("scraped_at", ""),
            "scraper_version": post_data.get("scraper_version", ""),
        }
        
        with open(single_fp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(post_row.keys()))
            writer.writeheader(); writer.writerow(post_row)
        
        return str(single_fp), str(single_fp)  # Return same file path twice for compatibility

    def close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="LinkedIn post permalink URL")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    args = parser.parse_args()

    scraper = LinkedInSeleniumScraper(config_path=args.config)
    scraper.initialize_driver()
    ok, msg = scraper.login()
    if not ok:
        print("❌ Login failed:", msg)
        scraper.close_driver()
        raise SystemExit(1)

    data = scraper.scrape_post(args.url)
    csv_file, _ = scraper.save_csvs(data)
    print("✅ Saved:", csv_file)
    
    # Print summary of extracted data
    print(f"\n📊 EXTRACTION SUMMARY:")
    print(f"📝 Post Author: {data.get('post_author', 'N/A')}")
    print(f"👤 Author Title: {data.get('author_title', 'N/A')}")
    print(f"📅 Date Posted: {data.get('date_posted', 'N/A')}")
    print(f"💬 Comments: {len(data.get('comments', []))}")
    print(f"🔗 Links: {len(data.get('links', []))}")
    
    scraper.close_driver()

if __name__ == "__main__":
    if not os.path.exists("config.json"):
        print("❌ config.json missing. Example:")
        print(json.dumps({
            "linkedin_credentials": {"email": "you@example.com", "password": "YOUR_PASSWORD"},
            "chrome_options": {},
            "scraping_settings": {"headless": False},
            "output_settings": {"output_directory": "output", "timestamp_format": "%Y%m%d_%H%M%S"}
        }, indent=2))
        raise SystemExit(1)
    main()
