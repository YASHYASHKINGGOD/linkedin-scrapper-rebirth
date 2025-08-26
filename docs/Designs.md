# Designs.md - LinkedIn Selenium Scraper Architecture

## Architecture Overview

### High-Level Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    LinkedIn Selenium Scraper                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Config        │  │   Web Driver    │  │   Data Export   │ │
│  │   Management    │  │   Controller    │  │   Pipeline      │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│           │                     │                     │         │
│           ▼                     ▼                     ▼         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   LinkedIn      │  │   Content       │  │   Output        │ │
│  │   Session       │  │   Scraper       │  │   Formatter     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│           │                     │                     │         │
│           └─────────────────────┼─────────────────────┘         │
│                                 ▼                               │
│                    ┌─────────────────┐                         │
│                    │   Logging &     │                         │
│                    │   Monitoring    │                         │
│                    └─────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

### Component Descriptions

1. **Config Management**: Handles configuration loading, validation, and environment setup
2. **Web Driver Controller**: Manages Chrome WebDriver lifecycle and anti-automation hardening
3. **LinkedIn Session**: Handles authentication, session management, and login flow
4. **Content Scraper**: Core scraping logic for posts, comments, and engagement data
5. **Data Export Pipeline**: Converts scraped data to JSON, CSV, and Excel formats
6. **Output Formatter**: Structures and formats data for different output types
7. **Logging & Monitoring**: Comprehensive logging, error tracking, and performance monitoring

## DOM Selector Strategy

### Selector Hierarchy and Fallbacks

LinkedIn's DOM structure changes frequently, so we implement a multi-level selector strategy:

```python
# Primary selectors (current as of 2025)
PRIMARY_SELECTORS = {
    "post_container": "div[data-id^='urn:li:activity']",
    "post_content": ".feed-shared-update-v2__description",
    "post_author": ".feed-shared-actor__name",
    "post_timestamp": ".feed-shared-actor__sub-description time",
    "engagement_bar": ".social-counts-reactions",
    "comment_section": ".comments-comments-list"
}

# Fallback selectors (older/alternative structures)
FALLBACK_SELECTORS = {
    "post_container": [
        "article[data-id^='urn:li:activity']",
        ".feed-shared-update-v2",
        ".occludable-update"
    ],
    "post_content": [
        ".feed-shared-text",
        ".feed-shared-inline-show-more-text",
        ".feed-shared-update-v2__commentary"
    ]
}

# Dynamic selectors (generated based on context)
DYNAMIC_SELECTORS = {
    "show_more_button": "button[aria-label*='more']",
    "load_more_comments": "button[data-test-id='comments-show-more']"
}
```

### Selector Testing Strategy

1. **Validation Pipeline**: Test selectors against known page structures
2. **Fallback Cascade**: Try primary, then fallback selectors in order
3. **Dynamic Detection**: Identify new patterns automatically
4. **Update Notifications**: Log when selectors fail for manual review

## Content Expansion Approach

### Post Content Expansion

```python
def expand_post_content(self, post_element):
    """
    Expand truncated post content using multi-step approach
    """
    expansion_strategies = [
        self._click_show_more_button,
        self._click_see_more_link,
        self._scroll_and_wait,
        self._keyboard_navigation
    ]
    
    for strategy in expansion_strategies:
        try:
            if strategy(post_element):
                return self._extract_full_content(post_element)
        except Exception as e:
            logger.debug(f"Expansion strategy {strategy.__name__} failed: {e}")
            continue
    
    # Return partial content if all strategies fail
    return self._extract_partial_content(post_element)
```

### Comment Expansion Logic

```python
def expand_comments(self, post_element, max_attempts=6):
    """
    Expand comments with intelligent retry logic
    """
    expanded_count = 0
    
    while expanded_count < max_attempts:
        # Find expansion trigger
        expand_button = self._find_comment_expand_button(post_element)
        
        if not expand_button:
            break
            
        # Click with random delay
        self._click_with_delay(expand_button)
        
        # Wait for new content to load
        initial_count = self._count_visible_comments(post_element)
        self._wait_for_content_load()
        new_count = self._count_visible_comments(post_element)
        
        # Check if expansion was successful
        if new_count > initial_count:
            expanded_count += 1
            logger.debug(f"Expanded {new_count - initial_count} new comments")
        else:
            # No new content, likely reached end
            break
            
        # Progressive delay increase to avoid detection
        self._progressive_delay(expanded_count)
    
    return self._extract_all_comments(post_element)
```

