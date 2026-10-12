import os
import json
import traceback
import requests
import gspread
from google.oauth2.service_account import Credentials

def get_sheet():
    sa_json = os.environ.get("GCP_SA_KEY")
    sheet_id = os.environ.get("SPREADSHEET_ID")

    if not sa_json:
        raise ValueError("GCP_SA_KEY secret is missing in GitHub Actions")
    if not sheet_id:
        raise ValueError("SPREADSHEET_ID secret is missing in GitHub Actions")

    try:
        sa_info = json.loads(sa_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"GCP_SA_KEY is not valid JSON: {e}") from e

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_info(sa_info, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).sheet1

def scrape_leads():
    leads = []
    reddit_queries = [
        'Vapi alternative',
        'Bland AI pricing',
        'AI phone agent agency',
        'AI receptionist cost',
        'voice agent self hosted'
    ]

    headers = {"User-Agent": "web:getqualify-lead-bot:v1.0.0 (by /u/testuser)"}

    for q in reddit_queries:
        url = f"https://www.reddit.com/search.json?q={requests.utils.quote(q)}&sort=new&limit=10"
        print(f"Querying Reddit: {q}", flush=True)
        try:
            r = requests.get(url, headers=headers, timeout=15)
            print(f"Reddit Status for '{q}': {r.status_code}", flush=True)
            if r.status_code == 200:
                data = r.json()
                for post in data.get("data", {}).get("children", []):
                    p = post.get("data", {})
                    if p.get("stickied") or p.get("over_18"):
                        continue
                    leads.append([
                        "Reddit",
                        p.get("author", "N/A"),
                        p.get("title", ""),
                        f"https://reddit.com{p.get('permalink', '')}",
                        p.get("selftext", "")[:300].replace("\n", " ")
                    ])
        except Exception as e:
            print(f"Error fetching {q}: {e}", flush=True)

    return leads

def main():
    try:
        print("Scraping started...", flush=True)
        leads = scrape_leads()
        print(f"Total found leads: {len(leads)}", flush=True)

        sheet = get_sheet()
        existing_records = sheet.get_all_values()

        if not existing_records:
            sheet.append_row(["Platform", "Username", "Title", "URL", "Snippet"])
            existing_urls = set()
        else:
            existing_urls = set(row[3] for row in existing_records[1:] if len(row) > 3)

        if not leads:
            print("No lead found; testing row write...", flush=True)
            if len(existing_records) <= 1:
                sheet.append_row(["Test", "System", "Connection OK", "https://getqualify.in", "Verified Write Access"])
            return

        unique_rows = [row for row in leads if row[3] not in existing_urls]
        if unique_rows:
            sheet.append_rows(unique_rows)
            print(f"{len(unique_rows)} fresh leads added to Google Sheet.", flush=True)
        else:
            print("All leads already exist in the sheet.", flush=True)

    except Exception as e:
        print(f"FATAL ERROR: {e}", flush=True)
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
