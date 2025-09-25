# LinkedIn Sheets Ingestor - Production Handover Document

## 📋 Executive Summary

This is a production-ready incremental ingestion system that automatically extracts LinkedIn job and post data from Google Sheets. The system tracks progress and only processes new dates since the last successful run, making it perfect for daily automated execution.

**Current Status**: ✅ System deployed and tested with 436 LinkedIn URLs successfully ingested from September 2025 data.

---

## 🏗️ System Architecture

### Directory Structure
```
/Users/yash/linkedin scrapper rebirth/
├── linkedin_ingestor_cli.py              # Main CLI interface
├── src/
│   ├── clients/
│   │   └── google_sheets.py               # Google Sheets client
│   └── ingestion/
│       ├── state_manager.py               # State tracking & management
│       └── production_ingestor.py         # Core ingestion logic
├── sql/
│   └── production_ingestion_schema.sql   # Database schema
├── storage/production/                    # CSV output directory
├── google_sheet_ingestor_20250925_449.csv # Initial data backup
├── README_PRODUCTION_INGESTOR.md          # Detailed documentation
└── linkedin_ingestor.log                 # Application logs
```

### Key Components

1. **CLI Interface** (`linkedin_ingestor_cli.py`)
   - Main entry point for all operations
   - Commands: `init`, `run`, `status`, `config`

2. **State Manager** (`src/ingestion/state_manager.py`)
   - Tracks last successful ingestion dates
   - Manages run progress and statistics
   - Handles configuration

3. **Production Ingestor** (`src/ingestion/production_ingestor.py`)
   - Extracts data from Google Sheets
   - Processes only dates in target range
   - Handles errors gracefully

4. **Database Schema** (`sql/production_ingestion_schema.sql`)
   - Tracking tables for runs, progress, state
   - Views for monitoring and analytics

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.x with required packages
- PostgreSQL database running on localhost:5432
- Google Sheets API credentials configured
- Database `data_lake` with `linkedin_links` table

### 1. One-Time System Setup

```bash
# Navigate to project directory
cd "/Users/yash/linkedin scrapper rebirth"

# Initialize the system (sets up database schema and state)
python3 linkedin_ingestor_cli.py init
```

### 2. Daily Operations

```bash
# Run incremental ingestion (processes new dates automatically)
python3 linkedin_ingestor_cli.py run

# Check system status
python3 linkedin_ingestor_cli.py status
```

### 3. Advanced Operations

```bash
# Process specific date range
python3 linkedin_ingestor_cli.py run --start-date 2025-09-26 --end-date 2025-09-30

# Dry run (extract data but don't save to database)
python3 linkedin_ingestor_cli.py run --dry-run

# Verbose logging
python3 linkedin_ingestor_cli.py -v run

# View/modify configuration
python3 linkedin_ingestor_cli.py config get
python3 linkedin_ingestor_cli.py config set --key sheets.growth_desk.tab --value "October (2025)"
```

---

## 📊 File Breakdown

### Core Application Files

#### 1. `linkedin_ingestor_cli.py` (273 lines)
**Purpose**: Main command-line interface
**Key Functions**:
- `cmd_run()`: Execute incremental ingestion
- `cmd_status()`: Display system status  
- `cmd_config()`: Manage configuration
- `cmd_init()`: Initialize system

**Usage**: Primary entry point for all operations

#### 2. `src/ingestion/production_ingestor.py` (451 lines)
**Purpose**: Core ingestion logic with incremental processing
**Key Methods**:
- `run_incremental_ingestion()`: Main ingestion workflow
- `extract_growth_desk_data()`: Growth Desk sheet parser
- `extract_soul_product_data()`: Soul Product sheet parser
- `should_process_date()`: Date range filtering

**Usage**: Called by CLI to perform actual data extraction

#### 3. `src/ingestion/state_manager.py` (325 lines)
**Purpose**: State tracking and progress management
**Key Methods**:
- `determine_date_range()`: Calculate next dates to process
- `create_ingestion_run()`: Start new run tracking
- `update_ingestion_state()`: Update completion status
- `get_ingestion_status()`: Current system status