## Rate Limiting Strategy

### Multi-Level Rate Limiting

```python
class RateLimiter:
    def __init__(self, config):
        self.base_delay = config['random_delay_range']
        self.progressive_multiplier = 1.2
        self.request_count = 0
        self.session_start = time.time()
        
    def apply_delay(self, operation_type="default"):
        """Apply intelligent rate limiting based on operation type"""
        
        delays = {
            "login": (2.0, 4.0),
            "navigation": (1.0, 2.5),
            "content_extraction": (0.5, 1.5),
            "comment_expansion": (1.5, 3.0),
            "scroll": (0.3, 0.8)
        }
        
        min_delay, max_delay = delays.get(operation_type, self.base_delay)
        
        # Progressive delay increase for long sessions
        session_multiplier = 1 + (time.time() - self.session_start) / 3600 * 0.1
        
        # Request frequency adjustment
        frequency_multiplier = 1 + self.request_count / 100 * 0.05
        
        final_delay = random.uniform(min_delay, max_delay) * session_multiplier * frequency_multiplier
        
        logger.debug(f"Applying {final_delay:.2f}s delay for {operation_type}")
        time.sleep(final_delay)
        
        self.request_count += 1
```

## Data Models

### Post Data Structure

```python
@dataclass
class LinkedInPost:
    """Structured representation of a LinkedIn post"""
    
    # Identifiers
    post_id: str
    post_url: str
    
    # Author information
    author_name: str
    author_profile_url: str
    author_title: str
    author_company: str
    
    # Content
    content_text: str
    content_html: str
    media_attachments: List[MediaAttachment]
    
    # Metadata
    timestamp: datetime
    post_type: str  # "text", "image", "video", "document", "poll"
    
    # Engagement
    like_count: int
    comment_count: int
    share_count: int
    reaction_breakdown: Dict[str, int]  # {"like": 45, "love": 12, ...}
    
    # Comments
    comments: List[Comment]
    
    # Extraction metadata
    scraped_at: datetime
    scraper_version: str
    extraction_quality: float  # 0.0-1.0 confidence score
```

### Comment Data Structure

```python
@dataclass
class Comment:
    """Structured representation of a comment"""
    
    # Identifiers
    comment_id: str
    parent_comment_id: Optional[str]  # For nested replies
    
    # Author
    author_name: str
    author_profile_url: str
    
    # Content
    text_content: str
    
    # Engagement
    like_count: int
    reply_count: int
    
    # Metadata
    timestamp: datetime
    is_reply: bool
    depth_level: int  # Nesting depth (0=top-level, 1=reply, 2=reply-to-reply)
    
    # Nested replies
    replies: List['Comment'] = field(default_factory=list)
```

### Media Attachment Structure

```python
@dataclass
class MediaAttachment:
    """Structured representation of media attachments"""
    
    media_type: str  # "image", "video", "document", "link"
    media_url: str
    thumbnail_url: Optional[str]
    
    # Metadata
    title: Optional[str]
    description: Optional[str]
    file_size: Optional[int]
    duration: Optional[int]  # For videos
    
    # Download info
    downloaded: bool = False
    local_path: Optional[str] = None
```

## Configuration Schema

### Complete Configuration Structure

