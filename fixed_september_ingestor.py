#!/usr/bin/env python3
"""
Fixed September Ingestor - Correct Column Mapping
Extracts data from Google Sheets with the correct column structure based on screenshots.

Soul in Product Sheet Structure:
A: Opportunity No, B: Company, C: Role, D: Location, E: Industry/Domain, F: Post Link, G: Experience, H: CTC, I: Email

Growth Desk Sheet Structure:  
A: Company, B: Role, C: Location, D: Link, E: CTC, F: Experience
"""

import os
import sys
import csv
import re
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

# Add src to Python path
sys.path.insert(0, 'src')
from src.clients.google_sheets import GoogleSheetsClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Sheets configuration with correct column mapping
SHEETS_CONFIG = [
    {
        "id": "1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q",
        "name": "Job Dashboard - The Growth Desk",
        "tabs": ["September (2025)"],
        "columns": {
            "company": 0,    # Column A
            "role": 1,       # Column B  
            "location": 2,   # Column C
            "url": 3,        # Column D (Link)
            "ctc": 4,        # Column E
            "experience": 5  # Column F
        }
    },
    {
        "id": "1p7O7tUBYM94IqEmIlXp8a5B0nGdX8DwP-bmVFu0FAK0",
        "name": "Soul in Product - Dashboard", 
        "tabs": ["September Openings "],
        "columns": {
            "opportunity_no": 0,  # Column A
            "company": 1,         # Column B
            "role": 2,            # Column C
            "location": 3,        # Column D
            "industry": 4,        # Column E
            "url": 5,             # Column F (Post Link)
            "experience": 6,      # Column G
            "ctc": 7,            # Column H
            "email": 8           # Column I
        }
    }
]

# September date patterns
SEPTEMBER_PATTERNS = [
    re.compile(r"(?i)opportunities?\s+posted\s+on\s+(\d{1,2})(?:st|nd|rd|th)?\s+september", re.IGNORECASE),
    re.compile(r"(?i)(\d{1,2})(?:st|nd|rd|th)?\s+september", re.IGNORECASE),
    re.compile(r"(?i)september\s+(\d{1,2})(?:st|nd|rd|th)?", re.IGNORECASE),
    re.compile(r"(?i)(\d{1,2})(?:th|st|nd|rd)?\s+sep(?:tember)?", re.IGNORECASE)
]

def setup_environment():
    """Setup environment variables"""
    env_vars = {
        "GOOGLE_OAUTH_CLIENT_JSON": "./client_secret_28309019366-uep6ho3i3k5096d1od4fo8gp1c1tj375.apps.googleusercontent.com.json",
        "GOOGLE_OAUTH_TOKEN_JSON": "./.secrets/google_token.json",
        "GOOGLE_OAUTH_REDIRECT_PORT": "8765"
    }
    
    for key, value in env_vars.items():
        if key not in os.environ:
            os.environ[key] = value

def extract_september_date(text: str) -> str:
    """Extract September date from text"""
    if not text:
        return ""
    
    for pattern in SEPTEMBER_PATTERNS:
        match = pattern.search(text)
        if match:
            day = match.group(1)
            return f"Sep {day}, 2025"
    
    return ""

def get_cell_value(row: List, col_idx: int) -> str:
    """Safely get cell value"""
    if col_idx < len(row) and row[col_idx]:
        return str(row[col_idx]).strip()
    return ""

