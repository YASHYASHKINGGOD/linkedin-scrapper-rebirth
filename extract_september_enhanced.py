#!/usr/bin/env python3
"""
Enhanced September Data Extractor with Regex Logic

This script extracts September 2025 LinkedIn links with company/role/location metadata
using regex patterns to match various date formats in Google Sheets.

Usage:
    python extract_september_enhanced.py [--dry-run]
"""

import os
import sys
import csv
import re
import argparse
from pathlib import Path
from datetime import datetime

# Add src to Python path
sys.path.insert(0, 'src')

from src.clients.google_sheets import GoogleSheetsClient


def setup_environment():
    """Setup environment like the working ingest script"""
    env_vars = {
        "GOOGLE_OAUTH_CLIENT_JSON": "./client_secret_28309019366-uep6ho3i3k5096d1od4fo8gp1c1tj375.apps.googleusercontent.com.json",
        "GOOGLE_OAUTH_TOKEN_JSON": "./.secrets/google_token.json",
        "GOOGLE_OAUTH_REDIRECT_PORT": "8765",
        "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/data_lake"
    }
    
    for key, value in env_vars.items():
        if key not in os.environ:
            os.environ[key] = value


# Regex patterns for September date detection
SEPTEMBER_DATE_PATTERNS = [
    re.compile(r"(?i)jobs\s+updated\s+on\s+sep(?:t(?:ember)?)?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})?", re.IGNORECASE),
    re.compile(r"(?i)opportunities?\s+posted\s+on\s+(\d{1,2})(?:st|nd|rd|th)?\s+sep(?:t(?:ember)?)?\b", re.IGNORECASE),
    re.compile(r"(?i)(\d{1,2})(?:st|nd|rd|th)?\s+sep(?:t(?:ember)?)?\s*(\d{4})?", re.IGNORECASE),
    re.compile(r"(?i)sep(?:t(?:ember)?)?\s+(\d{1,2})(?:st|nd|rd|th)?\s*(\d{4})?", re.IGNORECASE),
    re.compile(r"(?i)(\d{1,2})(?:st|nd|rd|th)?\s+september", re.IGNORECASE),
    re.compile(r"(?i)september\s+(\d{1,2})(?:st|nd|rd|th)?", re.IGNORECASE)
]


def is_september_date_header(text: str) -> str:
    """Check if text matches September date patterns and return normalized date"""
    text = text.strip()
    if not text:
        return ""
    
    for pattern in SEPTEMBER_DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            # Extract day and year if available
            groups = match.groups()
            if len(groups) >= 1 and groups[0]:
                day = groups[0]
                year = "2025"  # Default to 2025
                if len(groups) >= 2 and groups[1]:
                    year = groups[1]
                return f"Sep {day}, {year}"
    
    # Fallback - if text contains "september" or "sep", consider it a date
    if re.search(r"(?i)sep(?:t(?:ember)?)?", text) and len(text) < 100:
        return text
    
    return ""


def extract_september_data():
    """Extract September data with enhanced date parsing"""
    
    setup_environment()
    client = GoogleSheetsClient()
    
    # Define the working sheets with their specific tab configurations
    sheets_config = [
        {
            "id": "1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q",
            "name": "Job Dashboard - The Growth Desk",
            "tabs": ["September (2025)"],  # Single tab approach first
            "type": "standard"
        },
        {
            "id": "1p7O7tUBYM94IqEmIlXp8a5B0nGdX8DwP-bmVFu0FAK0", 
            "name": "Soul in Product - Dashboard",
            "tabs": ["September Openings "],
            "type": "standard"
        },
        {
            "id": "1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q",
            "name": "The FinTech PM - Job Dashboard (Premium Version)",
            "tabs": ["The FinTech PM", "Top 1% PM", "The Remote PM"],
            "type": "fintech_multi_tab"
        }
    ]
    
    all_records = []
    
    for sheet_config in sheets_config:
        print(f"\n📊 Processing: {sheet_config['name']}")
        
        for tab_name in sheet_config["tabs"]:
            try:
                print(f"  📋 Processing tab: {tab_name}")
                
                # Get the tab data
                values = client.get_values(sheet_config["id"], tab_name)
                print(f"    📄 Found {len(values)} rows")
                
                # Parse the data based on sheet type
                if sheet_config["type"] == "fintech_multi_tab":
                    records = parse_fintech_sheet_data(values, sheet_config["name"], tab_name)
                else:
                    records = parse_standard_sheet_data(values, sheet_config["name"], tab_name)
                
                all_records.extend(records)
                print(f"    ✅ Extracted {len(records)} September records")
                
            except Exception as e:
                print(f"    ❌ Failed to process {tab_name}: {e}")
                continue
    
    return all_records


