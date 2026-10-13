# Task 2 Brief: Website Email & Owner Enrichment Engine

## Goal
Implement `scripts/enrichment.py` to crawl the public websites of discovered businesses (`/`, `/contact`, `/about`) to extract verified business email addresses and owner/manager names, eliminating `N/A` fields.

## Requirements
1. **File to Create:** `scripts/enrichment.py`
2. **Test File to Create:** `tests/test_enrichment.py`
3. **Functions to Implement:**
   - `clean_email(email_str: str) -> str | None`:
     Filters out false positives:
     - Image file patterns: `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp` (e.g. `logo@2x.png`)
     - Platform trackers / CMS junk: `wixpress.com`, `sentry.io`, `example.com`, `domain.com`, `email.com`, `wix.com`, `wordpress.org`, `cloudflare.com`
     - Returns valid lowercase email or `None`.
   - `extract_emails_from_html(html: str, domain: str = "") -> list[str]`:
     Parses `mailto:` links and runs email regex across raw HTML.
     Deduplicates and sorts priority to business domain emails (matching `domain`) and standard operational addresses (`info@`, `contact@`, `office@`, `appointments@`, `support@`).
   - `extract_owner_name_from_html(html: str) -> str`:
     Extracts practitioner or business owner names (e.g., "Dr. [Name]", "Founder", "Owner", "Practice Manager") using regex and clean text parsing. Returns "N/A" if not found.
   - `enrich_business_contact(website_url: str, timeout: int = 6) -> dict`:
     Fetches homepage and `/contact` page with a polite timeout (5-6s) and standard Chrome user agent.
     Returns:
     ```python
     {
         "email": str,              # e.g. "contact@austindental.com" or "N/A"
         "owner_name": str,         # e.g. "Dr. Sarah Miller" or "N/A"
         "has_after_hours_notice": bool
     }
     ```
     Gracefully catches timeouts, SSL errors, and connection drops, returning fallback without raising unhandled exceptions.
4. **Tests:**
   - Unit tests for `clean_email` verifying it rejects image extensions and placeholder domains.
   - Unit tests for `extract_emails_from_html` verifying `mailto:` and body email extraction.
   - Unit tests for `extract_owner_name_from_html`.
   - Mock test for `enrich_business_contact` verifying return dictionary structure and error resilience.
5. **Validation:**
   Run tests with `python -m unittest tests/test_enrichment.py`.
6. **Commit:**
   `git add scripts/enrichment.py tests/test_enrichment.py`
   `git commit -m "feat: implement website contact and email enrichment"`
