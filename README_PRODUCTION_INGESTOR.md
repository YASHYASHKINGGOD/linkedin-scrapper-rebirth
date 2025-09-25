# LinkedIn Sheets Ingestor - Production System

A production-ready incremental ingestion system for extracting LinkedIn job and post data from Google Sheets with comprehensive tracking, monitoring, and automated incremental processing.

## 🎯 Overview

This system automatically tracks ingestion progress and processes only new dates since the last successful run. It handles two Google Sheets:
- **Job Dashboard - The Growth Desk** (266 records from our September data)
- **Soul in Product - Dashboard** (183 records from our September data)

## 🏗️ Architecture

### Core Components

1. **State Manager** (`src/ingestion/state_manager.py`)
   - Tracks last successful ingestion dates per sheet
   - Manages ingestion runs and progress
   - Handles configuration and statistics

2. **Production Ingestor** (`src/ingestion/production_ingestor.py`)
   - Incremental data extraction from Google Sheets
   - Date-range based processing
   - Robust error handling and logging

3. **CLI Interface** (`linkedin_ingestor_cli.py`)
   - Command-line interface for all operations
   - Status monitoring and configuration management

4. **Database Schema** (`sql/production_ingestion_schema.sql`)
   - Tracking tables for runs, progress, and state
   - Configuration management
   - Statistics and monitoring views

## 📊 Database Schema

### Main Tables
- `ingestion_runs` - Track each ingestion execution
- `ingestion_progress` - Progress by sheet and date
- `ingestion_state` - Overall state per sheet
- `ingestion_config` - System configuration
- `linkedin_links` - Main data table (existing)

### Key Views
- `v_ingestion_status` - Current status summary
- `v_run_statistics` - Detailed run analytics

## 🚀 Quick Start

### 1. Initialize the System
```bash
# Set up the database schema and initialize from existing data
python3 linkedin_ingestor_cli.py init
```

### 2. Check Current Status
```bash
# View ingestion status and next date range to process
python3 linkedin_ingestor_cli.py status
```

### 3. Run Incremental Ingestion
```bash
# Process new dates automatically (recommended)
python3 linkedin_ingestor_cli.py run

# Process specific date range
python3 linkedin_ingestor_cli.py run --start-date 2025-09-20 --end-date 2025-09-25

# Dry run (extract but don't save to database)
python3 linkedin_ingestor_cli.py run --dry-run
```

## 📋 Command Reference

### Status Commands
```bash
# Show detailed status
python3 linkedin_ingestor_cli.py status

# View configuration
python3 linkedin_ingestor_cli.py config get

# Set configuration value
python3 linkedin_ingestor_cli.py config set --key sheets.growth_desk.tab --value "October (2025)"
```

### Ingestion Commands
```bash
# Normal incremental run (processes dates since last successful run)
python3 linkedin_ingestor_cli.py run

# Run with initialization (if state is lost)
python3 linkedin_ingestor_cli.py run --initialize

# Specify custom storage path
python3 linkedin_ingestor_cli.py run --storage-path ./custom_storage

# Verbose logging
python3 linkedin_ingestor_cli.py -v run
```

## 🔧 Configuration

The system stores configuration in the `ingestion_config` table:

```sql
-- Key configurations
sheets.growth_desk.id = '1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q'
sheets.growth_desk.tab = 'September (2025)'
sheets.growth_desk.name = 'Job Dashboard - The Growth Desk'

sheets.soul_product.id = '1p7O7tUBYM94IqEmIlXp8a5B0nGdX8DwP-bmVFu0FAK0'
sheets.soul_product.tab = 'September Openings '
sheets.soul_product.name = 'Soul in Product - Dashboard'

ingestion.storage_path = './storage/production'
```

## 📈 Monitoring & Analytics

### Check Recent Runs
```sql
SELECT * FROM v_run_statistics LIMIT 5;
```

### Sheet Progress
```sql
SELECT * FROM v_ingestion_status;
```

### Detailed Progress by Date
```sql
SELECT 
    sheet_name,
    ingestion_date,
    records_found,
    jobs_count,
    posts_count,
    status
FROM ingestion_progress 
WHERE run_id = 'your-run-id'
ORDER BY ingestion_date;
```

