#!/usr/bin/env python3
"""
Proxy Management System for LinkedIn Scraper

This module handles proxy rotation, health monitoring, and automatic failover
to maintain scraping reliability and anonymity.
"""

import asyncio
import aiohttp
import random
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import requests
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


@dataclass
class ProxyInfo:
    """Information about a proxy server"""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"
    country: Optional[str] = None
    city: Optional[str] = None
    is_residential: bool = False
    
    # Health monitoring
    success_count: int = field(default=0)
    failure_count: int = field(default=0)
    last_used: Optional[datetime] = field(default=None)
    last_success: Optional[datetime] = field(default=None)
    last_failure: Optional[datetime] = field(default=None)
    response_times: List[float] = field(default_factory=list)
    is_healthy: bool = field(default=True)
    consecutive_failures: int = field(default=0)
    
    def __post_init__(self):
        """Initialize calculated properties"""
        if not self.response_times:
            self.response_times = []
    
    @property
    def url(self) -> str:
        """Get proxy URL string"""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.protocol}://{auth}{self.host}:{self.port}"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        total = self.success_count + self.failure_count
        return (self.success_count / total * 100) if total > 0 else 0.0
    
    @property
    def average_response_time(self) -> float:
        """Calculate average response time in seconds"""
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0
    
    def record_success(self, response_time: float = 0.0):
        """Record successful proxy usage"""
        self.success_count += 1
        self.last_success = datetime.now()
        self.last_used = datetime.now()
        self.consecutive_failures = 0
        
        if response_time > 0:
            self.response_times.append(response_time)
            # Keep only last 50 response times
            if len(self.response_times) > 50:
                self.response_times = self.response_times[-50:]
        
        # Mark as healthy if it was unhealthy
        if not self.is_healthy:
            self.is_healthy = True
            logger.info(f"✅ Proxy {self.host}:{self.port} marked as healthy again")
    
    def record_failure(self, error: str = ""):
        """Record failed proxy usage"""
        self.failure_count += 1
        self.last_failure = datetime.now()
        self.last_used = datetime.now()
        self.consecutive_failures += 1
        
        # Mark as unhealthy after 3 consecutive failures
        if self.consecutive_failures >= 3 and self.is_healthy:
            self.is_healthy = False
            logger.warning(f"❌ Proxy {self.host}:{self.port} marked as unhealthy after {self.consecutive_failures} failures")
    
    def should_rotate(self, max_usage_time: int = 1800) -> bool:
        """Check if proxy should be rotated based on usage patterns"""
        if not self.last_used:
            return False
        
        usage_duration = (datetime.now() - self.last_used).total_seconds()
        return (
            usage_duration > max_usage_time or  # Used too long
            self.consecutive_failures >= 2 or   # Recent failures
            not self.is_healthy                 # Marked as unhealthy
        )