**Usage**: Manages what dates to process and tracks progress

### Database Files

#### 4. `sql/production_ingestion_schema.sql` (119 lines)
**Purpose**: Database schema for tracking system
**Tables Created**:
- `ingestion_runs`: Track each execution
- `ingestion_progress`: Progress by sheet/date
- `ingestion_state`: Overall state per sheet  
- `ingestion_config`: System configuration

**Usage**: Run once to set up tracking infrastructure

### Data Files

#### 5. `google_sheet_ingestor_20250925_449.csv`
**Purpose**: Backup of initial September 2025 data
**Contents**: 449 LinkedIn URLs with metadata
**Columns**: url, company, role, location, experience, ctc, industry, opportunity_no, email, date_in_source, sheet_name, tab, row_number, spreadsheet_id, classification, category

### Configuration Files

#### 6. Authentication Files
- `client_secret_28309019366-uep6ho3i3k5096d1od4fo8gp1c1tj375.apps.googleusercontent.com.json`
- `.secrets/google_token.json`

These handle Google Sheets API authentication.

---

## 🔧 Configuration Management

### Current Google Sheets Configuration
```sql
-- Growth Desk Sheet
sheets.growth_desk.id = '1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q'
sheets.growth_desk.tab = 'September (2025)'
sheets.growth_desk.name = 'Job Dashboard - The Growth Desk'

-- Soul Product Sheet  
sheets.soul_product.id = '1p7O7tUBYM94IqEmIlXp8a5B0nGdX8DwP-bmVFu0FAK0'
sheets.soul_product.tab = 'September Openings '
sheets.soul_product.name = 'Soul in Product - Dashboard'
```

### Updating for New Months
```bash
# Update tab names for October
python3 linkedin_ingestor_cli.py config set --key sheets.growth_desk.tab --value "October (2025)"
python3 linkedin_ingestor_cli.py config set --key sheets.soul_product.tab --value "October Openings "
```

---

## 📈 Monitoring & Status

### Check System Status
```bash
python3 linkedin_ingestor_cli.py status
```
**Output Example**:
```
📊 INGESTION STATUS
============================================================

📋 Sheet Status:
  Job Dashboard - The Growth Desk:
    Last successful date: 2025-09-24
    Total records: 253
    Days behind: 1
    
📅 Next ingestion range: 2025-09-25 to 2025-09-25

🏃 Recent Runs:
  ✅ dec2d2e6 | 2025-09-24 to 2025-09-25 | 34 records | completed
```

### Database Monitoring
```sql
-- Check ingestion status
SELECT * FROM v_ingestion_status;

-- View recent run statistics  
SELECT * FROM v_run_statistics LIMIT 5;

-- Check progress by date
SELECT sheet_name, ingestion_date, records_found, status 
FROM ingestion_progress 
ORDER BY ingestion_date DESC LIMIT 10;
```

---

## 🔄 How Incremental Processing Works

### Logic Flow
1. **State Check**: System queries last successful date per sheet
2. **Range Calculation**: Determines next date range to process
3. **Sheet Processing**: Extracts data only for target dates
4. **Progress Tracking**: Records progress by date and sheet
5. **State Update**: Updates last successful dates on completion

### Example Scenarios

**Scenario 1: Fresh System**
```
State: No previous runs
Action: Process Sep 1, 2025 → Today
Result: All available data ingested
```

**Scenario 2: Daily Run**
```
State: Last successful = Sep 24, 2025
Action: Process Sep 25, 2025 → Today  
Result: Only new dates processed
```

**Scenario 3: After Downtime**
```
State: Last successful = Sep 20, 2025
Action: Process Sep 21, 2025 → Today
Result: Gap period automatically filled
```

---

## 📁 Output Files

### CSV File Naming
Format: `google_sheet_ingestor_YYYYMMDD_HHMMSS_<count>.csv`

**Examples**:
- `google_sheet_ingestor_20250925_449.csv` (initial backup)
- `google_sheet_ingestor_20250925_113308_34.csv` (incremental run)

