#!/usr/bin/env python3
"""
Corrected Final September Ingestor
Fixed Growth Desk column mapping based on debug analysis
"""

import os
import sys
import csv
import re
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any

sys.path.insert(0, 'src')
from src.clients.google_sheets import GoogleSheetsClient

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Setup environment
env_vars = {
    "GOOGLE_OAUTH_CLIENT_JSON": "./client_secret_28309019366-uep6ho3i3k5096d1od4fo8gp1c1tj375.apps.googleusercontent.com.json",
    "GOOGLE_OAUTH_TOKEN_JSON": "./.secrets/google_token.json",
    "GOOGLE_OAUTH_REDIRECT_PORT": "8765"
}

for key, value in env_vars.items():
    if key not in os.environ:
        os.environ[key] = value

def get_cell_value(row, col_idx):
    """Safely get cell value"""
    if col_idx < len(row) and row[col_idx]:
        return str(row[col_idx]).strip()
    return ""

def extract_growth_desk_data(values):
    """Extract data from Growth Desk sheet with corrected column mapping"""
    records = []
    current_date = ""
    
    logger.info(f"Processing {len(values)} rows from Growth Desk")
    
    for row_idx, row in enumerate(values):
        if not row:
            continue
        
        # Handle date rows (single cell with date)
        if len(row) == 1 and row[0]:
            cell_text = str(row[0]).strip().lower()
            # Match patterns like "1st September", "24th September"
            date_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+september', cell_text)
            if date_match:
                day = date_match.group(1)
                current_date = f"Sep {day}, 2025"
                logger.info(f"  Found date section: {current_date}")
                continue
        
        # Skip header rows - be more specific to avoid false positives
        row_text = " ".join([str(cell).strip() for cell in row if cell]).lower()
        # Only skip if it looks like an actual header (has multiple header keywords)
        header_keywords = ["company", "role", "location", "link", "ctc", "experience"]
        header_matches = sum(1 for word in header_keywords if word in row_text)
        if header_matches >= 3:  # Must have at least 3 header keywords to be considered a header
            logger.debug(f"  Skipping row {row_idx + 1}: Header row with {header_matches} keywords")
            continue
        
        # Extract data from columns - CORRECTED MAPPING based on debug output
        company = get_cell_value(row, 0)    # Column A - Company
        role = get_cell_value(row, 1)       # Column B - Role  
        location = get_cell_value(row, 2)   # Column C - Location
        
        # Search for LinkedIn URL in any column (robust approach)
        url = ""
        for i, cell in enumerate(row):
            if cell and "linkedin.com" in str(cell):
                url = str(cell).strip()
                break
        
        # If no LinkedIn URL found, skip
        if not url:
            logger.debug(f"  Skipping row {row_idx + 1}: No LinkedIn URL found in any column")
            continue
        
        # Extract remaining fields
        ctc = get_cell_value(row, 4)        # Column E - CTC
        experience = get_cell_value(row, 5)  # Column F - Experience
        
        # Must have company and not be just a dash
        if not company or company.strip() == "-":
            logger.debug(f"  Skipping row {row_idx + 1}: Invalid company (company='{company}')")
            continue
        
        # Debug: Log when we find a valid record
        logger.debug(f"  Valid record found at row {row_idx + 1}: {company} - {role} - {url}")
        
        # Use current date or default
        record_date = current_date if current_date else "Sep 1, 2025"
        
        record = {
            "url": url,
            "company": company,
            "role": role,
            "location": location,
            "experience": experience,
            "ctc": ctc,
            "date_in_source": record_date,
            "sheet_name": "Job Dashboard - The Growth Desk",
            "tab": "September (2025)",
            "row_number": row_idx + 1,
            "spreadsheet_id": "1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q",
            "classification": "job" if "/jobs/" in url else ("post" if "/posts/" in url else "other"),
            "category": "jobs" if "/jobs/" in url else ("posts" if "/posts/" in url else "others")
        }
        
        records.append(record)
        logger.debug(f"  Added record from row {row_idx + 1}: {company} - {role}")
        
    logger.info(f"Extracted {len(records)} records from Growth Desk")
    return records