class ProxyManager:
    """Advanced proxy management with rotation and health monitoring"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize proxy manager"""
        self.proxies: List[ProxyInfo] = []
        self.current_proxy: Optional[ProxyInfo] = None
        self.rotation_enabled = True
        self.health_check_interval = 300  # 5 minutes
        self.last_health_check = datetime.now()
        self.config_path = config_path
        
        # Load proxies from configuration
        self._load_proxy_config()
        
        # Test endpoints for health checks
        self.test_endpoints = [
            "http://httpbin.org/ip",
            "http://icanhazip.com",
            "https://api.ipify.org?format=json"
        ]
    
    def _load_proxy_config(self) -> None:
        """Load proxy configuration from file or environment"""
        if self.config_path:
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self._parse_proxy_config(config)
            except FileNotFoundError:
                logger.warning(f"Proxy config file not found: {self.config_path}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid proxy config JSON: {e}")
        
        # Add sample free proxies for testing (not recommended for production)
        if not self.proxies:
            self._add_sample_proxies()
    
    def _parse_proxy_config(self, config: Dict[str, Any]) -> None:
        """Parse proxy configuration from dict"""
        proxy_list = config.get("proxies", [])
        
        for proxy_config in proxy_list:
            proxy = ProxyInfo(
                host=proxy_config["host"],
                port=proxy_config["port"],
                username=proxy_config.get("username"),
                password=proxy_config.get("password"),
                protocol=proxy_config.get("protocol", "http"),
                country=proxy_config.get("country"),
                city=proxy_config.get("city"),
                is_residential=proxy_config.get("is_residential", False)
            )
            self.proxies.append(proxy)
        
        logger.info(f"📋 Loaded {len(self.proxies)} proxies from configuration")
    
    def _add_sample_proxies(self) -> None:
        """Add sample free proxies for testing (not recommended for production)"""
        logger.warning("⚠️  Using sample free proxies - not recommended for production use")
        
        # These are sample free proxies that may not work reliably
        sample_proxies = [
            {"host": "8.210.83.33", "port": 80},
            {"host": "47.74.152.29", "port": 8888},
            {"host": "43.134.68.153", "port": 3128},
            {"host": "103.149.162.194", "port": 80},
            {"host": "185.32.6.129", "port": 8090}
        ]
        
        for proxy_data in sample_proxies:
            proxy = ProxyInfo(
                host=proxy_data["host"],
                port=proxy_data["port"],
                protocol="http"
            )
            self.proxies.append(proxy)
    
    def add_proxy(self, host: str, port: int, username: str = None, 
                  password: str = None, protocol: str = "http", **kwargs) -> None:
        """Add a new proxy to the pool"""
        proxy = ProxyInfo(
            host=host,
            port=port,
            username=username,
            password=password,
            protocol=protocol,
            **kwargs
        )
        self.proxies.append(proxy)
        logger.info(f"➕ Added proxy: {host}:{port}")
    
    def get_healthy_proxies(self) -> List[ProxyInfo]:
        """Get list of healthy proxies"""
        return [proxy for proxy in self.proxies if proxy.is_healthy]
    
    def get_best_proxy(self) -> Optional[ProxyInfo]:
        """Get the best available proxy based on performance metrics"""
        healthy_proxies = self.get_healthy_proxies()
        
        if not healthy_proxies:
            logger.warning("⚠️  No healthy proxies available")
            return None
        
        # Sort by success rate, then by average response time
        healthy_proxies.sort(
            key=lambda p: (-p.success_rate, p.average_response_time)
        )
        
        # Add some randomization to avoid always using the same "best" proxy
        top_proxies = healthy_proxies[:min(3, len(healthy_proxies))]
        return random.choice(top_proxies)
    
    def rotate_proxy(self, force: bool = False) -> Optional[ProxyInfo]:
        """Rotate to a different proxy"""
        if not force and self.current_proxy and not self.current_proxy.should_rotate():
            return self.current_proxy
        
        # Get a different proxy (avoid current one unless it's the only option)
        healthy_proxies = self.get_healthy_proxies()
        
        if not healthy_proxies:
            logger.error("❌ No healthy proxies available for rotation")
            return None
        
        # Try to get a different proxy than current
        available_proxies = [p for p in healthy_proxies if p != self.current_proxy]
        if not available_proxies:
            available_proxies = healthy_proxies
        
        new_proxy = self.get_best_proxy()
        if new_proxy and new_proxy != self.current_proxy:
            old_proxy_info = f"{self.current_proxy.host}:{self.current_proxy.port}" if self.current_proxy else "None"
            logger.info(f"🔄 Rotating proxy: {old_proxy_info} -> {new_proxy.host}:{new_proxy.port}")
            self.current_proxy = new_proxy
        
        return self.current_proxy
    
    def get_current_proxy(self) -> Optional[ProxyInfo]:
        """Get current proxy or select one if none is active"""
        if not self.current_proxy or not self.current_proxy.is_healthy:
            self.current_proxy = self.rotate_proxy(force=True)
        
        return self.current_proxy
    
    async def test_proxy_health(self, proxy: ProxyInfo, timeout: int = 10) -> bool:
        """Test proxy health asynchronously"""
        test_url = random.choice(self.test_endpoints)
        start_time = time.time()
        
        try:
            proxy_url = proxy.url
            connector = aiohttp.TCPConnector()
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout_config
            ) as session:
                async with session.get(
                    test_url,
                    proxy=proxy_url
                ) as response:
                    if response.status == 200:
                        response_time = time.time() - start_time
                        proxy.record_success(response_time)
                        logger.debug(f"✅ Proxy {proxy.host}:{proxy.port} health check passed ({response_time:.2f}s)")
                        return True
                    else:
                        proxy.record_failure(f"HTTP {response.status}")
                        return False
        
        except Exception as e:
            proxy.record_failure(str(e))
            logger.debug(f"❌ Proxy {proxy.host}:{proxy.port} health check failed: {e}")
            return False
    
    async def run_health_checks(self) -> None:
        """Run health checks on all proxies"""
        logger.info("🔍 Running proxy health checks...")
        
        tasks = []
        for proxy in self.proxies:
            task = asyncio.create_task(self.test_proxy_health(proxy))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        healthy_count = sum(1 for proxy in self.proxies if proxy.is_healthy)
        logger.info(f"📊 Health check complete: {healthy_count}/{len(self.proxies)} proxies healthy")
        
        self.last_health_check = datetime.now()
    
    def should_run_health_check(self) -> bool:
        """Check if it's time to run health checks"""
        time_since_check = (datetime.now() - self.last_health_check).total_seconds()
        return time_since_check > self.health_check_interval
    
    def get_proxy_stats(self) -> Dict[str, Any]:
        """Get comprehensive proxy statistics"""
        healthy_proxies = self.get_healthy_proxies()
        total_success = sum(p.success_count for p in self.proxies)
        total_failure = sum(p.failure_count for p in self.proxies)
        total_requests = total_success + total_failure
        
        stats = {
            "total_proxies": len(self.proxies),
            "healthy_proxies": len(healthy_proxies),
            "unhealthy_proxies": len(self.proxies) - len(healthy_proxies),
            "total_requests": total_requests,
            "total_success": total_success,
            "total_failures": total_failure,
            "overall_success_rate": (total_success / total_requests * 100) if total_requests > 0 else 0,
            "current_proxy": {
                "host": self.current_proxy.host if self.current_proxy else None,
                "port": self.current_proxy.port if self.current_proxy else None,
                "success_rate": self.current_proxy.success_rate if self.current_proxy else 0
            },
            "proxy_details": []
        }
        
        for proxy in self.proxies:
            proxy_stats = {
                "host": proxy.host,
                "port": proxy.port,
                "is_healthy": proxy.is_healthy,
                "success_count": proxy.success_count,
                "failure_count": proxy.failure_count,
                "success_rate": proxy.success_rate,
                "average_response_time": proxy.average_response_time,
                "consecutive_failures": proxy.consecutive_failures,
                "last_used": proxy.last_used.isoformat() if proxy.last_used else None,
                "country": proxy.country,
                "is_residential": proxy.is_residential
            }
            stats["proxy_details"].append(proxy_stats)
        
        return stats
    
    def get_playwright_proxy_config(self) -> Optional[Dict[str, Any]]:
        """Get proxy configuration for Playwright"""
        proxy = self.get_current_proxy()
        if not proxy:
            return None
        
        config = {
            "server": f"{proxy.protocol}://{proxy.host}:{proxy.port}"
        }
        
        if proxy.username and proxy.password:
            config["username"] = proxy.username
            config["password"] = proxy.password
        
        return config
    
    def record_proxy_usage(self, success: bool, error_msg: str = "", response_time: float = 0.0):
        """Record the result of using current proxy"""
        if not self.current_proxy:
            return
        
        if success:
            self.current_proxy.record_success(response_time)
        else:
            self.current_proxy.record_failure(error_msg)
            
            # Auto-rotate if proxy fails
            if self.current_proxy.consecutive_failures >= 2:
                logger.warning(f"🔄 Auto-rotating due to failures: {self.current_proxy.host}:{self.current_proxy.port}")
                self.rotate_proxy(force=True)
    
    def cleanup_old_data(self, max_age_days: int = 7):
        """Clean up old proxy performance data"""
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        for proxy in self.proxies:
            # Reset stats for very old failures
            if proxy.last_failure and proxy.last_failure < cutoff_date:
                proxy.consecutive_failures = 0
                if not proxy.is_healthy:
                    proxy.is_healthy = True
                    logger.info(f"🔄 Reset unhealthy status for proxy {proxy.host}:{proxy.port}")
    
    def disable_proxy_rotation(self):
        """Disable automatic proxy rotation"""
        self.rotation_enabled = False
        logger.info("🔒 Proxy rotation disabled")
    
    def enable_proxy_rotation(self):
        """Enable automatic proxy rotation"""
        self.rotation_enabled = True
        logger.info("🔓 Proxy rotation enabled")


# Global proxy manager instance
global_proxy_manager = ProxyManager()


# Convenience functions
def get_proxy_manager() -> ProxyManager:
    """Get global proxy manager instance"""
    return global_proxy_manager


def get_current_proxy_config() -> Optional[Dict[str, Any]]:
    """Get current proxy configuration for Playwright"""
    return global_proxy_manager.get_playwright_proxy_config()


async def run_proxy_health_checks():
    """Run health checks on all proxies"""
    await global_proxy_manager.run_health_checks()