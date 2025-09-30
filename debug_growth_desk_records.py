#!/usr/bin/env python3

import sys
import re
from datetime import datetime

sys.path.insert(0, 'src')
from src.clients.google_sheets import GoogleSheetsClient

# Google Sheets setup - use the correct credential files
import os

# Setup environment like the main ingestor
env_vars = {
    "GOOGLE_OAUTH_CLIENT_JSON": "./client_secret_28309019366-uep6ho3i3k5096d1od4fo8gp1c1tj375.apps.googleusercontent.com.json",
    "GOOGLE_OAUTH_TOKEN_JSON": "./.secrets/google_token.json",
    "GOOGLE_OAUTH_REDIRECT_PORT": "8765"
}

for key, value in env_vars.items():
    if key not in os.environ:
        os.environ[key] = value

def get_growth_desk_data():
    """Debug the Growth Desk sheet parsing"""
    
    # Initialize Google Sheets client
    client = GoogleSheetsClient()
    
    # Get all values from Growth Desk sheet
    all_values = client.get_values("1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q", "September (2025)")
    
    print(f"Total rows in Growth Desk sheet: {len(all_values)}")
    print("\n=== First 10 rows ===")
    for i, row in enumerate(all_values[:10]):
        print(f"Row {i+1}: {row}")
    
    # Look for date patterns
    date_pattern = r'\d+(?:st|nd|rd|th)?\s+September'
    print(f"\n=== Searching for date headers with pattern: {date_pattern} ===")
    
    current_date = None
    records_found = 0
    
    for row_idx, row in enumerate(all_values):
        # Check if this is a date header
        for cell in row:
            if cell and re.search(date_pattern, cell, re.IGNORECASE):
                current_date = cell
                print(f"Found date header at row {row_idx+1}: '{cell}'")
                continue
        
        # Skip if no current date
        if not current_date:
            continue
            
        # Check for LinkedIn URLs in this row
        linkedin_url = None
        for cell in row:
            if cell and 'linkedin.com' in cell:
                linkedin_url = cell
                break
        
        if linkedin_url:
            # Extract other fields based on expected column positions
            company = row[0] if len(row) > 0 else ""
            role = row[1] if len(row) > 1 else ""
            location = row[2] if len(row) > 2 else ""
            experience = row[4] if len(row) > 4 else ""
            ctc = row[3] if len(row) > 3 else ""
            
            print(f"\n--- Potential record at row {row_idx+1} ---")
            print(f"Date: {current_date}")
            print(f"Company: '{company}'")
            print(f"Role: '{role}'")
            print(f"Location: '{location}'")
            print(f"Experience: '{experience}'")
            print(f"CTC: '{ctc}'")
            print(f"URL: {linkedin_url}")
            
            # Apply validation logic from the ingestor
            if company and company.strip() and company.strip() != "-":
                print("✓ VALID RECORD (company not empty)")
                records_found += 1
            else:
                print("✗ INVALID RECORD (company empty or '-')")
                
            print(f"Full row: {row}")
    
    print(f"\n=== Summary ===")
    print(f"Total valid records found: {records_found}")

if __name__ == "__main__":
    get_growth_desk_data()