#!/usr/bin/env python3
"""
Complete Notion Scraper - Get ALL 482 entries
Uses advanced virtual scrolling techniques to force Notion to load all rows
"""

import asyncio
import csv
import json
from datetime import datetime
from typing import List, Dict
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re

async def get_total_count(page) -> int:
    """Get the total count from Notion's counter."""
    try:
        # Look for the count indicator
        count_text = await page.locator('text=/Count\\s+\\d+/').inner_text(timeout=5000)
        count_match = re.search(r'Count\s+(\d+)', count_text)
        if count_match:
            return int(count_match.group(1))
    except:
        pass
    return 0

async def force_load_all_rows(page, target_count: int = 482):
    """Aggressively force Notion to load all virtual rows."""
    print(f"🎯 Target: Load all {target_count} entries")
    
    # Multiple scrolling strategies
    strategies = [
        "viewport_scrolling",
        "table_container_scrolling", 
        "keyboard_navigation",
        "element_focusing",
        "zoom_and_scroll"
    ]
    
    loaded_count = 0
    attempt = 0
    max_attempts = 200
    
    while loaded_count < target_count and attempt < max_attempts:
        attempt += 1
        
        # Strategy 1: Viewport scrolling
        if attempt % 4 == 0:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.keyboard.press('End')
            await asyncio.sleep(1)
        
        # Strategy 2: Find and scroll table container
        if attempt % 4 == 1:
            await page.evaluate("""
                () => {
                    const scrollers = document.querySelectorAll('.notion-scroller, .notion-table-view, div[style*="overflow"]');
                    scrollers.forEach(el => {
                        if (el.scrollHeight > el.clientHeight) {
                            el.scrollTop = el.scrollHeight;
                        }
                    });
                }
            """)
            await asyncio.sleep(1)
        
        # Strategy 3: Keyboard navigation
        if attempt % 4 == 2:
            # Focus on table and use keyboard
            table = page.locator('.notion-table-view').first
            if await table.count() > 0:
                await table.focus()
                for _ in range(10):
                    await page.keyboard.press('PageDown')
                    await asyncio.sleep(0.3)
        
        # Strategy 4: Element focusing to trigger loading
        if attempt % 4 == 3:
            # Try to focus elements at the bottom
            await page.evaluate("""
                () => {
                    const rows = document.querySelectorAll('div[data-block-id], .notion-collection-item');
                    if (rows.length > 0) {
                        const lastRow = rows[rows.length - 1];
                        lastRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        if (lastRow.focus) lastRow.focus();
                    }
                }
            """)
            await asyncio.sleep(2)
        
        # Strategy 5: Zoom out to fit more rows per viewport (every 20 attempts)
        if attempt % 20 == 0:
            zoom_level = max(0.3, 1.0 - (attempt / 400))  # Gradually zoom out
            await page.evaluate(f"document.body.style.zoom = '{zoom_level}'")
            print(f"   📐 Zoomed to {zoom_level:.1f}x to fit more rows")
        
        # Check progress every 5 attempts
        if attempt % 5 == 0:
            # Count current rows/blocks
            current_rows = await page.evaluate("""
                () => {
                    const selectors = [
                        'div[data-block-id]',
                        '.notion-collection-item', 
                        'a[href*="linkedin.com"]'
                    ];
                    let maxCount = 0;
                    for (const sel of selectors) {
                        const count = document.querySelectorAll(sel).length;
                        maxCount = Math.max(maxCount, count);
                    }
                    return maxCount;
                }
            """)
            
            linkedin_links = await page.evaluate('document.querySelectorAll("a[href*=\\"linkedin.com\\"]").length')
            
            if current_rows > loaded_count:
                loaded_count = current_rows
                print(f"   📈 Attempt {attempt}: {current_rows} rows loaded, {linkedin_links} LinkedIn links")
            else:
                print(f"   ⏸️  Attempt {attempt}: No progress ({current_rows} rows, {linkedin_links} links)")
        
        # Try to click load more buttons
        if attempt % 10 == 0:
            load_more_clicked = await page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button, div[role="button"], span[role="button"]');
                    for (const btn of buttons) {
                        const text = (btn.textContent || '').toLowerCase();
                        if (text.includes('load') || text.includes('more') || text.includes('show') || text.includes('next')) {
                            try {
                                btn.click();
                                return true;
                            } catch (e) {}
                        }
                    }
                    return false;
                }
            """)
            
            if load_more_clicked:
                print(f"   🎯 Clicked load more button")
                await asyncio.sleep(3)
        
        # Brief pause
        await asyncio.sleep(0.5)
    
    final_count = await page.evaluate('document.querySelectorAll("a[href*=\\"linkedin.com\\"]").length')
    print(f"🏁 Finished: {final_count} LinkedIn links loaded after {attempt} attempts")
    
    # Reset zoom
    await page.evaluate("document.body.style.zoom = '1.0'")
    
    return final_count

async def extract_all_data(page) -> List[Dict]:
    """Extract all LinkedIn data from the fully loaded page."""
    print("📄 Extracting all data from loaded page...")
    
    html_content = await page.content()
    
    # Save for debugging
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    debug_file = f"./storage/complete_foc_{timestamp}.html"
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"💾 Saved complete HTML: {debug_file}")
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Get all LinkedIn links
    linkedin_links = soup.find_all('a', href=lambda x: x and 'linkedin.com' in x.lower())
    print(f"🔗 Found {len(linkedin_links)} LinkedIn links in HTML")
    
    # Extract data with enhanced context parsing
    extracted_data = []
    seen_urls = set()
    
    for i, link in enumerate(linkedin_links):
        href = link.get('href', '').strip()
        
        # Clean URL
        if href.startswith('//'):
            href = 'https:' + href
        elif href.startswith('/'):
            href = 'https://linkedin.com' + href
        
        # Remove tracking parameters
        if '?' in href:
            href = href.split('?')[0]
        
        # Skip duplicates
        if href in seen_urls:
            continue
        seen_urls.add(href)
        
        # Extract context and metadata
        link_text = link.get_text(strip=True)
        context = extract_context_from_notion_structure(link, soup)
        
        record = {
            'entry_number': len(extracted_data) + 1,
            'url': href,
            'link_text': link_text,
            'company': context.get('company', ''),
            'role': context.get('role', ''), 
            'location': context.get('location', ''),
            'date_posted': context.get('date', ''),
            'url_type': classify_url(href),
            'context': context.get('full_context', '')[:300],
            'extraction_method': 'complete_scraper',
            'extracted_at': datetime.now().isoformat()
        }
        
        extracted_data.append(record)
    
    print(f"✅ Extracted {len(extracted_data)} unique LinkedIn opportunities")
    return extracted_data

def extract_context_from_notion_structure(link_element, soup) -> Dict[str, str]:
    """Extract job context from Notion's table structure."""
    context = {
        'company': '',
        'role': '',
        'location': '',
        'date': '',
        'full_context': ''
    }
    
    # Try to find the parent table row or block
    current = link_element
    for level in range(6):  # Go up several levels
        if current.parent:
            current = current.parent
            
            # Look for Notion table row indicators
            class_list = current.get('class', [])
            if any('row' in str(cls).lower() or 'item' in str(cls).lower() for cls in class_list):
                row_text = current.get_text(strip=True)
                context['full_context'] = row_text
                
                # Parse structured data
                parsed = parse_job_text(row_text)
                context.update(parsed)
                break
        else:
            break
    
    return context

