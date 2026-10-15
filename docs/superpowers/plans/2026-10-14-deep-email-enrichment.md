# Deep Contact Page Crawling & DNS/MX Email Discovery Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Boost verified email capture rate on discovered B2B local business leads from ~20% to >85% by combining aggressive multi-subpage web crawling (up to 5 subpages) with DNS MX record validation and public RDAP / mailbox synthesis.

**Architecture:**
1. **Aggressive Subpage Discovery & Parallel Crawler:** Scans homepage HTML `<a href="...">` anchors for contextual contact/team paths, falls back to common subpage conventions (`/contact-us`, `/contact`, `/about-us`, `/about`, `/team`, `/our-team`, `/staff`), and fetches up to **5 subpages** in parallel using `concurrent.futures.ThreadPoolExecutor(max_workers=5)` with bounded timeouts.
2. **Obfuscated Email Unmasking:** Detects and normalizes masked addresses (e.g. `info [at] domain [dot] com`, `contact (at) domain.com`, entity-encoded emails).
3. **DNS MX Verification & RDAP / Mailbox Synthesis:** When on-page email is absent across all 5 subpages, checks domain mail-exchange (MX) records via Cloudflare DoH (`cloudflare-dns.com/dns-query`). If active mail servers exist, queries public ICANN RDAP for registrant contacts or synthesizes canonical verified inboxes (`info@domain.com` or `contact@domain.com`).
4. **CRM-Ready Clean Format:** Synthesized emails are output cleanly as `info@company.com` (no brackets or status tags) for direct compatibility with Instantly, Smartlead, Lemlist, and CRMs.

**Tech Stack:** Python 3.11, `requests`, `BeautifulSoup4`, `urllib.parse`, `concurrent.futures`, Cloudflare DoH (`cloudflare-dns.com/dns-query`), ICANN RDAP (`rdap.org`).

## Locked Decisions (from /gsd-discuss-phase)
- **Subpage Crawl Depth:** Aggressive — up to 5 subpages with full DOM link discovery.
- **Mailbox Synthesis:** Enabled whenever the domain has confirmed active email servers (DNS MX).
- **Email Output Format:** Clean email address (e.g. `info@company.com`) without annotation tags for seamless CRM/cold outreach ingestion.
- **Privacy & Junk Protection:** Strict filter against registrar abuse (`abuse@godaddy.com`, `abuse@cloudflare.com`), whois proxy guards (`@domainsbyproxy.com`, `@contactprivacy.com`), and media files (`.png`, `.webp`, `.jpg`).
- **Zero Cost & Serverless:** 100% native to GitHub Actions; no external paid APIs or tokens required.
- **Regression Constraint:** All 63 existing unit and integration tests must remain 100% passing.

---

### Task 1: Aggressive Subpage Discovery & Parallel Contact Crawler

**Files:**
- Modify: `scripts/enrichment.py:100-248`
- Modify: `scripts/enrichment.py:365-462`
- Test: `tests/test_enrichment.py`

**Interfaces:**
- Consumes: `website_url: str`, `html: str`, `domain: str`
- Produces: `enrich_business_contact(website_url: str | None, timeout: int = 5) -> dict[str, Any]` returning enriched email, owner name, after-hours flag.

- [ ] **Step 1: Write failing tests for 5-subpage discovery and obfuscated email extraction**

Add to `tests/test_enrichment.py`:
- `test_discover_contact_subpage_urls`: tests extraction of up to 5 relevant internal URLs (`/contact-us`, `/about-us`, `/our-team`, `/staff`, `/doctors`) from homepage HTML links.
- `test_extract_obfuscated_emails`: tests `clean_email("info [at] company [dot] com")` and regex parsing of `contact (at) domain.com`.
- `test_multi_subpage_enrichment`: tests `enrich_business_contact` discovering email located only on a nested `/team` or `/contact-us` subpage.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests/test_enrichment.py`
Expected: FAIL (subpage discovery and obfuscation functions not yet implemented).

- [ ] **Step 3: Implement aggressive subpage discovery and parallel fetching in `scripts/enrichment.py`**

1. Implement `discover_contact_subpage_urls(html: str, base_url: str, max_subpages: int = 5) -> list[str]`:
   - Scans `<a href="...">` anchors for paths or link text containing `contact`, `about`, `team`, `staff`, `doctor`, `dentist`, `attorney`, `provider`, `meet`.
   - Filters out external social/tracker links (`facebook.com`, `yelp.com`, `google.com`, `instagram.com`).
   - Appends standard fallback candidates (`/contact-us`, `/contact`, `/about-us`, `/about`, `/team`, `/our-team`, `/staff`) if anchors are few.
   - Limits to the top 5 unique subpages.
2. Expand `clean_email` and `extract_emails_from_html`:
   - Add regex pattern for obfuscated email formats (`[at]`, `(at)`, `\sat\s`, `[dot]`, `(dot)`, `\sdot\s`).
   - Decode and normalize to clean RFC email strings.
3. In `enrich_business_contact`:
   - If homepage produces no email or owner, dispatch `ThreadPoolExecutor(max_workers=5)` across discovered subpages with a bounded 3.5s timeout.
   - Aggregate all emails and owner names discovered across subpages.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests/test_enrichment.py`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add scripts/enrichment.py tests/test_enrichment.py
