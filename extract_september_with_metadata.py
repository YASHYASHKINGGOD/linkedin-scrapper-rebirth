#!/usr/bin/env python3
"""
Extract September 2025 data with full metadata from Google Sheets

This script extracts September LinkedIn links with company/role/location metadata
using the same authentication system as the working ingest scripts.

Usage:
    python extract_september_with_metadata.py [--dry-run]
"""

import os
import sys
import csv
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


def extract_september_data():
    """Extract September data with metadata using manual approach"""
    
    setup_environment()
    client = GoogleSheetsClient()
    
    # Define the working sheets
    sheets_config = [
        {
            "id": "1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q",
            "name": "Job Dashboard - The Growth Desk",
            "september_tab": "September (2025)"
        },
        {
            "id": "1p7O7tUBYM94IqEmIlXp8a5B0nGdX8DwP-bmVFu0FAK0", 
            "name": "Soul in Product - Dashboard",
            "september_tab": "September Openings "
        }
    ]
    
    all_records = []
    
    for sheet in sheets_config:
        print(f"\n📊 Processing: {sheet['name']}")
        
        try:
            # Get the September tab data
            values = client.get_values(sheet["id"], sheet["september_tab"])
            
            print(f"  📋 Found {len(values)} rows in {sheet['september_tab']}")
            
            # Parse the data - we need to identify the structure
            records = parse_sheet_data(values, sheet["name"], sheet["september_tab"])
            all_records.extend(records)
            
            print(f"  ✅ Extracted {len(records)} records with metadata")
            
        except Exception as e:
            print(f"  ❌ Failed to process {sheet['name']}: {e}")
            continue
    
    return all_records


def parse_sheet_data(values, sheet_name, tab_name):
    """Parse sheet data to extract LinkedIn URLs with metadata"""
    records = []
    
    if not values:
        return records
    
    # Find header row and column indices
    header_indices = {}
    data_start_row = 0
    current_date = ""
    
    for row_idx, row in enumerate(values):
        # Convert row to strings
        row_str = [str(cell).strip() if cell else "" for cell in row]
        
        # Check if this looks like a header row
        row_text = " ".join(row_str).lower()
        if any(keyword in row_text for keyword in ["company", "role", "position", "location", "link", "url"]):
            # Found header row
            for col_idx, header in enumerate(row_str):
                header_lower = header.lower()
                if "company" in header_lower:
                    header_indices["company"] = col_idx
                elif "role" in header_lower or "position" in header_lower:
                    header_indices["role"] = col_idx
                elif "location" in header_lower:
                    header_indices["location"] = col_idx
                elif "link" in header_lower or "url" in header_lower:
                    header_indices["url"] = col_idx
            
            data_start_row = row_idx + 1
            print(f"    🔍 Found headers at row {row_idx + 1}: {header_indices}")
            break
    
    # If no explicit headers found, try to infer from data patterns
    if not header_indices:
        print("    🔍 No explicit headers found, trying to infer structure...")
        # Look for URLs in the data to infer structure
        for row_idx, row in enumerate(values[:10]):  # Check first 10 rows
            for col_idx, cell in enumerate(row):
                if cell and "linkedin.com" in str(cell):
                    header_indices["url"] = col_idx
                    # Assume common patterns: Company, Role, Location, URL
                    if col_idx >= 3:
                        header_indices["company"] = max(0, col_idx - 3)
                        header_indices["role"] = max(0, col_idx - 2)
                        header_indices["location"] = max(0, col_idx - 1)
                    data_start_row = 1
                    break
            if header_indices:
                break
    
    print(f"    🎯 Using column mapping: {header_indices}")
    
    # Extract data rows
    for row_idx, row in enumerate(values[data_start_row:], data_start_row + 1):
        try:
            # Look for date headers (like "Sep 18, 2025" or "September 18")
            row_text = " ".join([str(cell) for cell in row if cell]).strip()
            if row_text and len(row_text) < 50 and any(month in row_text.lower() for month in ["sep", "september", "2025"]):
                current_date = row_text
                continue
            
            # Extract data from this row
            def get_cell(col_idx):
                return str(row[col_idx]).strip() if col_idx is not None and col_idx < len(row) and row[col_idx] else ""
            
            url = get_cell(header_indices.get("url"))
            
            # Only process rows with LinkedIn URLs
            if not url or ("linkedin.com" not in url and "lnkd.in" not in url):
                continue
            
            company = get_cell(header_indices.get("company"))
            role = get_cell(header_indices.get("role"))
            location = get_cell(header_indices.get("location"))
            
            # Skip if all metadata is empty
            if not any([company, role, location]):
                continue
            
            records.append({
                "date": current_date or "September 2025",
                "company": company,
                "role": role,
                "location": location,
                "url": url,
                "sheet_name": sheet_name,
                "tab_title": tab_name,
                "row_number": row_idx + 1
            })
            
        except Exception as e:
            print(f"    ⚠️ Error processing row {row_idx + 1}: {e}")
            continue
    
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
    parser = argparse.ArgumentParser(description="Extract September data with metadata")
    parser.add_argument("--dry-run", action="store_true", help="Just show what would be extracted")
    parser.add_argument("--output", default="./storage/ingest/google_sheets/september_extracted.csv",
                       help="Output CSV path")
    
    args = parser.parse_args()
    
    print("🚀 September Data Extraction with Metadata")
    print("=" * 50)
    
    try:
        # Extract the data
        records = extract_september_data()
        
        if not records:
            print("⚠️ No records extracted")
            return False
        
        print(f"\n📊 Extraction Summary:")
        print(f"  🔗 Total records extracted: {len(records)}")
        
        # Show samples
        print(f"\n📋 Sample records:")
        for i, record in enumerate(records[:3], 1):
            print(f"  {i}. {record.get('company', 'N/A')} - {record.get('role', 'N/A')} in {record.get('location', 'N/A')}")
        
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