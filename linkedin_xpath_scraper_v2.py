#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinkedIn Post Scraper (XPath-First, Single File)

- Logs in and scrapes one or more LinkedIn post permalinks.
- Uses robust XPath selectors (fallback CSS only when unavoidable).
- Extracts: Author name, Author headline (e.g., "Hiring! Hiring!"), Date, Post text,
  Links, Images, and Comments (commenter name, headline, comment text).
- Saves JSON + two CSVs (post summary + comments).

USAGE
-----
1) pip install selenium webdriver-manager
2) Create config.json:
{
  "linkedin_credentials": {"email": "you@example.com", "password": "YOUR_PASSWORD"},
  "scraping_settings": {"headless": false},
  "output_settings": {"output_directory": "output", "timestamp_format": "%Y%m%d_%H%M%S"}
}
3) Run:
   python linkedin_xpath_scraper.py --url "https://www.linkedin.com/posts/...."

You can pass multiple --url flags.
"""

import json
import os
import time
import csv
import random
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)

from webdriver_manager.chrome import ChromeDriverManager

# ------------- Helpers -------------

def rdelay(lo=0.7, hi=1.3):
    time.sleep(random.uniform(lo, hi))

def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("scraping_settings", {})
    cfg["scraping_settings"].setdefault("headless", False)
    cfg.setdefault("output_settings", {})
    cfg["output_settings"].setdefault("output_directory", "outputs")
    cfg["output_settings"].setdefault("timestamp_format", "%Y%m%d_%H%M%S")
    return cfg

def setup_driver(cfg: Dict[str, Any]) -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-sandbox")
    if cfg["scraping_settings"]["headless"]:
        opts.add_argument("--headless=new")
    service = Service(ChromeDriverManager().install())
    d = webdriver.Chrome(service=service, options=opts)
    d.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    d.implicitly_wait(5)
    d.set_page_load_timeout(45)
    return d

def login(driver: webdriver.Chrome, cfg: Dict[str, Any]):
    driver.get("https://www.linkedin.com/login")
    rdelay()
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "username")))
    driver.find_element(By.ID, "username").send_keys(cfg["linkedin_credentials"]["email"])
    driver.find_element(By.ID, "password").send_keys(cfg["linkedin_credentials"]["password"])
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    rdelay(1.8, 2.6)
    if not any(k in driver.current_url for k in ("feed", "/in/", "mynetwork", "jobs", "messaging", "notifications")):
        raise RuntimeError("Login failed or requires verification. Complete it and rerun.")

def get_post_root(driver: webdriver.Chrome):
    # Prefer article with data-activity-urn; LinkedIn also uses 'main-feed-activity-card'
    # Also try broader selectors for different post structures
    root_xpaths = [
        "//article[@data-activity-urn]",
        "//article[contains(@class,'main-feed-activity-card')]",
        "//article",  # Any article element
        "//main",     # Main content container
        "//div[contains(@class,'feed-shared-update')]",  # Feed update containers
    ]
    
    for xpath in root_xpaths:
        roots = driver.find_elements(By.XPATH, xpath)
        if roots:
            print(f"✅ Found post root with: {xpath}")
            return roots[0]
    
    raise RuntimeError("Post root element not found with any selector")

def scroll_into_view(driver: webdriver.Chrome, el):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    except Exception:
        pass

def click_js(driver: webdriver.Chrome, el):
    try:
        driver.execute_script("arguments[0].click();", el)
    except Exception:
        pass

def expand_post_text(driver: webdriver.Chrome, root):
    # Common "show more" buttons near commentary.
    xpaths = [
        ".//*[contains(@data-test-id,'main-feed-activity-card__commentary')]//button[contains(@aria-label,'more')]",
        ".//button[contains(@aria-label,'more')]"
    ]
    for xp in xpaths:
        try:
            btn = root.find_element(By.XPATH, xp)
            scroll_into_view(driver, btn)
            try:
                btn.click()
            except (ElementClickInterceptedException, StaleElementReferenceException):
                click_js(driver, btn)
            time.sleep(0.35)
            break
        except NoSuchElementException:
            continue

def open_comments_thread(driver: webdriver.Chrome, root):
    # Click the "Comments" social action to ensure comments are visible
    try:
        comments_btn = root.find_element(By.XPATH, ".//*[@data-test-id='social-actions__comments']")
        scroll_into_view(driver, comments_btn)
        try:
            comments_btn.click()
        except (ElementClickInterceptedException, StaleElementReferenceException):
            click_js(driver, comments_btn)
        time.sleep(0.6)
    except NoSuchElementException:
        pass

def load_more_comments(driver: webdriver.Chrome, max_clicks=3):
    # Attempt to click "more comments" buttons a few times
    for _ in range(max_clicks):
        expanded = False
        for xp in [
            "//button[contains(@aria-label,'more comments')]",
            "//a[contains(@data-test-id,'see-more-comments')]",
            "//button[contains(@aria-label,'Load more comments')]",
        ]:
            btns = driver.find_elements(By.XPATH, xp)
            if btns:
                b = btns[0]
                scroll_into_view(driver, b)
                try:
                    b.click()
                except Exception:
                    click_js(driver, b)
                time.sleep(0.8)
                expanded = True
                break
        if not expanded:
            break

# ------------- Extraction -------------

def extract_author(root) -> Tuple[str, str, str]:
    """Return (author_name, author_title, author_profile_url) using XPath relative to post root"""
    author = ""
    author_title = ""
    author_url = ""

    # lockup container (entity header)
    try:
        lock = root.find_element(By.XPATH, ".//*[@data-test-id='main-feed-activity-card__entity-lockup']")
    except NoSuchElementException:
        lock = root

    # Author name + URL
    try:
        a = lock.find_element(By.XPATH, ".//a[@data-tracking-control-name='public_post_feed-actor-name']")
        author = (a.get_attribute("innerText") or a.text or "").strip()
        author_url = a.get_attribute("href") or ""
    except NoSuchElementException:
        # fallback: any profile link in lockup
        try:
            a = lock.find_element(By.XPATH, ".//a[contains(@href,'/in/')]")
            author = (a.get_attribute("innerText") or a.text or "").strip()
            author_url = a.get_attribute("href") or ""
        except NoSuchElementException:
            pass

    # Author title/headline (e.g., "Hiring! Hiring!")
    try:
        p = lock.find_element(By.XPATH, ".//p[contains(@class,'text-color-text-low-emphasis')]")
        author_title = (p.get_attribute("innerText") or p.text or "").strip()
    except NoSuchElementException:
        # first such <p> after the author link
        try:
            p = root.find_element(By.XPATH,
                ".//a[@data-tracking-control-name='public_post_feed-actor-name']"
                "/ancestor::div[contains(@class,'flex')][1]"
                "//p[contains(@class,'text-color-text-low-emphasis')][1]"
            )
            author_title = (p.get_attribute("innerText") or p.text or "").strip()
        except NoSuchElementException:
            pass

    return author, author_title, author_url

def extract_date(root) -> str:
    # Prefer datetime attribute; fallback to text ("16h", "1w", etc.)
    try:
        t = root.find_element(By.XPATH,
            ".//*[@data-test-id='main-feed-activity-card__entity-lockup']//time | .//time"
        )
        return t.get_attribute("datetime") or (t.text or "").strip()
    except NoSuchElementException:
        return ""

def extract_post_text(root) -> str:
    # Handle both: (1) commentary present on the <p> itself, (2) wrapper with inner segments.
    texts = []

    # Any element (often <p>) that has the commentary data-test-id
    els = root.find_elements(By.XPATH, ".//*[@data-test-id='main-feed-activity-card__commentary']")
    for el in els:
        txt = (el.get_attribute("innerText") or el.text or "").strip()
        if txt:
            texts.append(txt)

    # Inner segments under the commentary (if wrapper)
    try:
        comm = root.find_element(By.XPATH, ".//*[@data-test-id='main-feed-activity-card__commentary']")
        segs = comm.find_elements(By.XPATH, ".//*[contains(@class,'attributed-text-segment-list__content')]")
        for s in segs:
            st = (s.get_attribute("innerText") or s.text or "").strip()
            if st:
                texts.append(st)
    except NoSuchElementException:
        pass

    # Fallback: any attributed segment paragraphs inside the article
    if not texts:
        segs = root.find_elements(By.XPATH, ".//p[contains(@class,'attributed-text-segment-list__content')]")
        for s in segs:
            st = (s.get_attribute("innerText") or s.text or "").strip()
            if st:
                texts.append(st)

    # Deduplicate preserving order
    out = []
    seen = set()
    for t in texts:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return "\n".join(out).strip()

def extract_links(root) -> List[str]:
    links = []
    for xp in [
        ".//*[@data-test-id='main-feed-activity-card__commentary']//a[@href]",
        ".//p[contains(@class,'attributed-text-segment-list__content')]//a[@href]",
    ]:
        for a in root.find_elements(By.XPATH, xp):
            href = (a.get_attribute("href") or "").strip()
            if href and href not in links:
                links.append(href)
    return links

def extract_images(root) -> List[Dict[str, str]]:
    imgs = []
    nodes = root.find_elements(By.XPATH, ".//ul[@data-test-id='feed-images-content']//img")
    for n in nodes:
        src = n.get_attribute("src") or ""
        alt = n.get_attribute("alt") or ""
        if src and not any(i["url"] == src for i in imgs):
            imgs.append({"url": src, "alt": alt})
    return imgs

def extract_comments(driver: webdriver.Chrome, root, limit: int = 50) -> List[Dict[str, str]]:
    open_comments_thread(driver, root)
    load_more_comments(driver, max_clicks=3)

    comments = []
    # Each top-level comment block
    blocks = driver.find_elements(By.XPATH, "//section[contains(@class,'comment')] | //div[contains(@class,'comment__body')]")
    for c in blocks[:limit]:
        d = {"commentor": "", "commentor_title": "", "comment_text": ""}
        # Name
        try:
            a = c.find_element(By.XPATH, ".//a[contains(@class,'comment__author')] | .//a[@data-tracking-control-name='public_post_comment_actor-name']")
            d["commentor"] = (a.get_attribute("innerText") or a.text or "").strip()
        except NoSuchElementException:
            pass
        # Headline/Title
        try:
            p = c.find_element(By.XPATH, ".//p[contains(@class,'comment__author-headline')]")
            d["commentor_title"] = (p.get_attribute("innerText") or p.text or "").strip()
        except NoSuchElementException:
            pass
        # Body text
        body = ""
        for xp in [
            ".//p[contains(@class,'comment__text')]",
            ".//p[contains(@class,'attributed-text-segment-list__content') and contains(@class,'comment__text')]",
        ]:
            els = c.find_elements(By.XPATH, xp)
            if els:
                body = (els[0].get_attribute("innerText") or els[0].text or "").strip()
                break
        d["comment_text"] = body
        if any((d["commentor"], d["comment_text"])):
            comments.append(d)
    return comments

# ------------- Orchestration -------------

def scrape_post(driver: webdriver.Chrome, url: str) -> Dict[str, Any]:
    driver.get(url)
    rdelay(1.0, 2.0)
    
    # Wait for any of the possible post root elements to be present
    WebDriverWait(driver, 20).until(
        EC.any_of(
            EC.presence_of_element_located((By.XPATH, "//article[@data-activity-urn]")),
            EC.presence_of_element_located((By.XPATH, "//article[contains(@class,'main-feed-activity-card')]")),
            EC.presence_of_element_located((By.XPATH, "//article")),
            EC.presence_of_element_located((By.XPATH, "//main")),
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'feed-shared-update')]")),
        )
    )
    root = get_post_root(driver)
    expand_post_text(driver, root)

    author, author_title, author_url = extract_author(root)
    date_posted = extract_date(root)
    post_text = extract_post_text(root)
    links = extract_links(root)
    images = extract_images(root)
    comments = extract_comments(driver, root, limit=50)

    data = {
        "post_url": url,
        "scraped_at": datetime.now().isoformat(),
        "post_author": author,
        "author_title": author_title,
        "author_profile_url": author_url,
        "date_posted": date_posted,
        "post_text": post_text,
        "links": links,
        "images": images,
        "comment_count": len(comments),
        "comments": comments,
        "scraper_version": "xpath-1.0"
    }
    return data

def save_outputs(data: Dict[str, Any], outdir: Path) -> Tuple[str, str, str]:
    outdir.mkdir(exist_ok=True, parents=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON
    json_path = outdir / f"linkedin_post_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Post summary CSV
    row = {
        "post_url": data.get("post_url",""),
        "post_author": data.get("post_author",""),
        "author_title": data.get("author_title",""),
        "author_profile_url": data.get("author_profile_url",""),
        "date_posted": data.get("date_posted",""),
        "post_text": data.get("post_text",""),
        "links": "; ".join(data.get("links",[])),
        "image_urls": "; ".join([i.get("url","") for i in data.get("images",[])]),
        "comment_count": data.get("comment_count",0),
        "scraped_at": data.get("scraped_at",""),
        "scraper_version": data.get("scraper_version",""),
    }
    post_csv = outdir / f"linkedin_post_{ts}_post.csv"
    with open(post_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        w.writeheader(); w.writerow(row)

    # Comments CSV
    comments_csv = outdir / f"linkedin_post_{ts}_comments.csv"
    with open(comments_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["post_url","post_author","commentor","commentor_title","comment_text"])
        w.writeheader()
        for c in data.get("comments",[]):
            w.writerow({
                "post_url": data.get("post_url",""),
                "post_author": data.get("post_author",""),
                "commentor": c.get("commentor",""),
                "commentor_title": c.get("commentor_title",""),
                "comment_text": c.get("comment_text",""),
            })

    return str(json_path), str(post_csv), str(comments_csv)

def main():
    ap = argparse.ArgumentParser(description="LinkedIn XPath Post Scraper")
    ap.add_argument("--url", action="append", required=True, help="LinkedIn post permalink URL (can repeat)")
    ap.add_argument("--config", default="config.json", help="Path to config.json")
    args = ap.parse_args()

    cfg = load_config(args.config)
    outdir = Path(cfg["output_settings"]["output_directory"])

    driver = setup_driver(cfg)
    try:
        login(driver, cfg)
        for u in args.url:
            data = scrape_post(driver, u)
            jp, pcsv, ccsv = save_outputs(data, outdir)
            print("✅ JSON: ", jp)
            print("✅ POST CSV: ", pcsv)
            print("✅ COMMENTS CSV: ", ccsv)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    if not os.path.exists("config.json"):
        print("❌ Missing config.json. See file header for example.")
        raise SystemExit(1)
    main()
