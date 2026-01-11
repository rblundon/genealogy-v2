#!/usr/bin/env python3
"""
Standalone Playwright extractor script with undetected-playwright stealth.
Called via subprocess to avoid asyncio conflicts.

Usage: python playwright_extractor.py <url>
Output: Extracted text on stdout, errors on stderr
"""

import sys


def extract_legacy_text(url: str) -> str:
    """Extract obituary text from Legacy.com using Playwright with stealth mode."""
    from playwright.sync_api import sync_playwright
    from undetected_playwright import stealth_sync

    print(f"Extracting content from: {url}", file=sys.stderr)
    print("Using undetected-playwright stealth mode", file=sys.stderr)

    with sync_playwright() as p:
        # Launch with stealth settings to avoid bot detection
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage'
            ]
        )

        # Create context with realistic settings
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            }
        )

        # Apply stealth mode to bypass bot detection
        context = stealth_sync(context)

        page = context.new_page()

        # Navigate to page - use 'load' instead of 'networkidle' to avoid timeout
        print(f"Navigating to page...", file=sys.stderr)
        response = page.goto(url, wait_until='load', timeout=30000)

        if response:
            print(f"HTTP Status: {response.status}", file=sys.stderr)

        # Wait for JavaScript to render
        import time
        time.sleep(3)

        # Check for Cloudflare challenge page
        title = page.title()
        if 'Just a moment' in title or 'Cloudflare' in title:
            print(f"WARNING: Cloudflare challenge detected, waiting longer...", file=sys.stderr)
            time.sleep(10)
            # Try reloading
            page.reload(wait_until='load', timeout=30000)
            time.sleep(3)
            title = page.title()
            if 'Just a moment' in title or 'Cloudflare' in title:
                print(f"ERROR: Still blocked by Cloudflare after retry", file=sys.stderr)
                context.close()
                browser.close()
                return ""

        # Wait for obituary content to load
        try:
            page.wait_for_selector('article, .obituary-text, [data-test="obituary-text"]', timeout=15000)
        except:
            print("Warning: Could not find expected obituary selectors", file=sys.stderr)

        # Try specific selectors
        selectors = [
            'article',
            '[data-testid="obituary-text"]',
            '[data-test="obituary-text"]',
            '.obituary-text',
            '.obit-text',
            '#obituaryText',
            'main article',
            'main',
            'body'  # Fallback
        ]

        text = None
        for selector in selectors:
            try:
                element = page.query_selector(selector)
                if element:
                    text = element.inner_text()
                    if text and len(text) > 200:  # Require meaningful content
                        print(f"Extracted {len(text)} chars using: {selector}", file=sys.stderr)
                        break
            except:
                continue

        context.close()
        browser.close()

        if not text or len(text) < 100:
            print(f"ERROR: Could not extract content (got {len(text) if text else 0} chars)", file=sys.stderr)
            return ""

        # Clean text
        lines = [line.strip() for line in text.split('\n')]
        lines = [line for line in lines if line]
        return '\n'.join(lines)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: playwright_extractor.py <url>", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]

    try:
        result = extract_legacy_text(url)
        print(result)  # Output to stdout
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
