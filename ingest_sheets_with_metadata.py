#!/usr/bin/env python3
"""
Enhanced Google Sheets Ingestion with Full Metadata

This script extracts LinkedIn links from Google Sheets along with all available
metadata (company, role, location, etc.) and properly inserts it into the database.

Usage:
    python ingest_sheets_with_metadata.py [--dry-run] [--month-filter aug]
"""

import os
import sys
import argparse
import json
import psycopg
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add the src directory to Python path for imports
sys.path.insert(0, 'src')

from src.ingest.combined_links_csv import run_combined_csv
from src.extractor.common.io import write_csv


def get_database_connection():
    """Get database connection using user's preferred PostgreSQL URL"""
    database_url = "postgresql://postgres:postgres@localhost:5432/data_lake"
    try:
        return psycopg.connect(database_url)
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return None


def load_sheets_config():
    """Load Google Sheets URLs from config"""
    config_files = [
        "config/sheets_v2.yaml",
        "config/sheets.yaml.sample"
    ]
    
    sheets_urls = []
    
    # Try to load from YAML config first
    try:
        import yaml
        for config_file in config_files:
            if Path(config_file).exists():
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                    # Handle both formats: sheets: [...] and sheets: { urls: [...] }
                    sheets_data = config.get('sheets', [])
                    if isinstance(sheets_data, list):
                        sheets_urls = sheets_data
                    else:
                        sheets_urls = sheets_data.get('urls', [])
                    
                    if sheets_urls:
                        print(f"📋 Loaded {len(sheets_urls)} sheet URLs from {config_file}")
                        return sheets_urls
                        break
    except ImportError:
        print("⚠️ PyYAML not available, falling back to hardcoded URLs")
    except Exception as e:
        print(f"⚠️ Failed to load config: {e}, falling back to hardcoded URLs")
    
    # Fallback to hardcoded URLs (from the existing script)
    sheets_urls = [
        "https://docs.google.com/spreadsheets/d/1p7O7tUBYM94IqEmIlXp8a5B0nGdX8DwP-bmVFu0FAK0",
        "https://docs.google.com/spreadsheets/d/1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q",
        "https://docs.google.com/spreadsheets/d/1tXqhAyY5NLhPTXmhkCODdBJmA_hfJQdv4KwCc6HhsZM"
    ]
    
    print(f"📋 Using {len(sheets_urls)} hardcoded sheet URLs")
    return sheets_urls


def extract_links_with_metadata(month_filter: str = "sep") -> List[Dict[str, Any]]:
    """Extract links with full metadata from Google Sheets"""
    
    print(f"🔍 Extracting links with metadata for month filter: {month_filter}")
    
    sheets_urls = load_sheets_config()
    if not sheets_urls:
        print("❌ No sheet URLs configured")
        return []
    
    try:
        # Use the combined CSV extraction which gets full metadata
        result = run_combined_csv(sheets_urls, month_filter=month_filter)
        
        # Read the generated CSV to get the structured data
        csv_path = result.get("output_csv")
        if not csv_path or not Path(csv_path).exists():
            print(f"❌ Generated CSV not found: {csv_path}")
            return []
        
        print(f"📖 Reading extracted data from: {csv_path}")
        
        import csv
        records = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip rows without URLs
                url = row.get('url', '').strip()
                if not url or 'linkedin.com' not in url and 'lnkd.in' not in url:
                    continue
                
                records.append({
                    'url': url,
                    'company': row.get('company', '').strip(),
                    'role': row.get('role', '').strip(),
                    'location': row.get('location', '').strip(),
                    'date_in_source': row.get('date', '').strip(),
                    'sheet_name': row.get('sheet_name', '').strip(),
                    'tab_title': row.get('tab_title', '').strip(),
                    'row_number': row.get('row_number', '').strip(),
                    'source': 'google_sheets_v2',
                    'status': 'queued',
                    'priority': 0
                })
        
        print(f"✅ Extracted {len(records)} records with metadata")
        return records
        
    except Exception as e:
        print(f"❌ Failed to extract links with metadata: {e}")
        return []