git commit -m "feat: implement aggressive subpage discovery and parallel contact crawler"
```

---

### Task 2: DNS MX Record Verification & Public RDAP / Mailbox Synthesis

**Files:**
- Modify: `scripts/enrichment.py`
- Test: `tests/test_enrichment.py`

**Interfaces:**
- Produces:
  - `check_domain_mx_records(domain: str, timeout: float = 3.0) -> bool`
  - `fetch_rdap_contact_email(domain: str, timeout: float = 3.0) -> str | None`
  - `synthesize_verified_mailbox(domain: str) -> str | None`

- [ ] **Step 1: Write failing tests for MX check, RDAP parser, and mailbox synthesis**

Add to `tests/test_enrichment.py`:
- `test_check_domain_mx_records_active`: mock Cloudflare DoH returning status 0 with MX answers -> returns `True`.
- `test_check_domain_mx_records_inactive`: mock DoH returning NXDOMAIN / empty answers -> returns `False`.
- `test_fetch_rdap_contact_email`: mock RDAP JSON with entity contact email -> returns clean email without privacy proxy noise.
- `test_enrich_business_contact_mx_synthesis`: when website returns no on-page email but domain MX is active, fallback yields clean `info@{domain}`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests/test_enrichment.py`
Expected: FAIL.

- [ ] **Step 3: Implement MX validation and RDAP lookup in `scripts/enrichment.py`**

1. Implement `check_domain_mx_records(domain: str, timeout: float = 3.0) -> bool`:
   - Uses zero-pip DoH: `requests.get("https://cloudflare-dns.com/dns-query", params={"name": domain, "type": "MX"}, headers={"Accept": "application/dns-json"}, timeout=timeout)`.
   - Returns `True` if `Answer` contains records with type 15 (MX).
   - Graceful fallback: return `False` on any timeout or failure.
2. Implement `fetch_rdap_contact_email(domain: str, timeout: float = 3.0) -> str | None`:
   - Fetches `https://rdap.org/domain/{domain}`.
   - Parses `entities` vcard `email` fields.
   - Strictly ignores privacy protection proxies (`@contactprivacy.com`, `@domainsbyproxy.com`, `@whoisguard.com`, `@registrar.com`, `abuse@`).
3. In `enrich_business_contact`:
   - If `all_emails` is empty after homepage and 5 subpages:
     - Check `has_mx = check_domain_mx_records(domain)`.
     - If `has_mx`:
       - Attempt `rdap_email = fetch_rdap_contact_email(domain)`.
       - If `rdap_email`: use it.
       - Otherwise, synthesize canonical clean `info@{domain}`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests/test_enrichment.py`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add scripts/enrichment.py tests/test_enrichment.py
git commit -m "feat: implement DNS MX validation and public RDAP mailbox synthesis"
```

---

### Task 3: Pipeline Integration, High-Email Yield Benchmarking & Verification

**Files:**
- Modify: `scripts/scrape_leads.py`
- Modify: `tests/test_integration.py`
- Modify: `README.md`

- [ ] **Step 1: Write integration test validating improved email capture**

In `tests/test_integration.py`:
- Test that `scrape_leads` with multi-subpage websites and active MX records yields valid emails for $\ge 85\%$ of leads.

- [ ] **Step 2: Run full test suite across codebase**

Run: `python -m unittest discover tests`
Expected: All tests pass.

- [ ] **Step 3: Run live dry-run benchmark**

Run: `python scripts/scrape_leads.py --dry-run --limit 10`
Verify in terminal that $\ge 8$ out of 10 leads have populated `Email` fields (e.g. `contact@...`, `dr...@...`, `info@...`).

- [ ] **Step 4: Update Documentation in `README.md`**

Document the new email discovery architecture:
- Aggressive subpage crawler (up to 5 subpages).
- Obfuscated email unmasking.
- DNS MX validation + RDAP mailbox synthesis.

- [ ] **Step 5: Commit and Push to GitHub**

```bash
git add scripts/scrape_leads.py tests/test_integration.py README.md
git commit -m "feat: complete aggressive subpage email crawler and DNS MX verification"
git push origin main
```
