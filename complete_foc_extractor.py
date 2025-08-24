#!/usr/bin/env python3
"""
Complete FOC Community Notion Extractor
Aggressively scrolls to get ALL entries from the table
"""

import os
import csv
import asyncio
from datetime import datetime
from typing import List, Dict
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re

async def extract_complete_foc_data():
    """Complete extraction with aggressive scrolling."""
    
    print("🚀 COMPLETE FOC TABLE EXTRACTOR")
    print("📅 Time:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("🎯 Extracting ALL entries from FOC Community table")
    print("📜 Using aggressive scrolling to load everything")
    print("=" * 70)
    
    url = "https://foccommunity.notion.site/14d2955ab7ed80569735c3061cffa884?v=14d2955ab7ed8194aef0000c929e4422"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,  # Use headless for production
            args=['--no-sandbox', '--disable-web-security']
        )
        page = await browser.new_page()
        
        # Set realistic browser settings
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        try:
            print("   🌐 Loading FOC Community page...")
            await page.goto(url, timeout=90000)
            print("   ✅ Page loaded successfully")
            
            # Wait for initial content
            await asyncio.sleep(8)
            print("   ⏳ Initial content load complete")
            
            # Aggressive scrolling strategy
            print("   📜 Starting aggressive scroll to load ALL table entries...")
            
            prev_link_count = 0
            stable_attempts = 0
            scroll_round = 0
            
            for scroll_round in range(100):  # Up to 100 scroll attempts
                # Multiple scrolling strategies
                
                # Strategy 1: Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
                
                # Strategy 2: Page down key
                await page.keyboard.press('PageDown')
                await asyncio.sleep(1)
                
                # Strategy 3: Scroll by fixed amount
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)
                
                # Strategy 4: Try to find and scroll specific containers
                await page.evaluate('''
                    () => {
                        // Find scrollable containers and scroll them
                        const containers = document.querySelectorAll('div[style*="overflow"], .notion-table-view, div[role="table"]');
                        containers.forEach(container => {
                            if (container.scrollHeight > container.clientHeight) {
                                container.scrollTop = container.scrollHeight;
                            }
                        });
                    }
                ''')
                await asyncio.sleep(1)
                
                # Check progress every few scrolls
                if scroll_round % 3 == 0:
                    current_link_count = await page.evaluate('document.querySelectorAll("a[href*=\\"linkedin.com\\"]").length')
                    
                    if current_link_count > prev_link_count:
                        print(f"   📈 Round {scroll_round}: Found {current_link_count} LinkedIn links (+{current_link_count - prev_link_count})")
                        prev_link_count = current_link_count
                        stable_attempts = 0
                    else:
                        stable_attempts += 1
                    
                    # If no progress for several rounds, try more aggressive tactics
                    if stable_attempts >= 10:
                        print(f"   🔄 No progress for 10 rounds, trying aggressive tactics...")
                        
                        # Try clicking any "Load more" buttons
                        load_more_clicked = await page.evaluate('''
                            () => {
                                const buttons = Array.from(document.querySelectorAll('button, div[role="button"], span[role="button"]'));
                                for (let btn of buttons) {
                                    const text = btn.textContent?.toLowerCase() || '';
                                    if (text.includes('load') || text.includes('more') || text.includes('show')) {
                                        btn.click();
                                        return true;
                                    }
                                }
                                return false;
                            }
                        ''')
                        
                        if load_more_clicked:
                            print("   🎯 Clicked potential 'load more' button")
                            await asyncio.sleep(5)
                            stable_attempts = 0
                        
                        # Try scrolling to absolute positions
                        for pos in [5000, 10000, 15000, 20000, 25000]:
                            await page.evaluate(f"window.scrollTo(0, {pos})")
                            await asyncio.sleep(2)
                    
                    # Exit if we're really stable
                    if stable_attempts >= 20:
                        print(f"   ✅ Content appears fully loaded after {scroll_round} scroll rounds")
                        break
                
                # Brief pause every 20 rounds
                if scroll_round % 20 == 0 and scroll_round > 0:
                    print(f"   ⏸️  Brief pause at round {scroll_round}")
                    await asyncio.sleep(5)
            
            # Final count
            final_link_count = await page.evaluate('document.querySelectorAll("a[href*=\\"linkedin.com\\"]").length')
            print(f"   🏁 Scrolling complete! Found {final_link_count} LinkedIn links total")
            
            print("   📄 Extracting complete page HTML...")
            html_content = await page.content()
            
            # Save complete HTML
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            html_file = f"./storage/foc_complete_{timestamp}.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"   💾 Complete HTML saved: {html_file}")
            
        except Exception as e:
            print(f"   ❌ Error during extraction: {e}")
            return []
        
        finally:
            await browser.close()
    
    # Enhanced HTML parsing
    print("   🔍 Parsing HTML for structured table data...")
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Find all LinkedIn links
    linkedin_links = soup.find_all('a', href=lambda x: x and 'linkedin.com' in x.lower())
    print(f"   🔗 Found {len(linkedin_links)} LinkedIn links in HTML")
    
    # Extract with better context parsing
    extracted_data = []
    for i, link in enumerate(linkedin_links):
        href = link.get('href', '').strip()
        
        # Clean URL
        if href.startswith('//'):
            href = 'https:' + href
        elif href.startswith('/'):
            href = 'https://linkedin.com' + href
        
        # Get link text
        link_text = link.get_text(strip=True)
        
        # Enhanced context extraction
        context_data = extract_enhanced_context(link)
        
        record = {
            'link_number': i + 1,
            'url': href,
            'link_text': link_text,
            'company': context_data.get('company', ''),
            'role': context_data.get('role', ''),
            'location': context_data.get('location', ''),
            'date_posted': context_data.get('date', ''),
            'full_context': context_data.get('full_context', '')[:500],
            'url_type': classify_url(href),
            'extracted_at': datetime.now().isoformat()
        }
        
        extracted_data.append(record)
    
    print(f"   ✅ Extracted {len(extracted_data)} complete records")
    return extracted_data

