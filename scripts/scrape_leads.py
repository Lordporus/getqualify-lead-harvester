import os
import json
import base64
import re
import traceback
from datetime import datetime, timezone
import requests
import gspread
from google.oauth2.service_account import Credentials

# Outreach-ready Google Sheet Columns
SHEET_HEADERS = [
    "Platform",
    "Name / Username",
    "Business / Company",
    "Email",
    "Phone Number",
    "Website URL",
    "Post / Source URL",
    "Title / Subject",
    "Lead Type / Intent",
    "Pain Point / Snippet",
    "Recommended Outreach Hook",
    "Date Captured",
    "Outreach Status"
]

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
PHONE_REGEX = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}')
URL_REGEX = re.compile(r'https?://(?:www\.)?([a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+)(/[^\s)\]]*)?')

def extract_contact_info(text: str) -> dict:
    """Extract email, phone, and external website from text."""
    emails = EMAIL_REGEX.findall(text)
    phones = PHONE_REGEX.findall(text)
    
    # Filter valid phone candidates (minimum 10 digits)
    valid_phones = [p.strip() for p in phones if len(re.sub(r'\D', '', p)) >= 10]
    
    urls = URL_REGEX.findall(text)
    excluded_domains = {
        'reddit.com', 'redd.it', 'twitter.com', 'x.com', 'github.com', 
        'youtube.com', 'ycombinator.com', 'google.com', 't.co', 'preview.redd.it'
    }
    external_websites = []
    for domain, path in urls:
        if domain.lower() not in excluded_domains:
            full_url = f"https://{domain}{path}"
            external_websites.append(full_url)
            
    return {
        "email": emails[0] if emails else "N/A",
        "phone": valid_phones[0] if valid_phones else "N/A",
        "website": external_websites[0] if external_websites else "N/A"
    }