def parse_fintech_sheet_data(values, sheet_name, tab_name):
    """Parse FinTech PM sheet format with date headers like 'Jobs Updated on Sep 18, 2025'"""
    records = []
    
    if not values:
        return records
    
    current_date = ""
    header_indices = {}
    
    # The FinTech sheet typically has: Company, Role, Location, URL structure
    # Let's find the header row first
    for row_idx, row in enumerate(values):
        row_str = [str(cell).strip() if cell else "" for cell in row]
        row_text = " ".join(row_str).lower()
        
        # Check for column headers
        if any(keyword in row_text for keyword in ["company", "role", "location"]):
            for col_idx, header in enumerate(row_str):
                header_lower = header.lower()
                if "company" in header_lower:
                    header_indices["company"] = col_idx
                elif "role" in header_lower or "position" in header_lower:
                    header_indices["role"] = col_idx
                elif "location" in header_lower:
                    header_indices["location"] = col_idx
            break
    
    print(f"      🔍 FinTech headers found: {header_indices}")
    
    # Process each row
    for row_idx, row in enumerate(values):
        row_str = [str(cell).strip() if cell else "" for cell in row]
        row_text = " ".join(row_str)
        
        # Check if this is a date header
        date_match = is_september_date_header(row_text)
        if date_match:
            current_date = date_match
            print(f"        📅 Found date: {current_date}")
            continue
        
        # Skip if no current date or not September
        if not current_date:
            continue
        
        # Look for LinkedIn URLs in any column
        linkedin_url = ""
        for col_idx, cell in enumerate(row):
            if cell and ("linkedin.com" in str(cell) or "lnkd.in" in str(cell)):
                linkedin_url = str(cell).strip()
                break
        
        if not linkedin_url:
            continue
        
        # Extract metadata
        def get_cell(col_idx):
            return str(row[col_idx]).strip() if col_idx is not None and col_idx < len(row) and row[col_idx] else ""
        
        company = get_cell(header_indices.get("company"))
        role = get_cell(header_indices.get("role"))
        location = get_cell(header_indices.get("location"))
        
        # If no headers found, try to infer from position relative to URL
        if not header_indices and linkedin_url:
            url_col = next((i for i, cell in enumerate(row) if cell and "linkedin.com" in str(cell)), None)
            if url_col is not None and url_col >= 2:
                company = get_cell(url_col - 2) if url_col >= 2 else ""
                role = get_cell(url_col - 1) if url_col >= 1 else ""
                location = get_cell(url_col + 1) if url_col + 1 < len(row) else ""
        
        records.append({
            "date": current_date,
            "company": company,
            "role": role,
            "location": location,
            "url": linkedin_url,
            "sheet_name": sheet_name,
            "tab_title": tab_name,
            "row_number": row_idx + 1
        })
    
    return records


