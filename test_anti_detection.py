#!/usr/bin/env python3
"""
Anti-Detection Features Test Script

This script demonstrates and tests the advanced anti-detection features
of the LinkedIn Job Scraper without actually scraping LinkedIn.
"""

import asyncio
import time
import json
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

# Import our anti-detection modules
from src.scraper.anti_detection import AdvancedAntiDetection, BrowserProfile
from src.scraper.proxy_manager import ProxyManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_browser_fingerprinting():
    """Test browser fingerprinting avoidance features"""
    logger.info("🎭 Testing Browser Fingerprinting Avoidance...")
    
    anti_detection = AdvancedAntiDetection()
    
    # Test profile generation
    profile = anti_detection.get_random_profile()
    logger.info(f"   Generated Profile:")
    logger.info(f"   User Agent: {profile.user_agent[:60]}...")
    logger.info(f"   Viewport: {profile.viewport}")
    logger.info(f"   Language: {profile.language}")
    logger.info(f"   Timezone: {profile.timezone}")
    logger.info(f"   Platform: {profile.platform}")
    
    # Test session ID generation
    session_id = anti_detection.generate_session_id()
    logger.info(f"   Session ID: {session_id}")
    
    # Test human timing
    timing_samples = []
    for action in ["page_load_wait", "between_actions", "scroll_pause"]:
        delay = anti_detection.get_human_timing(action)
        timing_samples.append(f"{action}: {delay:.2f}s")
    logger.info(f"   Human Timings: {', '.join(timing_samples)}")
    
    logger.info("✅ Browser fingerprinting test completed\n")


def test_proxy_management():
    """Test proxy management and health monitoring"""
    logger.info("🌐 Testing Proxy Management...")
    
    proxy_manager = ProxyManager()
    
    # Check initial state
    stats = proxy_manager.get_proxy_stats()
    logger.info(f"   Total Proxies: {stats['total_proxies']}")
    logger.info(f"   Healthy Proxies: {stats['healthy_proxies']}")
    
    # Test proxy selection
    best_proxy = proxy_manager.get_best_proxy()
    if best_proxy:
        logger.info(f"   Best Proxy: {best_proxy.host}:{best_proxy.port}")
        logger.info(f"   Success Rate: {best_proxy.success_rate:.1f}%")
    else:
        logger.warning("   No healthy proxies available")
    
    # Test Playwright configuration
    playwright_config = proxy_manager.get_playwright_proxy_config()
    if playwright_config:
        logger.info(f"   Playwright Config: {playwright_config}")
    else:
        logger.info("   No proxy configured for Playwright")
    
    logger.info("✅ Proxy management test completed\n")


async def test_proxy_health_checks():
    """Test asynchronous proxy health monitoring"""
    logger.info("🔍 Testing Proxy Health Checks...")
    
    proxy_manager = ProxyManager()
    
    if proxy_manager.proxies:
        # Run health checks on all proxies
        await proxy_manager.run_health_checks()
        
        # Show results
        stats = proxy_manager.get_proxy_stats()
        logger.info(f"   Health Check Results:")
        logger.info(f"   - Total: {stats['total_proxies']}")
        logger.info(f"   - Healthy: {stats['healthy_proxies']}")
        logger.info(f"   - Unhealthy: {stats['unhealthy_proxies']}")
        logger.info(f"   - Overall Success Rate: {stats['overall_success_rate']:.1f}%")
    else:
        logger.info("   No proxies configured - skipping health checks")
    
    logger.info("✅ Proxy health check test completed\n")


def test_behavioral_simulation():
    """Test behavioral simulation features"""
    logger.info("🤖 Testing Behavioral Simulation...")
    
    anti_detection = AdvancedAntiDetection()
    
    # Test timing patterns
    logger.info("   Testing human timing patterns...")
    for i in range(3):
        delay = anti_detection.get_human_timing("between_actions")
        logger.info(f"   - Sample {i+1}: {delay:.2f}s")
    
    # Test session statistics
    stats = anti_detection.get_session_stats()
    logger.info(f"   Session Stats:")
    logger.info(f"   - Duration: {stats['session_duration_seconds']:.1f}s")
    logger.info(f"   - Actions: {stats['total_actions']}")
    logger.info(f"   - Actions/min: {stats['actions_per_minute']:.1f}")
    
    # Test profile rotation decision
    should_rotate = anti_detection.should_rotate_profile()
    logger.info(f"   Should rotate profile: {should_rotate}")
    
    logger.info("✅ Behavioral simulation test completed\n")


def test_browser_context_configuration():
    """Test browser context configuration with anti-detection"""
    logger.info("🌐 Testing Browser Context Configuration...")
    
    anti_detection = AdvancedAntiDetection()
    
    # Test context configuration
    base_options = {
        "headless": True,
        "viewport": {"width": 1280, "height": 720}
    }
    
    enhanced_options = anti_detection.configure_browser_context(base_options)
    
    logger.info("   Enhanced Context Options:")
    logger.info(f"   - User Agent: {enhanced_options.get('user_agent', 'Not set')[:60]}...")
    logger.info(f"   - Viewport: {enhanced_options.get('viewport', 'Not set')}")
    logger.info(f"   - Locale: {enhanced_options.get('locale', 'Not set')}")
    logger.info(f"   - Timezone: {enhanced_options.get('timezone_id', 'Not set')}")
    
    # Show headers
    headers = enhanced_options.get('extra_http_headers', {})
    logger.info(f"   - Headers: {len(headers)} headers configured")
    for key, value in list(headers.items())[:3]:
        logger.info(f"     {key}: {value}")
    
    logger.info("✅ Browser context configuration test completed\n")


