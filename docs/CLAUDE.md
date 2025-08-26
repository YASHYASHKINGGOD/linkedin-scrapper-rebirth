# CLAUDE.md - LinkedIn Selenium Scraper

## Environment Setup

### Prerequisites
- Python 3.8+
- Chrome browser installed
- Git for version control

### Quick Setup
```bash
# Clone and navigate to repository
git clone <your-repo-url>
cd linkedin-scrapper-rebirth

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install selenium webdriver-manager pandas openpyxl

# Create config file (see Configuration section)
cp config.json.example config.json
```

## Configuration

### config.json Structure
Create `config.json` in the root directory with your LinkedIn credentials and scraping settings:

```json
{
    "linkedin_credentials": {
        "email": "your-email@example.com",
        "password": "your-password-here"
    },
    "scraping_settings": {
        "headless": false,
        "random_delay_range": [1.0, 2.5],
        "page_load_timeout": 20,
        "max_comment_expansion_attempts": 6,
        "implicit_wait_timeout": 10,
        "explicit_wait_timeout": 15
    },
    "chrome_options": {
        "disable_automation_flags": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage"
        ],
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "window_size": [1920, 1080]
    },
    "output_settings": {
        "save_to_json": true,
        "save_to_csv": true,
        "save_to_excel": true,
        "output_directory": "outputs"
    }
}
```

### Security Notes
- Never commit real credentials to version control
- Use environment variables for production deployments
- Consider using encrypted credential storage

## How Selenium Login Works

### Anti-Automation Hardening
Our Selenium setup includes several anti-detection measures:

1. **Chrome Options**:
   - `--disable-blink-features=AutomationControlled` - Removes automation indicators
   - `--no-sandbox` - Bypasses sandbox restrictions
   - Custom user agent string
   - Removal of navigator.webdriver property via JavaScript

2. **Behavioral Mimicry**:
   - Random delays between actions (1.0-2.5 seconds by default)
   - Human-like typing patterns
   - Realistic page load waits

3. **Success Detection**:
   - URL pattern matching (feed, mynetwork, jobs, etc.)
   - Page source analysis for error indicators
   - Multi-step verification process

### Login Flow Steps
1. Navigate to https://www.linkedin.com/login
2. Wait for username/password fields to load
3. Fill credentials with random delays
4. Click submit button
5. Wait for navigation and verify success
6. Handle 2FA/CAPTCHA if required

## Quick-Start Steps

### 1. Login Verification
Test your setup with a simple login check:
```bash
# Activate virtual environment
source venv/bin/activate

# Run login verification
python selenium_scraper.py
```

Expected output:
```
✅ SUCCESS: Login verification passed!
You can now proceed with scraping operations.
```

### 2. Configuration Troubleshooting
If login fails:
- Set `"headless": false` in config.json for visual debugging
- Check credentials are correct
- Ensure you can login manually in browser
- Review scraper.log for detailed errors

### 3. First Run with 2FA
For accounts with 2FA enabled:
1. Set `"headless": false` in config.json
2. Run the verification script
3. Complete 2FA/CAPTCHA manually in the browser window
4. Script will continue automatically after verification

## Scraping Posts and Saving Results

### Basic Post Scraping (Coming Soon)
```python
from selenium_scraper import LinkedInSeleniumScraper

with LinkedInSeleniumScraper() as scraper:
    # Initialize and login
    scraper.initialize_driver()
    success, message = scraper.login()
    
    if success:
        # Scrape posts from feed
        posts = scraper.scrape_feed_posts(max_posts=50)
        
        # Save results
        scraper.save_posts_to_files(posts)
```

### Output Formats
Results are automatically saved in multiple formats:

1. **JSON** (`outputs/posts_YYYYMMDD_HHMMSS.json`)
   - Raw structured data
   - Best for programmatic processing

2. **CSV** (`outputs/posts_YYYYMMDD_HHMMSS.csv`)
   - Tabular format
   - Easy Excel import

3. **Excel** (`outputs/posts_YYYYMMDD_HHMMSS.xlsx`)
   - Formatted spreadsheet
   - Multiple sheets for posts/comments

### Data Fields Captured
- Post ID and URL
- Author information
- Post content and timestamp
- Engagement metrics (likes, comments, shares)
- Comments with nested replies
- Media attachments (images, videos, documents)

## Logging and Monitoring

### Log Files
- `scraper.log` - Main application log with INFO level
- Console output for real-time monitoring
- Rotating logs to prevent disk space issues

### Log Levels
- **DEBUG**: Detailed execution traces
- **INFO**: Normal operation messages
- **WARNING**: Recoverable issues
- **ERROR**: Failed operations
- **CRITICAL**: System failures

## Best Practices

### Rate Limiting
- Use random delays between requests
- Monitor your account for unusual activity warnings
- Stay within LinkedIn's usage guidelines

### Error Handling
- Always use context managers (`with` statements)
- Implement retry logic for transient failures
- Clean up resources properly

### Session Management
- Reuse browser sessions when possible
- Handle cookie persistence for repeated runs
- Respect LinkedIn's terms of service

## Troubleshooting

### Common Issues

1. **ChromeDriver Issues**
   ```bash
   # Update webdriver-manager
   pip install --upgrade webdriver-manager
   ```

2. **Element Not Found**
   - LinkedIn may have updated their DOM structure
   - Check for element selector updates
   - Use multiple fallback selectors

3. **Login Failures**
   - Verify credentials in config.json
   - Check for account locks or security challenges
   - Try non-headless mode for manual intervention

4. **Network Issues**
   - Check internet connection
   - Verify LinkedIn isn't blocking your IP
   - Consider using different network/VPN

### Getting Help
- Check `scraper.log` for detailed error information
- Enable DEBUG logging for verbose output
- Review the TROUBLESHOOTING.md document
- Test with minimal configuration first

## Development Notes

### Session: 2025-08-26
- Initial Selenium-based scraper setup
- Replaced Playwright with Selenium WebDriver
- Implemented robust login flow with anti-automation hardening
- Created configuration system for flexible settings
- Added comprehensive logging and error handling
- Built verification system for testing login functionality

### Next Steps
- Add post scraping functionality
- Implement comment expansion logic
- Build data export pipeline
- Create scheduled scraping workflows
- Add proxy support for large-scale operations
