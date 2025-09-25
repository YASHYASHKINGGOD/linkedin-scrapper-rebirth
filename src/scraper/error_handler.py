#!/usr/bin/env python3
"""
Advanced Error Handling and Retry Logic for LinkedIn Scraper

This module provides sophisticated error handling, retry mechanisms,
rate limiting detection, and recovery strategies.
"""

import time
import random
import logging
from typing import Dict, Any, Callable, Optional, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Classification of different error types for targeted handling"""
    NETWORK_ERROR = "network_error"
    RATE_LIMIT = "rate_limit"
    LOGIN_REQUIRED = "login_required" 
    CAPTCHA_CHALLENGE = "captcha_challenge"
    ELEMENT_NOT_FOUND = "element_not_found"
    TIMEOUT_ERROR = "timeout_error"
    BROWSER_CRASH = "browser_crash"
    LINKEDIN_BLOCKING = "linkedin_blocking"
    DATA_EXTRACTION_ERROR = "data_extraction_error"
    UNKNOWN_ERROR = "unknown_error"


class RetryStrategy(Enum):
    """Different retry strategies based on error type"""
    IMMEDIATE = "immediate"
    LINEAR_BACKOFF = "linear_backoff"
    EXPONENTIAL_BACKOFF = "exponential_backoff" 
    FIXED_DELAY = "fixed_delay"
    NO_RETRY = "no_retry"


@dataclass
class ErrorConfig:
    """Configuration for handling specific error types"""
    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    should_reset_session: bool = False
    should_change_user_agent: bool = False
    should_wait_longer: bool = False
    custom_handler: Optional[Callable] = None


@dataclass 
class RetryContext:
    """Context information for retry attempts"""
    attempt: int = 0
    total_attempts: int = 0
    last_error: Optional[Exception] = None
    error_type: Optional[ErrorType] = None
    start_time: datetime = field(default_factory=datetime.now)
    delays: List[float] = field(default_factory=list)
    error_messages: List[str] = field(default_factory=list)


class AdvancedErrorHandler:
    """Advanced error handling with smart retry logic"""
    
    def __init__(self):
        """Initialize error handler with default configurations"""
        self.error_configs = {
            ErrorType.NETWORK_ERROR: ErrorConfig(
                max_retries=5,
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                base_delay=2.0,
                jitter=True
            ),
            ErrorType.RATE_LIMIT: ErrorConfig(
                max_retries=3,
                strategy=RetryStrategy.FIXED_DELAY,
                base_delay=30.0,  # Wait 30 seconds for rate limits
                should_wait_longer=True
            ),
            ErrorType.LOGIN_REQUIRED: ErrorConfig(
                max_retries=2,
                strategy=RetryStrategy.LINEAR_BACKOFF,
                base_delay=5.0,
                should_reset_session=True
            ),
            ErrorType.CAPTCHA_CHALLENGE: ErrorConfig(
                max_retries=1,
                strategy=RetryStrategy.FIXED_DELAY,
                base_delay=60.0,  # Wait 1 minute for CAPTCHA
                should_reset_session=True,
                should_change_user_agent=True
            ),
            ErrorType.ELEMENT_NOT_FOUND: ErrorConfig(
                max_retries=3,
                strategy=RetryStrategy.LINEAR_BACKOFF,
                base_delay=1.0
            ),
            ErrorType.TIMEOUT_ERROR: ErrorConfig(
                max_retries=4,
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                base_delay=3.0
            ),
            ErrorType.BROWSER_CRASH: ErrorConfig(
                max_retries=2,
                strategy=RetryStrategy.FIXED_DELAY,
                base_delay=10.0,
                should_reset_session=True
            ),
            ErrorType.LINKEDIN_BLOCKING: ErrorConfig(
                max_retries=1,
                strategy=RetryStrategy.FIXED_DELAY,
                base_delay=300.0,  # Wait 5 minutes
                should_reset_session=True,
                should_change_user_agent=True,
                should_wait_longer=True
            ),
            ErrorType.DATA_EXTRACTION_ERROR: ErrorConfig(
                max_retries=2,
                strategy=RetryStrategy.LINEAR_BACKOFF,
                base_delay=2.0
            ),
            ErrorType.UNKNOWN_ERROR: ErrorConfig(
                max_retries=2,
                strategy=RetryStrategy.LINEAR_BACKOFF,
                base_delay=5.0
            )
        }
        
        # Statistics tracking
        self.error_stats = {error_type: 0 for error_type in ErrorType}
        self.success_after_retry = 0
        self.total_operations = 0
    
    def classify_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorType:
        """Classify an error to determine the appropriate handling strategy"""
        error_msg = str(error).lower()
        context = context or {}
        
        # Network-related errors
        if any(term in error_msg for term in ['connection', 'network', 'dns', 'resolve', 'unreachable']):
            return ErrorType.NETWORK_ERROR
        
        # Rate limiting indicators
        if any(term in error_msg for term in ['rate limit', 'too many requests', '429', 'throttle']):
            return ErrorType.RATE_LIMIT
        
        # Login/authentication issues
        if any(term in error_msg for term in ['login', 'unauthorized', '401', 'authentication', 'signin']):
            return ErrorType.LOGIN_REQUIRED
        
        # CAPTCHA challenges
        if any(term in error_msg for term in ['captcha', 'challenge', 'verification', 'security check']):
            return ErrorType.CAPTCHA_CHALLENGE
        
        # Element/selector issues
        if any(term in error_msg for term in ['element not found', 'selector', 'locator', 'no such element']):
            return ErrorType.ELEMENT_NOT_FOUND
        
        # Timeout errors
        if any(term in error_msg for term in ['timeout', 'timed out', 'deadline exceeded']):
            return ErrorType.TIMEOUT_ERROR
        
        # Browser crashes
        if any(term in error_msg for term in ['browser', 'chrome', 'crashed', 'disconnected', 'session']):
            return ErrorType.BROWSER_CRASH
        
        # LinkedIn-specific blocking
        if any(term in error_msg for term in ['blocked', 'restricted', 'suspended', 'temporarily unavailable']):
            return ErrorType.LINKEDIN_BLOCKING
        
        # Data extraction failures
        if any(term in error_msg for term in ['extraction', 'parsing', 'decode', 'invalid data']):
            return ErrorType.DATA_EXTRACTION_ERROR
        
        return ErrorType.UNKNOWN_ERROR
    
    def calculate_delay(self, config: ErrorConfig, attempt: int, context: RetryContext) -> float:
        """Calculate delay before next retry based on strategy"""
        base_delay = config.base_delay
        
        if config.strategy == RetryStrategy.IMMEDIATE:
            delay = 0
        elif config.strategy == RetryStrategy.FIXED_DELAY:
            delay = base_delay
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = base_delay * attempt
        elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = base_delay * (2 ** (attempt - 1))
        else:
            delay = base_delay
        
        # Apply maximum delay limit
        delay = min(delay, config.max_delay)
        
        # Add jitter to avoid thundering herd
        if config.jitter:
            jitter_amount = delay * 0.1 * random.random()
            delay += jitter_amount
        
        # Special case: longer waits for rate limits and blocking
        if config.should_wait_longer and attempt > 1:
            delay *= 2
        
        return delay
    
    def should_retry(self, error_type: ErrorType, attempt: int, context: RetryContext) -> bool:
        """Determine if operation should be retried"""
        config = self.error_configs.get(error_type, self.error_configs[ErrorType.UNKNOWN_ERROR])
        
        if attempt >= config.max_retries:
            return False
        
        # Special conditions where we shouldn't retry
        if error_type == ErrorType.CAPTCHA_CHALLENGE and attempt > 0:
            # Only retry CAPTCHA once
            return False
        
        if error_type == ErrorType.LINKEDIN_BLOCKING:
            # Be very conservative with blocking
            return attempt < 1
        
        return True
    
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle an error and return recovery instructions"""
        error_type = self.classify_error(error, context)
        config = self.error_configs[error_type]
        
        # Update statistics
        self.error_stats[error_type] += 1
        
        recovery_actions = {
            "error_type": error_type.value,
            "should_retry": True,  # Will be determined later
            "reset_session": config.should_reset_session,
            "change_user_agent": config.should_change_user_agent,
            "wait_longer": config.should_wait_longer,
            "delay": config.base_delay,
            "max_retries": config.max_retries,
            "strategy": config.strategy.value,
            "custom_handler": config.custom_handler,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat()
        }
        
        logger.warning(f"🚨 Error detected: {error_type.value} - {str(error)}")
        logger.info(f"🔄 Recovery actions: {recovery_actions}")
        
        return recovery_actions
    
    def execute_with_retry(self, 
                          operation: Callable,
                          operation_name: str = "operation",
                          context: Dict[str, Any] = None,
                          *args, **kwargs) -> Any:
        """Execute an operation with intelligent retry logic"""
        
        context = context or {}
        retry_context = RetryContext()
        self.total_operations += 1
        
        logger.info(f"🚀 Starting operation: {operation_name}")
        
        while True:
            retry_context.attempt += 1
            retry_context.total_attempts += 1
            
            try:
                logger.debug(f"🔄 Attempt {retry_context.attempt} for {operation_name}")
                result = operation(*args, **kwargs)
                
                # Success!
                if retry_context.attempt > 1:
                    self.success_after_retry += 1
                    logger.info(f"✅ {operation_name} succeeded after {retry_context.attempt} attempts")
                
                return result
                
            except Exception as error:
                retry_context.last_error = error
                retry_context.error_messages.append(str(error))
                
                # Classify and handle the error
                error_type = self.classify_error(error, context)
                retry_context.error_type = error_type
                
                logger.warning(f"❌ {operation_name} failed (attempt {retry_context.attempt}): {error_type.value}")
                
                # Check if we should retry
                if not self.should_retry(error_type, retry_context.attempt, retry_context):
                    logger.error(f"🛑 Max retries reached for {operation_name}. Giving up.")
                    raise error
                
                # Calculate delay and wait
                config = self.error_configs[error_type]
                delay = self.calculate_delay(config, retry_context.attempt, retry_context)
                retry_context.delays.append(delay)
                
                logger.info(f"⏳ Waiting {delay:.1f}s before retry #{retry_context.attempt + 1}")
                time.sleep(delay)
                
                # Apply recovery actions if needed
                recovery = self.handle_error(error, context)
                if recovery.get("reset_session"):
                    logger.warning("🔄 Session reset recommended")
                if recovery.get("change_user_agent"):
                    logger.warning("🎭 User agent change recommended")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get error handling statistics"""
        return {
            "total_operations": self.total_operations,
            "success_after_retry": self.success_after_retry,
            "error_counts": {error_type.value: count for error_type, count in self.error_stats.items() if count > 0},
            "retry_success_rate": f"{(self.success_after_retry / max(1, self.total_operations)) * 100:.1f}%"
        }
    
    def reset_stats(self):
        """Reset error handling statistics"""
        self.error_stats = {error_type: 0 for error_type in ErrorType}
        self.success_after_retry = 0
        self.total_operations = 0
        
    def export_config(self, file_path: str):
        """Export current error handling configuration"""
        config_data = {}
        for error_type, config in self.error_configs.items():
            config_data[error_type.value] = {
                "max_retries": config.max_retries,
                "strategy": config.strategy.value,
                "base_delay": config.base_delay,
                "max_delay": config.max_delay,
                "jitter": config.jitter,
                "should_reset_session": config.should_reset_session,
                "should_change_user_agent": config.should_change_user_agent,
                "should_wait_longer": config.should_wait_longer
            }
        
        with open(file_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        logger.info(f"📤 Error handling config exported to: {file_path}")


# Convenience decorators
def with_retry(operation_name: str = None, error_handler: AdvancedErrorHandler = None):
    """Decorator to add retry logic to any function"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            handler = error_handler or AdvancedErrorHandler()
            name = operation_name or func.__name__
            return handler.execute_with_retry(func, name, *args, **kwargs)
        return wrapper
    return decorator


# Global error handler instance
global_error_handler = AdvancedErrorHandler()