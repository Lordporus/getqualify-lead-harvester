# Task 4 Brief: Integrate Pipeline into `scripts/scrape_leads.py` & Update Google Sheets Schema

## Goal
Integrate the B2B discovery engine (`scripts/b2b_discovery.py`), enrichment engine (`scripts/enrichment.py`), and Voice AI hook generator (`scripts/hooks.py`) into `scripts/scrape_leads.py`. Connect the end-to-end flow to Google Sheets with robust deduplication.

## Requirements
1. **File to Modify:** `scripts/scrape_leads.py`
2. **Integration Flow:**
   - In `scrape_leads()`:
     - Iterates through target niches: `dental`, `medical`, `hvac`, `legal`, `autorepair`.
     - Rotates target metro cities (e.g., `"Austin"`, `"Dallas"`, `"Miami"`, `"Phoenix"`, `"Atlanta"`).
     - Calls `fetch_niche_businesses(niche, city, limit=5)`.
     - For each business discovered:
       - Calls `enrich_business_contact(website)`.
       - Calls `generate_voice_ai_hook(niche, business_name, city)`.
       - Constructs lead row with all 13 columns:
         1. `Platform`: `"B2B Directory / Web"`
         2. `Name / Username`: Owner/Doctor name if found, else `"Practice / Business Manager"`
         3. `Business / Company`: Real company name
         4. `Email`: Enriched business email or `"N/A"`
         5. `Phone Number`: Direct formatted phone number
         6. `Website URL`: Verified website URL
         7. `Post / Source URL`: Website URL or directory record
         8. `Title / Subject`: Industry & location, e.g. `"Dental Practice - Austin, TX"`
         9. `Lead Type / Intent`: Niche-specific operational call role
         10. `Pain Point / Snippet`: Concrete call bottleneck statement
         11. `Recommended Outreach Hook`: Personalized cold email / cold call pitch
         12. `Date Captured`: UTC timestamp string
         13. `Outreach Status`: `"Ready for Outreach"`
   - Deduplication:
     - Maintains index of existing Phone Numbers (Col 5) and Websites (Col 6).
     - Skips any newly scraped business whose phone or website already exists in the Google Sheet.
   - CLI Support:
     - Add support for `--dry-run` argument so the script can be tested locally without needing `GCP_SA_KEY` or `SPREADSHEET_ID`.
3. **Tests:**
   - Create `tests/test_integration.py` to test end-to-end lead row generation and deduplication logic.
4. **Validation:**
   - Run `python -m unittest tests/test_integration.py`.
   - Run `python scripts/scrape_leads.py --dry-run` and verify that 5-10 enriched B2B leads are generated with real business names, phones, and websites.
5. **Commit:**
   `git add scripts/scrape_leads.py tests/test_integration.py`
   `git commit -m "feat: integrate B2B business discovery and enrichment into main pipeline"`
