# LinkedIn Scrapper Pipeline - Product Handover
**Version**: 2.0  
**Date**: 2025-09-24  
**Status**: Production Ready  

## 📋 **Overview**
This is a comprehensive LinkedIn scraping pipeline that extracts job postings and social posts from Google Sheets, stores them in PostgreSQL with full metadata, and manages the scraping workflow.

---

## 🗂️ **File Structure & What Each File Does**

### **🔧 Core Production Scripts**

| File | Purpose | Usage |
|------|---------|-------|
| **`production_september_ingestor.py`** | ✅ Main production ingestor | `python production_september_ingestor.py` |
| **`ingest_3sheets_links_v1.py`** | ⚠️ Legacy URL-only ingestor | `python ingest_3sheets_links_v1.py` |
| **`extract_september_enhanced.py`** | 🔍 Enhanced September extractor | `python extract_september_enhanced.py` |
| **`fix_missing_sheets_metadata.py`** | 🛠️ Metadata repair tool | `python fix_missing_sheets_metadata.py` |

### **🏗️ Infrastructure & Libraries (src/)**

#### **Google Sheets Integration**
- **`src/clients/google_sheets.py`** - Google Sheets API client
- **`src/extractor/google_sheets/`** - Sheet parsing logic
  - `links.py` - LinkedIn URL extraction
  - `select.py` - Tab selection by month  
  - `urls.py` - URL parsing utilities
  - `client.py` - Authentication handling

#### **Database Operations**
- **`src/db/import_and_backup.py`** - Database import with backups
- **`src/app.py`** - Main CLI application interface

#### **Data Processing**
- **`src/ingest/`** - Data ingestion modules
  - `combined_links_csv.py` - Multi-sheet combiner
  - `google_sheets_run.py` - Google Sheets workflow
  - `august_sheet_links.py` - August-specific parser
  - `sheet3_links.py` - Three-tab sheet parser

#### **Scraping Engine**
- **`src/scraper/`** - LinkedIn scraping components
- **`src/workers/`** - Background processing workers
- **`batch_linkedin_scraper_base.py`** - Main LinkedIn scraper

### **⚙️ Configuration**
- **`config/sheets_v2.yaml`** - Google Sheets URLs configuration
- **`client_secret_*.json`** - Google OAuth credentials  
- **`.secrets/google_token.json`** - OAuth tokens (auto-generated)

### **📁 Data Storage**
- **`storage/production/`** - Production ingestion outputs
- **`storage/ingest/google_sheets/`** - Raw extraction CSVs
- **`storage/backups/`** - Database backup CSVs
- **`logs/`** - Application logs

---

## 🎯 **Main Production Workflows**

### **1. Google Sheets Ingestion**
```bash
# Full production ingestion (recommended)
python production_september_ingestor.py

# Dry run first (testing)
python production_september_ingestor.py --dry-run

# Limit records for testing
python production_september_ingestor.py --limit 10
```

### **2. Database Operations**  
```bash
# Import CSV to database with backup
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/data_lake" \
python -m src.app import-and-backup \
--csv ./storage/production/september_data.csv \
--backup-dir ./storage/backups
```

### **3. LinkedIn Scraping**
```bash
# Scrape LinkedIn posts with full metadata
python batch_linkedin_scraper_base.py
```

---

## 🗄️ **Database Schema**

### **linkedin_links table** (29 columns)
```sql
-- Core identification
id, url, url_canonical

-- Metadata extracted from sheets
company, role, location, date_in_source
sheet_name, tab, row_number
spreadsheet_id, spreadsheet_title

-- Processing status
source, classification, category, status, priority
attempt_count, next_attempt_at, last_error

-- Scraping results
scrape_ok, last_scraped_at, scraped_at, error_message

-- Timestamps
created_at, updated_at, discovered_at, extracted_at, queued_at
```

---

## 📊 **Google Sheets Configuration**

### **Current Active Sheets (September 2025)**
1. **Job Dashboard - The Growth Desk**
   - ID: `1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q`
   - Tab: `September (2025)`
   - Format: Standard (Company, Role, Location columns)

2. **Soul in Product - Dashboard**  
   - ID: `1p7O7tUBYM94IqEmIlXp8a5B0nGdX8DwP-bmVFu0FAK0`
   - Tab: `September Openings`
   - Format: Standard with date headers

3. **The FinTech PM - Job Dashboard**
   - ID: `1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q`
   - Tabs: `The FinTech PM`, `Top 1% PM`, `The Remote PM`
   - Format: Multi-tab with date sections

---

## 🚀 **How to Run Production Ingestion**

### **Step 1: Clean Start (if needed)**
```bash
# Backup and clear database
psql postgresql://postgres:postgres@localhost:5432/data_lake -c "
CREATE TABLE linkedin_links_backup_$(date +%Y%m%d) AS TABLE linkedin_links;
TRUNCATE TABLE linkedin_links RESTART IDENTITY CASCADE;
"
```

