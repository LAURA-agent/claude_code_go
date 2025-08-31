#!/usr/bin/env python3
"""
Document Cache Manager for MCP Client
Implements proper caching strategy based on Anthropic's prompt caching guidelines
"""

import json
import hashlib
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import base64

class DocumentCacheManager:
    def __init__(self, cache_dir: str = "/home/user/rp_client/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_index_file = self.cache_dir / "cache_index.json"
        self.cache_index = self._load_cache_index()
        
        # Anthropic prompt caching settings
        self.cache_lifetime_minutes = 5  # Default 5-minute cache
        self.extended_cache_lifetime_minutes = 60  # Extended 1-hour cache
        self.min_cacheable_tokens = 1024  # Minimum tokens for caching
        
    def _load_cache_index(self) -> Dict:
        """Load cache index from disk"""
        if self.cache_index_file.exists():
            try:
                with open(self.cache_index_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[CACHE] Error loading cache index: {e}")
        return {
            "documents": {},
            "cache_stats": {
                "total_cached": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "bytes_saved": 0
            }
        }
    
    def _save_cache_index(self):
        """Save cache index to disk"""
        try:
            with open(self.cache_index_file, 'w') as f:
                json.dump(self.cache_index, f, indent=2)
        except Exception as e:
            print(f"[CACHE] Error saving cache index: {e}")
    
    def _generate_document_hash(self, file_path: str) -> str:
        """Generate hash for document content"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _estimate_tokens(self, content: bytes) -> int:
        """Estimate token count for content (rough approximation)"""
        # Rough estimate: 1 token ≈ 4 characters
        return len(content) // 4
    
    def should_cache_document(self, file_path: str) -> Tuple[bool, str]:
        """Determine if document should be cached based on Anthropic's guidelines"""
        try:
            file_size = os.path.getsize(file_path)
            
            # Check file size (don't cache very small files)
            if file_size < 4096:  # ~1024 tokens minimum
                return False, "File too small for efficient caching"
            
            # Check file type
            file_ext = Path(file_path).suffix.lower()
            cacheable_extensions = ['.txt', '.md', '.json', '.csv', '.log', '.xml', '.html']
            if file_ext not in cacheable_extensions:
                return False, f"File type {file_ext} not optimal for caching"
            
            # Estimate tokens
            with open(file_path, 'rb') as f:
                content = f.read()
            estimated_tokens = self._estimate_tokens(content)
            
            if estimated_tokens < self.min_cacheable_tokens:
                return False, f"Estimated {estimated_tokens} tokens below minimum {self.min_cacheable_tokens}"
            
            return True, f"Document suitable for caching ({estimated_tokens} estimated tokens)"
            
        except Exception as e:
            return False, f"Error checking document: {e}"
    
    def get_cached_document(self, file_path: str) -> Optional[Dict]:
        """Retrieve cached document if valid"""
        doc_hash = self._generate_document_hash(file_path)
        
        if doc_hash in self.cache_index["documents"]:
            cached_doc = self.cache_index["documents"][doc_hash]
            
            # Check if cache is still valid
            cache_time = datetime.fromisoformat(cached_doc["cached_at"])
            cache_duration = timedelta(minutes=cached_doc.get("cache_lifetime", self.cache_lifetime_minutes))
            
            if datetime.now() - cache_time < cache_duration:
                self.cache_index["cache_stats"]["cache_hits"] += 1
                self._save_cache_index()
                print(f"[CACHE HIT] Document {Path(file_path).name} retrieved from cache")
                return cached_doc
            else:
                # Cache expired
                print(f"[CACHE EXPIRED] Document {Path(file_path).name} cache expired")
                del self.cache_index["documents"][doc_hash]
                
        self.cache_index["cache_stats"]["cache_misses"] += 1
        self._save_cache_index()
        return None
    
    def cache_document(self, file_path: str, content: bytes, 
                      use_extended_cache: bool = False) -> Dict:
        """Cache document with metadata"""
        doc_hash = self._generate_document_hash(file_path)
        file_name = Path(file_path).name
        
        # Determine cache lifetime
        cache_lifetime = (self.extended_cache_lifetime_minutes 
                         if use_extended_cache 
                         else self.cache_lifetime_minutes)
        
        # Create cache entry
        cache_entry = {
            "file_path": file_path,
            "file_name": file_name,
            "hash": doc_hash,
            "size": len(content),
            "estimated_tokens": self._estimate_tokens(content),
            "content_base64": base64.b64encode(content).decode('utf-8'),
            "cached_at": datetime.now().isoformat(),
            "cache_lifetime": cache_lifetime,
            "cache_control": {
                "type": "ephemeral" if cache_lifetime <= 5 else "extended",
                "breakpoint_eligible": True  # Can be used as cache breakpoint
            }
        }
        
        # Store in cache
        self.cache_index["documents"][doc_hash] = cache_entry
        self.cache_index["cache_stats"]["total_cached"] += 1
        self.cache_index["cache_stats"]["bytes_saved"] += len(content)
        self._save_cache_index()
        
        print(f"[CACHE STORED] Document {file_name} cached for {cache_lifetime} minutes")
        return cache_entry
    
    def prepare_cached_context(self, document_paths: List[str]) -> Dict:
        """Prepare multiple documents as cached context for prompt"""
        cached_documents = []
        cache_hits = 0
        cache_misses = 0
        
        for doc_path in document_paths:
            cached_doc = self.get_cached_document(doc_path)
            if cached_doc:
                cached_documents.append(cached_doc)
                cache_hits += 1
            else:
                # Load and cache if suitable
                should_cache, reason = self.should_cache_document(doc_path)
                if should_cache:
                    with open(doc_path, 'rb') as f:
                        content = f.read()
                    cached_doc = self.cache_document(doc_path, content)
                    cached_documents.append(cached_doc)
                cache_misses += 1
        
        return {
            "cached_documents": cached_documents,
            "cache_performance": {
                "hits": cache_hits,
                "misses": cache_misses,
                "efficiency": cache_hits / (cache_hits + cache_misses) if (cache_hits + cache_misses) > 0 else 0
            },
            "total_tokens": sum(doc["estimated_tokens"] for doc in cached_documents),
            "cache_control_hint": "use_cached" if cache_hits > cache_misses else "rebuild_cache"
        }
    
    def get_cache_statistics(self) -> Dict:
        """Get current cache statistics"""
        stats = self.cache_index["cache_stats"].copy()
        stats["active_documents"] = len(self.cache_index["documents"])
        stats["cache_dir_size"] = sum(
            f.stat().st_size for f in self.cache_dir.rglob('*') if f.is_file()
        )
        return stats
    
    def clear_expired_cache(self):
        """Remove expired cache entries"""
        expired_count = 0
        for doc_hash in list(self.cache_index["documents"].keys()):
            cached_doc = self.cache_index["documents"][doc_hash]
            cache_time = datetime.fromisoformat(cached_doc["cached_at"])
            cache_duration = timedelta(minutes=cached_doc.get("cache_lifetime", self.cache_lifetime_minutes))
            
            if datetime.now() - cache_time >= cache_duration:
                del self.cache_index["documents"][doc_hash]
                expired_count += 1
        
        if expired_count > 0:
            self._save_cache_index()
            print(f"[CACHE CLEANUP] Removed {expired_count} expired entries")
        
        return expired_count