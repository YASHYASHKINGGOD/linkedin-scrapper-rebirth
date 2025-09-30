#!/usr/bin/env python3
"""
Import September LinkedIn URLs into database
Converts our CSV format to the expected import format and uses the robust import pipeline.
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.append('src')
from db.import_and_backup import import_and_backup

# Database configuration
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/data_lake"
INPUT_CSV = "./storage/production/clean_september_output.csv"
TEMP_CSV = "./storage/production/september_for_import.csv"
BACKUP_DIR = "./storage/backups"

def convert_csv_format():
    """Convert our September CSV to the expected import format."""
    print("🔄 Converting CSV format for database import...")
    
    # Expected columns: date,company,role,location,url,sheet_name,tab_title,row_number
    converted_rows = []
    
    with open(INPUT_CSV, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        
        row_num = 1
        for row in reader:
            # Extract company from company_clean or URL for posts
            company = row.get('company_clean', 'Unknown')
            if company == 'No Company':
                company = 'Unknown'
            
            # Generate role based on category
            if row['category'] == 'jobs':
                role = 'Job Posting'
            else:
                role = 'Social Post'
            
            converted_row = {
                'date': row['date_in_source'].replace('"', ''),  # Clean quoted dates
                'company': company,
                'role': role,
                'location': row.get('location', 'Unknown'),
                'url': row['url'],
                'sheet_name': row['sheet_name'],
                'tab_title': row['sheet_name'],  # Use sheet_name as tab_title
                'row_number': row_num
            }
            
            converted_rows.append(converted_row)
            row_num += 1
    
    # Write converted CSV
    os.makedirs(os.path.dirname(TEMP_CSV), exist_ok=True)
    
    with open(TEMP_CSV, 'w', encoding='utf-8', newline='') as outfile:
        fieldnames = ['date', 'company', 'role', 'location', 'url', 'sheet_name', 'tab_title', 'row_number']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(converted_rows)
    
    print(f"✅ Converted {len(converted_rows)} URLs to import format")
    print(f"📁 Saved to: {TEMP_CSV}")
    return TEMP_CSV

def main():
    """Import September URLs into the database."""
    print("🚀 SEPTEMBER URLS DATABASE IMPORT")
    print("=" * 50)
    
    # Check if input file exists
    if not os.path.exists(INPUT_CSV):
        print(f"❌ Input CSV not found: {INPUT_CSV}")
        sys.exit(1)
    
    # Convert CSV format
    converted_csv = convert_csv_format()
    
    try:
        print("\n🔄 Importing URLs into database...")
        
        # Use the robust import and backup system
        backup_path = import_and_backup(
            database_url=DATABASE_URL,
            csv_path=converted_csv,
            backup_dir=BACKUP_DIR,
            insert_window_minutes=10,
            create_provenance=True
        )
        
        print(f"✅ Successfully imported URLs!")
        print(f"📁 Backup created: {backup_path}")
        
        # Clean up temp file
        os.unlink(converted_csv)
        print(f"🧹 Cleaned up temporary file: {converted_csv}")
        
    except Exception as e:
        print(f"❌ Error during import: {e}")
        if os.path.exists(converted_csv):
            print(f"🔍 Debug: Check temp file at {converted_csv}")
        sys.exit(1)
    
    print("\n🎉 September URLs import completed successfully!")

if __name__ == "__main__":
    main()