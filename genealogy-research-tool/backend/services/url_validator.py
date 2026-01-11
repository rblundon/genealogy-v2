"""
URL validation service for obituary sources.
Currently supports Legacy.com with architecture for future sites.
"""

import re
from typing import Optional, Dict
from urllib.parse import urlparse


class URLValidator:
    """Validate and parse obituary URLs from various sources."""

    # Legacy.com URL patterns
    LEGACY_PATTERNS = [
        r'https?://(?:www\.)?legacy\.com/.*',
        r'https?://(?:www\.)?legacy\.com/us/obituaries/.*',
        r'https?://(?:www\.)?legacy\.com/obituaries/.*',
    ]

    def __init__(self):
        self.supported_sites = ['legacy.com']

    def validate_url(self, url: str) -> Dict[str, any]:
        """
        Validate an obituary URL and determine its source.

        Args:
            url: URL to validate

        Returns:
            {
                'valid': bool,
                'site': str or None,
                'url': str (normalized),
                'error': str or None
            }
        """
        if not url or not isinstance(url, str):
            return {
                'valid': False,
                'site': None,
                'url': None,
                'error': 'URL is required and must be a string'
            }

        url = url.strip()

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            return {
                'valid': False,
                'site': None,
                'url': url,
                'error': f'Invalid URL format: {str(e)}'
            }

        # Check if URL has scheme
        if not parsed.scheme:
            return {
                'valid': False,
                'site': None,
                'url': url,
                'error': 'URL must include http:// or https://'
            }

        # Check if Legacy.com
        if self._is_legacy_url(url):
            return {
                'valid': True,
                'site': 'legacy.com',
                'url': url,
                'error': None
            }

        # Not a supported site
        return {
            'valid': False,
            'site': None,
            'url': url,
            'error': f'URL is not from a supported obituary site. Supported sites: {", ".join(self.supported_sites)}'
        }

    def _is_legacy_url(self, url: str) -> bool:
        """Check if URL matches Legacy.com patterns."""
        for pattern in self.LEGACY_PATTERNS:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False

    def is_supported_site(self, url: str) -> bool:
        """Quick check if URL is from a supported site."""
        result = self.validate_url(url)
        return result['valid']
