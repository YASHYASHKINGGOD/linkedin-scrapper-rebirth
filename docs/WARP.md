# WARP.md - LinkedIn Selenium Scraper Commands

## One-Liner Commands

### Environment Setup
```bash
# Create virtual environment and install dependencies
python3 -m venv venv && source venv/bin/activate && pip install selenium webdriver-manager pandas openpyxl
```

### Login Testing
```bash
# Run login-only check (make sure config.json is configured first)
source venv/bin/activate && python selenium_scraper.py
```

### Full Scrape Operations (Coming Soon)
```bash
# Run full scrape with default settings
source venv/bin/activate && python -c "from selenium_scraper import LinkedInSeleniumScraper; LinkedInSeleniumScraper().run_full_scrape()"
```

### Documentation Regeneration
```bash
# Regenerate all documentation (run these prompts in Warp AI)
# See "Reusable AI Prompts" section below
```

### Development Commands
```bash
# Clean up cache and temporary files
find . -type f -name "*.pyc" -delete && find . -type d -name "__pycache__" -delete

# Check code quality (when implemented)
source venv/bin/activate && python -m flake8 selenium_scraper.py

# Run tests (when implemented)
source venv/bin/activate && python -m pytest tests/
```

### Logs and Monitoring
```bash
# View recent scraper logs
tail -n 50 scraper.log

# Monitor log in real-time
tail -f scraper.log

# Clean old logs
find . -name "scraper.log.*" -mtime +7 -delete
```

### Output Management
```bash
# List recent outputs
ls -la outputs/ | head -10

# Archive old outputs
mkdir -p archives/$(date +%Y%m) && mv outputs/* archives/$(date +%Y%m)/

# Clean outputs directory
rm -rf outputs/* && mkdir -p outputs
```

## Reusable AI Prompts

### Code Generation Prompts

#### Post Scraping Module
```
Create a post scraping module for selenium_scraper.py that:
1. Navigates to LinkedIn feed after login
2. Scrolls to load posts dynamically
3. Extracts post content, author, timestamp, engagement metrics
4. Handles "Show more" expansion for long posts
5. Extracts comments with nested replies
6. Returns structured data as Python dictionaries
7. Includes robust error handling and logging
8. Follows the existing code style and patterns
```

#### Comment Expansion Logic
```
Add comment expansion functionality to selenium_scraper.py that:
1. Finds "Show more comments" buttons
2. Clicks to expand comments up to max_comment_expansion_attempts
3. Handles nested comment replies
4. Extracts comment author, content, timestamp, likes
5. Implements random delays between expansions
6. Gracefully handles cases where expansion fails
7. Logs expansion progress and results
```

#### Data Export Pipeline
```
Create data export functions for selenium_scraper.py that:
1. Takes scraped posts data as input
2. Saves to JSON with proper formatting and indentation
3. Creates CSV with flattened post structure
4. Generates Excel file with multiple sheets (Posts, Comments, Authors)
5. Uses timestamp-based filenames
6. Creates output directory if needed
7. Handles large datasets efficiently
8. Includes data validation before export
```

### Documentation Update Prompts

#### API Documentation
```
Generate comprehensive API documentation for selenium_scraper.py covering:
1. Class methods with parameters and return types
2. Configuration options and their effects
3. Error handling and exception types
4. Usage examples for common scenarios
5. Integration patterns for external applications
6. Performance considerations and limitations
```

#### Configuration Guide
```
Create a detailed configuration guide explaining:
1. All config.json options with examples
2. Performance tuning recommendations
3. Security best practices for credentials
4. Environment-specific settings
5. Troubleshooting configuration issues
6. Advanced Chrome options and their purposes
```

#### Troubleshooting Guide
```
Expand the troubleshooting documentation to include:
1. Common error scenarios and solutions
2. Network and connectivity issues
3. LinkedIn-specific challenges (rate limits, blocks)
4. Chrome/WebDriver compatibility problems
5. Configuration validation steps
6. Diagnostic commands and log analysis
7. Recovery procedures for failed scrapes
```

