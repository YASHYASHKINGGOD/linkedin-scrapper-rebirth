# Operatingmanual.md - LinkedIn Selenium Scraper Operations

## Prerequisites

### System Requirements
- **Operating System**: macOS 10.15+, Ubuntu 18.04+, or Windows 10+
- **Python**: Version 3.8 or higher
- **Chrome Browser**: Latest stable version
- **Memory**: Minimum 4GB RAM (8GB+ recommended for large-scale scraping)
- **Disk Space**: 1GB+ free space for outputs and logs

### Network Requirements
- Stable internet connection (minimum 10 Mbps recommended)
- Direct access to linkedin.com (no corporate firewalls blocking)
- Optional: VPN access for IP rotation

### Account Requirements
- Valid LinkedIn account with login credentials
- Account should not have recent security restrictions
- 2FA/MFA setup if required by your account

## Environment Setup

### Initial Setup (First Time)
```bash
# 1. Clone repository and navigate
git clone <your-repo-url>
cd linkedin-scrapper-rebirth

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install selenium webdriver-manager pandas openpyxl

# 4. Verify Chrome installation
which google-chrome  # Linux
which "Google Chrome"  # macOS
where chrome.exe      # Windows

# 5. Create configuration file
cp config.json config.json.backup
# Edit config.json with your credentials (see Configuration section)
```

### Environment Verification
```bash
# Test Python and dependencies
python --version
python -c "import selenium, pandas, openpyxl; print('Dependencies OK')"

# Test WebDriver manager
python -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install(); print('WebDriver OK')"

# Validate configuration
python -c "import json; json.load(open('config.json')); print('Config valid')"
```

## Configuration

### Basic Configuration Setup
1. **Copy template**: `cp config.json config.json.example`
2. **Edit credentials**:
   ```json
   {
       "linkedin_credentials": {
           "email": "your-actual-email@domain.com",
           "password": "your-secure-password"
       }
   }
   ```
3. **Set initial settings**:
   - `"headless": false` for first run (to handle 2FA if needed)
   - `"random_delay_range": [1.0, 2.5]` for reasonable delays
   - `"page_load_timeout": 20` for slower connections

### Environment Variables (Optional but Recommended)
```bash
# Set credentials via environment (more secure)
export LINKEDIN_EMAIL="your-email@domain.com"
export LINKEDIN_PASSWORD="your-password"

# Update config to use environment variables
# "email": "${LINKEDIN_EMAIL}",
# "password": "${LINKEDIN_PASSWORD}"
```

## First-Time Login (Headed Mode)

### Recommended First-Run Process
1. **Set headed mode** in config.json:
   ```json
   {
       "scraping_settings": {
           "headless": false
       }
   }
   ```

2. **Run login test**:
   ```bash
   source venv/bin/activate
   python selenium_scraper.py
   ```

3. **Handle authentication challenges**:
   - **2FA/MFA**: Complete the challenge in the opened browser
   - **CAPTCHA**: Solve the CAPTCHA manually
   - **Email verification**: Check your email and verify if prompted
   - **Phone verification**: Enter code if requested

4. **Verify success**:
   - Look for "✅ LOGIN SUCCESSFUL" message
   - Browser should show LinkedIn feed/profile page
   - Check logs for any warnings

5. **Optional - Save session**:
   - Keep browser open for session reuse
   - Copy browser profile directory for persistence
   - Enable cookie saving in configuration

### Troubleshooting First Login
- **Browser doesn't open**: Check Chrome installation path
- **Stuck on login page**: Verify credentials in config
- **Too many redirects**: Try clearing browser cache/cookies
- **Access denied**: Check if account is locked/restricted

## Normal Operation

### Standard Scraping Workflow
1. **Pre-flight checks**:
   ```bash
   # Check environment
   source venv/bin/activate
   python -c "from selenium_scraper import LinkedInSeleniumScraper; print('Import OK')"
   
   # Verify configuration
   python -c "import json; c=json.load(open('config.json')); print(f'Config loaded for {c[\"linkedin_credentials\"][\"email\"]}')"
   
   # Check disk space
   df -h .  # Linux/macOS
   dir     # Windows
   ```

2. **Execute scraping**:
   ```bash
   # Login verification only
   python selenium_scraper.py
   
   # Full scraping session (when implemented)
   # python -c "from selenium_scraper import LinkedInSeleniumScraper; LinkedInSeleniumScraper().run_full_scrape()"
   ```

3. **Monitor progress**:
   ```bash
   # Real-time log monitoring
   tail -f scraper.log
   
   # Check outputs
   ls -la outputs/
   ```

### Headless Operation (Production Mode)
After successful first-time setup:
1. **Enable headless mode**:
   ```json
   {
       "scraping_settings": {
           "headless": true
       }
   }
   ```

2. **Test headless operation**:
   ```bash
   python selenium_scraper.py
   # Should complete without opening browser window
   ```

3. **Schedule recurring runs** (optional):
   ```bash
   # Crontab example (run daily at 2 AM)
   0 2 * * * /path/to/venv/bin/python /path/to/selenium_scraper.py
   ```

## Logs and Monitoring

### Log Files and Locations
- **Main log**: `scraper.log` (in project root)
- **Rotation**: Automatic when file exceeds size limit
- **Archive**: `scraper.log.1`, `scraper.log.2`, etc.
- **Chrome logs**: System temp directory (auto-cleaned)