def parse_growth_desk_sheet(values: List[List], sheet_name: str, tab_name: str, sheet_id: str) -> List[Dict[str, Any]]:
    """Parse Job Dashboard - The Growth Desk sheet with correct column mapping"""
    records = []
    if not values:
        return records
    
    logger.info(f"  Parsing Growth Desk sheet with {len(values)} rows")
    
    current_date = ""
    
    for row_idx, row in enumerate(values):
        if not row:
            continue
            
        row_text = " ".join([str(cell).strip() for cell in row if cell])
        
        # Check for September date headers - handle formats like "1st September"
        if len(row) == 1 and row[0]:
            cell_text = str(row[0]).strip().lower()
            # Look for date patterns like "1st September", "2nd September", "24th September"
            import re
            date_pattern = r'(\d{1,2})(?:st|nd|rd|th)?\s+september'
            match = re.search(date_pattern, cell_text)
            if match:
                day = match.group(1)
                current_date = f"Sep {day}, 2025"
                logger.debug(f"    Found date: {current_date}")
                continue
        
        # Skip header rows
        if any(word in row_text.lower() for word in ["company", "role", "location", "link"]):
            continue
        
        # Extract data using correct column mapping
        company = get_cell_value(row, 0)     # Column A
        role = get_cell_value(row, 1)        # Column B
        location = get_cell_value(row, 2)    # Column C
        url = get_cell_value(row, 3)         # Column D (Link)
        ctc = get_cell_value(row, 4)         # Column E
        experience = get_cell_value(row, 5)  # Column F
        
        # Must have URL and should be LinkedIn
        if not url or "linkedin.com" not in url:
            continue
            
        # Must have meaningful data (company is required)
        if not company or company in ["-", ""]:
            continue
        
        # Use current date if available, otherwise use default
        record_date = current_date
        if not record_date:
            record_date = "Sep 1, 2025"  # Default based on debug output
        
        record = {
            "url": url,
            "company": company,
            "role": role,
            "location": location,
            "experience": experience,
            "ctc": ctc,
            "date_in_source": record_date,
            "sheet_name": sheet_name,
            "tab": tab_name.strip(),
            "row_number": row_idx + 1,
            "spreadsheet_id": sheet_id,
            "spreadsheet_title": sheet_name,
            "source": "google_sheet_fixed",
            "classification": "job" if "/jobs/" in url else ("post" if "/posts/" in url else "other"),
            "category": "jobs" if "/jobs/" in url else ("posts" if "/posts/" in url else "others"),
            "status": "queued",
            "priority": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "discovered_at": datetime.now(timezone.utc),
            "extracted_at": datetime.now(timezone.utc),
            "attempt_count": 0,
            "next_attempt_at": datetime.now(timezone.utc),
            "url_canonical": url.lower()
        }
        
        records.append(record)
        logger.debug(f"    Extracted: {company} - {role} - {url}")
    
    logger.info(f"  Extracted {len(records)} Growth Desk records")
    return records

def parse_soul_product_sheet(values: List[List], sheet_name: str, tab_name: str, sheet_id: str) -> List[Dict[str, Any]]:
    """Parse Soul in Product sheet with correct column mapping"""
    records = []
    if not values:
        return records
    
    logger.info(f"  Parsing Soul in Product sheet with {len(values)} rows")
    
    current_date = ""
    
    for row_idx, row in enumerate(values):
        if not row:
            continue
            
        row_text = " ".join([str(cell).strip() for cell in row if cell])
        
        # Check for September date headers
        date_match = extract_september_date(row_text)
        if date_match:
            current_date = date_match
            logger.debug(f"    Found date: {current_date}")
            continue
        
        # Skip header rows
        if any(word in row_text.lower() for word in ["opportunity", "company", "role", "location"]):
            continue
            
        # Extract data using correct column mapping
        opportunity_no = get_cell_value(row, 0)  # Column A
        company = get_cell_value(row, 1)         # Column B
        role = get_cell_value(row, 2)            # Column C
        location = get_cell_value(row, 3)        # Column D
        industry = get_cell_value(row, 4)        # Column E
        url = get_cell_value(row, 5)             # Column F (Post Link)
        experience = get_cell_value(row, 6)      # Column G
        ctc = get_cell_value(row, 7)            # Column H
        email = get_cell_value(row, 8)          # Column I
        
        # Must have URL and should be LinkedIn
        if not url or "linkedin.com" not in url:
            continue
            
        # Must have meaningful data
        if not any([company, role, location]):
            continue
        
        # Use current date if available
        record_date = current_date
        if not record_date:
            record_date = "Sep 24, 2025"  # Default based on screenshots
        
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
            "sheet_name": sheet_name,
            "tab": tab_name.strip(),
            "row_number": row_idx + 1,
            "spreadsheet_id": sheet_id,
            "spreadsheet_title": sheet_name,
            "source": "google_sheet_fixed",
            "classification": "job" if "/jobs/" in url else ("post" if "/posts/" in url else "other"),
            "category": "jobs" if "/jobs/" in url else ("posts" if "/posts/" in url else "others"),
            "status": "queued",
            "priority": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "discovered_at": datetime.now(timezone.utc),
            "extracted_at": datetime.now(timezone.utc),
            "attempt_count": 0,
            "next_attempt_at": datetime.now(timezone.utc),
            "url_canonical": url.lower()
        }
        
        records.append(record)
        logger.debug(f"    Extracted: {company} - {role} - {url}")
    
    logger.info(f"  Extracted {len(records)} Soul in Product records")
    return records