### Testing and Quality Assurance Prompts

#### Unit Tests
```
Create comprehensive unit tests for selenium_scraper.py that:
1. Mock WebDriver interactions
2. Test configuration loading and validation
3. Verify login flow logic
4. Test data extraction functions
5. Cover error handling scenarios
6. Include performance benchmarks
7. Use pytest framework with fixtures
8. Achieve >90% code coverage
```

#### Integration Tests
```
Create integration tests that:
1. Test full login flow with test account
2. Verify post scraping on sample data
3. Test all export formats
4. Validate configuration scenarios
5. Test error recovery mechanisms
6. Include performance regression tests
7. Can run in CI/CD pipeline
```

#### Code Quality Checks
```
Set up code quality tools including:
1. flake8 for style checking
2. black for code formatting
3. mypy for type checking
4. bandit for security analysis
5. Pre-commit hooks configuration
6. GitHub Actions workflow
7. Code coverage reporting
```

### Deployment and Operations Prompts

#### Docker Configuration
```
Create Docker setup for the LinkedIn scraper including:
1. Multi-stage Dockerfile with Python 3.11
2. Chrome and ChromeDriver installation
3. Virtual display for headless operation
4. Volume mounting for outputs and config
5. Health check endpoints
6. Environment variable configuration
7. docker-compose.yml for easy deployment
```

#### Scheduling System
```
Implement a scheduling system that:
1. Runs scrapes at specified intervals
2. Handles overlapping job prevention
3. Includes retry logic with exponential backoff
4. Sends notifications on success/failure
5. Manages output archiving
6. Monitors resource usage
7. Supports multiple LinkedIn accounts
8. Integrates with existing codebase
```

#### Monitoring and Alerting
```
Create monitoring system that:
1. Tracks scraping success rates
2. Monitors performance metrics
3. Alerts on failures or anomalies
4. Generates daily/weekly reports
5. Tracks LinkedIn account health
6. Monitors output data quality
7. Includes dashboard visualization
8. Integrates with external services (Slack, email)
```

## Development Workflow Commands

### Version Control
```bash
# Commit with proper message format
git add -A && git commit -m "feat(scraper): add post scraping functionality"

# Create feature branch
git checkout -b feature/comment-extraction

# Push and set upstream
git push -u origin feature/comment-extraction
```

### Environment Management
```bash
# Create requirements.txt
source venv/bin/activate && pip freeze > requirements.txt

# Install from requirements
source venv/bin/activate && pip install -r requirements.txt

# Update dependencies
source venv/bin/activate && pip install --upgrade selenium webdriver-manager pandas openpyxl
```

### Configuration Management
```bash
# Create config template
cp config.json config.json.example && sed -i 's/your-email@example.com/EMAIL_HERE/g' config.json.example

# Validate config
python -c "import json; json.load(open('config.json')); print('Config valid')"

# Backup config
cp config.json config.json.backup.$(date +%Y%m%d_%H%M%S)
```

## Quick Reference

### File Structure
```
linkedin-scrapper-rebirth/
├── selenium_scraper.py      # Main scraper module
├── config.json              # Configuration file
├── requirements.txt         # Python dependencies
├── scraper.log             # Application logs
├── venv/                   # Virtual environment
├── outputs/                # Scraped data outputs
├── docs/                   # Documentation
└── tests/                  # Test files (when added)
```

### Key Configuration Settings
- `headless: false` - Run with visible browser (recommended for setup)
- `random_delay_range: [1.0, 2.5]` - Delay between actions
- `page_load_timeout: 20` - Maximum page load wait time
- `max_comment_expansion_attempts: 6` - Comment expansion limit

### Common Troubleshooting Commands
```bash
# Check if Chrome is installed
which google-chrome || which chromium-browser

# Verify Python version
python3 --version

# Test WebDriver installation
python -c "from selenium import webdriver; from webdriver_manager.chrome import ChromeDriverManager; print('WebDriver OK')"

# Check config file syntax
python -c "import json; json.load(open('config.json')); print('Config syntax OK')"
```
