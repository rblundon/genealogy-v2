#!/usr/bin/env python3
"""
Standalone Playwright extractor script with undetected-playwright stealth.
Called via subprocess to avoid asyncio conflicts.

Usage: python playwright_extractor.py <url>
Output: Extracted text on stdout, errors on stderr
"""

import sys
import re


def clean_legacy_obituary(text: str) -> str:
    """
    Clean up Legacy.com obituary text by finding the actual obituary content.

    Strategy:
    1. Look for the obituary by finding text that starts with "Lastname, Firstname" pattern
    2. Extract the continuous content containing obituary keywords
    3. Stop at junk markers

    Args:
        text: Raw extracted text

    Returns:
        Cleaned obituary text
    """
    # Normalize whitespace but preserve some structure
    # Replace multiple spaces/tabs with single space, but keep newlines for structure
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Find obituary start - look for "Lastname, Firstname" pattern
    # This matches: "Blundon, Patricia L." or "Smith, John" etc.
    name_pattern = r'([A-Z][a-z]+,\s+[A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+"[^"]+")?\s*(?:\((?:Nee|nee|née)\s+[A-Z][a-z]+\))?)'

    # Junk markers - stop extracting when we hit these
    junk_markers = [
        'search by name',
        'sign the guest book',
        'send flowers',
        'get email updates',
        'memories and condolences',
        'not sure what to say',
        'add a photo',
        'how you can show support',
        'make a donation',
        'recent obituaries',
        'how to support',
        'plant a tree',
        'plant trees',
        'privacy policy',
        'terms of use',
        'submit an obituary',
        'order digital guest book',
        'showing results',
        'your email will not',
        'how do you know',
        'dedicate a star',
        'donate to charity',
        'more ways to support',
        'light a candle',
        'write a memory',
        'leave a message',
        'the best poems',
        'share your condolences',
        'what to say',
        'find an obituary',
        'grief support',
        'advertisement',
        'sponsored',
    ]

    # Obituary content indicators - the real obituary will have several of these
    content_indicators = [
        'passed away', 'passed on', 'died', 'departed',
        'survived by', 'preceded in death', 'predeceased',
        'beloved', 'loving', 'cherished', 'devoted', 'dear',
        'husband', 'wife', 'father', 'mother', 'son', 'daughter',
        'brother', 'sister', 'grandmother', 'grandfather',
        'funeral', 'memorial', 'visitation', 'interment', 'cemetery',
        'funeral home', 'in lieu of flowers',
        'age of', 'years old', 'at the age',
        '(nee', '(née',
    ]

    # Find all positions where name pattern appears
    name_matches = list(re.finditer(name_pattern, text))

    best_obituary = None
    best_score = 0

    for match in name_matches:
        start_pos = match.start()

        # Extract text from this position
        candidate = text[start_pos:]

        # Find where to stop - look for junk markers
        end_pos = len(candidate)
        for junk in junk_markers:
            junk_pos = candidate.lower().find(junk)
            if junk_pos != -1 and junk_pos < end_pos:
                end_pos = junk_pos

        # Also stop at very short lines that look like navigation
        lines = candidate[:end_pos].split('\n')
        clean_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Skip very short lines that look like nav items
            if len(line) < 20 and not any(ind in line.lower() for ind in content_indicators):
                if clean_lines:  # Only stop if we have content
                    break
            clean_lines.append(line)

        candidate = ' '.join(clean_lines)

        # Clean up the candidate
        candidate = re.sub(r'\s+', ' ', candidate).strip()

        # Score this candidate
        lower_candidate = candidate.lower()
        score = sum(1 for ind in content_indicators if ind in lower_candidate)

        # Must have enough content indicators and reasonable length
        if score >= 3 and 200 < len(candidate) < 5000 and score > best_score:
            best_score = score
            best_obituary = candidate

    if best_obituary:
        return best_obituary

    # Fallback: try to extract any contiguous text with obituary keywords
    # Split into lines and find a run of lines containing keywords
    lines = text.split('\n')
    in_obituary = False
    obituary_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        lower_line = line.lower()

        # Check for junk
        is_junk = any(junk in lower_line for junk in junk_markers)
        if is_junk:
            if in_obituary:
                break  # End of obituary
            continue

        # Check for obituary content
        has_indicator = any(ind in lower_line for ind in content_indicators)

        if has_indicator or (in_obituary and len(line) > 30):
            in_obituary = True
            obituary_lines.append(line)
        elif in_obituary and len(obituary_lines) > 3:
            # Already have good content, this might be the end
            break

    if obituary_lines and len(' '.join(obituary_lines)) > 200:
        return ' '.join(obituary_lines)

    return ""


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

        # Legacy.com-specific selectors (in priority order)
        selectors = [
            # Try to find the actual obituary body FIRST
            'div.obituary-text',
            'div.obit-text',
            'div[itemprop="description"]',
            '#obituaryText',
            'article[itemprop="articleBody"]',
            '[data-testid="obituary-text"]',
            '[data-test="obituary-text"]',

            # Fallback to broader containers
            'article.obituary',
            'main article',

            # Last resort - but these need aggressive cleaning
            'article',
            'main',
            'body',
        ]

        # Obituary indicators to validate content
        obituary_indicators = [
            'passed away',
            'died',
            'survived by',
            'preceded in death',
            'beloved',
            'loving',
            'cherished',
        ]

        text = None
        fallback_text = None

        for selector in selectors:
            try:
                element = page.query_selector(selector)
                if not element:
                    continue

                candidate_text = element.inner_text()

                if not candidate_text or len(candidate_text) < 100:
                    continue

                lower_text = candidate_text.lower()

                # Must contain at least 2 indicators to be considered obituary
                indicator_count = sum(1 for indicator in obituary_indicators if indicator in lower_text)

                if indicator_count >= 2:
                    text = candidate_text
                    print(f"  ✓ Extracted {len(text)} chars using: {selector}", file=sys.stderr)
                    print(f"  ✓ Found {indicator_count} obituary indicators", file=sys.stderr)
                    break
                else:
                    # Save as fallback if no better option found
                    if not fallback_text and len(candidate_text) > 200:
                        fallback_text = candidate_text
                        print(f"  ⚠ Selector '{selector}' found {len(candidate_text)} chars but only {indicator_count} indicators, saving as fallback...", file=sys.stderr)

            except Exception as e:
                print(f"  ⚠ Selector '{selector}' failed: {e}", file=sys.stderr)
                continue

        # Use fallback if no text with indicators was found
        if not text and fallback_text:
            text = fallback_text
            print(f"  ⚠ Using fallback text ({len(text)} chars) - insufficient obituary indicators", file=sys.stderr)

        context.close()
        browser.close()

        if not text or len(text) < 100:
            print(f"ERROR: Could not extract content (got {len(text) if text else 0} chars)", file=sys.stderr)
            return ""

        # Clean up the extracted text
        cleaned_text = clean_legacy_obituary(text)
        print(f"  ✓ Final cleaned text: {len(cleaned_text)} characters", file=sys.stderr)

        # Debug: show cleaned text preview
        if cleaned_text:
            print(f"  [DEBUG] Cleaned preview (first 300 chars): {cleaned_text[:300]}", file=sys.stderr)
            print(f"  [DEBUG] Cleaned preview (last 200 chars): ...{cleaned_text[-200:]}", file=sys.stderr)
        else:
            print(f"  [DEBUG] Cleaned text is empty!", file=sys.stderr)
            # Show raw text around likely obituary start
            name_match = re.search(r'[A-Z][a-z]+,\s+[A-Z][a-z]+', text)
            if name_match:
                start = max(0, name_match.start() - 20)
                end = min(len(text), name_match.start() + 500)
                print(f"  [DEBUG] Raw text near name pattern: {text[start:end]}", file=sys.stderr)
            else:
                print(f"  [DEBUG] Raw text preview: {text[:500]}", file=sys.stderr)

        return cleaned_text


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