def test_with_real_browser():
    """Test anti-detection features with a real browser instance"""
    logger.info("🚀 Testing with Real Browser (Test Site)...")
    
    anti_detection = AdvancedAntiDetection()
    proxy_manager = ProxyManager()
    
    # Configure browser context
    base_options = {
        "headless": True,
        "args": ["--disable-blink-features=AutomationControlled"]
    }
    
    enhanced_options = anti_detection.configure_browser_context(base_options)
    
    # Add proxy if available
    proxy_config = proxy_manager.get_playwright_proxy_config()
    if proxy_config:
        enhanced_options["proxy"] = proxy_config
        logger.info(f"   Using proxy: {proxy_config['server']}")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(**{k: v for k, v in enhanced_options.items() 
                                         if k not in ['extra_http_headers', 'permissions']})
            
            context = browser.new_context(
                user_agent=enhanced_options.get('user_agent'),
                viewport=enhanced_options.get('viewport'),
                locale=enhanced_options.get('locale'),
                timezone_id=enhanced_options.get('timezone_id'),
                extra_http_headers=enhanced_options.get('extra_http_headers', {}),
            )
            
            page = context.new_page()
            
            # Add stealth scripts
            anti_detection.add_stealth_scripts(page)
            
            # Test with a detection testing site
            test_url = "https://bot.sannysoft.com/"  # Bot detection test site
            logger.info(f"   Navigating to test site: {test_url}")
            
            start_time = time.time()
            page.goto(test_url, timeout=30000)
            
            # Wait with human-like timing
            anti_detection.wait_for_human_timing("page_load_wait")
            
            # Apply behavioral patterns
            anti_detection.apply_behavioral_patterns(page)
            
            # Check for detection signals
            blocking_signals = anti_detection.detect_blocking_signals(page)
            
            response_time = time.time() - start_time
            
            logger.info("   Test Results:")
            logger.info(f"   - Page loaded in: {response_time:.2f}s")
            logger.info(f"   - Title: {page.title()}")
            logger.info(f"   - Blocking signals detected: {any(blocking_signals.values())}")
            
            if any(blocking_signals.values()):
                detected = [k for k, v in blocking_signals.items() if v]
                logger.warning(f"   - Detected blocks: {detected}")
            else:
                logger.info("   - No blocking signals detected ✅")
            
            # Record proxy usage if using proxy
            if proxy_config:
                proxy_manager.record_proxy_usage(True, response_time=response_time)
                logger.info("   - Proxy usage recorded")
            
        except Exception as e:
            logger.error(f"   Browser test failed: {e}")
            if proxy_config:
                proxy_manager.record_proxy_usage(False, str(e))
        
        finally:
            try:
                context.close()
                browser.close()
            except:
                pass
    
    logger.info("✅ Real browser test completed\n")


def create_sample_config():
    """Create a sample configuration file for testing"""
    config = {
        "anti_detection": {
            "enabled": True
        },
        "proxy_rotation": {
            "enabled": False,
            "config_path": "./proxies.json"
        },
        "behavioral_simulation": {
            "enabled": True
        },
        "debug": {
            "show_browser": False
        }
    }
    
    with open("test_config.json", "w") as f:
        json.dump(config, f, indent=2)
    
    logger.info("📝 Created test_config.json")


def show_statistics_summary():
    """Show comprehensive statistics from all components"""
    logger.info("📊 Final Statistics Summary")
    logger.info("=" * 50)
    
    # Anti-detection stats
    anti_detection = AdvancedAntiDetection()
    ad_stats = anti_detection.get_session_stats()
    
    logger.info("🎭 Anti-Detection Statistics:")
    logger.info(f"   Session Duration: {ad_stats['session_duration_seconds']:.1f}s")
    logger.info(f"   Total Actions: {ad_stats['total_actions']}")
    logger.info(f"   Average Interval: {ad_stats['average_action_interval']:.2f}s")
    
    # Proxy stats
    proxy_manager = ProxyManager()
    proxy_stats = proxy_manager.get_proxy_stats()
    
    logger.info("🌐 Proxy Management Statistics:")
    logger.info(f"   Total Proxies: {proxy_stats['total_proxies']}")
    logger.info(f"   Healthy Proxies: {proxy_stats['healthy_proxies']}")
    logger.info(f"   Success Rate: {proxy_stats['overall_success_rate']:.1f}%")
    
    if proxy_stats['proxy_details']:
        logger.info("   Top Performing Proxies:")
        sorted_proxies = sorted(proxy_stats['proxy_details'], 
                              key=lambda x: x['success_rate'], reverse=True)[:3]
        for i, proxy in enumerate(sorted_proxies, 1):
            logger.info(f"   {i}. {proxy['host']}:{proxy['port']} - "
                       f"{proxy['success_rate']:.1f}% success rate")
    
    logger.info("=" * 50)


async def main():
    """Run all anti-detection tests"""
    logger.info("🧪 Starting Anti-Detection Features Test Suite")
    logger.info("=" * 60)
    
    # Create sample config
    create_sample_config()
    
    # Test individual components
    test_browser_fingerprinting()
    test_proxy_management()
    test_behavioral_simulation()
    test_browser_context_configuration()
    
    # Test async features
    await test_proxy_health_checks()
    
    # Test with real browser (optional - comment out if you don't want to make external requests)
    test_with_real_browser()
    
    # Show final statistics
    show_statistics_summary()
    
    logger.info("🎉 All anti-detection tests completed successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()