def main():
    logger.info("🚀 Starting Fixed September Ingestion")
    logger.info("=" * 50)
    
    setup_environment()
    
    # Initialize Google Sheets client
    try:
        client = GoogleSheetsClient()
        logger.info("✅ Google Sheets client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Google Sheets client: {e}")
        return
    
    all_records = []
    
    # Process each sheet
    for sheet_config in SHEETS_CONFIG:
        try:
            sheet_id = sheet_config["id"]
            sheet_name = sheet_config["name"]
            
            logger.info(f"Processing sheet: {sheet_name}")
            
            for tab_name in sheet_config["tabs"]:
                logger.info(f"  Processing tab: {tab_name}")
                
                # Get sheet data
                values = client.get_values(sheet_id, tab_name)
                logger.info(f"    Retrieved {len(values)} rows")
                
                # Parse based on sheet type
                if "Growth Desk" in sheet_name:
                    records = parse_growth_desk_sheet(values, sheet_name, tab_name, sheet_id)
                elif "Soul in Product" in sheet_name:
                    records = parse_soul_product_sheet(values, sheet_name, tab_name, sheet_id)
                else:
                    logger.warning(f"    Unknown sheet type: {sheet_name}")
                    continue
                
                all_records.extend(records)
                logger.info(f"    ✅ Extracted {len(records)} records")
                
        except Exception as e:
            logger.error(f"❌ Failed to process sheet {sheet_name}: {e}")
            continue
    
    if not all_records:
        logger.error("❌ No records extracted")
        return
    
    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = f"./storage/production/september_FIXED_extraction_{timestamp}.csv"
    
    # Ensure output directory exists
    Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Define all columns
    columns = [
        "url", "company", "role", "location", "experience", "ctc", "industry", 
        "opportunity_no", "email", "date_in_source", "sheet_name", "tab", 
        "row_number", "spreadsheet_id", "spreadsheet_title", "source", 
        "classification", "category", "status", "priority", "created_at", 
        "updated_at", "discovered_at", "extracted_at", "attempt_count", 
        "next_attempt_at", "url_canonical"
    ]
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_records)
    
    logger.info(f"💾 Saved {len(all_records)} records to {csv_path}")
    
    # Print summary
    logger.info("\n🎉 Fixed Ingestion Complete!")
    logger.info(f"📊 Total records extracted: {len(all_records)}")
    
    # Breakdown by sheet
    logger.info("📋 Per-sheet breakdown:")
    for sheet_name in set(r["sheet_name"] for r in all_records):
        count = sum(1 for r in all_records if r["sheet_name"] == sheet_name)
        logger.info(f"  • {sheet_name}: {count} records")
    
    # Breakdown by type
    logger.info("📊 By content type:")
    for category in set(r["category"] for r in all_records):
        count = sum(1 for r in all_records if r["category"] == category)
        logger.info(f"  • {category}: {count} records")
    
    logger.info(f"📄 CSV saved to: {csv_path}")

if __name__ == "__main__":
    main()