def extract_business_name(title: str, text: str, author: str) -> str:
    """Heuristic extraction of company or agency name."""
    combined = f"{title} {text}"
    patterns = [
        r'(?:our company|my company|our agency|my agency|our business|my startup|at)\s+([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)?)',
        r'(?:we run|we build|founder of|co-founder of|CEO of)\s+([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)?)',
        r'company named\s+([A-Z][A-Za-z0-9]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            cand = match.group(1).strip()
            if cand.lower() not in {"reddit", "vapi", "bland", "retell", "the", "a", "an", "our", "my", "ai"}:
                return cand
    return "N/A"

def classify_lead_intent(title: str, text: str) -> tuple[str, str]:
    """Classifies the buyer intent and suggests a customized outreach hook."""
    combined = (f"{title} {text}").lower()
    
    if any(k in combined for k in ["alternative", "switch", "replace", "vs", "better than", "moved away from", "leaving"]):
        return (
            "Seeking Alternative",
            "Pitch voice agent platform directly against their current tool (highlight sub-800ms latency, 99.9% uptime & 30-50% lower per-minute costs)."
        )
    elif any(k in combined for k in ["pricing", "price", "cost", "expensive", "credit", "bill", "rates", "per minute", "overcharge"]):
        return (
            "Pricing / Cost Concern",
            "Offer transparent per-minute pricing or volume discounts to dramatically slash their current voice AI bill."
        )
    elif any(k in combined for k in ["hire", "agency", "build for", "contractor", "freelancer", "looking for someone to build", "quote"]):
        return (
            "Agency / Custom Build Request",
            "High-intent inbound request. Propose turnkey AI phone agent agency build with quick 3-day demo deployment."
        )
    elif any(k in combined for k in ["self-host", "self host", "open source", "local", "livekit", "asterisk", "freeswitch"]):
        return (
            "Self-Hosted / Tech Stack",
            "Present developer-friendly voice infrastructure or managed enterprise alternative to eliminate maintenance overhead."
        )
    else:
        return (
            "General Voice AI Interest",
            "Reach out asking about their current call handling bottlenecks and offer an interactive live demo phone call."
        )

def get_sheet():
    """Authenticates with Google Sheets using GCP_SA_KEY and SPREADSHEET_ID."""
    sa_json = os.environ.get("GCP_SA_KEY", "")
    sheet_id = os.environ.get("SPREADSHEET_ID", "")

    if not sa_json or not sa_json.strip():
        raise ValueError(
            "GCP_SA_KEY secret is missing or empty in GitHub Actions. "
            "Please go to Repository Settings -> Secrets and variables -> Actions, and add GCP_SA_KEY."
        )
    if not sheet_id or not sheet_id.strip():
        raise ValueError(
            "SPREADSHEET_ID secret is missing or empty in GitHub Actions. "
            "Please go to Repository Settings -> Secrets and variables -> Actions, and add SPREADSHEET_ID."
        )

    sa_json = sa_json.strip()
    sheet_id = sheet_id.strip()

    # Unwrap potential enclosing quotes
    if (sa_json.startswith('"') and sa_json.endswith('"')) or (sa_json.startswith("'") and sa_json.endswith("'")):
        sa_json = sa_json[1:-1].strip()

    sa_info = None
    # 1. Try direct JSON parsing
    try:
        sa_info = json.loads(sa_json)
        print("Successfully parsed GCP_SA_KEY as raw JSON.", flush=True)
    except json.JSONDecodeError as direct_err:
        # 2. Try Base64 decoding fallback
        try:
            decoded_bytes = base64.b64decode(sa_json)
            decoded_str = decoded_bytes.decode("utf-8")
            sa_info = json.loads(decoded_str)
            print("Successfully decoded and parsed GCP_SA_KEY from Base64.", flush=True)
        except Exception:
            preview = sa_json[:20] + "..." if len(sa_json) > 20 else sa_json
            raise ValueError(
                f"GCP_SA_KEY is neither valid JSON nor valid Base64 JSON.\n"
                f"Received length={len(sa_json)} characters. Preview='{preview}'.\n"
                f"JSON Error: {direct_err}.\n"
                f"Please ensure you copied the entire contents of your Google Cloud Service Account JSON key."
            ) from direct_err

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_info(sa_info, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).sheet1

def scrape_reddit_leads() -> list[list]:
    """Scrapes voice AI leads from Reddit search API."""
    leads = []
    queries = [
        'Vapi alternative',
        'Bland AI pricing',
        'Bland AI alternative',
        'Retell AI alternative',
        'AI phone agent agency',
        'AI receptionist cost',
        'AI cold calling agent',
        'voice agent self hosted',
        'AI receptionist for small business'
    ]

    headers = {"User-Agent": "web:getqualify-voiceai-harvester:v2.0 (by /u/voiceleadbot)"}
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    for q in queries:
        url = f"https://www.reddit.com/search.json?q={requests.utils.quote(q)}&sort=new&limit=15"
        print(f"[Reddit] Searching: '{q}'", flush=True)
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                for post in data.get("data", {}).get("children", []):
                    p = post.get("data", {})
                    if p.get("stickied") or p.get("over_18"):
                        continue
                    
                    author = p.get("author", "N/A")
                    title = p.get("title", "").strip()
                    permalink = p.get("permalink", "")
                    post_url = f"https://reddit.com{permalink}" if permalink else ""
                    selftext = p.get("selftext", "")
                    clean_snippet = selftext[:400].replace("\n", " ").strip()
                    if not clean_snippet:
                        clean_snippet = title

                    # Enrich lead details
                    contact_info = extract_contact_info(f"{title} {selftext}")
                    business_name = extract_business_name(title, selftext, author)
                    lead_type, outreach_hook = classify_lead_intent(title, clean_snippet)

                    leads.append([
                        "Reddit",
                        author,
                        business_name,
                        contact_info["email"],
                        contact_info["phone"],
                        contact_info["website"],
                        post_url,
                        title,
                        lead_type,
                        clean_snippet,
                        outreach_hook,
                        now_str,
                        "Ready for Outreach"
                    ])
            else:
                print(f"[Reddit] Query '{q}' returned HTTP status {r.status_code}", flush=True)
        except Exception as e:
            print(f"[Reddit] Error fetching '{q}': {e}", flush=True)

    return leads

def scrape_hackernews_leads() -> list[list]:
    """Scrapes tech founder and business leads from HackerNews discussions (Algolia API)."""
    leads = []
    queries = [
        'Vapi AI',
        'Bland AI',
        'Retell AI',
        'AI voice agent',
        'AI phone receptionist'
    ]

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    for q in queries:
        url = f"https://hn.algolia.com/api/v1/search_by_date?query={requests.utils.quote(q)}&tags=(story,comment)&hitsPerPage=10"
        print(f"[HackerNews] Searching: '{q}'", flush=True)
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                for hit in data.get("hits", []):
                    author = hit.get("author", "N/A")
                    story_title = hit.get("story_title") or hit.get("title") or f"Discussion on {q}"
                    comment_text = hit.get("comment_text") or hit.get("story_text") or ""
                    
                    # Clean HTML tags from HN snippets
                    clean_text = re.sub(r'<[^>]+>', ' ', comment_text)[:400].replace("\n", " ").strip()
                    if not clean_text:
                        clean_text = story_title

                    # Post URL
                    object_id = hit.get("objectID", "")
                    post_url = f"https://news.ycombinator.com/item?id={object_id}" if object_id else hit.get("url", "")

                    contact_info = extract_contact_info(f"{story_title} {clean_text}")
                    business_name = extract_business_name(story_title, clean_text, author)
                    lead_type, outreach_hook = classify_lead_intent(story_title, clean_text)

                    leads.append([
                        "HackerNews / Web",
                        author,
                        business_name,
                        contact_info["email"],
                        contact_info["phone"],
                        contact_info["website"],
                        post_url,
                        story_title,
                        lead_type,
                        clean_text,
                        outreach_hook,
                        now_str,
                        "Ready for Outreach"
                    ])
        except Exception as e:
            print(f"[HackerNews] Error fetching '{q}': {e}", flush=True)

    return leads

def main():
    try:
        print("=== Starting Voice AI Lead Harvester ===", flush=True)
        sheet = get_sheet()
        existing_records = sheet.get_all_values()

        # Check and initialize headers
        if not existing_records:
            print("Sheet is empty. Adding outreach-ready headers...", flush=True)
            sheet.append_row(SHEET_HEADERS)
            existing_urls = set()
        else:
            first_row = existing_records[0]
            # If the sheet currently has older or different headers, update row 1 to full schema
            if len(first_row) < len(SHEET_HEADERS) or first_row[0] != SHEET_HEADERS[0]:
                print("Updating Google Sheet header row to complete outreach schema...", flush=True)
                for col_idx, header_val in enumerate(SHEET_HEADERS, start=1):
                    sheet.update_cell(1, col_idx, header_val)
            
            # Index existing post URLs (column index 6 / 7th column: Post / Source URL)
            # Support both old schema (URL at index 3) and new schema (URL at index 6)
            existing_urls = set()
            for row in existing_records[1:]:
                if len(row) > 6 and row[6].startswith("http"):
                    existing_urls.add(row[6])
                elif len(row) > 3 and row[3].startswith("http"):
                    existing_urls.add(row[3])

        # Harvest from multi-channel engines
        reddit_leads = scrape_reddit_leads()
        hn_leads = scrape_hackernews_leads()
        all_leads = reddit_leads + hn_leads
        print(f"Total leads harvested: {len(all_leads)} (Reddit: {len(reddit_leads)}, HackerNews/Web: {len(hn_leads)})", flush=True)

        if not all_leads:
            print("No new leads found during this run cycle.", flush=True)
            if len(existing_records) <= 1:
                # Add sample verification row so user can confirm write access
                now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                sheet.append_row([
                    "System",
                    "VoiceBot Lead System",
                    "GetQualify AI",
                    "contact@getqualify.in",
                    "+1-800-555-0199",
                    "https://getqualify.in",
                    "https://getqualify.in/demo",
                    "Google Sheet Integration Verified",
                    "System Health Check",
                    "Verified automated write permissions for Voice AI Harvester.",
                    "Ready for automated outreach.",
                    now_str,
                    "Active"
                ])
                print("Added verification test lead to confirm write permissions.", flush=True)
            return

        # Deduplicate based on Post / Source URL (index 6)
        unique_rows = [row for row in all_leads if row[6] and row[6] not in existing_urls]
        
        # In-memory deduplication within current batch
        seen_batch_urls = set()
        deduped_batch = []
        for row in unique_rows:
            url = row[6]
            if url not in seen_batch_urls:
                seen_batch_urls.add(url)
                deduped_batch.append(row)

        if deduped_batch:
            sheet.append_rows(deduped_batch)
            print(f"Successfully added {len(deduped_batch)} fresh, outreach-ready leads to Google Sheets!", flush=True)
        else:
            print("All scraped leads already exist in your Google Sheet. No duplicates added.", flush=True)

        print("=== Lead Harvesting Complete ===", flush=True)

    except Exception as e:
        print(f"FATAL ERROR in Lead Harvester: {e}", flush=True)
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
