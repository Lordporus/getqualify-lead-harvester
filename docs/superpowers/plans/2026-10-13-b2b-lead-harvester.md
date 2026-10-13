# B2B Voice AI Lead Harvester Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the scraper into an industry-grade B2B lead generation engine that discovers high-call-volume local and service businesses, enriches their verified contact info (Business Name, Phone Number, Website, Email, Owner/Contact), generates niche-specific Voice AI pitch hooks, and delivers deduplicated, outreach-ready leads to Google Sheets.

**Architecture:** Replace brittle forum text searches with a 3-stage B2B pipeline: (1) Free local business directory querying (OpenStreetMap / Overpass API & public business endpoints) targeting high-call niches (Dentists, Medspas, HVAC, Law Firms, Auto Repair, Real Estate); (2) Automated website enrichment to extract verified emails (`info@`, `contact@`, `owner@`) and contact names from `/contact` and `/about` pages; (3) Niche-specific Voice AI outreach hook generation and deduplicated batch write to Google Sheets.

**Tech Stack:** Python 3.11, `requests`, `gspread`, `google-auth`, `re`, `urllib`, GitHub Actions workflow.

**Spec:** Option 1 architecture agreed with user.

## Global Constraints
- Zero reliance on paid third-party scraper subscriptions or APIs (runs 100% free on public endpoints & Google Service Account).
- Output must strictly populate all 13 columns in the user's existing Google Sheet schema with zero junk/regex noise.
- Every lead row must contain a valid Business Name, direct Phone Number, and Website URL, with email enrichment prioritized.
- Must execute reliably within GitHub Actions without 403 cloud IP blocks.
- Deduplication must check both Phone Number and Website URL against existing Google Sheet records.

## Review Focus
1. **Empty/Non-responsive Websites:** Target business websites that timeout or fail to resolve must not crash the crawler; they should fall back cleanly with domain and phone preserved.
2. **Email False Positives:** Avoid capturing generic image/file extensions or third-party tracking emails (e.g. `sentry@`, `wixpress@`, `example@`, `.png`).
3. **Overpass / Directory Rate Limits:** Requests to business directory APIs must use modest batch sizes (e.g., 20–30 per niche) with proper headers and timeouts.
4. **Phone Formatting:** Raw telephone strings from international or local formats must be normalized into readable telephone format (e.g. `+1 (512) 555-0199`).
5. **Google Sheets Quota & Deduplication:** Avoid duplicate rows on consecutive daily runs by checking both column 5 (Phone) and column 6 (Website).

---

### Task 1: B2B Business Discovery Engine (`scripts/b2b_discovery.py`)

**Files:**
- Create: `scripts/b2b_discovery.py`
- Test: `tests/test_b2b_discovery.py`

**Interfaces:**
- Produces: `fetch_niche_businesses(niche_key: str, city: str, limit: int = 15) -> list[dict]`
  Returns dicts with keys: `{"business_name", "phone", "website", "city", "niche", "category"}`.

- [ ] **Step 1: Write test for `fetch_niche_businesses`**
```python
# tests/test_b2b_discovery.py
from scripts.b2b_discovery import normalize_phone, fetch_niche_businesses

def test_normalize_phone():
    assert normalize_phone("5125550199") == "+1 (512) 555-0199"
    assert normalize_phone("+1-512-555-0199") == "+1 (512) 555-0199"

def test_fetch_niche_businesses_schema():
    results = fetch_niche_businesses("dental", "Austin", limit=3)
    assert isinstance(results, list)
    if results:
        lead = results[0]
        assert "business_name" in lead
        assert "phone" in lead
        assert "website" in lead
```

- [ ] **Step 2: Run test to verify it fails initially**
Run: `python -m unittest tests/test_b2b_discovery.py`
Expected: FAIL with ModuleNotFoundError or ImportError

- [ ] **Step 3: Implement `scripts/b2b_discovery.py`**
Implement phone normalizer and Overpass/OSM public API query builder targeting high-call niches:
- Dental clinics (`amenity=dentist`)
- Doctors/Clinics (`amenity=doctors` or `amenity=clinic`)
- HVAC/Plumbers (`craft=plumber` or `craft=hvac`)
- Lawyers/Legal (`office=lawyer`)
- Car repair (`shop=car_repair`)
Filter for entities that have `name`, `phone` (or `contact:phone`), and `website` (or `contact:website`).

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_b2b_discovery.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/b2b_discovery.py tests/test_b2b_discovery.py
git commit -m "feat: implement B2B local business discovery engine"
```

---

### Task 2: Website Email & Owner Enrichment Engine (`scripts/enrichment.py`)

**Files:**
- Create: `scripts/enrichment.py`
- Test: `tests/test_enrichment.py`

**Interfaces:**
- Consumes: `website: str`
- Produces: `enrich_business_contact(website_url: str) -> dict`
  Returns `{"email": str, "owner_name": str, "has_after_hours_notice": bool}`.

- [ ] **Step 1: Write test for `enrich_business_contact`**
```python
# tests/test_enrichment.py
from scripts.enrichment import extract_emails_from_html, clean_email