### Log Levels and Interpretation
```
DEBUG   - Detailed execution steps, timing information
INFO    - Normal operation messages, progress updates
WARNING - Recoverable issues, fallback actions taken  
ERROR   - Failed operations, exceptions caught
CRITICAL- System failures, immediate attention required
```

### Key Log Patterns to Monitor
```bash
# Successful operations
grep "✅" scraper.log

# Login issues
grep -i "login\|auth" scraper.log

# Rate limiting or blocks
grep -i "rate\|block\|429" scraper.log

# WebDriver issues
grep -i "driver\|chrome" scraper.log

# Data extraction problems
grep -i "extract\|scrape" scraper.log
```

### Real-Time Monitoring
```bash
# Live log monitoring with highlights
tail -f scraper.log | grep --color=always -E "(ERROR|WARNING|SUCCESS|FAILED)"

# Monitor specific operations
tail -f scraper.log | grep -i "login\|scrape\|export"

# Count operations per minute
tail -f scraper.log | grep -o "INFO" | uniq -c
```

## Outputs and Results

### Output Directory Structure
```
outputs/
├── posts_20250826_143022.json     # Raw JSON data
├── posts_20250826_143022.csv      # Tabular CSV format  
├── posts_20250826_143022.xlsx     # Excel with multiple sheets
├── metadata_20250826_143022.json  # Scraping metadata
└── errors_20250826_143022.log     # Session-specific errors
```

### Output File Formats

#### JSON Output
- **Structure**: Array of post objects with nested comments
- **Use case**: Programmatic processing, API integration
- **Size**: Typically largest but most complete

#### CSV Output  
- **Structure**: Flattened rows with post and comment data
- **Use case**: Excel analysis, database import
- **Limitations**: Nested data is flattened

#### Excel Output
- **Sheets**: Posts, Comments, Authors, Metadata
- **Use case**: Business reporting, manual analysis
- **Features**: Formatted columns, charts (when implemented)

### Data Validation
```bash
# Check output file integrity
python -c "import json; json.load(open('outputs/posts_YYYYMMDD_HHMMSS.json')); print('JSON valid')"

# Count records
wc -l outputs/posts_YYYYMMDD_HHMMSS.csv

# Check file sizes
du -sh outputs/*
```

## Safe Shutdown

### Graceful Termination
```bash
# If scraper is running, use Ctrl+C for graceful shutdown
# This will:
# 1. Complete current operation
# 2. Save partial results
# 3. Close browser cleanly
# 4. Write final log entries
```

### Force Termination (Emergency)
```bash
# Find and kill scraper processes
ps aux | grep selenium_scraper
kill -TERM <process_id>

# Kill orphaned Chrome processes
pkill -f chrome
# OR on Windows: taskkill /f /im chrome.exe

# Clean up temporary files
rm -f /tmp/chrome_* /tmp/scoped_dir*
```

### Post-Shutdown Cleanup
```bash
# Verify all processes stopped
ps aux | grep -E "(chrome|selenium)"

# Check for partial output files
ls -la outputs/*_partial*

# Review final log entries
tail -20 scraper.log
```

## Maintenance Procedures

### Regular Maintenance (Weekly)

#### Log Management
```bash
# Rotate logs manually if needed
mv scraper.log scraper.log.$(date +%Y%m%d)
touch scraper.log

# Clean old logs (keep last 30 days)
find . -name "scraper.log.*" -mtime +30 -delete
```

#### Output Management
```bash
# Archive old outputs
mkdir -p archives/$(date +%Y%m)
mv outputs/* archives/$(date +%Y%m)/

# Compress archives
tar -czf archives/archive_$(date +%Y%m%d).tar.gz archives/$(date +%Y%m)/
```

#### Dependency Updates
```bash
# Update Python packages
source venv/bin/activate
pip list --outdated
pip install --upgrade selenium webdriver-manager pandas openpyxl

# Update Chrome browser (system-specific)
# Usually auto-updates, but check manually if issues occur
```

### Driver Updates
```bash
# Force WebDriver update
python -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()"

# Clear WebDriver cache if issues occur
rm -rf ~/.wdm/drivers/
```

### Configuration Validation
```bash
# Validate current config
python -c "
import json, jsonschema
config = json.load(open('config.json'))
# Add validation logic here
print('Configuration validated successfully')
"
```

### Selector Updates (When LinkedIn Changes)
1. **Identify broken selectors** from error logs
2. **Test selectors manually** in browser dev tools
3. **Update selector constants** in code
4. **Add fallback selectors** for robustness
5. **Test with sample pages** before production

### Performance Monitoring
```bash
# Check memory usage during runs
ps aux | grep selenium_scraper | awk '{print $4, $6}'

# Monitor disk usage
du -sh outputs/ logs/ venv/

# Network usage (if available)
sudo iftop  # or equivalent network monitor
```

### Security Maintenance
- **Rotate credentials** quarterly
- **Review access logs** for unusual patterns  
- **Update browser** for latest security patches
- **Audit configuration** for exposed secrets
- **Check account status** on LinkedIn regularly

### Troubleshooting Checklist
1. ✅ Chrome browser installed and updated
2. ✅ Python virtual environment activated  
3. ✅ Dependencies installed and current
4. ✅ Configuration file present and valid
5. ✅ LinkedIn account accessible manually
6. ✅ Network connectivity to linkedin.com
7. ✅ Sufficient disk space for outputs
8. ✅ No conflicting processes running
9. ✅ Logs contain no persistent errors
10. ✅ Output files generated successfully

This operational manual provides comprehensive guidance for running and maintaining the LinkedIn Selenium scraper in production environments.
