#!/usr/bin/env python3
"""
Final Corrected September Ingestor
Based on the actual sheet structures observed
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
    """Extract data from Growth Desk sheet"""
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
        
        # Skip header rows
        row_text = " ".join([str(cell).strip() for cell in row if cell]).lower()
        if any(word in row_text for word in ["company", "role", "location", "link", "ctc", "experience"]):
            continue
        
        # Extract data from columns
        company = get_cell_value(row, 0)
        role = get_cell_value(row, 1)
        location = get_cell_value(row, 2)
        url = get_cell_value(row, 3)
        ctc = get_cell_value(row, 4)
        experience = get_cell_value(row, 5)
        
        # Must have LinkedIn URL
        if not url or "linkedin.com" not in url:
            continue
        
        # Must have company (even if it's a dash, some entries have "-")
        if not company:
            continue
        
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
    logger.info("🚀 Final September Ingestion - Corrected Version")
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
    
    if not all_records:
        logger.error("❌ No records extracted")
        return
    
    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = f"./storage/production/september_FINAL_extraction_{timestamp}.csv"
    Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Define columns
    columns = [
        "url", "company", "role", "location", "experience", "ctc", "industry",
        "opportunity_no", "email", "date_in_source", "sheet_name", "tab",
        "row_number", "spreadsheet_id", "classification", "category"
    ]
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_records)
    
    logger.info(f"💾 Saved {len(all_records)} records to {csv_path}")
    
    # Print summary
    logger.info("\n🎉 Final Ingestion Summary:")
    logger.info(f"📊 Total records extracted: {len(all_records)}")
    
    # By sheet
    for sheet_name in set(r["sheet_name"] for r in all_records):
        count = sum(1 for r in all_records if r["sheet_name"] == sheet_name)
        logger.info(f"  • {sheet_name}: {count} records")
    
    # By type
    logger.info("📊 By content type:")
    for category in set(r["category"] for r in all_records):
        count = sum(1 for r in all_records if r["category"] == category)
        logger.info(f"  • {category}: {count} records")
    
    # By date
    logger.info("📅 By date:")
    dates = {}
    for record in all_records:
        date = record["date_in_source"]
        dates[date] = dates.get(date, 0) + 1
    
    for date, count in sorted(dates.items()):
        logger.info(f"  • {date}: {count} records")
    
    logger.info(f"📄 Final CSV: {csv_path}")

if __name__ == "__main__":
    main()