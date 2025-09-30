#!/usr/bin/env python3

import os
import sys
import re
sys.path.insert(0, 'src')
from src.clients.google_sheets import GoogleSheetsClient

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

def main():
    client = GoogleSheetsClient()
    values = client.get_values("1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q", "September (2025)")
    
    print(f"Total rows: {len(values)}")
    print("\n=== Tracing extraction logic for first 15 rows ===")
    
    current_date = ""
    records_found = 0
    
    for row_idx in range(15):  # First 15 rows
        if row_idx >= len(values):
            break
            
        row = values[row_idx]
        print(f"\nRow {row_idx + 1}: {row}")
        
        # Check if empty row
        if not row:
            print("  -> Empty row, continuing")
            continue
        
        # Handle date rows (single cell with date)
        if len(row) == 1 and row[0]:
            cell_text = str(row[0]).strip().lower()
            date_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+september', cell_text)
            if date_match:
                day = date_match.group(1)
                current_date = f"Sep {day}, 2025"
                print(f"  -> DATE ROW: Set current_date = {current_date}")
                continue
            else:
                print(f"  -> Single cell but no date pattern: '{cell_text}'")
        
        # Skip header rows
        row_text = " ".join([str(cell).strip() for cell in row if cell]).lower()
        if any(word in row_text for word in ["company", "role", "location", "link", "ctc", "experience"]):
            print(f"  -> HEADER ROW: Skipping due to header keywords in '{row_text}'")
            continue
        
        print(f"  -> Processing row with current_date = {current_date}")
        
        # Extract data from columns
        company = get_cell_value(row, 0)
        role = get_cell_value(row, 1)
        location = get_cell_value(row, 2)
        
        print(f"     company='{company}', role='{role}', location='{location}'")
        
        # Search for LinkedIn URL in any column
        url = ""
        for i, cell in enumerate(row):
            if cell and "linkedin.com" in str(cell):
                url = str(cell).strip()
                print(f"     Found LinkedIn URL in column {i}: {url}")
                break
        
        if not url:
            print(f"  -> SKIP: No LinkedIn URL found")
            continue
        
        # Check company validation
        if not company or company.strip() == "-":
            print(f"  -> SKIP: Invalid company ('{company}')")
            continue
        
        # If we get here, this should be a valid record
        print(f"  -> ✓ VALID RECORD: {company} - {role}")
        records_found += 1
        
    print(f"\n=== SUMMARY ===")
    print(f"Records found in first 15 rows: {records_found}")

if __name__ == "__main__":
    main()