### Output Location
- **Storage Directory**: `./storage/production/`
- **Logs**: `./linkedin_ingestor.log`

---

## 🚨 Troubleshooting Guide

### Common Issues & Solutions

#### 1. "No new data to process"
**Cause**: System is up to date
**Solution**: 
```bash
# Check status
python3 linkedin_ingestor_cli.py status

# Force specific date
python3 linkedin_ingestor_cli.py run --start-date 2025-09-25 --end-date 2025-09-25
```

#### 2. Google Sheets Authentication Error
**Cause**: Missing or expired credentials
**Solution**:
```bash
# Check files exist
ls -la client_secret_*.json
ls -la .secrets/google_token.json

# Re-authenticate if needed (system will prompt)
python3 linkedin_ingestor_cli.py run
```

#### 3. Database Connection Issues
**Cause**: PostgreSQL not running or wrong credentials
**Solution**:
```bash
# Test connection
psql postgresql://postgres:postgres@localhost:5432/data_lake -c "SELECT COUNT(*) FROM linkedin_links;"

# Check if PostgreSQL is running
brew services list | grep postgresql
```

#### 4. Permission Issues
**Cause**: File permissions or directory access
**Solution**:
```bash
# Fix permissions
chmod +x linkedin_ingestor_cli.py
mkdir -p storage/production
```

### Log Analysis
```bash
# View recent logs
tail -f linkedin_ingestor.log

# Search for errors
grep -i error linkedin_ingestor.log

# View verbose logs
python3 linkedin_ingestor_cli.py -v run
```

---

## 🔧 Maintenance Tasks

### Daily Operations
```bash
# Run incremental ingestion (recommended: daily at 9 AM)
python3 linkedin_ingestor_cli.py run
```

### Weekly Tasks
```bash
# Check system status
python3 linkedin_ingestor_cli.py status

# Review logs for errors
grep -i "error\|failed" linkedin_ingestor.log | tail -20
```

### Monthly Tasks
```bash
# Update sheet tab configurations for new month
python3 linkedin_ingestor_cli.py config set --key sheets.growth_desk.tab --value "October (2025)"
python3 linkedin_ingestor_cli.py config set --key sheets.soul_product.tab --value "October Openings "

# Archive old CSV files
mkdir -p archive/$(date +%Y-%m)
mv storage/production/google_sheet_ingestor_2025092*.csv archive/$(date +%Y-%m)/
```

---

## 🎯 Production Deployment

### Automated Daily Execution
Add to crontab for daily execution at 9 AM:
```bash
# Edit crontab
crontab -e

# Add this line
0 9 * * * cd "/Users/yash/linkedin scrapper rebirth" && python3 linkedin_ingestor_cli.py run >> daily_ingestion.log 2>&1
```

### Monitoring Setup
```bash
# Create monitoring script
cat << 'EOF' > check_ingestion_health.sh
#!/bin/bash
cd "/Users/yash/linkedin scrapper rebirth"
python3 linkedin_ingestor_cli.py status | grep -q "Days behind: 0" || echo "ALERT: Ingestion falling behind"
EOF

chmod +x check_ingestion_health.sh
```

---

## 📊 Current Data Status

### Database State (as of deployment)
- **Total URLs**: 436 unique LinkedIn links
- **Growth Desk Records**: 253
- **Soul Product Records**: 183  
- **Job Postings**: 152
- **LinkedIn Posts**: 284
- **Date Range**: September 1-24, 2025

### Files Created
- ✅ Main backup: `google_sheet_ingestor_20250925_449.csv`
- ✅ Test run: `google_sheet_ingestor_20250925_113308_34.csv`
- ✅ Database schema: Fully deployed and configured
- ✅ State tracking: Initialized and ready

---

## 🆘 Emergency Procedures