def extract_soul_product_data(values):
    """Extract data from Soul in Product sheet"""
    records = []
    current_date = ""
    
    logger.info(f"Processing {len(values)} rows from Soul in Product")
    
    for row_idx, row in enumerate(values):
        if not row:
            continue
        
        # Look for date headers in the sheet content
        row_text = " ".join([str(cell).strip() for cell in row if cell])
        
        # Handle date patterns like "Opportunities Posted on 23rd September"
        date_match = re.search(r'opportunities\s+posted\s+on\s+(\d{1,2})(?:st|nd|rd|th)?\s+september', row_text.lower())
        if date_match:
            day = date_match.group(1)
            current_date = f"Sep {day}, 2025"
            logger.info(f"  Found date section: {current_date}")
            continue
        
        # Skip header rows
        if any(word in row_text.lower() for word in ["opportunity", "company", "role", "location", "post link"]):
            continue
        
        # Extract data using Soul in Product column structure
        opportunity_no = get_cell_value(row, 0)
        company = get_cell_value(row, 1)
        role = get_cell_value(row, 2)
        location = get_cell_value(row, 3)
        industry = get_cell_value(row, 4)
        url = get_cell_value(row, 5)
        experience = get_cell_value(row, 6)
        ctc = get_cell_value(row, 7)
        email = get_cell_value(row, 8)
        
        # Must have LinkedIn URL
        if not url or "linkedin.com" not in url:
            continue
        
        # Must have company
        if not company:
            continue
        
        # Use current date or default to Sep 24 (latest based on screenshots)
        record_date = current_date if current_date else "Sep 24, 2025"
        
        record = {
            "url": url,
            "company": company,
            "role": role,
            "location": location,
            "experience": experience,
            "ctc": ctc,
            "industry": industry,
            "opportunity_no": opportunity_no,
            "email": email,
            "date_in_source": record_date,
            "sheet_name": "Soul in Product - Dashboard",
            "tab": "September Openings",
            "row_number": row_idx + 1,
            "spreadsheet_id": "1p7O7tUBYM94IqEmIlXp8a5B0nGdX8DwP-bmVFu0FAK0",
            "classification": "job" if "/jobs/" in url else ("post" if "/posts/" in url else "other"),
            "category": "jobs" if "/jobs/" in url else ("posts" if "/posts/" in url else "others")
        }
        
        records.append(record)
    
    logger.info(f"Extracted {len(records)} records from Soul in Product")
    return records

def main():
    logger.info("🚀 Corrected September Ingestion - Fixed Column Mapping")
    logger.info("=" * 60)
    
    # Initialize Google Sheets client
    client = GoogleSheetsClient()
    logger.info("✅ Google Sheets client initialized")
    
    all_records = []
    
    # Process Growth Desk sheet
    logger.info("📋 Processing Job Dashboard - The Growth Desk")
    try:
        values = client.get_values("1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q", "September (2025)")
        growth_records = extract_growth_desk_data(values)
        all_records.extend(growth_records)
    except Exception as e:
        logger.error(f"❌ Failed to process Growth Desk: {e}")
    
    # Process Soul in Product sheet  
    logger.info("📋 Processing Soul in Product - Dashboard")
    try:
        values = client.get_values("1p7O7tUBYM94IqEmIlXp8a5B0nGdX8DwP-bmVFu0FAK0", "September Openings ")
        soul_records = extract_soul_product_data(values)
        all_records.extend(soul_records)
    except Exception as e:
        logger.error(f"❌ Failed to process Soul in Product: {e}")
    
    logger.info(f"🎯 Total records extracted: {len(all_records)}")
    
    # Save to CSV
    storage_dir = Path("./storage/production")
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"september_CORRECTED_extraction_{timestamp}.csv"
    csv_path = storage_dir / csv_filename
    
    # Define all possible columns
    all_columns = [
        "url", "company", "role", "location", "experience", "ctc", 
        "industry", "opportunity_no", "email", "date_in_source", 
        "sheet_name", "tab", "row_number", "spreadsheet_id", 
        "classification", "category"
    ]
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=all_columns)
        writer.writeheader()
        
        for record in all_records:
            # Fill missing columns with empty strings
            complete_record = {col: record.get(col, '') for col in all_columns}
            writer.writerow(complete_record)
    
    logger.info(f"💾 CSV saved: {csv_path}")
    
    # Summary statistics
    growth_count = len([r for r in all_records if "Growth Desk" in r.get("sheet_name", "")])
    soul_count = len([r for r in all_records if "Soul in Product" in r.get("sheet_name", "")])
    
    job_count = len([r for r in all_records if r.get("classification") == "job"])
    post_count = len([r for r in all_records if r.get("classification") == "post"])
    other_count = len([r for r in all_records if r.get("classification") == "other"])
    
    logger.info("📊 EXTRACTION SUMMARY:")
    logger.info(f"   Growth Desk records: {growth_count}")
    logger.info(f"   Soul in Product records: {soul_count}")
    logger.info(f"   Jobs: {job_count}")
    logger.info(f"   Posts: {post_count}")
    logger.info(f"   Others: {other_count}")
    
    return csv_path, len(all_records)

if __name__ == "__main__":
    csv_path, total_records = main()
    print(f"\n✅ Extraction complete!")
    print(f"📁 Output: {csv_path}")
    print(f"📊 Records: {total_records}")