def insert_records_with_metadata(records: List[Dict[str, Any]], dry_run: bool = False) -> int:
    """Insert records with full metadata into the database"""
    
    if dry_run:
        print(f"🔍 DRY RUN: Would insert {len(records)} records with metadata")
        for i, record in enumerate(records[:5], 1):
            print(f"  {i}. {record['company']} - {record['role']} in {record['location']}")
        if len(records) > 5:
            print(f"  ... and {len(records) - 5} more records")
        return len(records)
    
    print(f"💽 Inserting {len(records)} records with metadata into database...")
    
    conn = get_database_connection()
    if not conn:
        return 0
    
    inserted_count = 0
    updated_count = 0
    
    try:
        with conn:
            for i, record in enumerate(records, 1):
                try:
                    # Try to insert new record first
                    cursor = conn.execute("""
                        INSERT INTO linkedin_links (
                            url, source, status, priority,
                            company, role, location, date_in_source,
                            sheet_name, tab, row_number,
                            discovered_at, created_at, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (url) DO UPDATE SET
                            company = COALESCE(NULLIF(linkedin_links.company, ''), EXCLUDED.company),
                            role = COALESCE(NULLIF(linkedin_links.role, ''), EXCLUDED.role),
                            location = COALESCE(NULLIF(linkedin_links.location, ''), EXCLUDED.location),
                            date_in_source = COALESCE(NULLIF(linkedin_links.date_in_source, ''), EXCLUDED.date_in_source),
                            sheet_name = COALESCE(NULLIF(linkedin_links.sheet_name, ''), EXCLUDED.sheet_name),
                            tab = COALESCE(NULLIF(linkedin_links.tab, ''), EXCLUDED.tab),
                            row_number = COALESCE(NULLIF(CAST(linkedin_links.row_number AS TEXT), ''), EXCLUDED.row_number),
                            updated_at = CURRENT_TIMESTAMP
                        RETURNING id, (xmax = 0) AS inserted
                    """, (
                        record['url'],
                        record['source'],
                        record['status'],
                        record['priority'],
                        record['company'],
                        record['role'],
                        record['location'],
                        record['date_in_source'],
                        record['sheet_name'],
                        record['tab_title'],
                        record['row_number'],
                        datetime.now(timezone.utc),
                        datetime.now(timezone.utc),
                        datetime.now(timezone.utc)
                    ))
                    
                    result = cursor.fetchone()
                    if result:
                        link_id, was_inserted = result
                        if was_inserted:
                            inserted_count += 1
                        else:
                            updated_count += 1
                            
                        if i % 100 == 0:
                            print(f"  📝 Processed {i}/{len(records)} records...")
                
                except Exception as e:
                    print(f"  ⚠️ Failed to process record {i} ({record['url'][:50]}...): {e}")
                    continue
            
            conn.commit()
            
            print(f"  ✅ Successfully inserted {inserted_count} new records")
            print(f"  🔄 Updated {updated_count} existing records")
            
            return inserted_count + updated_count
    
    except Exception as e:
        print(f"❌ Database operation failed: {e}")
        return 0
    
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Enhanced Google Sheets ingestion with full metadata support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract and insert with metadata
  python ingest_sheets_with_metadata.py

  # Dry run to see what would be processed
  python ingest_sheets_with_metadata.py --dry-run

  # Different month filter
  python ingest_sheets_with_metadata.py --month-filter aug
        """
    )
    
    parser.add_argument("--month-filter", default="sep",
                       help="Month filter for tab detection (default: sep)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Extract links but don't insert into database")
    
    args = parser.parse_args()
    
    print("🚀 Enhanced Google Sheets Ingestion with Metadata")
    print("=" * 50)
    
    try:
        # Extract links with metadata
        records = extract_links_with_metadata(month_filter=args.month_filter)
        
        if not records:
            print("⚠️ No records extracted. Check your sheet permissions and configuration.")
            return False
        
        print(f"📊 Extraction Summary:")
        print(f"  🔗 Total records with metadata: {len(records)}")
        
        # Show sample of extracted data
        print(f"\n📋 Sample records:")
        for i, record in enumerate(records[:3], 1):
            print(f"  {i}. {record['company']} - {record['role']} in {record['location']}")
        
        # Insert into database
        processed_count = insert_records_with_metadata(records, dry_run=args.dry_run)
        
        # Final summary
        print(f"\n🎉 Ingestion Complete!")
        print(f"  📊 Records extracted: {len(records)}")
        print(f"  💽 Records processed: {processed_count}")
        
        if args.dry_run:
            print(f"\n💡 This was a dry run. Use without --dry-run to apply changes.")
        
        return True
        
    except Exception as e:
        print(f"❌ Ingestion failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)