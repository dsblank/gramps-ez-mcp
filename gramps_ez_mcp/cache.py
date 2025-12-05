#!/usr/bin/env python3
"""
Session-aware caching system for Comet ML MCP server.
Provides caching decorators that respect different sessions and allow cache invalidation.
"""

import hashlib
import json
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union
from datetime import datetime, timedelta


class CacheEntry:
    """Represents a cached value with metadata."""
    
    def __init__(self, value: Any, created_at: datetime, ttl_seconds: Optional[int] = None):
        self.value = value
        self.created_at = created_at
        self.ttl_seconds = ttl_seconds
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.ttl_seconds is None:
            return False
        return datetime.now() - self.created_at > timedelta(seconds=self.ttl_seconds)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'value': self.value,
            'created_at': self.created_at.isoformat(),
            'ttl_seconds': self.ttl_seconds
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        """Create from dictionary."""
        return cls(
            value=data['value'],
            created_at=datetime.fromisoformat(data['created_at']),
            ttl_seconds=data.get('ttl_seconds')
        )


class SessionCache:
    """Session-aware cache that maintains separate caches per session."""
    
    def __init__(self):
        self._caches: Dict[str, Dict[str, CacheEntry]] = {}
        self._session_metadata: Dict[str, Dict[str, Any]] = {}
    
    def _get_session_id(self) -> str:
        """Get the current session ID."""
        from .session import get_session_context
        session_context = get_session_context()
        
        # Create a unique session ID based on the API instance
        if session_context.is_initialized():
            # Use the API instance's identity as session ID
            api = session_context.api
            session_id = f"session_{id(api)}_{hash(str(api))}"
        else:
            # Fallback to a default session
            session_id = "default_session"
        
        return session_id
    
    def _generate_cache_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate a unique cache key for a function call."""
        # Create a deterministic key from function name and arguments
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': sorted(kwargs.items()) if kwargs else {}
        }
        
        # Create a hash of the key data
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, func_name: str, args: tuple, kwargs: dict) -> Optional[Any]:
        """Get a cached value for a function call."""
        session_id = self._get_session_id()
        cache_key = self._generate_cache_key(func_name, args, kwargs)
        
        if session_id not in self._caches:
            return None
        
        if cache_key not in self._caches[session_id]:
            return None
        
        entry = self._caches[session_id][cache_key]
        
        # Check if expired
        if entry.is_expired():
            del self._caches[session_id][cache_key]
            return None
        
        return entry.value
    
    def set(self, func_name: str, args: tuple, kwargs: dict, value: Any, ttl_seconds: Optional[int] = None):
        """Set a cached value for a function call."""
        session_id = self._get_session_id()
        cache_key = self._generate_cache_key(func_name, args, kwargs)
        
        if session_id not in self._caches:
            self._caches[session_id] = {}
            self._session_metadata[session_id] = {
                'created_at': datetime.now(),
                'last_accessed': datetime.now()
            }
        
        entry = CacheEntry(value, datetime.now(), ttl_seconds)
        self._caches[session_id][cache_key] = entry
        self._session_metadata[session_id]['last_accessed'] = datetime.now()
    
    def invalidate(self, func_name: Optional[str] = None, session_id: Optional[str] = None):
        """Invalidate cache entries.
        
        Args:
            func_name: If provided, only invalidate entries for this function
            session_id: If provided, only invalidate entries for this session
        """
        if session_id:
            # Invalidate specific session
            if session_id in self._caches:
                if func_name:
                    # Remove only entries for this function
                    keys_to_remove = [
                        key for key in self._caches[session_id].keys()
                        if key.startswith(f"{func_name}_")
                    ]
                    for key in keys_to_remove:
                        del self._caches[session_id][key]
                else:
                    # Remove all entries for this session
                    del self._caches[session_id]
                    del self._session_metadata[session_id]
        else:
            # Invalidate all sessions
            if func_name:
                # Remove entries for this function from all sessions
                for session in self._caches:
                    keys_to_remove = [
                        key for key in self._caches[session].keys()
                        if key.startswith(f"{func_name}_")
                    ]
                    for key in keys_to_remove:
                        del self._caches[session][key]
            else:
                # Clear all caches
                self._caches.clear()
                self._session_metadata.clear()
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get information about cached sessions."""
        info = {}
        for session_id, metadata in self._session_metadata.items():
            cache_size = len(self._caches.get(session_id, {}))
            info[session_id] = {
                'created_at': metadata['created_at'].isoformat(),
                'last_accessed': metadata['last_accessed'].isoformat(),
                'cache_size': cache_size
            }
        return info
    
    def cleanup_expired(self):
        """Remove expired entries from all sessions."""
        for session_id in list(self._caches.keys()):
            expired_keys = []
            for key, entry in self._caches[session_id].items():
                if entry.is_expired():
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._caches[session_id][key]
            
            # Remove empty sessions
            if not self._caches[session_id]:
                del self._caches[session_id]
                if session_id in self._session_metadata:
                    del self._session_metadata[session_id]


# Global cache instance
_cache = SessionCache()


def cached(ttl_seconds: Optional[int] = None, key_func: Optional[Callable] = None):
    """
    Decorator for caching function results with session awareness.
    
    Args:
        ttl_seconds: Time-to-live in seconds. None means no expiration.
        key_func: Optional function to generate custom cache keys.
                 Should take (args, kwargs) and return a string.
    
    Example:
        @cached(ttl_seconds=300)  # Cache for 5 minutes
        def expensive_function(param1, param2):
            # ... expensive computation
            return result
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(args, kwargs)
            else:
                cache_key = _cache._generate_cache_key(func.__name__, args, kwargs)
            
            # Try to get from cache
            cached_result = _cache.get(func.__name__, args, kwargs)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            _cache.set(func.__name__, args, kwargs, result, ttl_seconds)
            
            return result
        
        # Add cache management methods to the wrapper
        wrapper.cache_invalidate = lambda: _cache.invalidate(func.__name__)
        wrapper.cache_clear = lambda: _cache.invalidate(func.__name__)
        
        return wrapper
    return decorator


def cache_invalidate(func_name: Optional[str] = None, session_id: Optional[str] = None):
    """Invalidate cache entries.
    
    Args:
        func_name: Function name to invalidate (optional)
        session_id: Session ID to invalidate (optional)
    """
    _cache.invalidate(func_name, session_id)


def cache_clear():
    """Clear all cache entries."""
    _cache.invalidate()


def get_cache_info() -> Dict[str, Any]:
    """Get information about the current cache state."""
    _cache.cleanup_expired()
    return _cache.get_session_info()


def cache_cleanup():
    """Clean up expired cache entries."""
    _cache.cleanup_expired()
