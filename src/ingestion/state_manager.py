#!/usr/bin/env python3
"""
Production Ingestion State Manager
Manages ingestion state, tracks progress, and handles incremental runs
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import uuid
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

@dataclass
class SheetConfig:
    """Configuration for a Google Sheet"""
    name: str
    sheet_id: str
    tab_name: str
    display_name: str

@dataclass
class IngestionRun:
    """Represents an ingestion run"""
    run_id: str
    start_date: date
    end_date: date
    status: str
    total_records: int = 0
    growth_desk_records: int = 0
    soul_product_records: int = 0
    csv_output_path: Optional[str] = None
    error_message: Optional[str] = None

class IngestionStateManager:
    """Manages ingestion state and progress tracking"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self._connection = None
    
    def get_connection(self):
        """Get database connection (lazy loading)"""
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(**self.db_config)
        return self._connection
    
    def close(self):
        """Close database connection"""
        if self._connection and not self._connection.closed:
            self._connection.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def get_sheet_configs(self) -> Dict[str, SheetConfig]:
        """Get sheet configurations from database"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT key, value FROM ingestion_config WHERE key LIKE 'sheets.%'")
                config_rows = cur.fetchall()
                
        # Parse configuration into sheet configs
        config_dict = {row['key']: row['value'] for row in config_rows}
        
        sheets = {}
        
        # Growth Desk sheet
        if all(f'sheets.growth_desk.{field}' in config_dict for field in ['id', 'tab', 'name']):
            sheets['growth_desk'] = SheetConfig(
                name='growth_desk',
                sheet_id=config_dict['sheets.growth_desk.id'],
                tab_name=config_dict['sheets.growth_desk.tab'],
                display_name=config_dict['sheets.growth_desk.name']
            )
        
        # Soul in Product sheet
        if all(f'sheets.soul_product.{field}' in config_dict for field in ['id', 'tab', 'name']):
            sheets['soul_product'] = SheetConfig(
                name='soul_product',
                sheet_id=config_dict['sheets.soul_product.id'],
                tab_name=config_dict['sheets.soul_product.tab'],
                display_name=config_dict['sheets.soul_product.name']
            )
        
        return sheets
    
    def get_last_successful_date(self, sheet_name: str) -> Optional[date]:
        """Get the last successfully processed date for a sheet"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT last_successful_date 
                    FROM ingestion_state 
                    WHERE sheet_name = %s
                """, (sheet_name,))
                
                result = cur.fetchone()
                return result['last_successful_date'] if result else None
    
    def get_ingestion_status(self) -> List[Dict[str, Any]]:
        """Get current ingestion status for all sheets"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM v_ingestion_status")
                return [dict(row) for row in cur.fetchall()]
    
    def determine_date_range(self, force_start_date: Optional[date] = None, 
                           force_end_date: Optional[date] = None) -> Tuple[date, date]:
        """
        Determine the date range to process based on current state
        
        Args:
            force_start_date: Override start date (for manual runs)
            force_end_date: Override end date (for manual runs)
            
        Returns:
            Tuple of (start_date, end_date)
        """
        today = date.today()
        
        if force_start_date and force_end_date:
            return force_start_date, force_end_date
        
        # Get the earliest last successful date across all sheets
        sheets = self.get_sheet_configs()
        earliest_date = None
        
        for sheet_name, config in sheets.items():
            last_date = self.get_last_successful_date(config.display_name)
            if last_date is None:
                # No previous ingestion - start from September 1, 2025
                earliest_date = date(2025, 9, 1)
                break
            else:
                # Start from the day after last successful date
                candidate_date = last_date + timedelta(days=1)
                if earliest_date is None or candidate_date < earliest_date:
                    earliest_date = candidate_date
        
        if earliest_date is None:
            earliest_date = date(2025, 9, 1)
        
        # End date is today (or forced end date)
        end_date = force_end_date or today
        
        # Don't process future dates
        if earliest_date > today:
            logger.warning(f"Calculated start date {earliest_date} is in the future. Using today's date.")
            earliest_date = today
        
        return earliest_date, end_date
    
    def create_ingestion_run(self, start_date: date, end_date: date) -> IngestionRun:
        """Create a new ingestion run"""
        run_id = str(uuid.uuid4())
        run = IngestionRun(
            run_id=run_id,
            start_date=start_date,
            end_date=end_date,
            status='running'
        )
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ingestion_runs (
                        run_id, start_date, end_date, status, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, NOW(), NOW())
                """, (run.run_id, run.start_date, run.end_date, run.status))
                conn.commit()
        
        logger.info(f"Created ingestion run {run_id} for {start_date} to {end_date}")
        return run
    
    def update_run_status(self, run: IngestionRun, status: str, 
                         error_message: Optional[str] = None,
                         csv_output_path: Optional[str] = None):
        """Update ingestion run status"""
        run.status = status
        run.error_message = error_message
        run.csv_output_path = csv_output_path
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE ingestion_runs 
                    SET status = %s, error_message = %s, csv_output_path = %s,
                        updated_at = NOW(), 
                        completed_at = CASE WHEN %s IN ('completed', 'failed') THEN NOW() ELSE completed_at END,
                        total_records = %s, growth_desk_records = %s, soul_product_records = %s
                    WHERE run_id = %s
                """, (status, error_message, csv_output_path, status, 
                     run.total_records, run.growth_desk_records, run.soul_product_records, run.run_id))
                conn.commit()
    
    def record_sheet_progress(self, run: IngestionRun, sheet_config: SheetConfig, 
                            ingestion_date: date, records_found: int,
                            jobs_count: int, posts_count: int, others_count: int,
                            status: str = 'completed', error_message: Optional[str] = None):
        """Record progress for a specific sheet and date"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ingestion_progress (
                        run_id, sheet_name, sheet_id, tab_name, ingestion_date,
                        records_found, jobs_count, posts_count, others_count,
                        status, error_message, processed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (run_id, sheet_name, ingestion_date) DO UPDATE SET
                        records_found = EXCLUDED.records_found,
                        jobs_count = EXCLUDED.jobs_count,
                        posts_count = EXCLUDED.posts_count,
                        others_count = EXCLUDED.others_count,
                        status = EXCLUDED.status,
                        error_message = EXCLUDED.error_message,
                        processed_at = NOW()
                """, (run.run_id, sheet_config.display_name, sheet_config.sheet_id, 
                     sheet_config.tab_name, ingestion_date, records_found,
                     jobs_count, posts_count, others_count, status, error_message))
                conn.commit()
    
    def update_ingestion_state(self, sheet_name: str, sheet_id: str, 
                              last_successful_date: date, run_id: str, 
                              records_count: int):
        """Update the overall ingestion state for a sheet"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ingestion_state (
                        sheet_name, sheet_id, last_successful_date, 
                        last_successful_run_id, total_records_ingested, last_updated
                    ) VALUES (%s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (sheet_name, sheet_id) DO UPDATE SET
                        last_successful_date = GREATEST(ingestion_state.last_successful_date, EXCLUDED.last_successful_date),
                        last_successful_run_id = EXCLUDED.last_successful_run_id,
                        total_records_ingested = ingestion_state.total_records_ingested + EXCLUDED.total_records_ingested,
                        last_updated = NOW()
                """, (sheet_name, sheet_id, last_successful_date, run_id, records_count))
                conn.commit()
    
    def get_config_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a configuration value"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT value FROM ingestion_config WHERE key = %s", (key,))
                result = cur.fetchone()
                return result['value'] if result else default
    
    def set_config_value(self, key: str, value: str, description: Optional[str] = None):
        """Set a configuration value"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ingestion_config (key, value, description, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        description = COALESCE(EXCLUDED.description, ingestion_config.description),
                        updated_at = NOW()
                """, (key, value, description))
                conn.commit()
    
    def get_run_statistics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent run statistics"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM v_run_statistics LIMIT %s", (limit,))
                return [dict(row) for row in cur.fetchall()]
    
    def initialize_from_existing_data(self):
        """Initialize ingestion state from existing data in linkedin_links table"""
        logger.info("Initializing ingestion state from existing data...")
        
        sheets = self.get_sheet_configs()
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                for sheet_key, config in sheets.items():
                    # Find the latest date for this sheet
                    cur.execute("""
                        SELECT 
                            date_in_source,
                            COUNT(*) as record_count,
                            MAX(created_at) as last_created
                        FROM linkedin_links 
                        WHERE sheet_name = %s
                          AND date_in_source ~ '^"Sep [0-9]+, 2025"?$'
                        GROUP BY date_in_source
                        ORDER BY 
                            CAST(SUBSTRING(date_in_source FROM 'Sep ([0-9]+)') AS INTEGER) DESC
                        LIMIT 1
                    """, (config.display_name,))
                    
                    result = cur.fetchone()
                    if result:
                        # Parse the date string like "Sep 24, 2025"
                        date_str = result['date_in_source'].strip('"')
                        try:
                            parsed_date = datetime.strptime(date_str, "Sep %d, %Y").date()
                            
                            # Create a synthetic run ID for the existing data
                            synthetic_run_id = f"existing-data-{config.name}"
                            
                            # Update ingestion state
                            self.update_ingestion_state(
                                sheet_name=config.display_name,
                                sheet_id=config.sheet_id,
                                last_successful_date=parsed_date,
                                run_id=synthetic_run_id,
                                records_count=result['record_count']
                            )
                            
                            logger.info(f"Initialized {config.display_name}: last date = {parsed_date}, records = {result['record_count']}")
                        except ValueError as e:
                            logger.warning(f"Could not parse date '{date_str}' for {config.display_name}: {e}")
                    else:
                        logger.info(f"No existing data found for {config.display_name}")