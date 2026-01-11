"""
Obituary content fetcher from various websites.
Currently supports Legacy.com with architecture for future sites.
"""

import time
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict
import hashlib


class ObituaryFetcher:
    """Fetch obituary content from supported websites."""

    def __init__(self):
        self.user_agent = 'GenealogyResearchBot/1.0 (Educational/Research Purpose)'
        self.timeout = 10  # seconds
        self.rate_limit_delay = 2  # seconds between requests
        self.last_request_time = 0

    def fetch(self, url: str, site: str) -> Dict[str, any]:
        """
        Fetch obituary content from URL.

        Args:
            url: Obituary URL
            site: Site identifier (e.g., 'legacy.com')

        Returns:
            {
                'success': bool,
                'url': str,
                'url_hash': str,
                'content_hash': str or None,
                'raw_html': str or None,
                'extracted_text': str or None,
                'http_status_code': int or None,
                'error': str or None
            }
        """
        # Rate limiting
        self._respect_rate_limit()

        try:
            # Fetch HTML
            response = requests.get(
                url,
                headers={'User-Agent': self.user_agent},
                timeout=self.timeout
            )

            http_status = response.status_code

            # Check for errors
            if http_status == 404:
                return self._error_response(url, http_status, 'Obituary not found (404)')

            if http_status == 403:
                return self._error_response(url, http_status, 'Access forbidden - obituary may be behind paywall (403)')

            if http_status == 429:
                return self._error_response(url, http_status, 'Rate limited by server (429) - please try again later')

            if http_status != 200:
                return self._error_response(url, http_status, f'HTTP error: {http_status}')

            # Get HTML
            raw_html = response.text

            # Extract text based on site
            if site == 'legacy.com':
                extracted_text = self._extract_legacy_text(raw_html, url=url)
            else:
                return self._error_response(url, http_status, f'Unsupported site: {site}')

            if not extracted_text:
                return self._error_response(url, http_status, 'Could not extract obituary text from page')

            # Generate hashes
            url_hash = self._hash_string(url)
            content_hash = self._hash_string(extracted_text)

            return {
                'success': True,
                'url': url,
                'url_hash': url_hash,
                'content_hash': content_hash,
                'raw_html': raw_html,
                'extracted_text': extracted_text,
                'http_status_code': http_status,
                'error': None
            }

        except requests.Timeout:
            return self._error_response(url, None, 'Request timed out - please try again')

        except requests.RequestException as e:
            return self._error_response(url, None, f'Network error: {str(e)}')

        except Exception as e:
            return self._error_response(url, None, f'Unexpected error: {str(e)}')

    def _extract_legacy_text(self, html: str, url: str = None) -> Optional[str]:
        """
        Extract obituary text from Legacy.com HTML.
        Uses Playwright with undetected-playwright stealth mode via subprocess.

        Args:
            html: Raw HTML content (not used with Playwright)
            url: URL to fetch with Playwright

        Returns:
            Extracted obituary text or None
        """
        # Legacy.com requires JavaScript rendering
        # Use subprocess to avoid asyncio conflicts with FastAPI

        if not url:
            print("ERROR: URL required for Legacy.com extraction")
            return None

        try:
            import subprocess
            import os

            # Path to extractor script
            script_path = os.path.join(os.path.dirname(__file__), 'playwright_extractor.py')

            print(f"Using undetected-playwright subprocess to extract Legacy.com content from: {url}")

            # Run in subprocess with timeout
            result = subprocess.run(
                ['python3', script_path, url],
                capture_output=True,
                text=True,
                timeout=90  # Allow more time for Cloudflare challenges
            )

            # Log stderr for debugging
            if result.stderr:
                for line in result.stderr.strip().split('\n'):
                    print(f"  [Playwright] {line}")

            if result.returncode != 0:
                print(f"ERROR: Playwright extraction failed with code {result.returncode}")
                return None

            extracted_text = result.stdout.strip()

            if not extracted_text or len(extracted_text) < 100:
                print(f"ERROR: Could not extract content - site may be blocking automated access")
                print(f"TIP: Try providing the obituary_text manually in your request")
                return None

            print(f"✓ Extracted {len(extracted_text)} characters from Legacy.com")
            return extracted_text

        except subprocess.TimeoutExpired:
            print("ERROR: Page load timed out - site may be blocking automated access")
            print("TIP: Try providing the obituary_text manually in your request")
            return None

        except Exception as e:
            print(f"ERROR: Playwright extraction failed: {e}")
            print("TIP: Try providing the obituary_text manually in your request")
            import traceback
            traceback.print_exc()
            return None

    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        if not text:
            return ""

        # Remove excess whitespace
        lines = [line.strip() for line in text.split('\n')]
        lines = [line for line in lines if line]  # Remove empty lines

        return '\n'.join(lines)

    def _respect_rate_limit(self):
        """Ensure rate limit delay between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _hash_string(self, text: str) -> str:
        """Generate SHA-256 hash of string."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def _error_response(self, url: str, status: Optional[int], error: str) -> Dict:
        """Create error response."""
        return {
            'success': False,
            'url': url,
            'url_hash': self._hash_string(url),
            'content_hash': None,
            'raw_html': None,
            'extracted_text': None,
            'http_status_code': status,
            'error': error
        }

    @staticmethod
    def verify_installation():
        """
        Verify undetected-playwright is properly installed.
        Call this at startup to give clear error messages.
        """
        try:
            from playwright.sync_api import sync_playwright
            from undetected_playwright import stealth_sync
            return True
        except ImportError as e:
            print("=" * 80)
            print(f"ERROR: Required package not installed: {e}")
            print("=" * 80)
            print("To fix this:")
            print("1. Install the packages:")
            print("   pip install playwright undetected-playwright")
            print("2. Install browsers:")
            print("   playwright install chromium")
            print("=" * 80)
            return False