def parse_job_text(text: str) -> Dict[str, str]:
    """Parse job text to extract structured information."""
    parsed = {
        'company': '',
        'role': '',
        'location': '',
        'date': ''
    }
    
    if not text or len(text) < 10:
        return parsed
    
    # Split on common delimiters
    for delimiter in [' | ', ' - ', ' – ', '\t', '  ']:
        if delimiter in text:
            parts = [p.strip() for p in text.split(delimiter) if p.strip()]
            
            if len(parts) >= 2:
                # Common pattern: Company | Role | Location | Date
                parsed['company'] = parts[0]
                if len(parts) > 1:
                    parsed['role'] = parts[1]
                if len(parts) > 2:
                    # Look for location indicators
                    for part in parts[2:]:
                        if any(loc in part.lower() for loc in ['remote', 'sf', 'ny', 'london', 'mumbai', 'bangalore']):
                            parsed['location'] = part
                            break
                
                # Look for dates
                for part in parts:
                    if re.search(r'\d{1,2}[/-]\d{1,2}|\d{4}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec', part.lower()):
                        parsed['date'] = part
                        break
                
                break
    
    return parsed

def classify_url(url: str) -> str:
    """Classify LinkedIn URL type."""
    url_lower = url.lower()
    if '/jobs/view/' in url_lower:
        return 'job'
    elif '/jobs/' in url_lower:
        return 'job_search'
    elif '/posts/' in url_lower:
        return 'post'
    elif '/in/' in url_lower:
        return 'profile'
    elif '/company/' in url_lower:
        return 'company'
    return 'other'

def save_complete_data(data: List[Dict]) -> str:
    """Save complete dataset to CSV."""
    if not data:
        return ""
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = f"./storage/foc_complete_all_{timestamp}.csv"
    
    fieldnames = [
        'entry_number', 'url', 'link_text', 'company', 'role', 
        'location', 'date_posted', 'url_type', 'context', 
        'extraction_method', 'extracted_at'
    ]
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f"\n💾 COMPLETE DATASET SAVED: {csv_file}")
    return csv_file

async def main():
    """Main scraper for ALL FOC entries."""
    print("🚀 COMPLETE FOC NOTION SCRAPER")
    print("📅 Time:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("🎯 Goal: Extract ALL entries from FOC Community database")
    print("=" * 70)
    
    url = "https://foccommunity.notion.site/14d2955ab7ed80569735c3061cffa884?v=14d2955ab7ed8194aef0000c929e4422"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # Run visible to monitor progress
            args=['--no-sandbox', '--disable-web-security']
        )
        
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1400, "height": 1000})
        
        try:
            print("🌐 Loading FOC Community page...")
            await page.goto(url, timeout=90000)
            await asyncio.sleep(10)  # Wait for initial load
            
            # Get expected count
            total_count = await get_total_count(page)
            print(f"📊 Expected entries: {total_count}")
            
            # Force load all entries
            loaded_count = await force_load_all_rows(page, total_count)
            
            # Extract all data
            all_data = await extract_all_data(page)
            
            # Save results
            csv_file = save_complete_data(all_data)
            
            # Results summary
            job_count = sum(1 for item in all_data if item.get('url_type') == 'job')
            
            print(f"\n✅ COMPLETE EXTRACTION FINISHED!")
            print(f"   📊 Total LinkedIn links: {len(all_data)}")
            print(f"   💼 Job opportunities: {job_count}")
            print(f"   📄 Saved to: {csv_file}")
            print(f"   🎯 Coverage: {len(all_data)}/{total_count} ({len(all_data)/total_count*100:.1f}%)")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    import os
    os.makedirs("./storage", exist_ok=True)
    asyncio.run(main())