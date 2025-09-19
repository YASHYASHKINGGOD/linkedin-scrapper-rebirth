#!/usr/bin/env python3
"""
LinkedIn Selenium Scraper (Patched Single File)

- Correct author/title/date extraction from entity lockup
- Full link capture from commentary (including LinkedIn URLs)
- Joined multi-segment post content
- Comment extraction aligned to LinkedIn's HTML
- CSV includes 'links' column
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

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# ---------------- Logging ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("scraper.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class LinkedInSeleniumScraper:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None

        self.output_dir = Path(self.config["output_settings"]["output_directory"])
        self.output_dir.mkdir(exist_ok=True)

    # ---------- Setup ----------
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        with open(config_path, "r") as f:
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
        config["chrome_options"].setdefault("window_size", [1280, 900])

        config.setdefault("scraping_settings", {})
        config["scraping_settings"].setdefault("headless", False)
        config["scraping_settings"].setdefault("implicit_wait_timeout", 5)
        config["scraping_settings"].setdefault("page_load_timeout", 45)
        config["scraping_settings"].setdefault("explicit_wait_timeout", 20)
        config["scraping_settings"].setdefault("random_delay_range", [0.8, 1.6])

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

        chrome_options.add_experimental_option(
            "excludeSwitches", ["enable-automation"]
        )
        chrome_options.add_experimental_option("useAutomationExtension", False)

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        driver.implicitly_wait(self.config["scraping_settings"]["implicit_wait_timeout"])
        driver.set_page_load_timeout(self.config["scraping_settings"]["page_load_timeout"])
        return driver

    def _random_delay(self, lo=None, hi=None):
        if lo is None or hi is None:
            lo, hi = self.config["scraping_settings"]["random_delay_range"]
        time.sleep(random.uniform(lo, hi))

    def initialize_driver(self):
        self.driver = self._setup_chrome_driver()
        self.wait = WebDriverWait(
            self.driver, self.config["scraping_settings"]["explicit_wait_timeout"]
        )
        return True

    def login(self) -> Tuple[bool, str]:
        self.driver.get("https://www.linkedin.com/login")
        self._random_delay()
        user = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
        pw = self.wait.until(EC.presence_of_element_located((By.ID, "password")))
        creds = self.config["linkedin_credentials"]
        user.send_keys(creds["email"])
        pw.send_keys(creds["password"])
        self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
        self._random_delay(2, 3)
        if "feed" in self.driver.current_url:
            return True, "Login successful"
        return False, "Login failed"

    def verify_login_status(self):
        return "feed" in self.driver.current_url

    # ---------- Post helpers ----------
    def _get_post_root(self):
        # Try multiple selectors to find the post root
        selectors = [
            "article[data-activity-urn]",
            "article.main-feed-activity-card", 
            "article",
            ".feed-shared-update-v2"
        ]
        
        for selector in selectors:
            roots = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if roots:
                return roots[0]
        
        raise NoSuchElementException("Could not find post root element")

    def _expand_post_content(self):
        for sel in [
            "[data-test-id='main-feed-activity-card__commentary'] button[aria-label*='more']",
            ".feed-shared-inline-show-more-text button",
        ]:
            btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
            if btns:
                try:
                    btns[0].click()
                    time.sleep(0.3)
                except:
                    pass

    def _extract_post_content(self):
        root = self._get_post_root()
        self._expand_post_content()
        try:
            comm = root.find_element(
                By.CSS_SELECTOR, "[data-test-id='main-feed-activity-card__commentary']"
            )
            segs = comm.find_elements(
                By.CSS_SELECTOR,
                "p.attributed-text-segment-list__content, .attributed-text-segment-list__content",
            )
            return {
                "post_text": "\n".join(
                    [s.get_attribute("innerText") or s.text for s in segs if s.text]
                ).strip()
            }
        except NoSuchElementException:
            return {"post_text": ""}

    def _extract_post_author(self):
        root = self._get_post_root()
        try:
            lock = root.find_element(
                By.CSS_SELECTOR, "[data-test-id='main-feed-activity-card__entity-lockup']"
            )
        except:
            lock = root
        info = {"post_author": "", "author_title": "", "author_profile_url": ""}
        try:
            a = lock.find_element(
                By.CSS_SELECTOR,
                "a[data-tracking-control-name='public_post_feed-actor-name']",
            )
            info["post_author"] = a.text.strip()
            info["author_profile_url"] = a.get_attribute("href")
        except:
            pass
        try:
            p = lock.find_element(By.CSS_SELECTOR, "p.text-color-text-low-emphasis")
            info["author_title"] = p.text.strip()
        except:
            pass
        return info

    def _extract_post_metadata(self):
        root = self._get_post_root()
        try:
            lock = root.find_element(
                By.CSS_SELECTOR, "[data-test-id='main-feed-activity-card__entity-lockup']"
            )
        except:
            lock = root
        try:
            t = lock.find_element(By.CSS_SELECTOR, "time")
            return {"date_posted": t.get_attribute("datetime") or t.text}
        except:
            return {"date_posted": ""}

    def _extract_links(self):
        root = self._get_post_root()
        try:
            comm = root.find_element(
                By.CSS_SELECTOR, "[data-test-id='main-feed-activity-card__commentary']"
            )
            anchors = comm.find_elements(By.CSS_SELECTOR, "a[href]")
            return list({a.get_attribute("href") for a in anchors if a.get_attribute("href")})
        except:
            return []

    def _extract_images(self):
        root = self._get_post_root()
        imgs = root.find_elements(
            By.CSS_SELECTOR, "ul[data-test-id='feed-images-content'] img"
        )
        return [{"url": i.get_attribute("src"), "alt": i.get_attribute("alt")} for i in imgs]

    def _extract_comments(self, limit=10):
        root = self._get_post_root()
        comments = []
        for c in root.find_elements(By.CSS_SELECTOR, "section.comment")[:limit]:
            d = {}
            try:
                d["commentor"] = c.find_element(By.CSS_SELECTOR, "a.comment__author").text
            except:
                d["commentor"] = ""
            try:
                d["commentor_title"] = c.find_element(
                    By.CSS_SELECTOR, "p.comment__author-headline"
                ).text
            except:
                d["commentor_title"] = ""
            try:
                d["comment_text"] = c.find_element(
                    By.CSS_SELECTOR, "p.comment__text"
                ).text
            except:
                d["comment_text"] = ""
            comments.append(d)
        return comments

    # ---------- Main ----------
    def scrape_post(self, url: str):
        self.driver.get(url)
        self._random_delay(1, 2)
        
        # Wait for any of these elements to appear
        try:
            self.wait.until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-activity-urn]")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article.main-feed-activity-card")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
                )
            )
        except TimeoutException:
            logger.error("Could not find article element - page may not have loaded properly")
            raise
        
        data = {
            "post_url": url,
            "scraped_at": datetime.now().isoformat(),
            "scraper_version": "1.1",
        }
        data.update(self._extract_post_content())
        data.update(self._extract_post_author())
        data.update(self._extract_post_metadata())
        data["links"] = self._extract_links()
        data["images"] = self._extract_images()
        data["comments"] = self._extract_comments()
        return data

    def save_post_data_csv(self, post_data: Dict[str, Any]):
        fn = f"linkedin_post_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        fp = self.output_dir / fn
        row = {
            "post_url": post_data.get("post_url", ""),
            "post_author": post_data.get("post_author", ""),
            "author_title": post_data.get("author_title", ""),
            "author_profile_url": post_data.get("author_profile_url", ""),
            "date_posted": post_data.get("date_posted", ""),
            "post_text": post_data.get("post_text", ""),
            "links": "; ".join(post_data.get("links", [])),
            "image_urls": "; ".join([img["url"] for img in post_data.get("images", [])]),
            "comment_count": len(post_data.get("comments", [])),
        }
        with open(fp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            writer.writeheader()
            writer.writerow(row)
        return str(fp)

    def close_driver(self):
        if self.driver:
            self.driver.quit()


if __name__ == "__main__":
    if not os.path.exists("config.json"):
        print("❌ config.json missing")
        exit(1)
    scraper = LinkedInSeleniumScraper()
    scraper.initialize_driver()
    ok, msg = scraper.login()
    if not ok:
        print("Login failed:", msg)
        exit(1)
    url = input("Enter LinkedIn post URL: ").strip()
    data = scraper.scrape_post(url)
    path = scraper.save_post_data_csv(data)
    print("✅ Data saved to:", path)
    scraper.close_driver()