def test_extract_emails_from_html():
    html = """<html><body>Contact us at info@austindental.com or call our office. Support: drsmith@austindental.com</body></html>"""
    emails = extract_emails_from_html(html, "austindental.com")
    assert "info@austindental.com" in emails or "drsmith@austindental.com" in emails

def test_clean_email_filters_junk():
    assert clean_email("image@2x.png") is None
    assert clean_email("wix@wixpress.com") is None
    assert clean_email("contact@austindental.com") == "contact@austindental.com"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_enrichment.py`
Expected: FAIL

- [ ] **Step 3: Implement `scripts/enrichment.py`**
Implement HTTP crawler with 6-second timeout for homepage and `/contact` page:
- Uses standard Chrome user-agent
- Extracts `mailto:` links and regex patterns for emails
- Filters out image assets, trackers, and CMS templates
- Extracts possible owner/doctor names from header/about blocks

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_enrichment.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/enrichment.py tests/test_enrichment.py
git commit -m "feat: implement website contact and email enrichment"
```

---

### Task 3: Voice AI Pitch Hook & Value Proposition Generator (`scripts/hooks.py`)

**Files:**
- Create: `scripts/hooks.py`
- Test: `tests/test_hooks.py`

**Interfaces:**
- Consumes: `niche: str`, `business_name: str`, `city: str`
- Produces: `generate_voice_ai_hook(niche: str, business_name: str, city: str) -> tuple[str, str, str]`
  Returns `(lead_type, pain_point_snippet, recommended_hook)`

- [ ] **Step 1: Write test for `generate_voice_ai_hook`**
```python
# tests/test_hooks.py
from scripts.hooks import generate_voice_ai_hook

def test_generate_dental_hook():
    lead_type, snippet, hook = generate_voice_ai_hook("dental", "Apex Dental", "Austin")
    assert "Dental" in lead_type or "Appointment" in lead_type
    assert "Apex Dental" in snippet or "Apex Dental" in hook
    assert "receptionist" in hook.lower() or "after-hours" in hook.lower()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_hooks.py`
Expected: FAIL

- [ ] **Step 3: Implement `scripts/hooks.py`**
Map target business niches to high-converting Voice AI outreach angles:
- **Dental/Medical:** Inbound call volume, after-hours appointment scheduling, emergency triage.
- **HVAC/Plumbing:** Emergency 24/7 service dispatch, capturing customer calls during peak seasons before they call a competitor.
- **Law Firms:** 24/7 instant client pre-qualification, eliminating receptionist telephone tag.
- **Auto Repair:** Automated status update lines and service estimate intake.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_hooks.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/hooks.py tests/test_hooks.py
git commit -m "feat: implement niche-specific Voice AI pitch hook generator"
```

---

### Task 4: Integrate Pipeline into `scripts/scrape_leads.py` & Update Google Sheets Schema

**Files:**
- Modify: `scripts/scrape_leads.py`
- Test: End-to-end integration test

**Interfaces:**
- Integrates `fetch_niche_businesses`, `enrich_business_contact`, and `generate_voice_ai_hook` into the main execution cycle.
- Populates all 13 Google Sheet columns:
  `[Platform, Name / Username, Business / Company, Email, Phone Number, Website URL, Post / Source URL, Title / Subject, Lead Type / Intent, Pain Point / Snippet, Recommended Outreach Hook, Date Captured, Outreach Status]`
- Deduplicates on both Phone Number and Website URL.

- [ ] **Step 1: Update `scripts/scrape_leads.py` with multi-niche rotation and enrichment**
Replace forum scraping with B2B business discovery across target cities and niches.
- [ ] **Step 2: Verify dry-run with local execution**
Run: `python scripts/scrape_leads.py --dry-run` or test run function in Python.
Verify lead output has valid Company, Phone, Website, and Email.
- [ ] **Step 3: Commit and push**
```bash
git add scripts/scrape_leads.py
git commit -m "feat: integrate B2B business discovery and website enrichment into main pipeline"
git push origin main
```

---

### Task 5: Update Workflow & Documentation

**Files:**
- Modify: `README.md`
- Modify: `.github/workflows/scrape_leads.yml`

- [ ] **Step 1: Update README.md with B2B setup, niche customization, and city configuration**
- [ ] **Step 2: Trigger workflow dispatch on GitHub to verify end-to-end production execution**
Run: `gh workflow run scrape_leads.yml --repo Lordporus/getqualify-lead-harvester`
Verify execution completes with status 0 and writes enriched B2B leads to the Google Sheet.
- [ ] **Step 3: Commit and push**
```bash
git add README.md .github/workflows/scrape_leads.yml
git commit -m "docs: document B2B Voice AI lead generation pipeline"
git push origin main
```