### **Step 2: Run Production Ingestor**
```bash
# Test first
python production_september_ingestor.py --dry-run

# Full production run
python production_september_ingestor.py
```

### **Step 3: Verify Results**
```bash
# Check database
psql postgresql://postgres:postgres@localhost:5432/data_lake -c "
SELECT 
    sheet_name,
    COUNT(*) as total,
    COUNT(company) as with_company,
    COUNT(role) as with_role
FROM linkedin_links 
GROUP BY sheet_name;
"
```

---

## 🔍 **Key Features**

### **✅ What Works**
- ✅ **Google Sheets Authentication** - OAuth with refresh tokens
- ✅ **Multi-sheet Extraction** - Handles 3 different sheet formats  
- ✅ **Full Metadata Capture** - Company, role, location, dates
- ✅ **Database Integration** - PostgreSQL with all 29 columns
- ✅ **Error Handling** - Comprehensive logging and recovery
- ✅ **Date Detection** - Regex-based September date parsing
- ✅ **LinkedIn URL Recognition** - Both `linkedin.com` and `lnkd.in`
- ✅ **Production Logging** - Structured logs in `./logs/`
- ✅ **CSV Backups** - Every import creates backups

### **⚠️ Known Issues**  
- ⚠️ **Some Google Sheets tabs** have permission/access issues
- ⚠️ **FinTech PM tabs** - Tab names don't match exactly
- ⚠️ **Rate limiting** - Google Sheets API has quotas
- ⚠️ **LinkedIn blocking** - Scraper may need proxy rotation

---

## 🛠️ **Troubleshooting**

### **Google Sheets Issues**
```bash
# Refresh OAuth tokens
rm ./.secrets/google_token.json
python production_september_ingestor.py --dry-run
```

### **Database Issues**
```bash
# Check table exists
psql postgresql://postgres:postgres@localhost:5432/data_lake -c "\d linkedin_links"

# Check recent imports
psql postgresql://postgres:postgres@localhost:5432/data_lake -c "
SELECT source, COUNT(*), MAX(created_at) 
FROM linkedin_links 
GROUP BY source;
"
```

### **Permission Issues**
```bash
# Check file permissions
chmod +x production_september_ingestor.py
chmod 600 client_secret_*.json
```

---

## 📈 **Performance & Scale**

### **Current Capacity**
- **3 Google Sheets** simultaneously  
- **~500 LinkedIn URLs** per ingestion
- **PostgreSQL** handles millions of records
- **~2-5 minutes** per full ingestion

### **Scaling Options**
- Add more sheets to `SHEETS_CONFIG`
- Implement parallel sheet processing
- Add database connection pooling
- Implement incremental updates

---

## 🔒 **Security & Credentials**

### **Required Files**
```
client_secret_*.json         # Google OAuth client (committed)
.secrets/google_token.json   # OAuth tokens (auto-generated)
config/sheets_v2.yaml        # Sheet URLs (committed)
```

### **Environment Variables**
```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/data_lake"
export GOOGLE_OAUTH_CLIENT_JSON="./client_secret_*.json"
export GOOGLE_OAUTH_TOKEN_JSON="./.secrets/google_token.json"
```

---

## 📚 **Getting Started (New Developer)**

### **1. Setup**
```bash
# Clone and setup
cd "linkedin scrapper rebirth"
pip install -r requirements.txt
mkdir -p logs storage/production storage/backups

# Database setup (if needed)
createdb data_lake
# Run schema migrations...
```

### **2. First Run**
```bash
# Test authentication
python production_september_ingestor.py --dry-run --limit 1

# Full ingestion
python production_september_ingestor.py
```

### **3. Verify**
```bash
# Check logs
tail -f logs/september_ingestion.log

# Check database
psql postgresql://postgres:postgres@localhost:5432/data_lake -c "
SELECT COUNT(*), source FROM linkedin_links GROUP BY source;
"
```

---

## 🎯 **Next Steps & Improvements**

### **Immediate (Priority 1)**
1. ✅ Fix FinTech PM tab access issues
2. ✅ Add Soul in Product sheet retry logic  
3. ✅ Implement incremental updates (only new data)
4. ✅ Add data validation and quality checks

### **Future Enhancements (Priority 2)**
1. 🔄 **Automated scheduling** (cron jobs)
2. 🔔 **Slack/email notifications** for failures  
3. 📊 **Dashboard** for monitoring ingestion
4. 🔍 **Advanced deduplication** logic
5. 🚀 **Multi-month support** (not just September)

---

## 💾 **Production Checklist**

### **Before Every Release**
- [ ] Run `--dry-run` first
- [ ] Check logs directory exists  
- [ ] Verify database connectivity
- [ ] Test Google Sheets authentication
- [ ] Backup current database state
- [ ] Monitor disk space for CSV outputs

### **After Every Release**  
- [ ] Verify record count in database
- [ ] Check for error logs
- [ ] Validate sample of extracted data
- [ ] Update this handover document

---

**🎉 That's the complete handover! The system is now production-ready for September LinkedIn data ingestion with full metadata capture.**