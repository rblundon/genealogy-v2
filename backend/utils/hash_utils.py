"""Hashing utilities for caching."""
import hashlib


def hash_url(url: str) -> str:
    """Generate SHA-256 hash of a URL"""
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def hash_content(content: str) -> str:
    """Generate SHA-256 hash of content"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def hash_prompt(prompt: str) -> str:
    """Generate SHA-256 hash of an LLM prompt"""
    return hashlib.sha256(prompt.encode('utf-8')).hexdigest()