def extract_enhanced_context(link_element) -> Dict[str, str]:
    """Enhanced context extraction from link's surrounding elements."""
    context_data = {
        'company': '',
        'role': '',
        'location': '',
        'date': '',
        'full_context': ''
    }
    
    # Try multiple parent levels to find table row context
    current = link_element
    for level in range(5):  # Go up 5 levels
        if current.parent:
            current = current.parent
            
            # Check if this looks like a table row
            if current.name in ['tr', 'div'] and ('role' in current.attrs or 'row' in str(current.get('class', ''))):
                row_text = current.get_text(strip=True)
                context_data['full_context'] = row_text
                
                # Try to parse structured data from row
                parsed = parse_table_row_text(row_text)
                context_data.update(parsed)
                break
            
            # Also check if current element has substantial text
            element_text = current.get_text(strip=True)
            if len(element_text) > 50 and len(element_text) < 500:
                if not context_data['full_context']:
                    context_data['full_context'] = element_text
                    
                    # Try to parse this text too
                    parsed = parse_table_row_text(element_text)
                    if not context_data['company'] and parsed.get('company'):
                        context_data.update(parsed)
    
    return context_data

def parse_table_row_text(text: str) -> Dict[str, str]:
    """Parse table row text to extract structured data."""
    parsed = {
        'company': '',
        'role': '',
        'location': '',
        'date': ''
    }
    
    if not text:
        return parsed
    
    # Try to split on common delimiters
    for delimiter in [' | ', ' - ', ' – ', ' — ', '\t']:
        if delimiter in text:
            parts = [p.strip() for p in text.split(delimiter)]
            
            if len(parts) >= 2:
                # First part often company, second often role
                parsed['company'] = parts[0]
                parsed['role'] = parts[1]
                
                # Look for location and date in remaining parts
                for part in parts[2:]:
                    part_lower = part.lower()
                    
                    # Location indicators
                    if any(word in part_lower for word in ['remote', 'san francisco', 'ny', 'london', 'berlin', 'mumbai', 'bangalore']):
                        if not parsed['location']:
                            parsed['location'] = part
                    
                    # Date indicators
                    if re.search(r'\d{1,2}[/-]\d{1,2}|\d{4}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec', part_lower):
                        if not parsed['date']:
                            parsed['date'] = part
                
                break
    
    # If no delimiters worked, try regex patterns
    if not parsed['company']:
        # Look for company-like patterns at the beginning
        company_match = re.match(r'^([A-Za-z][A-Za-z0-9\s&.,]{2,30})', text)
        if company_match:
            parsed['company'] = company_match.group(1).strip()
    
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
    """Save complete extracted data to CSV."""
    if not data:
        print("❌ No data to save")
        return ""
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = f"./storage/foc_complete_table_{timestamp}.csv"
    
    fieldnames = [
        'link_number', 'url', 'link_text', 'company', 'role', 
        'location', 'date_posted', 'url_type', 'full_context', 'extracted_at'
    ]
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f"\n💾 COMPLETE DATA SAVED: {csv_file}")
    print(f"📊 Total records: {len(data)}")
    
    # Detailed analysis
    url_types = {}
    companies = set()
    jobs_count = 0
    
    for record in data:
        url_type = record.get('url_type', 'unknown')
        url_types[url_type] = url_types.get(url_type, 0) + 1
        
        company = record.get('company', '').strip()
        if company and len(company) > 2:
            companies.add(company)
            
        if url_type == 'job':
            jobs_count += 1
    
    print(f"\n📈 DETAILED BREAKDOWN:")
    for url_type, count in url_types.items():
        print(f"   • {url_type}: {count} links")
    
    print(f"   • Unique companies: {len(companies)}")
    print(f"   • Job opportunities: {jobs_count}")
    
    # Show sample records with context
    print(f"\n🔗 SAMPLE RECORDS WITH CONTEXT:")
    job_samples = [r for r in data if r.get('url_type') == 'job'][:5]
    
    for i, record in enumerate(job_samples):
        company = record.get('company', 'N/A')[:25]
        role = record.get('role', 'N/A')[:35]
        location = record.get('location', 'N/A')[:20]
        print(f"   {i+1}. {company} | {role} | {location}")
    
    return csv_file

async def main():
    """Main extraction function."""
    os.makedirs("./storage", exist_ok=True)
    
    print("Starting complete FOC Community table extraction...")
    data = await extract_complete_foc_data()
    
    if data:
        csv_file = save_complete_data(data)
        
        print(f"\n✅ EXTRACTION COMPLETE!")
        print(f"   📊 Total records extracted: {len(data)}")
        print(f"   💾 Complete data file: {csv_file}")
        
        # Success metrics
        job_links = sum(1 for r in data if r.get('url_type') == 'job')
        with_company = sum(1 for r in data if r.get('company', '').strip())
        with_role = sum(1 for r in data if r.get('role', '').strip())
        
        print(f"\n🎯 EXTRACTION QUALITY:")
        print(f"   💼 Job links: {job_links}")
        print(f"   🏢 Records with company: {with_company}")
        print(f"   👔 Records with role: {with_role}")
        
        print(f"\n📋 NEXT STEPS:")
        print(f"   1. Review the complete CSV file")
        print(f"   2. Import into database if satisfied")
        print(f"   3. Use for job application workflow")
        
    else:
        print(f"\n❌ EXTRACTION FAILED")
        print("   No data was extracted from FOC Community")

if __name__ == "__main__":
    asyncio.run(main())