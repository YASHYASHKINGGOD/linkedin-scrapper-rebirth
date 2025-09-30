#!/usr/bin/env python3
"""
Fix Missing Google Sheets Metadata in LinkedIn Links Database

This script reads the CSV files from Google Sheets ingestion and updates
the linkedin_links table with the missing metadata fields.

Usage:
    python fix_missing_sheets_metadata.py [--dry-run] [--limit N]
"""

import os
import csv
import argparse
import psycopg
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import sys

def get_database_connection():
    """Get database connection using user's preferred PostgreSQL URL"""
    database_url = "postgresql://postgres:postgres@localhost:5432/data_lake"
    try:
        return psycopg.connect(database_url)
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return None

def find_latest_csv_files() -> List[str]:
    """Find the most recent CSV files from Google Sheets ingestion"""
    storage_path = Path("./storage/ingest/google_sheets")
    if not storage_path.exists():
        print(f"❌ Storage path {storage_path} does not exist")
        return []
    
    # Find all timestamped directories
    csv_files = []
    for subdir in storage_path.iterdir():
        if subdir.is_dir():
            links_csv = subdir / "links.csv"
            if links_csv.exists():
                csv_files.append(str(links_csv))
    
    # Sort by modification time, most recent first
    csv_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    print(f"📁 Found {len(csv_files)} CSV files")
    for csv_file in csv_files[:5]:  # Show first 5
        mtime = datetime.fromtimestamp(os.path.getmtime(csv_file))
        print(f"  • {csv_file} (modified: {mtime})")
    
    return csv_files

def read_csv_metadata(csv_file: str) -> List[Dict[str, Any]]:
    """Read metadata from a CSV file"""
    records = []
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            first_row = True
            
            for row_num, row in enumerate(reader, 2):  # Start from row 2 (after header)
                if first_row:
                    print(f"📝 CSV columns: {list(row.keys())}")
                    first_row = False
                
                # Clean up the URL - remove any leading 'www.' artifacts
                url = row.get('url', '').strip()
                if url.startswith('www.') or not url:
                    continue  # Skip invalid URLs
                
                # Only process actual LinkedIn URLs
                if 'linkedin.com' not in url and 'lnkd.in' not in url:
                    continue
                
                # Normalize LinkedIn URLs
                if url.startswith('https://lnkd.in/'):
                    # For lnkd.in links, we'll store them as-is
                    pass
                elif 'linkedin.com' in url:
                    # Clean up LinkedIn URLs
                    if not url.startswith('http'):
                        url = 'https://' + url
                
                # Handle both formats - new format and old format
                record = {
                    'url': url,
                    'source': row.get('source', 'google_sheet'),
                    'spreadsheet_id': row.get('spreadsheet_id', ''),
                    'spreadsheet_title': row.get('spreadsheet_title', ''),
                    'spreadsheet_url': row.get('spreadsheet_url', ''),
                    'sheet_name': row.get('sheet_name', ''),
                    'tab_title': row.get('tab_title', ''),
                    'tab_gid': row.get('tab_gid', ''),
                    'discovered_at': row.get('discovered_at', ''),
                    'company': row.get('company', ''),
                    'role': row.get('role', ''),
                    'location': row.get('location', ''),
                    'date': row.get('date', ''),
                    'row_number': row.get('row_number', str(row_num))
                }
                
                records.append(record)
                
                # Debug first few records
                if len(records) <= 3:
                    print(f"  🔍 Sample record {len(records)}: URL={url[:60]}..., Company={record['company']}, Role={record['role']}")
        
        print(f"📋 Read {len(records)} valid LinkedIn links from {csv_file}")
        return records
        
    except Exception as e:
        print(f"❌ Failed to read {csv_file}: {e}")
        return []

def update_database_records(records: List[Dict[str, Any]], dry_run: bool = True, limit: Optional[int] = None) -> int:
    """Update database records with metadata from CSV"""
    
    if limit:
        records = records[:limit]
        print(f"🔧 Limiting updates to first {limit} records")
    
    conn = get_database_connection()
    if not conn:
        return 0
    
    updated_count = 0
    
    try:
        with conn:
            for i, record in enumerate(records, 1):
                try:
                    # First check if this URL exists in the database
                    cursor = conn.execute(
                        "SELECT id, spreadsheet_id FROM linkedin_links WHERE url = %s",
                        (record['url'],)
                    )
                    result = cursor.fetchone()
                    
                    if not result:
                        print(f"  ⚠️ URL not found in database: {record['url']}")
                        continue
                    
                    db_id, current_spreadsheet_id = result
                    
                    # Skip if metadata is already populated
                    if current_spreadsheet_id and current_spreadsheet_id.strip():
                        continue
                    
                    if dry_run:
                        print(f"  🔍 DRY RUN - Would update ID {db_id}: {record.get('company', 'N/A')} -> {record.get('role', 'N/A')} in {record.get('location', 'N/A')}")
                        updated_count += 1
                    else:
                        # Update the record with metadata
                        cursor = conn.execute("""
                            UPDATE linkedin_links 
                            SET 
                                spreadsheet_id = %s,
                                spreadsheet_title = %s,
                                sheet_name = %s,
                                tab = %s,
                                row_number = %s,
                                company = %s,
                                role = %s,
                                location = %s,
                                date_in_source = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (
                            record.get('spreadsheet_id', ''),
                            record.get('spreadsheet_title', ''),
                            record.get('sheet_name', ''),
                            record.get('tab_title', ''),
                            record.get('row_number', ''),
                            record.get('company', ''),
                            record.get('role', ''),
                            record.get('location', ''),
                            record.get('date', ''),
                            db_id
                        ))
                        
                        updated_count += 1
                        if i % 100 == 0:
                            print(f"  📝 Updated {updated_count} records so far...")
                
                except Exception as e:
                    print(f"  ❌ Failed to update record {i}: {e}")
                    continue
    
    except Exception as e:
        print(f"❌ Database operation failed: {e}")
        return 0
    
    finally:
        conn.close()
    
    action = "Would update" if dry_run else "Updated"
    print(f"✅ {action} {updated_count} records")
    return updated_count

def main():
    parser = argparse.ArgumentParser(
        description="Fix missing Google Sheets metadata in linkedin_links table"
    )
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be updated without making changes")
    parser.add_argument("--limit", type=int,
                       help="Limit number of records to process (for testing)")
    parser.add_argument("--csv", 
                       help="Specific CSV file to process (otherwise use latest)")
    
    args = parser.parse_args()
    
    print("🔧 LinkedIn Links Metadata Fixer")
    print("=" * 40)
    
    # Find CSV files
    if args.csv:
        csv_files = [args.csv] if os.path.exists(args.csv) else []
    else:
        csv_files = find_latest_csv_files()
    
    if not csv_files:
        print("❌ No CSV files found")
        return False
    
    # Read metadata from the most recent CSV
    print(f"📖 Processing: {csv_files[0]}")
    records = read_csv_metadata(csv_files[0])
    
    if not records:
        print("❌ No valid records found in CSV")
        return False
    
    # Update database
    updated_count = update_database_records(records, dry_run=args.dry_run, limit=args.limit)
    
    # Summary
    print(f"\n🎉 Process Complete!")
    print(f"  📊 Records processed: {len(records)}")
    print(f"  ✅ Records updated: {updated_count}")
    
    if args.dry_run:
        print(f"\n💡 This was a dry run. Use without --dry-run to apply changes.")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)