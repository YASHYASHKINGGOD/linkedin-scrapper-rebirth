# TROUBLESHOOTING.md - LinkedIn Selenium Scraper

## Quick Diagnostics

### Check System Health
```bash
# Verify environment
source venv/bin/activate
python --version
python -c "import selenium; print('Selenium OK')"

# Test configuration
python -c "import json; json.load(open('config.json')); print('Config OK')"

# Check Chrome installation  
which google-chrome || which chromium-browser

# Test WebDriver
python -c "from webdriver_manager.chrome import ChromeDriverManager; print('WebDriver:', ChromeDriverManager().install())"
```

## Common Issues and Solutions

### 1. Login Problems

#### Issue: "Login failed - possibly incorrect credentials"
**Symptoms:**
- Login form accepts credentials but redirects back to login page
- No 2FA prompt appears
- Error in logs: "Login failed with error message"

**Solutions:**
1. **Verify credentials manually:**
   ```bash
   # Test login in regular browser first
   open https://www.linkedin.com/login
   ```

2. **Check account status:**
   - Ensure account is not locked or restricted
   - Verify no recent suspicious activity warnings
   - Check if account requires password reset

3. **Update configuration:**
   ```json
   {
       "scraping_settings": {
           "headless": false,
           "page_load_timeout": 30
       }
   }
   ```

#### Issue: "Login requires verification (2FA/CAPTCHA)"
**Symptoms:**
- Browser opens to challenge page
- Script waits indefinitely
- Manual intervention required

**Solutions:**
1. **Complete challenge manually:**
   - Keep browser window open
   - Complete 2FA or CAPTCHA
   - Script will continue automatically

2. **Set up session persistence:**
   ```json
   {
       "chrome_options": {
           "user_data_dir": "/tmp/linkedin_profile"
       }
   }
   ```

3. **Use app-specific password (if available):**
   - Generate app password in LinkedIn settings
   - Use instead of regular password

#### Issue: "Element not found during login"
**Symptoms:**
- Timeout waiting for username/password fields
- LinkedIn page loads differently than expected
- CSS selectors don't match

**Solutions:**
1. **Check LinkedIn page structure:**
   ```bash
   # Run in headed mode and inspect elements
   # Look for: #username, #password, button[type=submit]
   ```

2. **Update selectors if needed:**
   - LinkedIn may have changed DOM structure
   - Check browser developer tools for current IDs/classes
   - Update selenium_scraper.py with new selectors

### 2. WebDriver Issues

#### Issue: "ChromeDriver executable not found"
**Symptoms:**
- Error: "chromedriver executable needs to be in PATH"
- Script fails before opening browser

**Solutions:**
1. **Update webdriver-manager:**
   ```bash
   pip install --upgrade webdriver-manager
   ```

2. **Force driver reinstall:**
   ```bash
   python -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()"
   ```

3. **Check Chrome version compatibility:**
   ```bash
   google-chrome --version
   # Ensure Chrome and ChromeDriver versions match
   ```

#### Issue: "Browser crashes or becomes unresponsive"
**Symptoms:**
- Chrome window closes unexpectedly
- Selenium commands timeout
- High CPU/memory usage

**Solutions:**
1. **Reduce resource usage:**
   ```json
   {
       "chrome_options": {
           "disable_automation_flags": [
               "--no-sandbox",
               "--disable-dev-shm-usage",
               "--disable-extensions",
               "--disable-plugins",
               "--disable-images"
           ]
       }
   }
   ```

2. **Add stability options:**
   ```json
   {
       "chrome_options": {
           "window_size": [1280, 720],
           "additional_flags": [
               "--disable-gpu",
               "--disable-software-rasterizer"
           ]
       }
   }
   ```

### 3. Network and Connection Issues

#### Issue: "Page load timeout" or "Network connectivity problems"
**Symptoms:**
- Pages fail to load within timeout period
- Intermittent connection errors
- Slow page responses

**Solutions:**
1. **Increase timeouts:**
   ```json
   {
       "scraping_settings": {
           "page_load_timeout": 60,
           "explicit_wait_timeout": 30
       }
   }
   ```

2. **Check network stability:**
   ```bash
   ping linkedin.com
   curl -I https://www.linkedin.com
   ```

3. **Use connection retry logic:**
   ```python
   # Add to scraper configuration
   max_retries = 3
   retry_delay = 5
   ```

#### Issue: "403 Forbidden" or "429 Too Many Requests"
**Symptoms:**
- LinkedIn blocks requests
- Rate limiting responses
- Account temporary restrictions

**Solutions:**
1. **Increase delays dramatically:**
   ```json
   {
       "scraping_settings": {
           "random_delay_range": [5.0, 15.0]
       }
   }
   ```

2. **Switch to headed mode:**
   ```json
   {
       "scraping_settings": {
           "headless": false
       }
   }
   ```

3. **Wait for rate limit reset:**
   - Stop scraping for 24-48 hours
   - Check account for warnings
   - Resume with more conservative settings

### 4. Content Extraction Issues

#### Issue: "Unable to extract post content"
**Symptoms:**
- Posts load but content extraction fails
- Empty or partial data returned
- Selector not found errors

**Solutions:**
1. **Verify post URL format:**
   ```python
   # Supported formats:
   # https://www.linkedin.com/posts/username_activity-123456789
   # https://www.linkedin.com/feed/update/urn:li:activity:123456789
   ```

