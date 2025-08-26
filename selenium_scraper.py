#!/usr/bin/env python3
"""
LinkedIn Selenium Scraper
A robust LinkedIn scraper using Selenium with anti-automation hardening
"""

import json
import logging
import random
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import os
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LinkedInSeleniumScraper:
    """
    LinkedIn scraper using Selenium with anti-automation hardening
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the LinkedIn Selenium scraper
        
        Args:
            config_path: Path to configuration JSON file
        """
        self.config = self._load_config(config_path)
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        
        # Create output directory if it doesn't exist
        self.output_dir = Path(self.config['output_settings']['output_directory'])
        self.output_dir.mkdir(exist_ok=True)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {config_path} not found")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
    
    def _setup_chrome_driver(self) -> webdriver.Chrome:
        """
        Set up Chrome driver with anti-automation hardening
        
        Returns:
            Configured Chrome WebDriver instance
        """
        logger.info("Setting up Chrome driver with anti-automation hardening")
        
        # Chrome options
        chrome_options = Options()
        
        # Add automation hardening flags
        for flag in self.config['chrome_options']['disable_automation_flags']:
            chrome_options.add_argument(flag)
        
        # Set custom user agent
        user_agent = self.config['chrome_options']['user_agent']
        chrome_options.add_argument(f"--user-agent={user_agent}")
        
        # Window size
        width, height = self.config['chrome_options']['window_size']
        chrome_options.add_argument(f"--window-size={width},{height}")
        
        # Headless mode
        if self.config['scraping_settings']['headless']:
            chrome_options.add_argument("--headless")
            logger.info("Running in headless mode")
        else:
            logger.info("Running in headed mode (recommended for first run)")
        
        # Additional stealth options
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set up Chrome driver service
        service = Service(ChromeDriverManager().install())
        
        try:
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to remove webdriver property
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            # Set timeouts
            driver.implicitly_wait(self.config['scraping_settings']['implicit_wait_timeout'])
            driver.set_page_load_timeout(self.config['scraping_settings']['page_load_timeout'])
            
            logger.info("Chrome driver setup completed successfully")
            return driver
            
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {e}")
            raise
    
    def _random_delay(self, min_delay: Optional[float] = None, max_delay: Optional[float] = None):
        """
        Apply random delay to mimic human behavior
        
        Args:
            min_delay: Minimum delay in seconds
            max_delay: Maximum delay in seconds
        """
        if min_delay is None or max_delay is None:
            delay_range = self.config['scraping_settings']['random_delay_range']
            min_delay, max_delay = delay_range[0], delay_range[1]
        
        delay = random.uniform(min_delay, max_delay)
        logger.debug(f"Applying random delay: {delay:.2f} seconds")
        time.sleep(delay)
    
    def initialize_driver(self) -> bool:
        """
        Initialize the Chrome driver
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.driver = self._setup_chrome_driver()
            self.wait = WebDriverWait(
                self.driver, 
                self.config['scraping_settings']['explicit_wait_timeout']
            )
            logger.info("Driver initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize driver: {e}")
            return False
    
    def login(self) -> Tuple[bool, str]:
        """
        Perform LinkedIn login using credentials from config
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.driver:
            return False, "Driver not initialized"
        
        try:
            logger.info("Starting LinkedIn login process")
            
            # Navigate to LinkedIn login page
            login_url = "https://www.linkedin.com/login"
            logger.info(f"Navigating to {login_url}")
            self.driver.get(login_url)
            
            # Random delay after navigation
            self._random_delay()
            
            # Wait for and find username field
            logger.info("Waiting for username field")
            username_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            
            # Wait for password field
            logger.info("Waiting for password field")
            password_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "password"))
            )
            
            # Fill in credentials
            credentials = self.config['linkedin_credentials']
            logger.info("Filling in credentials")
            
            username_field.clear()
            username_field.send_keys(credentials['email'])
            self._random_delay(0.5, 1.0)
            
            password_field.clear()
            password_field.send_keys(credentials['password'])
            self._random_delay(0.5, 1.0)
            
            # Find and click submit button
            logger.info("Looking for submit button")
            submit_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
            )
            
            submit_button.click()
            logger.info("Login form submitted")
            
            # Short delay for navigation
            self._random_delay(2.0, 3.0)
            
            # Check if login was successful
            current_url = self.driver.current_url
            logger.info(f"Current URL after login attempt: {current_url}")
            
            # Success indicators
            success_patterns = [
                'feed',
                'mynetwork',
                'jobs',
                'messaging',
                'notifications',
                '/in/',
                'linkedin.com/feed'
            ]
            
            login_successful = any(pattern in current_url.lower() for pattern in success_patterns)
            
            if login_successful:
                logger.info("✅ Login successful!")
                return True, "Login successful"
            else:
                # Check for common error indicators
                page_source = self.driver.page_source.lower()
                
                if 'challenge' in page_source or 'verification' in page_source:
                    message = "Login requires verification (2FA/CAPTCHA). Please complete manually and run again."
                    logger.warning(message)
                    return False, message
                elif 'error' in page_source or 'incorrect' in page_source:
                    message = "Login failed - possibly incorrect credentials"
                    logger.error(message)
                    return False, message
                else:
                    message = f"Login status unclear. Current URL: {current_url}"
                    logger.warning(message)
                    return False, message
                    
        except TimeoutException as e:
            message = f"Timeout during login: {e}"
            logger.error(message)
            return False, message
        except Exception as e:
            message = f"Login failed with error: {e}"
            logger.error(message)
            return False, message
    
    def verify_login_status(self) -> bool:
        """
        Verify if user is currently logged in
        
        Returns:
            True if logged in, False otherwise
        """
        if not self.driver:
            return False
        
        try:
            current_url = self.driver.current_url
            success_patterns = ['feed', 'mynetwork', 'jobs', 'messaging', '/in/']
            return any(pattern in current_url.lower() for pattern in success_patterns)
        except:
            return False
    
    def close_driver(self):
        """Close the Chrome driver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Driver closed successfully")
            except Exception as e:
                logger.warning(f"Error closing driver: {e}")
            finally:
                self.driver = None
                self.wait = None
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures driver cleanup"""
        self.close_driver()