## 🔄 How Incremental Processing Works

1. **State Tracking**: System tracks the last successfully processed date for each sheet
2. **Date Range Calculation**: Automatically determines next date range to process
3. **Sheet Processing**: Extracts data only for dates in the target range
4. **Progress Recording**: Records progress by date and sheet
5. **State Updates**: Updates last successful dates upon completion

### Example Flow
```
Initial state: No previous data
├── Determines range: Sep 1, 2025 → Sep 25, 2025
├── Processes Growth Desk sheet for Sep 24-25 → 19 records
├── Processes Soul Product sheet for Sep 24-25 → 15 records
├── Updates state: Last successful date = Sep 25, 2025
└── Next run will start from Sep 26, 2025
```

## 📁 Output Files

### CSV Naming Convention
```
google_sheet_ingestor_YYYYMMDD_HHMMSS_<record_count>.csv
```

Example: `google_sheet_ingestor_20250925_113308_34.csv`

### CSV Structure
```csv
url,company,role,location,experience,ctc,industry,opportunity_no,email,date_in_source,sheet_name,tab,row_number,spreadsheet_id,classification,category
```

## ⚡ Performance & Scaling

- **Batch Processing**: Processes records in batches of 50
- **Date Filtering**: Only processes dates in target range
- **Deduplication**: Handles URL conflicts with UPSERT logic
- **Progress Tracking**: Granular progress tracking by date and sheet
- **Error Resilience**: Failed sheets don't block other sheets

## 🛠️ Troubleshooting

### Common Issues

1. **No new data to process**
   ```bash
   # Check current state
   python3 linkedin_ingestor_cli.py status
   
   # Force specific date range
   python3 linkedin_ingestor_cli.py run --start-date 2025-09-25 --end-date 2025-09-25
   ```

2. **Google Sheets authentication**
   ```bash
   # Ensure credentials are in place
   ls -la client_secret_*.json
   ls -la .secrets/google_token.json
   ```

3. **Database connection issues**
   ```bash
   # Test connection
   psql postgresql://postgres:postgres@localhost:5432/data_lake -c "SELECT COUNT(*) FROM linkedin_links;"
   ```

### Logs
```bash
# View logs
tail -f linkedin_ingestor.log

# Run with verbose logging
python3 linkedin_ingestor_cli.py -v run
```

## 📊 Current Data Status

After setting up the production system:
- ✅ **436 LinkedIn URLs** stored in `linkedin_links` table
- ✅ **253 records** from Growth Desk sheet
- ✅ **183 records** from Soul in Product sheet  
- ✅ **152 job postings** + **284 LinkedIn posts**
- ✅ **Backup CSV**: `google_sheet_ingestor_20250925_449.csv`

## 🎯 Next Steps

1. **Regular Execution**: Set up daily cron job
   ```bash
   # Add to crontab for daily 9 AM execution
   0 9 * * * cd /path/to/project && python3 linkedin_ingestor_cli.py run
   ```

2. **Month Transitions**: Update tab configurations for new months
   ```bash
   python3 linkedin_ingestor_cli.py config set --key sheets.growth_desk.tab --value "October (2025)"
   python3 linkedin_ingestor_cli.py config set --key sheets.soul_product.tab --value "October Openings "
   ```

3. **Monitoring**: Set up alerts for failed runs
   ```sql
   -- Query failed runs
   SELECT * FROM v_run_statistics WHERE status = 'failed';
   ```

## 🏆 Key Features Delivered

✅ **Incremental Processing** - Only processes new dates  
✅ **State Management** - Tracks progress automatically  
✅ **Error Resilience** - Handles failures gracefully  
✅ **Comprehensive Logging** - Full audit trail  
✅ **CLI Interface** - Easy operations and monitoring  
✅ **Configuration Management** - Flexible sheet/tab management  
✅ **Data Validation** - Robust extraction and deduplication  
✅ **Backup System** - Automatic CSV backups with proper naming  

The system is now production-ready and will automatically continue ingestion from where it left off on each run! 🚀