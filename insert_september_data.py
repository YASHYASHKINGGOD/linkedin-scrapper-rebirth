#!/usr/bin/env python3
"""
Script to insert the corrected September ingestion data into the linkedin_links table
Handles proper field mapping and duplicate detection
"""

import csv
import psycopg2
from psycopg2.extras import RealDictCursor
import sys
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'database': 'data_lake',
    'user': 'postgres',
    'password': 'postgres'
}

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG)

def check_existing_data():
    """Check what data already exists in the table"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as total_count FROM linkedin_links")
            total = cur.fetchone()['total_count']
            
            cur.execute("""
                SELECT COUNT(*) as september_count 
                FROM linkedin_links 
                WHERE date_in_source LIKE '%Sep%2025%' 
                   OR date_in_source LIKE '%September%'
                   OR sheet_name IN ('Job Dashboard - The Growth Desk', 'Soul in Product - Dashboard')
            """)
            september = cur.fetchone()['september_count']
            
            logger.info(f"Current database state: {total} total records, {september} September-related records")
            return total, september

def insert_data_batch(records_batch):
    """Insert a batch of records"""
    insert_query = """
    INSERT INTO linkedin_links (
        url, classification, source, category, sheet_name, tab, row_number,
        date_in_source, spreadsheet_id, company, role, location, 
        created_at, updated_at, extracted_at, discovered_at
    ) VALUES (
        %(url)s, %(classification)s, %(source)s, %(category)s, %(sheet_name)s, 
        %(tab)s, %(row_number)s, %(date_in_source)s, %(spreadsheet_id)s,
        %(company)s, %(role)s, %(location)s, 
        NOW(), NOW(), NOW(), NOW()
    ) ON CONFLICT (url) DO UPDATE SET
        updated_at = NOW(),
        sheet_name = EXCLUDED.sheet_name,
        tab = EXCLUDED.tab,
        row_number = EXCLUDED.row_number,
        date_in_source = EXCLUDED.date_in_source,
        company = EXCLUDED.company,
        role = EXCLUDED.role,
        location = EXCLUDED.location,
        classification = EXCLUDED.classification,
        category = EXCLUDED.category
    """
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(insert_query, records_batch)
            conn.commit()
            return cur.rowcount

def process_csv_file(csv_path):
    """Process the CSV file and insert data into database"""
    logger.info(f"Processing CSV file: {csv_path}")
    
    total_processed = 0
    total_inserted = 0
    total_updated = 0
    batch_size = 50
    batch = []
    
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            # Prepare the record for database insertion
            record = {
                'url': row['url'].strip(),
                'classification': row['classification'] or 'post',  # Default to 'post'
                'source': 'google_sheets_september_2025',
                'category': row['category'],
                'sheet_name': row['sheet_name'],
                'tab': row['tab'],
                'row_number': int(row['row_number']) if row['row_number'] else None,
                'date_in_source': row['date_in_source'],
                'spreadsheet_id': row['spreadsheet_id'],
                'company': row['company'] or None,
                'role': row['role'] or None,
                'location': row['location'] or None
            }
            
            batch.append(record)
            total_processed += 1
            
            # Insert batch when it reaches batch_size
            if len(batch) >= batch_size:
                try:
                    rows_affected = insert_data_batch(batch)
                    total_inserted += rows_affected
                    logger.info(f"Processed batch of {len(batch)} records (total: {total_processed})")
                except Exception as e:
                    logger.error(f"Error inserting batch: {e}")
                    # Log the problematic batch for debugging
                    for i, rec in enumerate(batch):
                        logger.error(f"  Batch record {i}: {rec['url'][:50]}...")
                    raise
                batch = []
        
        # Insert remaining records
        if batch:
            try:
                rows_affected = insert_data_batch(batch)
                total_inserted += rows_affected
                logger.info(f"Processed final batch of {len(batch)} records")
            except Exception as e:
                logger.error(f"Error inserting final batch: {e}")
                raise
    
    logger.info(f"✅ Data insertion complete!")
    logger.info(f"   Records processed: {total_processed}")
    logger.info(f"   Database operations: {total_inserted}")
    
    return total_processed, total_inserted

def verify_insertion():
    """Verify the data was inserted correctly"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check total records
            cur.execute("SELECT COUNT(*) as count FROM linkedin_links")
            total_count = cur.fetchone()['count']
            
            # Check September records
            cur.execute("""
                SELECT COUNT(*) as count FROM linkedin_links 
                WHERE sheet_name IN ('Job Dashboard - The Growth Desk', 'Soul in Product - Dashboard')
            """)
            september_count = cur.fetchone()['count']
            
            # Check by classification
            cur.execute("""
                SELECT classification, COUNT(*) as count 
                FROM linkedin_links 
                WHERE sheet_name IN ('Job Dashboard - The Growth Desk', 'Soul in Product - Dashboard')
                GROUP BY classification 
                ORDER BY classification
            """)
            classifications = cur.fetchall()
            
            # Check by sheet
            cur.execute("""
                SELECT sheet_name, COUNT(*) as count 
                FROM linkedin_links 
                WHERE sheet_name IN ('Job Dashboard - The Growth Desk', 'Soul in Product - Dashboard')
                GROUP BY sheet_name 
                ORDER BY sheet_name
            """)
            sheets = cur.fetchall()
            
            logger.info(f"📊 Verification Results:")
            logger.info(f"   Total records in database: {total_count}")
            logger.info(f"   September records: {september_count}")
            logger.info(f"   By classification:")
            for cls in classifications:
                logger.info(f"     {cls['classification']}: {cls['count']}")
            logger.info(f"   By sheet:")
            for sheet in sheets:
                logger.info(f"     {sheet['sheet_name']}: {sheet['count']}")

def main():
    csv_file = "./google_sheet_ingestor_20250925_449.csv"
    
    logger.info("🚀 Starting September data insertion")
    logger.info("=" * 60)
    
    # Check existing data
    total_before, september_before = check_existing_data()
    
    # Process and insert data
    try:
        processed, inserted = process_csv_file(csv_file)
        
        # Verify insertion
        verify_insertion()
        
        # Final summary
        total_after, september_after = check_existing_data()
        logger.info("📈 Summary:")
        logger.info(f"   Records before: {total_before} (September: {september_before})")
        logger.info(f"   Records after: {total_after} (September: {september_after})")
        logger.info(f"   Net change: +{total_after - total_before} total (+{september_after - september_before} September)")
        
    except Exception as e:
        logger.error(f"❌ Error during insertion: {e}")
        sys.exit(1)
    
    logger.info("✅ September data insertion completed successfully!")

if __name__ == "__main__":
    main()