"""
Performance Optimization Utilities
Caching, compression, and performance monitoring
"""

import time
import logging
from functools import wraps
from typing import Dict, Any, Optional, Callable
from flask import session

class PerformanceMonitor:
    """Monitor and log performance metrics."""
    
    def __init__(self):
        self.metrics = {}
    
    def time_function(self, name: str):
        """Decorator to time function execution."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    self.log_metric(name, execution_time)
                    return result
                except Exception as e:
                    execution_time = time.time() - start_time
                    logging.error(f"Function {name} failed after {execution_time:.3f}s: {e}")
                    raise
            return wrapper
        return decorator
    
    def log_metric(self, name: str, value: float):
        """Log performance metric."""
        if name not in self.metrics:
            self.metrics[name] = []
        
        self.metrics[name].append(value)
        
        # Keep only recent metrics
        if len(self.metrics[name]) > 100:
            self.metrics[name] = self.metrics[name][-50:]
        
        # Log slow operations
        if value > 2.0:  # More than 2 seconds
            logging.warning(f"Slow operation detected: {name} took {value:.3f}s")
    
    def get_average(self, name: str) -> Optional[float]:
        """Get average execution time for a metric."""
        if name in self.metrics and self.metrics[name]:
            return sum(self.metrics[name]) / len(self.metrics[name])
        return None

# Global performance monitor
perf_monitor = PerformanceMonitor()

class SessionCache:
    """Simple session-based caching system."""
    
    @staticmethod
    def get(key: str) -> Any:
        """Get cached value from session."""
        cache_key = f"_cache_{key}"
        cached_data = session.get(cache_key)
        
        if cached_data and isinstance(cached_data, dict):
            timestamp = cached_data.get("timestamp", 0)
            ttl = cached_data.get("ttl", 300)  # 5 minutes default
            
            if time.time() - timestamp < ttl:
                return cached_data.get("data")
        
        return None
    
    @staticmethod
    def set(key: str, value: Any, ttl: int = 300):
        """Cache value in session with TTL."""
        cache_key = f"_cache_{key}"
        session[cache_key] = {
            "data": value,
            "timestamp": time.time(),
            "ttl": ttl
        }
    
    @staticmethod
    def clear(key: str = None):
        """Clear specific cache key or all cache."""
        if key:
            cache_key = f"_cache_{key}"
            session.pop(cache_key, None)
        else:
            # Clear all cache keys
            cache_keys = [k for k in session.keys() if k.startswith("_cache_")]
            for cache_key in cache_keys:
                session.pop(cache_key, None)

def compress_story_content(content: str, max_length: int = 1000) -> str:
    """Compress story content while preserving key information."""
    if len(content) <= max_length:
        return content
    
    # Split into sentences
    sentences = content.split('. ')
    if len(sentences) <= 3:
        return content[:max_length] + "..."
    
    # Keep first and last sentences, summarize middle
    first_sentence = sentences[0] + "."
    last_sentence = sentences[-1]
    
    # Calculate available space for middle content
    available_space = max_length - len(first_sentence) - len(last_sentence) - 20
    
    if available_space > 50:
        # Try to keep some middle content
        middle_content = " ".join(sentences[1:-1])
        if len(middle_content) > available_space:
            middle_content = middle_content[:available_space] + "..."
        
        return f"{first_sentence} {middle_content} {last_sentence}"
    else:
        # Just keep first and last
        return f"{first_sentence} [...] {last_sentence}"

def optimize_session_size():
    """Optimize session size by compressing large data."""
    optimizations_made = []
    
    try:
        # Compress story if too long
        story = session.get("story", "")
        if len(story) > 2000:
            session["story"] = compress_story_content(story, 1500)
            optimizations_made.append("story_compressed")
        
        # Compress base story
        base_story = session.get("base_story", "")
        if len(base_story) > 1500:
            session["base_story"] = compress_story_content(base_story, 1000)
            optimizations_made.append("base_story_compressed")
        
        # Limit story history
        story_history = session.get("story_history", [])
        if len(story_history) > 6:
            session["story_history"] = story_history[-4:]
            optimizations_made.append("history_trimmed")
        
        # Remove old temporary data
        temp_keys = ["temp_data", "debug_info", "last_error", "recovery_data"]
        for key in temp_keys:
            if session.pop(key, None):
                optimizations_made.append(f"removed_{key}")
        
        if optimizations_made:
            logging.info(f"Session optimized: {', '.join(optimizations_made)}")
            
    except Exception as e:
        logging.error(f"Session optimization error: {e}")

def batch_session_updates(updates: Dict[str, Any]):
    """Apply multiple session updates efficiently."""
    try:
        for key, value in updates.items():
            session[key] = value
        session.permanent = True
    except Exception as e:
        logging.error(f"Batch session update error: {e}")
        # Try individual updates as fallback
        for key, value in updates.items():
            try:
                session[key] = value
            except Exception as update_error:
                logging.error(f"Failed to update session key {key}: {update_error}")

class RateLimiter:
    """Simple rate limiting for expensive operations."""
    
    def __init__(self):
        self.requests = {}
    
    def is_allowed(self, key: str, max_requests: int = 10, window: int = 60) -> bool:
        """Check if request is allowed within rate limit."""
        current_time = time.time()
        
        if key not in self.requests:
            self.requests[key] = []
        
        # Remove old requests outside the window
        self.requests[key] = [
            req_time for req_time in self.requests[key] 
            if current_time - req_time < window
        ]
        
        # Check if within limit
        if len(self.requests[key]) < max_requests:
            self.requests[key].append(current_time)
            return True
        
        return False

# Global rate limiter
rate_limiter = RateLimiter()

def cache_ai_response(prompt_key: str, response: str, ttl: int = 1800):
    """Cache AI responses to reduce API calls."""
    SessionCache.set(f"ai_response_{prompt_key}", response, ttl)

def get_cached_ai_response(prompt_key: str) -> Optional[str]:
    """Get cached AI response if available."""
    return SessionCache.get(f"ai_response_{prompt_key}")