def quick_login_verification() -> bool:
    """
    Quick verification function to test login functionality
    
    Returns:
        True if login verification passed, False otherwise
    """
    logger.info("🚀 Starting LinkedIn login verification")
    
    try:
        with LinkedInSeleniumScraper() as scraper:
            # Initialize driver
            if not scraper.initialize_driver():
                logger.error("❌ Failed to initialize driver")
                return False
            
            # Attempt login
            success, message = scraper.login()
            
            if success:
                logger.info("✅ Login verification PASSED")
                logger.info(f"Current URL: {scraper.driver.current_url}")
                
                # Additional verification
                if scraper.verify_login_status():
                    logger.info("✅ Login status verified")
                    return True
                else:
                    logger.warning("⚠️ Login may not be complete")
                    return False
            else:
                logger.error(f"❌ Login verification FAILED: {message}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Login verification failed with exception: {e}")
        return False


if __name__ == "__main__":
    """
    Run quick login verification when script is executed directly
    """
    print("LinkedIn Selenium Scraper - Quick Login Verification")
    print("="*50)
    
    # Check if config exists
    if not os.path.exists("config.json"):
        print("❌ config.json not found!")
        print("Please create config.json with your LinkedIn credentials")
        print("Example:")
        print(json.dumps({
            "linkedin_credentials": {
                "email": "your-email@example.com",
                "password": "your-password-here"
            }
        }, indent=2))
        exit(1)
    
    # Run verification
    success = quick_login_verification()
    
    if success:
        print("\n✅ SUCCESS: Login verification passed!")
        print("You can now proceed with scraping operations.")
    else:
        print("\n❌ FAILED: Login verification failed!")
        print("Please check:")
        print("1. Your credentials in config.json")
        print("2. Network connection")
        print("3. LinkedIn account status")
        print("4. Check scraper.log for detailed error information")
        
        # If running in headless mode and failed, suggest headed mode
        with open("config.json", 'r') as f:
            config = json.load(f)
        if config.get('scraping_settings', {}).get('headless', False):
            print("5. Try setting 'headless': false in config.json for troubleshooting")
