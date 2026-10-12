# GetQualify Voice AI Lead Harvester 🚀

Automated, outreach-ready lead generation engine for **AI Voice Agents & Phone Automation**. 

Designed to continuously monitor internet platforms, capture high-intent inquiries from businesses and founders looking for alternatives to **Vapi**, **Bland AI**, and **Retell AI**, extract contact information, categorize buyer intent, and automatically deliver enriched leads to your **Google Sheet**.

---

## 📊 Outreach-Ready Google Sheet Columns

Every captured lead is parsed and enriched with the following 13 data points:

| # | Column Name | Description | Example |
|---|-------------|-------------|---------|
| 1 | **Platform** | Source platform | `Reddit`, `HackerNews / Web` |
| 2 | **Name / Username** | Author name or handle | `tech_founder99` |
| 3 | **Business / Company** | Extracted company or agency name | `Apex Logistics` |
| 4 | **Email** | Extracted business or personal email | `alex@apexlogistics.io` |
| 5 | **Phone Number** | Extracted contact telephone/mobile | `+1-415-555-0199` |
| 6 | **Website URL** | Extracted company or project URL | `https://apexlogistics.io` |
| 7 | **Post / Source URL** | Direct link to the inquiry or post | `https://reddit.com/r/SaaS/...` |
| 8 | **Title / Subject** | Thread title or subject line | *"Looking for a Vapi alternative with lower latency"* |
| 9 | **Lead Type / Intent** | AI classified buyer intent | `Seeking Alternative`, `Pricing / Cost Concern`, `Agency / Custom Build Request` |
| 10 | **Pain Point / Snippet** | Concise excerpt of the lead's problem | *"Currently spending $0.15/min on Bland AI and latency is killing our conversion rate..."* |
| 11 | **Recommended Outreach Hook** | Pre-generated angle for cold email/DM | *"Pitch voice agent platform directly against their current tool (highlight sub-800ms latency & 30-50% lower per-minute costs)."* |
| 12 | **Date Captured** | UTC timestamp of discovery | `2026-10-12 10:45:00 UTC` |
| 13 | **Outreach Status** | Workflow tracking status | `Ready for Outreach` |

---

## 🎯 Target Lead Niches & Keywords

The scraper continuously tracks conversations around:
* **Vapi Alternatives:** Inquiries looking for better latency, lower pricing, or switching from Vapi.
* **Bland AI Pricing & Cost:** Founders and agencies complaining about per-minute fees, billing spikes, or credit burn.
* **Retell AI & Open-Source:** Inquiries comparing voice agent frameworks and self-hosting options.
* **AI Phone Receptionist & Agency Requests:** Businesses actively looking to hire an agency or contractor to build and deploy an AI phone agent.

---

## ⚙️ Step-by-Step Setup Guide

### 1. Google Cloud Service Account Setup
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or select an existing one).
3. Navigate to **APIs & Services > Library** and enable:
   - **Google Sheets API**
   - **Google Drive API**
4. Go to **APIs & Services > Credentials** > **Create Credentials** > **Service Account**.
5. Give the service account a name (e.g., `lead-harvester-bot`) and click **Done**.
6. Click on the created service account, go to the **Keys** tab, click **Add Key > Create new key**, select **JSON**, and download the `.json` file to your computer.

### 2. Share Your Google Sheet with the Service Account
1. Open your target Google Sheet in your browser.
2. Copy the **Service Account Email** (found in your downloaded JSON as `"client_email"`, e.g. `lead-harvester-bot@your-project.iam.gserviceaccount.com`).
3. In your Google Sheet, click the green **Share** button in the top-right corner.
4. Paste the service account email and grant it **Editor** permissions.

### 3. Obtain the Google Spreadsheet ID
Look at the URL of your Google Sheet:
```text
https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                       This highlighted part is your SPREADSHEET_ID
```

### 4. Configure GitHub Repository Secrets
1. In your GitHub repository, go to **Settings > Secrets and variables > Actions**.
2. Click **New repository secret**:
   * **Name:** `SPREADSHEET_ID`
   * **Secret:** Paste your spreadsheet ID string.
3. Click **New repository secret** again:
   * **Name:** `GCP_SA_KEY`
   * **Secret:** Open your downloaded JSON key file in a text editor (Notepad, VS Code, etc.), select **all** contents (`Ctrl+A`), and paste the complete raw JSON string into the secret field.
   > ⚠️ **Important:** Do *not* paste a file path. Paste the actual JSON starting with `{"type": "service_account", ...}`.

---

## 🚀 Running the Workflow

### Automatic Daily Schedule
The scraper automatically runs every day at **04:00 UTC** via GitHub Actions (`.github/workflows/scrape_leads.yml`).

### Manual Trigger (On Demand)
1. In your GitHub repository, go to the **Actions** tab.
2. In the left sidebar, click **Run Daily Voice AI Lead Harvester**.
3. Click the **Run workflow** dropdown on the right and click the green **Run workflow** button.
4. The scraper will execute, log progress, deduplicate against existing leads in your sheet, and append new outreach-ready rows.

---

## 💻 Running Locally (Optional)

You can run the scraper locally on your machine:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables (PowerShell example)
$env:SPREADSHEET_ID="your_google_sheet_id_here"
$env:GCP_SA_KEY=Get-Content -Raw "path/to/your/service_account.json"

# 3. Run the script
python scripts/scrape_leads.py
```
