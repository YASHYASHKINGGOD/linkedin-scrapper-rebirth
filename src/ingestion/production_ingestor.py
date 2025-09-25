#!/usr/bin/env python3
"""
Production Incremental LinkedIn Sheets Ingestor
Builds on the corrected September ingestor with incremental processing capabilities
"""

import os
import sys
import csv
import re
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Tuple
import uuid

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from clients.google_sheets import GoogleSheetsClient
from ingestion.state_manager import IngestionStateManager, SheetConfig, IngestionRun

logger = logging.getLogger(__name__)

class ProductionIngestor:
    """Production incremental ingestor for LinkedIn sheets data"""
    
    def __init__(self, db_config: Dict[str, str], storage_path: str = "./storage/production"):
        self.db_config = db_config
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Setup environment for Google Sheets
        self._setup_google_auth()
        
        # Initialize clients
        self.sheets_client = GoogleSheetsClient()
        self.state_manager = IngestionStateManager(db_config)
        
        # Track current run
        self.current_run: Optional[IngestionRun] = None
    
    def _setup_google_auth(self):
        """Setup Google Sheets authentication"""
        env_vars = {
            "GOOGLE_OAUTH_CLIENT_JSON": "./client_secret_28309019366-uep6ho3i3k5096d1od4fo8gp1c1tj375.apps.googleusercontent.com.json",
            "GOOGLE_OAUTH_TOKEN_JSON": "./.secrets/google_token.json", 
            "GOOGLE_OAUTH_REDIRECT_PORT": "8765"
        }
        
        for key, value in env_vars.items():
            if key not in os.environ:
                os.environ[key] = value
    
    def get_cell_value(self, row: List[str], col_idx: int) -> str:
        """Safely get cell value"""
        if col_idx < len(row) and row[col_idx]:
            return str(row[col_idx]).strip()
        return ""
    
    def parse_date_from_sheet_row(self, cell_text: str) -> Optional[date]:
        """Parse date from sheet row text"""
        # Handle patterns like "1st September", "24th September", etc.
        date_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+september', cell_text.lower())
        if date_match:
            day = int(date_match.group(1))
            return date(2025, 9, day)  # Assuming September 2025
        
        # Handle patterns like "Opportunities Posted on 23rd September"
        date_match = re.search(r'opportunities\s+posted\s+on\s+(\d{1,2})(?:st|nd|rd|th)?\s+september', cell_text.lower())
        if date_match:
            day = int(date_match.group(1))
            return date(2025, 9, day)
        
        return None
    
    def should_process_date(self, sheet_date: date, target_start_date: date, target_end_date: date) -> bool:
        """Check if a sheet date should be processed based on target range"""
        return target_start_date <= sheet_date <= target_end_date
    
    def extract_growth_desk_data(self, values: List[List[str]], target_start_date: date, target_end_date: date) -> List[Dict[str, Any]]:
        """Extract data from Growth Desk sheet (incremental version)"""
        records = []
        current_date = None
        
        logger.info(f"Processing Growth Desk sheet for dates {target_start_date} to {target_end_date}")
        
        for row_idx, row in enumerate(values):
            if not row:
                continue
            
            # Handle date rows (single cell with date)
            if len(row) == 1 and row[0]:
                parsed_date = self.parse_date_from_sheet_row(row[0])
                if parsed_date:
                    current_date = parsed_date
                    logger.debug(f"  Found date section: {current_date}")
                    continue
            
            # Skip if we don't have a current date or it's outside our target range
            if not current_date or not self.should_process_date(current_date, target_start_date, target_end_date):
                continue
            
            # Skip header rows - be more specific to avoid false positives
            row_text = " ".join([str(cell).strip() for cell in row if cell]).lower()
            header_keywords = ["company", "role", "location", "link", "ctc", "experience"]
            header_matches = sum(1 for word in header_keywords if word in row_text)
            if header_matches >= 3:  # Must have at least 3 header keywords to be considered a header
                continue
            
            # Extract data from columns
            company = self.get_cell_value(row, 0)    # Column A - Company
            role = self.get_cell_value(row, 1)       # Column B - Role  
            location = self.get_cell_value(row, 2)   # Column C - Location
            
            # Search for LinkedIn URL in any column (robust approach)
            url = ""
            for cell in row:
                if cell and "linkedin.com" in str(cell):
                    url = str(cell).strip()
                    break
            
            # Must have LinkedIn URL and valid company
            if not url or not company or company.strip() == "-":
                continue
            
            # Extract remaining fields
            ctc = self.get_cell_value(row, 4)        # Column E - CTC
            experience = self.get_cell_value(row, 5)  # Column F - Experience
            
            record = {
                "url": url,
                "company": company,
                "role": role,
                "location": location,
                "experience": experience,
                "ctc": ctc,
                "date_in_source": f"Sep {current_date.day}, 2025",
                "sheet_name": "Job Dashboard - The Growth Desk",
                "tab": "September (2025)",
                "row_number": row_idx + 1,
                "spreadsheet_id": "1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q",
                "classification": "job" if "/jobs/" in url else ("post" if "/posts/" in url else "other"),
                "category": "jobs" if "/jobs/" in url else ("posts" if "/posts/" in url else "others"),
                "industry": "",
                "opportunity_no": "",
                "email": ""
            }
            
            records.append(record)
        
        logger.info(f"Extracted {len(records)} records from Growth Desk sheet")
        return records
    
    def extract_soul_product_data(self, values: List[List[str]], target_start_date: date, target_end_date: date) -> List[Dict[str, Any]]:
        """Extract data from Soul in Product sheet (incremental version)"""
        records = []
        current_date = None
        
        logger.info(f"Processing Soul in Product sheet for dates {target_start_date} to {target_end_date}")
        
        for row_idx, row in enumerate(values):
            if not row:
                continue
            
            # Look for date headers in the sheet content
            row_text = " ".join([str(cell).strip() for cell in row if cell])
            parsed_date = self.parse_date_from_sheet_row(row_text)
            if parsed_date:
                current_date = parsed_date
                logger.debug(f"  Found date section: {current_date}")
                continue
            
            # Skip if we don't have a current date or it's outside our target range
            if not current_date or not self.should_process_date(current_date, target_start_date, target_end_date):
                continue
            
            # Skip header rows
            if any(word in row_text.lower() for word in ["opportunity", "company", "role", "location", "post link"]):
                continue
            
            # Extract data using Soul in Product column structure
            opportunity_no = self.get_cell_value(row, 0)
            company = self.get_cell_value(row, 1)
            role = self.get_cell_value(row, 2)
            location = self.get_cell_value(row, 3)
            industry = self.get_cell_value(row, 4)
            url = self.get_cell_value(row, 5)
            experience = self.get_cell_value(row, 6)
            ctc = self.get_cell_value(row, 7)
            email = self.get_cell_value(row, 8)
            
            # Must have LinkedIn URL and company
            if not url or "linkedin.com" not in url or not company:
                continue
            
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
                "date_in_source": f"Sep {current_date.day}, 2025",
                "sheet_name": "Soul in Product - Dashboard",
                "tab": "September Openings",
                "row_number": row_idx + 1,
                "spreadsheet_id": "1p7O7tUBYM94IqEmIlXp8a5B0nGdX8DwP-bmVFu0FAK0",
                "classification": "job" if "/jobs/" in url else ("post" if "/posts/" in url else "other"),
                "category": "jobs" if "/jobs/" in url else ("posts" if "/posts/" in url else "others")
            }
            
            records.append(record)
        
        logger.info(f"Extracted {len(records)} records from Soul in Product sheet")
        return records
    
    def save_to_csv(self, records: List[Dict[str, Any]], run_id: str) -> Path:
        """Save records to CSV file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") 
        csv_filename = f"google_sheet_ingestor_{timestamp}_{len(records)}.csv"
        csv_path = self.storage_path / csv_filename
        
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
            
            for record in records:
                # Fill missing columns with empty strings
                complete_record = {col: record.get(col, '') for col in all_columns}
                writer.writerow(complete_record)
        
        logger.info(f"CSV saved: {csv_path}")
        return csv_path
    
    def insert_to_database(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        """Insert records to database, return (inserted_count, updated_count)"""
        if not records:
            return 0, 0
        
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
        
        batch_size = 50
        total_operations = 0
        
        with psycopg2.connect(**self.db_config) as conn:
            with conn.cursor() as cur:
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    
                    # Prepare batch records
                    batch_records = []
                    for record in batch:
                        batch_record = {
                            'url': record['url'].strip(),
                            'classification': record['classification'] or 'post',
                            'source': f'incremental_ingestion_{datetime.now().strftime("%Y%m")}',
                            'category': record['category'],
                            'sheet_name': record['sheet_name'],
                            'tab': record['tab'],
                            'row_number': int(record['row_number']) if record['row_number'] else None,
                            'date_in_source': record['date_in_source'],
                            'spreadsheet_id': record['spreadsheet_id'],
                            'company': record['company'] or None,
                            'role': record['role'] or None,
                            'location': record['location'] or None
                        }
                        batch_records.append(batch_record)
                    
                    cur.executemany(insert_query, batch_records)
                    total_operations += len(batch_records)
                    
                    logger.debug(f"Inserted batch of {len(batch_records)} records")
                
                conn.commit()
        
        logger.info(f"Database insertion complete: {total_operations} operations")
        return total_operations, 0  # PostgreSQL doesn't easily distinguish inserts vs updates
    
    def run_incremental_ingestion(self, start_date: Optional[date] = None, 
                                 end_date: Optional[date] = None,
                                 dry_run: bool = False) -> IngestionRun:
        """Run incremental ingestion"""
        logger.info("🚀 Starting incremental ingestion")
        
        # Determine date range
        target_start, target_end = self.state_manager.determine_date_range(start_date, end_date)
        logger.info(f"📅 Processing dates: {target_start} to {target_end}")
        
        if target_start > target_end:
            logger.info("No new dates to process")
            return None
        
        # Create ingestion run
        run = self.state_manager.create_ingestion_run(target_start, target_end)
        self.current_run = run
        
        try:
            all_records = []
            sheet_configs = self.state_manager.get_sheet_configs()
            
            # Process Growth Desk sheet
            if 'growth_desk' in sheet_configs:
                config = sheet_configs['growth_desk']
                logger.info(f"📋 Processing {config.display_name}")
                
                try:
                    values = self.sheets_client.get_values(config.sheet_id, config.tab_name)
                    growth_records = self.extract_growth_desk_data(values, target_start, target_end)
                    all_records.extend(growth_records)
                    run.growth_desk_records = len(growth_records)
                    
                    # Record progress for each date found
                    date_counts = {}
                    for record in growth_records:
                        date_str = record['date_in_source']
                        parsed_date = datetime.strptime(date_str, "Sep %d, %Y").date()
                        if parsed_date not in date_counts:
                            date_counts[parsed_date] = {'jobs': 0, 'posts': 0, 'others': 0}
                        date_counts[parsed_date][record['category']] += 1
                    
                    for sheet_date, counts in date_counts.items():
                        self.state_manager.record_sheet_progress(
                            run, config, sheet_date, 
                            sum(counts.values()), counts['jobs'], counts['posts'], counts['others']
                        )
                    
                except Exception as e:
                    logger.error(f"❌ Failed to process {config.display_name}: {e}")
                    self.state_manager.record_sheet_progress(
                        run, config, target_start, 0, 0, 0, 0, 'failed', str(e)
                    )
            
            # Process Soul in Product sheet
            if 'soul_product' in sheet_configs:
                config = sheet_configs['soul_product']
                logger.info(f"📋 Processing {config.display_name}")
                
                try:
                    values = self.sheets_client.get_values(config.sheet_id, config.tab_name)
                    soul_records = self.extract_soul_product_data(values, target_start, target_end)
                    all_records.extend(soul_records)
                    run.soul_product_records = len(soul_records)
                    
                    # Record progress for each date found
                    date_counts = {}
                    for record in soul_records:
                        date_str = record['date_in_source']
                        parsed_date = datetime.strptime(date_str, "Sep %d, %Y").date()
                        if parsed_date not in date_counts:
                            date_counts[parsed_date] = {'jobs': 0, 'posts': 0, 'others': 0}
                        date_counts[parsed_date][record['category']] += 1
                    
                    for sheet_date, counts in date_counts.items():
                        self.state_manager.record_sheet_progress(
                            run, config, sheet_date,
                            sum(counts.values()), counts['jobs'], counts['posts'], counts['others']
                        )
                    
                except Exception as e:
                    logger.error(f"❌ Failed to process {config.display_name}: {e}")
                    self.state_manager.record_sheet_progress(
                        run, config, target_start, 0, 0, 0, 0, 'failed', str(e)
                    )
            
            run.total_records = len(all_records)
            logger.info(f"🎯 Total records extracted: {run.total_records}")
            
            if dry_run:
                logger.info("🧪 Dry run - skipping database insertion")
                csv_path = self.save_to_csv(all_records, run.run_id)
                self.state_manager.update_run_status(run, 'completed', csv_output_path=str(csv_path))
            else:
                # Save to CSV
                csv_path = self.save_to_csv(all_records, run.run_id)
                
                # Insert to database
                if all_records:
                    inserted, updated = self.insert_to_database(all_records)
                    logger.info(f"💾 Database: {inserted} operations completed")
                
                # Update ingestion state for each sheet
                for sheet_key, config in sheet_configs.items():
                    sheet_records = [r for r in all_records if r['sheet_name'] == config.display_name]
                    if sheet_records:
                        # Find the latest date processed for this sheet
                        latest_date = max(
                            datetime.strptime(r['date_in_source'], "Sep %d, %Y").date() 
                            for r in sheet_records
                        )
                        self.state_manager.update_ingestion_state(
                            config.display_name, config.sheet_id, latest_date, run.run_id, len(sheet_records)
                        )
                
                self.state_manager.update_run_status(run, 'completed', csv_output_path=str(csv_path))
            
            logger.info("✅ Incremental ingestion completed successfully!")
            return run
            
        except Exception as e:
            logger.error(f"❌ Ingestion failed: {e}")
            self.state_manager.update_run_status(run, 'failed', error_message=str(e))
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get current ingestion status"""
        status = self.state_manager.get_ingestion_status()
        recent_runs = self.state_manager.get_run_statistics(5)
        
        return {
            'status': status,
            'recent_runs': recent_runs,
            'next_dates': self.state_manager.determine_date_range()
        }
    
    def initialize_from_existing_data(self):
        """Initialize state from existing data in the database"""
        self.state_manager.initialize_from_existing_data()