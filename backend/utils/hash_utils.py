"""Hashing utilities for caching."""
import hashlib
from urllib.parse import urlparse, parse_qs, urlencode


def normalize_url(url: str) -> str:
    """
    Normalize a URL for consistent cache key generation.

    Normalization rules:
    - Convert to lowercase
    - Remove trailing slashes
    - Keep only essential query params (id, pid, obituary_id, person_id)
    - Sort query parameters alphabetically

    Args:
        url: The URL to normalize

    Returns:
        Normalized URL string
    """
    parsed = urlparse(url.lower().strip())

    # Remove trailing slashes from path
    path = parsed.path.rstrip("/")

    # Keep only essential query params for obituary identification
    essential_params = ["id", "pid", "obituary_id", "person_id"]
    query_dict = parse_qs(parsed.query)
    filtered_query = {k: v for k, v in query_dict.items() if k in essential_params}

    # Sort and encode query parameters
    sorted_params = sorted(filtered_query.items())
    normalized_query = urlencode(sorted_params, doseq=True)

    # Reconstruct normalized URL
    normalized_url = f"{parsed.scheme}://{parsed.netloc}{path}"
    if normalized_query:
        normalized_url += f"?{normalized_query}"

    return normalized_url


def hash_url(url: str) -> str:
    """
    Generate SHA-256 hash of a normalized URL.

    Args:
        url: The URL to hash

    Returns:
        SHA-256 hex digest of the normalized URL
    """
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def hash_content(content: str) -> str:
    """
    Generate SHA-256 hash of content.

    Args:
        content: The content string to hash

    Returns:
        SHA-256 hex digest of the content
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def hash_prompt(prompt: str, content: str = "", model: str = "") -> str:
    """
    Generate SHA-256 hash of an LLM prompt with content and model.

    Combines prompt, content, and model version to create a unique
    cache key for LLM responses.

    Args:
        prompt: The LLM prompt template
        content: The obituary content being processed
        model: The model version (e.g., 'gpt-4-turbo-preview')

    Returns:
        SHA-256 hex digest of the combined inputs
    """
    combined = f"{prompt}|{content}|{model}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
