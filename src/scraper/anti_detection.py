#!/usr/bin/env python3
"""
Advanced Anti-Detection System for LinkedIn Scraper

This module provides sophisticated browser fingerprinting avoidance,
proxy rotation, behavioral mimicking, and detection evasion techniques.
"""

import random
import time
import json
import string
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class BrowserProfile:
    """Browser fingerprinting profile"""
    user_agent: str
    viewport: Dict[str, int]
    language: str
    timezone: str
    platform: str
    screen_resolution: Dict[str, int]
    webgl_vendor: str
    webgl_renderer: str
    device_memory: int
    hardware_concurrency: int


@dataclass
class ProxyConfig:
    """Proxy configuration"""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"


class AdvancedAntiDetection:
    """Advanced anti-detection system with comprehensive evasion techniques"""
    
    def __init__(self):
        """Initialize anti-detection system"""
        self.current_profile = None
        self.session_start = datetime.now()
        self.action_count = 0
        self.last_action_time = None
        self.behavior_patterns = []
        
        # Load realistic browser profiles
        self.browser_profiles = self._generate_browser_profiles()
        
        # Human behavior timing patterns
        self.timing_patterns = {
            "page_load_wait": (2000, 6000),  # ms
            "between_actions": (800, 3000),   # ms
            "scroll_pause": (300, 1500),      # ms
            "typing_speed": (50, 200),        # ms per character
            "click_delay": (100, 500),        # ms
            "mouse_move_delay": (200, 800)    # ms
        }
        
    def _generate_browser_profiles(self) -> List[BrowserProfile]:
        """Generate realistic browser fingerprinting profiles"""
        profiles = []
        
        # Common user agents with realistic combinations
        user_agents = [
            # Chrome on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            
            # Chrome on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            
            # Firefox
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            
            # Safari
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        ]
        
        # Common screen resolutions
        resolutions = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1440, "height": 900},
            {"width": 1536, "height": 864},
            {"width": 2560, "height": 1440}
        ]
        
        # Common viewport sizes (slightly smaller than screen)
        viewports = [
            {"width": 1280, "height": 720},
            {"width": 1366, "height": 768},
            {"width": 1440, "height": 900},
            {"width": 1536, "height": 864},
            {"width": 1200, "height": 800}
        ]
        
        timezones = [
            "America/New_York", "America/Los_Angeles", "America/Chicago", "America/Denver",
            "Europe/London", "Europe/Berlin", "Europe/Paris", "Asia/Tokyo",
            "Asia/Kolkata", "Australia/Sydney", "America/Toronto"
        ]
        
        languages = ["en-US", "en-GB", "en-CA", "en-AU", "es-US", "fr-FR", "de-DE"]
        
        webgl_vendors = ["Google Inc.", "Intel Inc.", "NVIDIA Corporation", "ATI Technologies Inc."]
        webgl_renderers = [
            "ANGLE (Intel, Intel(R) Iris(TM) Plus Graphics 640 Direct3D11 vs_5_0 ps_5_0, D3D11-27.20.100.8681)",
            "ANGLE (NVIDIA, GeForce GTX 1060 6GB Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "Intel(R) UHD Graphics 620",
            "AMD Radeon Pro 580X OpenGL Engine"
        ]
        
        # Generate profiles
        for ua in user_agents:
            for _ in range(2):  # 2 variations per user agent
                profile = BrowserProfile(
                    user_agent=ua,
                    viewport=random.choice(viewports),
                    language=random.choice(languages),
                    timezone=random.choice(timezones),
                    platform="MacIntel" if "Mac" in ua else "Win32",
                    screen_resolution=random.choice(resolutions),
                    webgl_vendor=random.choice(webgl_vendors),
                    webgl_renderer=random.choice(webgl_renderers),
                    device_memory=random.choice([4, 8, 16]),
                    hardware_concurrency=random.choice([4, 8, 12, 16])
                )
                profiles.append(profile)
        
        return profiles
    
    def get_random_profile(self) -> BrowserProfile:
        """Get a random browser profile for fingerprinting evasion"""
        return random.choice(self.browser_profiles)
    
    def generate_session_id(self) -> str:
        """Generate a unique session ID for tracking"""
        timestamp = str(int(time.time() * 1000))
        random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"session_{timestamp}_{random_part}"
    
    def get_human_timing(self, action_type: str) -> float:
        """Get human-like timing for various actions"""
        if action_type in self.timing_patterns:
            min_time, max_time = self.timing_patterns[action_type]
            # Add some randomness with normal distribution
            base_time = random.randint(min_time, max_time)
            variation = base_time * 0.1 * random.gauss(0, 1)  # 10% variation
            return max(min_time * 0.5, base_time + variation) / 1000  # Convert to seconds
        return random.uniform(0.5, 2.0)
    
    def simulate_human_mouse_movement(self, page) -> None:
        """Simulate realistic human mouse movements"""
        try:
            # Get viewport dimensions
            viewport = page.viewport_size
            width, height = viewport["width"], viewport["height"]
            
            # Simulate random mouse movements
            for _ in range(random.randint(2, 5)):
                x = random.randint(50, width - 50)
                y = random.randint(50, height - 50)
                
                # Move mouse with realistic speed
                page.mouse.move(x, y)
                time.sleep(self.get_human_timing("mouse_move_delay"))
                
        except Exception as e:
            logger.debug(f"Mouse movement simulation failed: {e}")
    
    def simulate_reading_behavior(self, page) -> None:
        """Simulate human reading behavior with realistic scrolling"""
        try:
            # Get page height
            scroll_height = page.evaluate("document.documentElement.scrollHeight")
            viewport_height = page.viewport_size["height"]
            
            if scroll_height <= viewport_height:
                return  # No need to scroll
            
            # Simulate reading with pauses and scroll patterns
            current_position = 0
            total_scrolls = random.randint(3, 8)
            
            for i in range(total_scrolls):
                # Variable scroll distances (sometimes small, sometimes larger jumps)
                if random.random() < 0.3:  # 30% chance of larger jump
                    scroll_distance = random.randint(400, 800)
                else:  # 70% chance of smaller, reading-like scroll
                    scroll_distance = random.randint(100, 300)
                
                current_position += scroll_distance
                
                # Don't scroll beyond page
                if current_position > scroll_height - viewport_height:
                    current_position = scroll_height - viewport_height
                
                # Smooth scroll
                page.evaluate(f"window.scrollTo({{top: {current_position}, behavior: 'smooth'}})")
                
                # Pause to simulate reading
                reading_time = random.uniform(0.8, 3.2)
                time.sleep(reading_time)
                
                # Occasional reverse scroll (user scrolled back up)
                if random.random() < 0.15:  # 15% chance
                    back_scroll = random.randint(50, 200)
                    current_position = max(0, current_position - back_scroll)
                    page.evaluate(f"window.scrollTo({{top: {current_position}, behavior: 'smooth'}})")
                    time.sleep(self.get_human_timing("scroll_pause"))
                
                if current_position >= scroll_height - viewport_height:
                    break
                    
        except Exception as e:
            logger.debug(f"Reading behavior simulation failed: {e}")
    
    def simulate_typing_behavior(self, page, selector: str, text: str) -> None:
        """Simulate human-like typing with realistic timing"""
        try:
            element = page.query_selector(selector)
            if not element:
                return
            
            # Clear field first
            element.click()
            page.keyboard.press("Control+a" if "Win" in self.current_profile.platform else "Meta+a")
            page.keyboard.press("Delete")
            
            # Type character by character with human-like timing
            for i, char in enumerate(text):
                # Occasional typos and corrections (very rarely)
                if random.random() < 0.02 and i > 0:  # 2% chance
                    # Type wrong character
                    wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                    page.keyboard.type(wrong_char)
                    time.sleep(self.get_human_timing("typing_speed"))
                    # Correct it
                    page.keyboard.press("Backspace")
                    time.sleep(self.get_human_timing("typing_speed"))
                
                # Type the correct character
                page.keyboard.type(char)
                
                # Variable typing speed
                typing_delay = self.get_human_timing("typing_speed")
                
                # Slower for capital letters and special characters
                if char.isupper() or char in "!@#$%^&*()_+{}[]|\\:;\"'<>?,./":
                    typing_delay *= 1.5
                
                # Occasional longer pauses (thinking/looking at keyboard)
                if random.random() < 0.05:  # 5% chance
                    typing_delay *= 3
                
                time.sleep(typing_delay)
                
        except Exception as e:
            logger.debug(f"Typing behavior simulation failed: {e}")
    
    def add_stealth_scripts(self, page) -> None:
        """Add stealth scripts to avoid detection"""
        try:
            # Override navigator.webdriver
            stealth_script = """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Override chrome object
            window.chrome = {
                runtime: {},
                loadTimes: function() {
                    return {
                        requestTime: performance.now() / 1000,
                        startLoadTime: performance.now() / 1000,
                        commitLoadTime: performance.now() / 1000,
                        finishDocumentLoadTime: performance.now() / 1000,
                        finishLoadTime: performance.now() / 1000,
                        firstPaintTime: performance.now() / 1000,
                        firstPaintAfterLoadTime: 0,
                        navigationType: 'Other'
                    };
                },
                csi: function() {
                    return {
                        onloadT: Date.now(),
                        startE: Date.now(),
                        tran: 15
                    };
                }
            };
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5].map(() => 'Plugin'),
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            """
            
            page.add_init_script(stealth_script)
            
        except Exception as e:
            logger.debug(f"Failed to add stealth scripts: {e}")
    
    def configure_browser_context(self, context_options: Dict[str, Any]) -> Dict[str, Any]:
        """Configure browser context with anti-detection settings"""
        profile = self.get_random_profile()
        self.current_profile = profile
        
        # Base configuration
        enhanced_options = {
            **context_options,
            "user_agent": profile.user_agent,
            "viewport": profile.viewport,
            "locale": profile.language,
            "timezone_id": profile.timezone,
            "device_scale_factor": random.choice([1, 1.25, 1.5, 2]),
            "is_mobile": False,
            "has_touch": False,
            
            # Extra headers for authenticity
            "extra_http_headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": f"{profile.language},en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0"
            },
            
            # Permission overrides
            "permissions": ["geolocation", "notifications"],
            "color_scheme": "light",
            "reduced_motion": "no-preference",
            "forced_colors": "none"
        }
        
        logger.info(f"🎭 Using browser profile: {profile.user_agent[:50]}...")
        logger.debug(f"   Viewport: {profile.viewport}")
        logger.debug(f"   Locale: {profile.language}")
        logger.debug(f"   Timezone: {profile.timezone}")
        
        return enhanced_options
    
    def apply_behavioral_patterns(self, page) -> None:
        """Apply human-like behavioral patterns during scraping"""
        try:
            self.action_count += 1
            
            # Random actions to appear human
            action_probability = {
                "mouse_movement": 0.3,    # 30% chance
                "brief_pause": 0.2,       # 20% chance
                "mini_scroll": 0.15,      # 15% chance
                "focus_change": 0.1       # 10% chance
            }
            
            for action, probability in action_probability.items():
                if random.random() < probability:
                    if action == "mouse_movement":
                        self.simulate_human_mouse_movement(page)
                    elif action == "brief_pause":
                        time.sleep(random.uniform(0.5, 2.0))
                    elif action == "mini_scroll":
                        # Small random scroll
                        scroll_delta = random.randint(-200, 200)
                        page.mouse.wheel(0, scroll_delta)
                        time.sleep(0.3)
                    elif action == "focus_change":
                        # Brief focus on page title or URL bar
                        page.keyboard.press("Tab")
                        time.sleep(0.2)
                        page.keyboard.press("Escape")
            
            # Record timing for patterns
            current_time = datetime.now()
            if self.last_action_time:
                interval = (current_time - self.last_action_time).total_seconds()
                self.behavior_patterns.append(interval)
            
            self.last_action_time = current_time
            
        except Exception as e:
            logger.debug(f"Behavioral pattern application failed: {e}")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get current session statistics for analysis"""
        session_duration = (datetime.now() - self.session_start).total_seconds()
        
        return {
            "session_duration_seconds": session_duration,
            "total_actions": self.action_count,
            "actions_per_minute": (self.action_count / max(session_duration / 60, 1)),
            "average_action_interval": sum(self.behavior_patterns) / len(self.behavior_patterns) if self.behavior_patterns else 0,
            "current_profile": {
                "user_agent": self.current_profile.user_agent if self.current_profile else "Unknown",
                "viewport": self.current_profile.viewport if self.current_profile else "Unknown",
                "timezone": self.current_profile.timezone if self.current_profile else "Unknown"
            }
        }
    
    def should_rotate_profile(self) -> bool:
        """Determine if browser profile should be rotated"""
        session_duration = (datetime.now() - self.session_start).total_seconds()
        
        # Rotate profile after:
        # - 30 minutes of activity
        # - 100 actions
        # - Random chance for unpredictability
        
        return (
            session_duration > 1800 or  # 30 minutes
            self.action_count > 100 or
            random.random() < 0.05      # 5% random chance
        )
    
    def wait_for_human_timing(self, action_type: str = "between_actions") -> None:
        """Wait with human-like timing between actions"""
        delay = self.get_human_timing(action_type)
        
        # Add some behavioral patterns
        self.behavior_patterns.append(delay)
        
        # Keep only recent patterns (last 50)
        if len(self.behavior_patterns) > 50:
            self.behavior_patterns = self.behavior_patterns[-50:]
        
        time.sleep(delay)
    
    def get_proxy_rotation_config(self) -> Optional[ProxyConfig]:
        """Get next proxy configuration for rotation (placeholder)"""
        # This would integrate with proxy service providers
        # For now, return None to indicate no proxy rotation
        return None
    
    def detect_blocking_signals(self, page) -> Dict[str, bool]:
        """Detect if the page contains blocking or detection signals"""
        signals = {
            "captcha_detected": False,
            "rate_limited": False,
            "access_denied": False,
            "suspicious_redirect": False,
            "error_page": False
        }
        
        try:
            page_url = page.url.lower()
            page_content = page.content().lower()
            
            # Check for CAPTCHA
            captcha_indicators = [
                "captcha", "verify you are human", "security check",
                "prove you are not a robot", "i'm not a robot"
            ]
            signals["captcha_detected"] = any(indicator in page_content for indicator in captcha_indicators)
            
            # Check for rate limiting
            rate_limit_indicators = [
                "rate limit", "too many requests", "try again later",
                "request blocked", "throttle"
            ]
            signals["rate_limited"] = any(indicator in page_content for indicator in rate_limit_indicators)
            
            # Check for access denied
            access_denied_indicators = [
                "access denied", "forbidden", "not authorized",
                "blocked", "restricted access"
            ]
            signals["access_denied"] = any(indicator in page_content for indicator in access_denied_indicators)
            
            # Check for suspicious redirects
            suspicious_domains = ["challenge", "verify", "security", "blocked"]
            signals["suspicious_redirect"] = any(domain in page_url for domain in suspicious_domains)
            
            # Check for error pages
            error_indicators = ["404", "500", "error", "page not found", "server error"]
            signals["error_page"] = any(indicator in page_content for indicator in error_indicators)
            
        except Exception as e:
            logger.debug(f"Failed to detect blocking signals: {e}")
        
        return signals


# Global anti-detection instance
global_anti_detection = AdvancedAntiDetection()