2. **Check DOM structure manually:**
   ```bash
   # Open post in browser, inspect elements
   # Look for content containers, author info
   ```

3. **Add content waiting logic:**
   ```python
   # Wait for dynamic content to load
   WebDriverWait(driver, 10).until(
       EC.presence_of_element_located((By.CSS_SELECTOR, ".post-content"))
   )
   ```

#### Issue: "Comments not loading or expanding"
**Symptoms:**
- Comment sections empty
- "Show more comments" buttons not clicked
- Nested replies missing

**Solutions:**
1. **Reduce expansion attempts:**
   ```json
   {
       "scraping_settings": {
           "max_comment_expansion_attempts": 3
       }
   }
   ```

2. **Add manual scroll simulation:**
   ```python
   driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
   time.sleep(2)
   ```

### 5. Configuration Issues

#### Issue: "Config file not found or invalid JSON"
**Symptoms:**
- FileNotFoundError on startup
- JSON parsing errors
- Configuration validation fails

**Solutions:**
1. **Validate JSON syntax:**
   ```bash
   python -c "import json; print(json.load(open('config.json')))"
   ```

2. **Use config template:**
   ```bash
   cp config.json.example config.json
   # Edit with your credentials
   ```

3. **Check file permissions:**
   ```bash
   ls -la config.json
   chmod 644 config.json
   ```

#### Issue: "Environment variables not loading"
**Symptoms:**
- Credentials not found despite being set
- Environment variable substitution fails

**Solutions:**
1. **Verify environment variables:**
   ```bash
   echo $LINKEDIN_EMAIL
   echo $LINKEDIN_PASSWORD
   ```

2. **Export variables properly:**
   ```bash
   export LINKEDIN_EMAIL="your-email@domain.com"
   export LINKEDIN_PASSWORD="your-password"
   source venv/bin/activate
   ```

### 6. Performance Issues

#### Issue: "Scraper running very slowly"
**Symptoms:**
- Each post takes 30+ seconds
- Excessive delays between actions
- High resource usage

**Solutions:**
1. **Optimize delay settings:**
   ```json
   {
       "scraping_settings": {
           "random_delay_range": [1.0, 2.0],
           "implicit_wait_timeout": 5,
           "explicit_wait_timeout": 10
       }
   }
   ```

2. **Enable headless mode:**
   ```json
   {
       "scraping_settings": {
           "headless": true
       }
   }
   ```

3. **Disable unnecessary features:**
   ```json
   {
       "chrome_options": {
           "disable_automation_flags": [
               "--disable-images",
               "--disable-plugins",
               "--disable-extensions"
           ]
       }
   }
   ```

## Advanced Troubleshooting

### Enable Debug Logging
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)

# In config.json:
{
    "logging": {
        "level": "DEBUG"
    }
}
```

### Create Minimal Test Case
```python
# test_minimal.py - Minimal reproduction case
from selenium_scraper import LinkedInSeleniumScraper

def test_login_only():
    with LinkedInSeleniumScraper() as scraper:
        scraper.initialize_driver()
        success, message = scraper.login()
        print(f"Login result: {success}, Message: {message}")

if __name__ == "__main__":
    test_login_only()
```

### Browser Developer Mode
```python
# Add to chrome_options for debugging
chrome_options.add_argument("--remote-debugging-port=9222")
# Then connect Chrome DevTools to localhost:9222
```

### Check System Resources
```bash
# Monitor resource usage during scraping
top -p $(pgrep -f selenium_scraper)
htop  # if available

# Check disk space
df -h

# Monitor network usage
sudo netstat -i
```

## Recovery Procedures

### Session Recovery
```python
# If scraper crashes, check for partial data
ls outputs/*_partial*

# Resume from specific post
# (implement resume logic in your scraper)
```

### Data Recovery
```python
# Validate output files
python -c "
import json
try:
    json.load(open('outputs/latest.json'))
    print('JSON file valid')
except:
    print('JSON file corrupted, check backups')
"
```

### Account Recovery
1. **If account restricted:**
   - Stop all scraping immediately
   - Wait 48-72 hours
   - Login manually to check status
   - Contact LinkedIn support if needed

2. **If session expired:**
   - Clear browser cache/cookies
   - Delete session files
   - Re-run initial setup process

## Getting Help

### Information to Provide
When reporting issues, include:

1. **System information:**
   ```bash
   uname -a
   python --version
   google-chrome --version
   ```

2. **Configuration (sanitized):**
   ```bash
   # Remove credentials first
   cat config.json | jq 'del(.linkedin_credentials)'
   ```

3. **Error logs:**
   ```bash
   tail -50 scraper.log
   ```

4. **Steps to reproduce:**
   - Exact commands run
   - Expected vs actual behavior
   - Screenshots if relevant

### Emergency Contacts
- **LinkedIn Account Issues:** LinkedIn Help Center
- **Technical Issues:** Check project repository issues
- **Chrome/WebDriver:** Chrome DevTools documentation

### Useful Resources
- [Selenium Documentation](https://selenium-python.readthedocs.io/)
- [Chrome DevTools](https://developers.google.com/web/tools/chrome-devtools)
- [LinkedIn Help Center](https://www.linkedin.com/help)
- [WebDriver Manager](https://pypi.org/project/webdriver-manager/)

This troubleshooting guide covers the most common issues encountered when running the LinkedIn Selenium scraper. Keep it updated as new issues are discovered and resolved.