```json
{
    "linkedin_credentials": {
        "email": "string",
        "password": "string",
        "backup_accounts": [
            {
                "email": "string",
                "password": "string",
                "priority": "integer"
            }
        ]
    },
    "scraping_settings": {
        "headless": "boolean",
        "random_delay_range": [float, float],
        "page_load_timeout": "integer",
        "implicit_wait_timeout": "integer",
        "explicit_wait_timeout": "integer",
        "max_comment_expansion_attempts": "integer",
        "max_posts_per_session": "integer",
        "scroll_pause_time": "float"
    },
    "chrome_options": {
        "disable_automation_flags": ["string"],
        "user_agent": "string",
        "window_size": [integer, integer],
        "download_directory": "string",
        "extensions": ["string"]
    },
    "data_extraction": {
        "include_comments": "boolean",
        "include_media": "boolean",
        "expand_long_posts": "boolean",
        "extract_author_profiles": "boolean",
        "quality_threshold": "float"
    },
    "output_settings": {
        "save_to_json": "boolean",
        "save_to_csv": "boolean",
        "save_to_excel": "boolean",
        "output_directory": "string",
        "timestamp_format": "string",
        "file_prefix": "string",
        "compression": "string"
    },
    "performance": {
        "max_concurrent_requests": "integer",
        "memory_limit_mb": "integer",
        "disk_space_limit_gb": "integer",
        "session_timeout_minutes": "integer"
    },
    "logging": {
        "level": "string",
        "file_rotation": "boolean",
        "max_log_files": "integer",
        "log_file_size_mb": "integer"
    }
}
```

## Extensibility Notes

### Plugin Architecture (Future Enhancement)

```python
class ScraperPlugin:
    """Base class for scraper plugins"""
    
    def __init__(self, scraper_instance):
        self.scraper = scraper_instance
        
    def pre_login_hook(self):
        """Called before login attempt"""
        pass
        
    def post_login_hook(self):
        """Called after successful login"""
        pass
        
    def pre_scrape_hook(self, url):
        """Called before scraping a URL"""
        pass
        
    def post_scrape_hook(self, data):
        """Called after scraping completion"""
        return data
        
    def error_hook(self, error, context):
        """Called when errors occur"""
        pass

# Example plugins:
# - ProxyRotationPlugin
# - DataValidationPlugin  
# - CloudUploadPlugin
# - NotificationPlugin
```

### Custom Output Formats

```python
class OutputFormatter:
    """Base class for custom output formats"""
    
    @abstractmethod
    def format_posts(self, posts: List[LinkedInPost]) -> Any:
        pass
        
    @abstractmethod
    def save_to_file(self, data: Any, filepath: str):
        pass

# Implementations:
# - JSONLFormatter (newline-delimited JSON)
# - ParquetFormatter (columnar format)
# - DatabaseFormatter (direct DB insertion)
# - APIFormatter (POST to external API)
```

### Multi-Account Management

```python
class AccountManager:
    """Manages multiple LinkedIn accounts with rotation"""
    
    def __init__(self, accounts_config):
        self.accounts = self._load_accounts(accounts_config)
        self.current_account_index = 0
        self.account_cooldowns = {}
        
    def get_next_account(self):
        """Returns next available account, handling cooldowns"""
        pass
        
    def mark_account_blocked(self, account_email):
        """Mark account as temporarily unavailable"""
        pass
        
    def rotate_accounts(self):
        """Automatically rotate to next available account"""
        pass
```

## Security Considerations

### Credential Management
- Environment variable support for sensitive data
- Encrypted configuration file option
- Credential rotation capabilities
- Session token caching with encryption

### Anti-Detection Measures
- Dynamic user agent rotation
- Browser fingerprint randomization
- Request timing variance
- Natural scroll patterns
- Mouse movement simulation (future)

### Data Privacy
- PII scrubbing options
- Consent tracking
- Data retention policies
- Export compliance (GDPR)

## Performance Optimization

### Memory Management
- Streaming data processing for large datasets
- Garbage collection optimization
- Memory-mapped file operations
- Efficient data structures

### Concurrency Strategy
- Thread-pool for I/O operations
- Async/await for network requests
- Process-based parallelization option
- Resource pooling and reuse

### Caching Strategy
- Page content caching
- Selector result memoization
- Session state persistence
- Configuration hot-reloading

This architecture provides a robust, scalable foundation for LinkedIn scraping while maintaining flexibility for future enhancements and compliance requirements.
