#!/usr/bin/env python3
"""
Analyze scraped HTML file to check for description expansion indicators
"""

import os
import re
from pathlib import Path

def analyze_html_file(file_path):
    """Analyze a scraped HTML file for description expansion status"""
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
    
    print(f"🔍 Analyzing HTML file: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Look for the expandable text box
    expandable_text_pattern = r'data-testid="expandable-text-box"[^>]*>(.*?)</span>'
    matches = re.findall(expandable_text_pattern, html_content, re.DOTALL)
    
    if matches:
        print(f"✅ Found {len(matches)} expandable text box(es)")
        for i, match in enumerate(matches, 1):
            # Extract text content from HTML
            text_content = re.sub(r'<[^>]+>', '', match).strip()
            print(f"   📝 Text box #{i} length: {len(text_content)} characters")
            if len(text_content) > 100:
                print(f"   🔤 First 100 chars: {text_content[:100]}...")
    else:
        print("❌ No expandable text box found")
    
    # Look for "more" buttons
    more_button_patterns = [
        r'data-testid="expandable-text-button"',
        r'<button[^>]*>[^<]*more[^<]*</button>',
        r'<button[^>]*>.*?…\s*more.*?</button>',
    ]
    
    found_buttons = []
    for pattern in more_button_patterns:
        matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if matches:
            found_buttons.extend(matches)
    
    if found_buttons:
        print(f"🔘 Found {len(found_buttons)} 'more' button(s):")
        for i, button in enumerate(found_buttons, 1):
            print(f"   #{i}: {button[:100]}...")
    else:
        print("✅ No 'more' buttons found (description might be fully expanded)")
    
    # Look for specific truncation indicators
    truncation_indicators = [
        "… more",
        "...more",
        "show more",
        "read more",
    ]
    
    found_indicators = []
    for indicator in truncation_indicators:
        if indicator.lower() in html_content.lower():
            found_indicators.append(indicator)
    
    if found_indicators:
        print(f"⚠️  Truncation indicators found: {', '.join(found_indicators)}")
    else:
        print("✅ No obvious truncation indicators found")
    
    # Look for the job description content in different sections
    description_patterns = [
        r'<h2[^>]*>About the job</h2>.*?</div>',
        r'data-testid="expandable-text-box".*?</span>',
        r'class="jobs-box__html-content".*?</div>',
    ]
    
    longest_description = ""
    for pattern in description_patterns:
        matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
        for match in matches:
            text_content = re.sub(r'<[^>]+>', ' ', match).strip()
            text_content = ' '.join(text_content.split())  # Clean up whitespace
            if len(text_content) > len(longest_description):
                longest_description = text_content
    
    if longest_description:
        print(f"\n📄 Longest description found: {len(longest_description)} characters")
        print(f"🔤 Content preview: {longest_description[:200]}...")
        
        # Check if it looks complete
        if len(longest_description) > 1000:
            print("✅ Description seems substantial (>1000 chars)")
        else:
            print("⚠️  Description seems short (<1000 chars) - might be truncated")
    else:
        print("❌ No description content found")

def main():
    """Main function to analyze the HTML file"""
    html_file = "./storage/scrape/html/20250924/1758723223.html"
    
    print("🧪 LinkedIn Job Description Analysis")
    print("=" * 50)
    
    analyze_html_file(html_file)
    
    print("\n" + "=" * 50)
    print("Analysis complete!")

if __name__ == "__main__":
    main()