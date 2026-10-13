# Task 5 Brief: Update Workflow & Documentation

## Goal
Update `.github/workflows/scrape_leads.yml` and `README.md` to document and support the new B2B Voice AI Lead Harvester architecture.

## Requirements
1. **File to Modify:** `.github/workflows/scrape_leads.yml`
   - Ensure the workflow runs on daily schedule (`0 4 * * *`) and on-demand (`workflow_dispatch`).
   - Validate secrets `GCP_SA_KEY` and `SPREADSHEET_ID`.
   - Add workflow description and proper job name.
2. **File to Modify:** `README.md`
   - Document the B2B architecture: Local business discovery (OpenStreetMap/Overpass) + Website & Email crawler + Voice AI pitch hook generation + Google Sheets delivery.
   - Explain the 13-column schema with concrete examples for each column.
   - Document how to customize target niches (`dental`, `medical`, `hvac`, `legal`, `autorepair`) and target metro cities.
   - Detail local execution options:
     - `python scripts/scrape_leads.py --dry-run`
     - `python scripts/scrape_leads.py --limit 10`
   - Explain Google Service Account and Google Sheets setup steps.
3. **Commit:**
   `git add README.md .github/workflows/scrape_leads.yml`
   `git commit -m "docs: document B2B Voice AI lead generation pipeline"`