def parse_standard_sheet_data(values, sheet_name, tab_name):
    """Parse standard sheet format with 'Opportunities Posted on 22nd September' headers"""
    records = []
    
    if not values:
        return records
    
    current_date = ""
    header_indices = {}
    data_start_row = 0
    
    # Find headers and structure
    for row_idx, row in enumerate(values):
        row_str = [str(cell).strip() if cell else "" for cell in row]
        row_text = " ".join(row_str)
        
        # Check for date headers first
        date_match = is_september_date_header(row_text)
        if date_match:
            current_date = date_match
            print(f"        📅 Found date: {current_date}")
            continue
        
        # Look for column headers
        row_text_lower = row_text.lower()
        if any(keyword in row_text_lower for keyword in ["company", "role", "location"]):
            for col_idx, header in enumerate(row_str):
                header_lower = header.lower()
                if "company" in header_lower:
                    header_indices["company"] = col_idx
                elif "role" in header_lower or "position" in header_lower:
                    header_indices["role"] = col_idx
                elif "location" in header_lower:
                    header_indices["location"] = col_idx
            data_start_row = row_idx + 1
            print(f"      🔍 Standard headers found at row {row_idx + 1}: {header_indices}")
            break
    
    # Process data rows
    for row_idx, row in enumerate(values[data_start_row:], data_start_row + 1):
        row_str = [str(cell).strip() if cell else "" for cell in row]
        row_text = " ".join(row_str)
        
        # Check for new date headers
        date_match = is_september_date_header(row_text)
        if date_match:
            current_date = date_match
            print(f"        📅 Updated date: {current_date}")
            continue
        
        # Skip if no September date context
        if not current_date:
            continue
        
        # Look for LinkedIn URLs
        linkedin_url = ""
        for col_idx, cell in enumerate(row):
            if cell and ("linkedin.com" in str(cell) or "lnkd.in" in str(cell)):
                linkedin_url = str(cell).strip()
                break
        
        if not linkedin_url:
            continue
        
        # Extract metadata
        def get_cell(col_idx):
            return str(row[col_idx]).strip() if col_idx is not None and col_idx < len(row) and row[col_idx] else ""
        
        company = get_cell(header_indices.get("company"))
        role = get_cell(header_indices.get("role"))
        location = get_cell(header_indices.get("location"))
        
        records.append({
            "date": current_date,
            "company": company,
            "role": role,
            "location": location,
            "url": linkedin_url,
            "sheet_name": sheet_name,
            "tab_title": tab_name,
            "row_number": row_idx + 1
        })
    
    return records


def save_to_csv(records, output_path):
    """Save records to CSV in the same format as the working system"""
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    columns = ["date", "company", "role", "location", "url", "sheet_name", "tab_title", "row_number"]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)
    
    print(f"✅ Saved {len(records)} records to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Enhanced September data extractor with regex patterns")
    parser.add_argument("--dry-run", action="store_true", help="Just show what would be extracted")
    parser.add_argument("--output", default="./storage/ingest/google_sheets/september_enhanced.csv",
                       help="Output CSV path")
    
    args = parser.parse_args()
    
    print("🚀 Enhanced September Data Extraction with Regex Logic")
    print("=" * 55)
    
    try:
        # Extract the data
        records = extract_september_data()
        
        if not records:
            print("⚠️ No September records extracted")
            return False
        
        print(f"\n📊 Extraction Summary:")
        print(f"  🔗 Total September records: {len(records)}")
        
        # Show samples grouped by date
        dates = {}
        for record in records:
            date = record.get('date', 'Unknown')
            if date not in dates:
                dates[date] = []
            dates[date].append(record)
        
        print(f"\n📋 Records by date:")
        for date, date_records in dates.items():
            print(f"  📅 {date}: {len(date_records)} records")
            for i, record in enumerate(date_records[:2], 1):  # Show 2 samples per date
                print(f"    {i}. {record.get('company', 'N/A')} - {record.get('role', 'N/A')} in {record.get('location', 'N/A')}")
        
        if args.dry_run:
            print(f"\n💡 This was a dry run. Use without --dry-run to save CSV.")
            return True
        
        # Save to CSV
        save_to_csv(records, args.output)
        
        print(f"\n🎉 Extraction Complete!")
        print(f"  📄 CSV saved to: {args.output}")
        print(f"  💡 Next step: Import using:")
        print(f"     DATABASE_URL='postgresql://postgres:postgres@localhost:5432/data_lake' python -m src.app import-and-backup --csv {args.output} --backup-dir ./storage/backups")
        
        return True
        
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)