### System Recovery
If the system state becomes corrupted:
```bash
# 1. Reinitialize from existing data
python3 linkedin_ingestor_cli.py init

# 2. Force full reprocessing (if needed)
python3 linkedin_ingestor_cli.py run --start-date 2025-09-01 --end-date $(date +%Y-%m-%d)

# 3. Check status
python3 linkedin_ingestor_cli.py status
```

### Data Recovery
If database data is lost:
```bash
# Restore from backup CSV
python3 insert_september_data.py  # (uses google_sheet_ingestor_20250925_449.csv)
```

---

## 🎉 Success Criteria

The system is considered successfully deployed when:
- ✅ CLI commands execute without errors
- ✅ Status shows recent successful runs  
- ✅ New incremental runs process only new dates
- ✅ CSV backups are generated with proper naming
- ✅ Database contains expected number of records
- ✅ Logs show clean execution without errors

**Current Status**: ✅ All criteria met - System ready for production use!

---

## 📞 Support Information

### Key Files for Support
1. **Logs**: `linkedin_ingestor.log`
2. **Status**: `python3 linkedin_ingestor_cli.py status`
3. **Database**: Tables `ingestion_*` for tracking data
4. **CSV Backups**: `storage/production/` directory

### Quick Diagnostic Commands
```bash
# System health check
python3 linkedin_ingestor_cli.py status

# Database connection test
psql postgresql://postgres:postgres@localhost:5432/data_lake -c "SELECT COUNT(*) FROM linkedin_links;"

# Recent activity
tail -20 linkedin_ingestor.log

# Configuration check  
python3 linkedin_ingestor_cli.py config get
```

---

## 🎯 Command Reference Card

### Essential Commands

| Command | Purpose | Example |
|---------|---------|---------|
| `init` | Initialize system (one-time) | `python3 linkedin_ingestor_cli.py init` |
| `run` | Execute incremental ingestion | `python3 linkedin_ingestor_cli.py run` |
| `status` | Check system status | `python3 linkedin_ingestor_cli.py status` |
| `config get` | View configuration | `python3 linkedin_ingestor_cli.py config get` |
| `config set` | Update configuration | `python3 linkedin_ingestor_cli.py config set --key KEY --value VALUE` |

### Advanced Commands

| Command | Purpose | Example |
|---------|---------|---------|
| `run --dry-run` | Test without saving | `python3 linkedin_ingestor_cli.py run --dry-run` |
| `run --start-date --end-date` | Process specific dates | `python3 linkedin_ingestor_cli.py run --start-date 2025-09-26 --end-date 2025-09-30` |
| `-v run` | Verbose logging | `python3 linkedin_ingestor_cli.py -v run` |
| `run --initialize` | Force state reset | `python3 linkedin_ingestor_cli.py run --initialize` |

---

## 🎭 System Behavior Summary

### What It Does
- ✅ Automatically detects new dates to process
- ✅ Extracts LinkedIn URLs with metadata from Google Sheets
- ✅ Stores data in PostgreSQL with deduplication
- ✅ Creates CSV backups with proper naming
- ✅ Tracks progress and maintains state
- ✅ Provides detailed logging and monitoring

### What It Doesn't Do
- ❌ Scrape LinkedIn content (URLs only)
- ❌ Modify Google Sheets
- ❌ Delete existing database records
- ❌ Process dates from the future
- ❌ Handle multiple sheet formats automatically

---

## 💡 Best Practices

### Daily Operations
1. Run `python3 linkedin_ingestor_cli.py run` once per day
2. Check status weekly with `python3 linkedin_ingestor_cli.py status`
3. Monitor logs for errors: `tail linkedin_ingestor.log`

### Monthly Maintenance
1. Update sheet tab names for new months
2. Archive old CSV files
3. Review database growth and performance

### Troubleshooting Approach
1. Check status first: `python3 linkedin_ingestor_cli.py status`
2. Review recent logs: `tail -20 linkedin_ingestor.log`
3. Test database connection
4. Verify Google Sheets credentials

---

**System Ready for Production Use** ✅  
**Last Updated**: 2025-09-25  
**Version**: Production v1.0  
**Location**: `/Users/yash/linkedin scrapper rebirth/`