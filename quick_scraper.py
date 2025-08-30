#!/usr/bin/env python3

import csv
import json
import time
import logging
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QuickLinkedInScraper:
    def __init__(self):
        self.driver = None
        
    def setup_driver(self):
        """Initialize Chrome driver quickly"""
        chrome_options = Options()
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--user-data-dir=chrome_profile")
        chrome_options.add_argument("--profile-directory=Default")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(2)
        
        # Stealth
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        logger.info("Driver setup complete")
    
    def check_login(self):
        """Check if already logged in"""
        try:
            self.driver.get("https://www.linkedin.com")
            time.sleep(3)
            current_url = self.driver.current_url
            if "feed" in current_url or "/in/" in current_url:
                logger.info("✅ Already logged in!")
                return True
            return False
        except Exception as e:
            logger.error(f"Login check failed: {e}")
            return False
    
    def scrape_post(self, url):
        """Scrape a single LinkedIn post quickly"""
        logger.info(f"🔄 Scraping: {url}")
        
        try:
            self.driver.get(url)
            time.sleep(5)
            
            # Initialize data
            post_data = {
                'url': url,
                'author_name': '',
                'author_title': '',
                'post_text': '',
                'post_date': '',
                'external_links': [],
                'hashtags': [],
                'comments': [],
                'extraction_timestamp': datetime.now().isoformat(),
                'success': False
            }
            
            # Try to click see more
            try:
                see_more = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label*='see more'], .feed-shared-inline-show-more-text__see-more-less-toggle")
                if see_more.is_displayed():
                    self.driver.execute_script("arguments[0].click();", see_more)
                    time.sleep(2)
            except:
                pass
            
            # Extract author name - simple approach
            try:
                author_selectors = [
                    "a[href*='/in/'] span[dir='ltr']",
                    ".feed-shared-actor__name span",
                    "span.hoverable-link-text"
                ]
                
                for selector in author_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            # Skip if in comment section
                            try:
                                element.find_element(By.XPATH, "./ancestor::*[contains(@class, 'comment')]")
                                continue
                            except:
                                pass
                            
                            text = element.get_attribute('textContent').strip()
                            if text and len(text) > 2:
                                # Aggressive duplicate name removal
                                cleaned_name = text
                                
                                # Check for patterns like "John SmithJohn Smith"
                                if len(text) > 10:  # Only check longer names
                                    words = text.split()
                                    if len(words) >= 2:
                                        # Try different duplicate patterns
                                        if len(words) % 2 == 0:
                                            half = len(words) // 2
                                            first_half = ' '.join(words[:half])
                                            second_half = ' '.join(words[half:])
                                            if first_half == second_half:
                                                cleaned_name = first_half
                                        
                                        # Also check for simple repetition like "NameName"
                                        if len(words) == 2 and words[0] == words[1]:
                                            cleaned_name = words[0]
                                        
                                        # Check for character-level repetition
                                        mid = len(text) // 2
                                        if text[:mid] == text[mid:] and mid > 3:
                                            cleaned_name = text[:mid].strip()
                                
                                post_data['author_name'] = cleaned_name
                                break
                        if post_data['author_name']:
                            break
                    except:
                        continue
            except:
                pass
            
            # Extract post text
            try:
                text_selectors = [
                    ".feed-shared-text",
                    ".feed-shared-inline-show-more-text",
                    "[data-tracking-control-name*='text']"
                ]
                
                for selector in text_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            # Skip comments
                            try:
                                element.find_element(By.XPATH, "./ancestor::*[contains(@class, 'comment')]")
                                continue
                            except:
                                pass
                            
                            text = element.get_attribute('textContent').strip()
                            if text and len(text) > len(post_data['post_text']):
                                post_data['post_text'] = text
                        if post_data['post_text']:
                            break
                    except:
                        continue
            except:
                pass
            
            # Extract date
            try:
                time_elements = self.driver.find_elements(By.CSS_SELECTOR, "time, .feed-shared-actor__sub-description")
                for time_element in time_elements:
                    date_text = time_element.get_attribute('textContent').strip()
                    if date_text and ('d' in date_text or 'h' in date_text or 'ago' in date_text):
                        post_data['post_date'] = date_text
                        break
            except:
                pass
            
            # Extract external links and hashtags from post text
            if post_data['post_text']:
                # Find hashtags
                hashtags = re.findall(r'#\w+', post_data['post_text'])
                post_data['hashtags'] = list(set(hashtags))
                
                # Find external links (emails, websites)
                links = []
                # Email links
                emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', post_data['post_text'])
                for email in emails:
                    links.append(f"mailto:{email}")
                
                # URL links from href attributes
                try:
                    link_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href]")
                    for link in link_elements:
                        href = link.get_attribute('href')
                        if href and not href.startswith('https://www.linkedin.com') and not href.startswith('#'):
                            if 'http' in href:
                                links.append(href)
                except:
                    pass
                
                post_data['external_links'] = list(set(links))
            
            # Enhanced comment extraction with CSS selectors and XPath backup
            try:
                # First try to click "Show more comments" if available
                try:
                    show_comments_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                        "button[aria-label*='Show more comments'], .comments-comments-list__show-more-comments-button")
                    for button in show_comments_buttons:
                        if button.is_displayed() and button.is_enabled():
                            self.driver.execute_script("arguments[0].click();", button)
                            time.sleep(1)
                            break
                except:
                    pass
                
                # CSS selectors to try for comment containers
                comment_css_selectors = [
                    "div.comments-comment-item",
                    "article[data-urn*='comment']", 
                    "div[data-urn*='comment']",
                    "div.comments-comment-entity",
                    ".feed-shared-comments .comments-comment-item",
                    "section.comments div[class*='comment']"
                ]
                
                # XPath selectors as backup
                comment_xpath_selectors = [
                    "//div[contains(@class, 'comments-comment-item')]",
                    "//article[contains(@data-urn, 'comment')]",
                    "//div[contains(@class, 'comments-comment-entity')]",
                    "//div[contains(@class, 'feed-shared-comments')]//div[contains(@class, 'comment')]",
                    "//section[contains(@class, 'comments')]//div[contains(@class, 'comment-item')]"
                ]
                
                comment_elements = []
                
                # Try CSS selectors first
                for css_selector in comment_css_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, css_selector)
                        if elements:
                            comment_elements = elements[:5]  # Limit to 5 comments
                            logger.info(f"Found {len(comment_elements)} comments with CSS: {css_selector}")
                            break
                    except:
                        continue
                
                # If no comments found with CSS, try XPath
                if not comment_elements:
                    for xpath_selector in comment_xpath_selectors:
                        try:
                            elements = self.driver.find_elements(By.XPATH, xpath_selector)
                            if elements:
                                comment_elements = elements[:5]
                                logger.info(f"Found {len(comment_elements)} comments with XPath: {xpath_selector}")
                                break
                        except:
                            continue
                
                if comment_elements:
                    for i, comment_elem in enumerate(comment_elements, 1):
                        try:
                            # Initialize comment data with all 4 required fields
                            comment_data = {
                                'commentor_name': '',
                                'commentor_title': '',
                                'comment_time': '',
                                'comment_text': ''
                            }
                            
                            # Get all text from the comment element for analysis
                            full_text = comment_elem.get_attribute('textContent').strip()
                            logger.info(f"\n=== COMMENT {i} RAW TEXT ===")
                            logger.info(f"Full text: {repr(full_text)}")
                            
                            # Split into lines for structured parsing
                            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                            logger.info(f"Lines parsed: {repr(lines)}")
                            
                            # Method 1: Try specific selectors first with improved logic
                            try:
                                # Find all anchor elements that might contain user profiles
                                profile_links = comment_elem.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
                                
                                # Extract commentor name from profile links
                                for profile_link in profile_links:
                                    try:
                                        # Try different ways to get the name from the profile link
                                        name_candidates = []
                                        
                                        # Method 1: Get text from span elements within the link
                                        spans = profile_link.find_elements(By.TAG_NAME, "span")
                                        for span in spans:
                                            span_text = span.get_attribute('textContent').strip()
                                            if span_text and len(span_text) < 100 and ' ' in span_text:
                                                name_candidates.append(span_text)
                                        
                                        # Method 2: Get text directly from the link
                                        link_text = profile_link.get_attribute('textContent').strip()
                                        if link_text and len(link_text) < 100 and ' ' in link_text:
                                            name_candidates.append(link_text)
                                        
                                        # Choose the best candidate (longest reasonable name)
                                        for name_candidate in sorted(name_candidates, key=len, reverse=True):
                                            if (len(name_candidate) > 3 and 
                                                not name_candidate.lower().startswith('http') and
                                                not name_candidate.isdigit()):
                                                
                                                # Clean duplicate names
                                                words = name_candidate.split()
                                                if len(words) >= 2 and len(words) % 2 == 0:
                                                    half = len(words) // 2
                                                    if ' '.join(words[:half]) == ' '.join(words[half:]):
                                                        comment_data['commentor_name'] = ' '.join(words[:half])
                                                    else:
                                                        comment_data['commentor_name'] = name_candidate
                                                else:
                                                    comment_data['commentor_name'] = name_candidate
                                                break
                                        
                                        if comment_data['commentor_name']:
                                            break
                                    except:
                                        continue
                                
                                # If no name from profile links, try other selectors
                                if not comment_data['commentor_name']:
                                    name_selectors = [
                                        ".comments-post-meta__name-text",
                                        ".hoverable-link-text", 
                                        ".feed-shared-actor__name span",
                                        "[data-tracking-control-name*='actor'] span"
                                    ]
                                    
                                    for name_sel in name_selectors:
                                        try:
                                            name_elem = comment_elem.find_element(By.CSS_SELECTOR, name_sel)
                                            name_text = name_elem.get_attribute('textContent').strip()
                                            if name_text and len(name_text) < 100 and len(name_text) > 3:
                                                comment_data['commentor_name'] = name_text
                                                break
                                        except:
                                            continue
                                
                                # Extract commentor title/description
                                title_selectors = [
                                    ".feed-shared-actor__description",
                                    ".comments-post-meta__headline",
                                    ".t-12.t-normal",
                                    "[data-tracking-control-name*='headline']"
                                ]
                                
                                for title_sel in title_selectors:
                                    try:
                                        title_elem = comment_elem.find_element(By.CSS_SELECTOR, title_sel)
                                        title_text = title_elem.get_attribute('textContent').strip()
                                        if (title_text and 
                                            title_text != comment_data['commentor_name'] and
                                            len(title_text) > 10 and len(title_text) < 200):
                                            comment_data['commentor_title'] = title_text
                                            break
                                    except:
                                        continue
                                
                                # Extract comment time
                                time_selectors = [
                                    "time",
                                    ".feed-shared-actor__sub-description",
                                    "[data-tracking-control-name*='timestamp']",
                                    "[aria-label*='ago']"
                                ]
                                
                                for time_sel in time_selectors:
                                    try:
                                        time_elem = comment_elem.find_element(By.CSS_SELECTOR, time_sel)
                                        time_text = time_elem.get_attribute('textContent').strip()
                                        if time_text and ('ago' in time_text or 'h' in time_text or 'd' in time_text or 'w' in time_text or 'm' in time_text):
                                            comment_data['comment_time'] = time_text
                                            break
                                    except:
                                        continue
                                
                                # Extract comment text - more sophisticated approach
                                text_selectors = [
                                    ".feed-shared-text",
                                    ".attributed-text-segment-list__content",
                                    ".comments-comment-item__main-content .feed-shared-text",
                                    "[data-tracking-control-name*='comment_text']"
                                ]
                                
                                for text_sel in text_selectors:
                                    try:
                                        text_elem = comment_elem.find_element(By.CSS_SELECTOR, text_sel)
                                        comment_text = text_elem.get_attribute('textContent').strip()
                                        if (comment_text and 
                                            comment_text != comment_data['commentor_name'] and
                                            comment_text != comment_data['commentor_title'] and
                                            len(comment_text) > 2 and
                                            'Like' not in comment_text and 'Reply' not in comment_text):
                                            comment_data['comment_text'] = comment_text
                                            break
                                    except:
                                        continue
                                        
                            except Exception as e:
                                logger.debug(f"Selector method failed: {e}")
                            
                            # Method 2: Improved fallback text parsing if selectors failed
                            if not any([comment_data['commentor_name'], comment_data['comment_text']]):
                                try:
                                    logger.info(f"Using fallback parsing for comment {i}")
                                    
                                    # Special handling for single-line comments
                                    if len(lines) == 1 and lines[0]:
                                        single_line = lines[0]
                                        
                                        # Case 1: Short text likely to be just comment (like "CFBR", "Interested")
                                        if len(single_line) <= 50 and not ' ' in single_line:
                                            # This is likely just a comment text without clear name
                                            comment_data['comment_text'] = single_line
                                            logger.info(f"Single short word treated as comment: '{single_line}'")
                                        
                                        # Case 2: Looks like a person's name (2-3 words, reasonable length)
                                        elif (len(single_line.split()) >= 2 and 
                                              len(single_line.split()) <= 4 and 
                                              len(single_line) < 60 and 
                                              not single_line.lower().startswith(('http', 'www', 'thanks', 'interested', 'great', 'cfbr'))):
                                            comment_data['commentor_name'] = single_line
                                            logger.info(f"Single line treated as name: '{single_line}'")
                                        
                                        # Case 3: Long text, likely comment content
                                        else:
                                            comment_data['comment_text'] = single_line
                                            logger.info(f"Long single line treated as comment: '{single_line[:50]}...'")
                                    
                                    # Multi-line parsing
                                    elif len(lines) > 1:
                                        # Try to identify name in first few lines
                                        for idx, line in enumerate(lines[:3]):  # Check first 3 lines for name
                                            if (not comment_data['commentor_name'] and 
                                                len(line.split()) >= 2 and len(line.split()) <= 4 and
                                                len(line) < 60 and 
                                                not line.lower().startswith(('http', 'www', 'thanks', 'interested'))):
                                                comment_data['commentor_name'] = line
                                                break
                                        
                                        # Look for comment text in the longest line that's not the name
                                        longest_line = max(lines, key=len)
                                        if (longest_line != comment_data['commentor_name'] and 
                                            len(longest_line) > 10):
                                            comment_data['comment_text'] = longest_line
                                        
                                        # Look for time stamps and titles in remaining lines
                                        for line in lines:
                                            line = line.strip()
                                            
                                            # Skip if this is already identified as name or text
                                            if line == comment_data['commentor_name'] or line == comment_data['comment_text']:
                                                continue
                                            
                                            # Check if this is a time indicator
                                            if (not comment_data['comment_time'] and 
                                                (line.endswith('ago') or line.endswith('h') or 
                                                 line.endswith('d') or line.endswith('w') or
                                                 line.endswith('m') or 'edited' in line.lower())):
                                                comment_data['comment_time'] = line
                                                continue
                                            
                                            # Check if this is a title/description
                                            if (not comment_data['commentor_title'] and 
                                                len(line) > 20 and len(line) < 200 and
                                                ('at ' in line.lower() or '@' in line or 
                                                 'manager' in line.lower() or 'head' in line.lower() or
                                                 'specialist' in line.lower() or 'director' in line.lower() or
                                                 'engineer' in line.lower() or 'analyst' in line.lower())):
                                                comment_data['commentor_title'] = line
                                                continue
                                                
                                except Exception as e:
                                    logger.debug(f"Fallback parsing failed: {e}")
                            
                            # Log what we extracted
                            logger.info(f"\n📝 Comment {i} extracted:")
                            logger.info(f"   Name: '{comment_data['commentor_name']}'")
                            logger.info(f"   Title: '{comment_data['commentor_title']}'")
                            logger.info(f"   Time: '{comment_data['comment_time']}'")
                            logger.info(f"   Text: '{comment_data['comment_text']}'")
                            
                            # Add comment if we extracted any meaningful data
                            if (comment_data['commentor_name'] or 
                                comment_data['comment_text'] or 
                                comment_data['commentor_title']):
                                post_data['comments'].append(comment_data)
                                logger.info(f"✅ Added comment {i} to results")
                            else:
                                logger.warning(f"⚠️ Comment {i} had no extractable data")
                            
                        except Exception as e:
                            logger.error(f"Failed to extract comment {i}: {e}")
                            continue
                else:
                    logger.info("No comment elements found")
                    
            except Exception as e:
                logger.debug(f"Comment extraction failed: {e}")
            
            # Mark as successful if we got some data
            if post_data['author_name'] or post_data['post_text']:
                post_data['success'] = True
                logger.info(f"✅ Successfully scraped post by {post_data['author_name']}")
            else:
                logger.warning(f"⚠️ Limited data extracted from {url}")
            
            return post_data
            
        except Exception as e:
            logger.error(f"❌ Failed to scrape {url}: {e}")
            post_data['success'] = False
            post_data['error'] = str(e)
            return post_data
    
    def scrape_urls(self, urls):
        """Scrape multiple URLs"""
        results = []
        
        try:
            self.setup_driver()
            
            if not self.check_login():
                logger.error("Not logged in! Please login first.")
                return []
            
            for i, url in enumerate(urls, 1):
                logger.info(f"\n📋 Processing post {i}/{len(urls)}")
                result = self.scrape_post(url)
                results.append(result)
                
                # Delay between posts
                if i < len(urls):
                    logger.info("Waiting 3 seconds...")
                    time.sleep(3)
                
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
        
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Browser closed")
        
        return results
    
    def save_to_csv(self, results, filename=None):
        """Save results to CSV"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"outputs/quick_linkedin_scrape_{timestamp}.csv"
        
        os.makedirs('outputs', exist_ok=True)
        
        fieldnames = [
            'url', 'author_name', 'author_title', 'post_text', 'post_date',
            'external_links', 'hashtags', 'comments_json', 'comments_count',
            'extraction_timestamp', 'success', 'error'
        ]
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for result in results:
                    csv_row = result.copy()
                    
                    # Convert lists to strings
                    csv_row['external_links'] = '; '.join(result.get('external_links', []))
                    csv_row['hashtags'] = '; '.join(result.get('hashtags', []))
                    csv_row['comments_json'] = json.dumps(result.get('comments', []), ensure_ascii=False)
                    csv_row['comments_count'] = len(result.get('comments', []))
                    
                    # Remove the original list fields
                    csv_row.pop('external_links', None)
                    csv_row.pop('hashtags', None)
                    csv_row.pop('comments', None)
                    
                    writer.writerow(csv_row)
            
            logger.info(f"✅ Results saved to: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"❌ Failed to save CSV: {e}")
            return None

def main():
    # The 3 URLs you want to scrape
    urls = [
        "https://www.linkedin.com/posts/dipti-pandey-9a24a022a_hiring-productmanager-fintechjobs-activity-7365994755303854080-G80a?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ",
        "https://www.linkedin.com/posts/aaliya-baxamusa-01641a138_hiring-techjobs-productjobs-activity-7366002358796890112-qgAw?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ",
        "https://www.linkedin.com/posts/activity-7365981559994187777-tUdn?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ"
    ]
    
    logger.info(f"🚀 Quick LinkedIn scraper starting for {len(urls)} posts")
    
    scraper = QuickLinkedInScraper()
    results = scraper.scrape_urls(urls)
    
    if results:
        filename = scraper.save_to_csv(results)
        
        # Print summary
        successful = sum(1 for r in results if r.get('success', False))
        logger.info(f"\n📊 SUMMARY:")
        logger.info(f"✅ Successful: {successful}/{len(urls)}")
        logger.info(f"📄 Output file: {filename}")
        
        # Print brief results
        for i, result in enumerate(results, 1):
            status = "✅" if result.get('success') else "❌"
            author = result.get('author_name', 'Unknown')
            logger.info(f"{status} Post {i}: {author}")
        
        return filename
    else:
        logger.error("❌ No results obtained")
        return None

if __name__ == "__main__":
    main()
