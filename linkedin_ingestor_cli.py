#!/usr/bin/env python3
"""
LinkedIn Sheets Ingestor - Production CLI
Command-line interface for the production incremental ingestion system
"""

import argparse
import logging
import sys
from datetime import datetime, date
from pathlib import Path
import json
from typing import Optional

# Add src to path
sys.path.insert(0, 'src')
from ingestion.production_ingestor import ProductionIngestor
from ingestion.state_manager import IngestionStateManager

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'data_lake',
    'user': 'postgres',
    'password': 'postgres'
}

def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('linkedin_ingestor.log', mode='a')
        ]
    )

def parse_date(date_str: str) -> Optional[date]:
    """Parse date string in YYYY-MM-DD format"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")

def cmd_run(args):
    """Run incremental ingestion"""
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Starting LinkedIn Sheets Ingestor")
    logger.info("=" * 60)
    
    try:
        ingestor = ProductionIngestor(DB_CONFIG, args.storage_path)
        
        start_date = parse_date(args.start_date) if args.start_date else None
        end_date = parse_date(args.end_date) if args.end_date else None
        
        if args.initialize:
            logger.info("Initializing state from existing data...")
            ingestor.initialize_from_existing_data()
            logger.info("✅ Initialization complete")
        
        run = ingestor.run_incremental_ingestion(
            start_date=start_date,
            end_date=end_date,
            dry_run=args.dry_run
        )
        
        if run:
            print("\n" + "="*60)
            print("📊 INGESTION SUMMARY")
            print("="*60)
            print(f"Run ID: {run.run_id}")
            print(f"Date Range: {run.start_date} to {run.end_date}")
            print(f"Status: {run.status}")
            print(f"Total Records: {run.total_records}")
            print(f"  Growth Desk: {run.growth_desk_records}")
            print(f"  Soul in Product: {run.soul_product_records}")
            if run.csv_output_path:
                print(f"CSV Output: {run.csv_output_path}")
            if run.error_message:
                print(f"Error: {run.error_message}")
        else:
            print("ℹ️  No new data to process")
            
    except Exception as e:
        logger.error(f"❌ Ingestion failed: {e}")
        sys.exit(1)

def cmd_status(args):
    """Show ingestion status"""
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        ingestor = ProductionIngestor(DB_CONFIG)
        status_data = ingestor.get_status()
        
        print("📊 INGESTION STATUS")
        print("=" * 60)
        
        # Current status by sheet
        print("\n📋 Sheet Status:")
        for sheet_status in status_data['status']:
            print(f"  {sheet_status['sheet_name']}:")
            print(f"    Last successful date: {sheet_status['last_successful_date'] or 'Never'}")
            print(f"    Total records: {sheet_status['total_records_ingested'] or 0}")
            print(f"    Days behind: {sheet_status['days_behind']}")
            print(f"    Last updated: {sheet_status['last_updated']}")
        
        # Next date range
        next_start, next_end = status_data['next_dates']
        print(f"\n📅 Next ingestion range: {next_start} to {next_end}")
        
        # Recent runs
        print(f"\n🏃 Recent Runs:")
        for run in status_data['recent_runs'][:5]:
            status_emoji = {"completed": "✅", "failed": "❌", "running": "🏃"}.get(run['status'], "⚪")
            print(f"  {status_emoji} {run['run_id'][:8]} | {run['start_date']} to {run['end_date']} | {run['total_records']} records | {run['status']}")
            
    except Exception as e:
        logger.error(f"❌ Failed to get status: {e}")
        sys.exit(1)

def cmd_config(args):
    """Manage configuration"""
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        state_manager = IngestionStateManager(DB_CONFIG)
        
        if args.action == 'get':
            if args.key:
                value = state_manager.get_config_value(args.key)
                if value:
                    print(f"{args.key} = {value}")
                else:
                    print(f"Configuration key '{args.key}' not found")
            else:
                # Show all config
                with state_manager.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT key, value, description FROM ingestion_config ORDER BY key")
                        configs = cur.fetchall()
                
                print("⚙️  CONFIGURATION")
                print("=" * 60)
                for key, value, description in configs:
                    print(f"{key}: {value}")
                    if description:
                        print(f"  # {description}")
                    print()
        
        elif args.action == 'set':
            if not args.key or not args.value:
                print("Error: Both --key and --value are required for 'set' action")
                sys.exit(1)
            state_manager.set_config_value(args.key, args.value, args.description)
            print(f"✅ Set {args.key} = {args.value}")
            
    except Exception as e:
        logger.error(f"❌ Configuration operation failed: {e}")
        sys.exit(1)

def cmd_init(args):
    """Initialize the system"""
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Initializing LinkedIn Ingestor system...")
        
        # Check if we can connect to database
        state_manager = IngestionStateManager(DB_CONFIG)
        
        # Initialize from existing data
        logger.info("Scanning existing data in linkedin_links table...")
        state_manager.initialize_from_existing_data()
        
        # Show status after initialization
        ingestor = ProductionIngestor(DB_CONFIG)
        status_data = ingestor.get_status()
        
        print("\n✅ INITIALIZATION COMPLETE")
        print("=" * 60)
        
        for sheet_status in status_data['status']:
            print(f"📋 {sheet_status['sheet_name']}:")
            print(f"   Last date: {sheet_status['last_successful_date']}")
            print(f"   Records: {sheet_status['total_records_ingested']}")
        
        next_start, next_end = status_data['next_dates']
        print(f"\n📅 Next ingestion will process: {next_start} to {next_end}")
        
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        sys.exit(1)

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="LinkedIn Sheets Ingestor - Production CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize the system (run this first)
  python3 linkedin_ingestor_cli.py init
  
  # Run incremental ingestion (processes new dates automatically)
  python3 linkedin_ingestor_cli.py run
  
  # Run ingestion for specific date range
  python3 linkedin_ingestor_cli.py run --start-date 2025-09-20 --end-date 2025-09-25
  
  # Dry run (extract but don't save to database)
  python3 linkedin_ingestor_cli.py run --dry-run
  
  # Check current status
  python3 linkedin_ingestor_cli.py status
  
  # View configuration
  python3 linkedin_ingestor_cli.py config get
  
  # Set configuration
  python3 linkedin_ingestor_cli.py config set --key sheets.growth_desk.tab --value "October (2025)"
        """
    )
    
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run incremental ingestion')
    run_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD), overrides automatic detection')
    run_parser.add_argument('--end-date', help='End date (YYYY-MM-DD), defaults to today')
    run_parser.add_argument('--dry-run', action='store_true', help='Extract data but don\'t save to database')
    run_parser.add_argument('--initialize', action='store_true', help='Initialize state from existing data before running')
    run_parser.add_argument('--storage-path', default='./storage/production', help='Path for CSV storage')
    run_parser.set_defaults(func=cmd_run)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show ingestion status')
    status_parser.set_defaults(func=cmd_status)
    
    # Config command
    config_parser = subparsers.add_parser('config', help='Manage configuration')
    config_parser.add_argument('action', choices=['get', 'set'], help='Configuration action')
    config_parser.add_argument('--key', help='Configuration key')
    config_parser.add_argument('--value', help='Configuration value (for set action)')
    config_parser.add_argument('--description', help='Configuration description (for set action)')
    config_parser.set_defaults(func=cmd_config)
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize the system')
    init_parser.set_defaults(func=cmd_init)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)

if __name__ == "__main__":
    main()