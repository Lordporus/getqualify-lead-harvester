"""Voice AI B2B Lead Harvester Pipeline.

Main entry point for discovering high-call-volume local businesses, enriching
verified email & owner contact information, generating niche-specific Voice AI
pitches, and synchronizing deduplicated lead records to Google Sheets.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import logging
import os
import re
import sys
import traceback
import urllib.parse
from typing import Any, List, Optional, Set, Tuple

# Ensure repository root is on sys.path for direct script execution
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import requests

try:
    from scripts.agent_reach_adapter import fetch_agent_reach_intent_leads
    from scripts.b2b_discovery import (
        DEFAULT_METRO_CITIES,
        DEFAULT_NICHES,
        fetch_niche_businesses,
        harvest_target_leads,
        normalize_phone,
    )
    from scripts.deduplication import (
        LeadDeduplicator,
        canonical_domain,
        canonical_phone,
        lead_signature,
    )
    from scripts.enrichment import _normalize_domain, enrich_business_contact
    from scripts.hooks import generate_voice_ai_hook, normalize_niche
except ImportError:
    from agent_reach_adapter import fetch_agent_reach_intent_leads
    from b2b_discovery import (
        DEFAULT_METRO_CITIES,
        DEFAULT_NICHES,
        fetch_niche_businesses,
        harvest_target_leads,
        normalize_phone,
    )
    from deduplication import (
        LeadDeduplicator,
        canonical_domain,
        canonical_phone,
        lead_signature,
    )
    from enrichment import _normalize_domain, enrich_business_contact
    from hooks import generate_voice_ai_hook, normalize_niche

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Outreach-ready Google Sheet Columns (13-Column Target Schema)
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
    "Outreach Status",
]

# High-Intent Target Niches for Voice AI Agents
DEFAULT_NICHES = [
    "dental",
    "medical",
    "hvac",
    "legal",
    "autorepair",
]

# High-Volume US Metro Areas (15-city cascade matrix)
DEFAULT_METRO_CITIES = [
    "Austin",
    "Dallas",
    "Miami",
    "Phoenix",
    "Atlanta",
    "Houston",
    "Orlando",
    "Tampa",
    "Charlotte",
    "Nashville",
    "Las Vegas",
    "Denver",
    "San Antonio",
    "Columbus",
    "Indianapolis",
]

CITY_STATE_MAP = {
    "Austin": "Austin, TX",
    "Dallas": "Dallas, TX",
    "Miami": "Miami, FL",
    "Phoenix": "Phoenix, AZ",
    "Atlanta": "Atlanta, GA",
    "Houston": "Houston, TX",
    "Orlando": "Orlando, FL",
    "Tampa": "Tampa, FL",
    "Charlotte": "Charlotte, NC",
    "Nashville": "Nashville, TN",
    "Las Vegas": "Las Vegas, NV",
    "Denver": "Denver, CO",
    "San Antonio": "San Antonio, TX",
    "Columbus": "Columbus, OH",
    "Indianapolis": "Indianapolis, IN",
    "Chicago": "Chicago, IL",
    "Seattle": "Seattle, WA",
}


def normalize_phone_key(phone: Optional[str]) -> str:
    """Extract standard 10-digit phone key for deduplication."""
    return canonical_phone(phone)


def normalize_url_key(url: Optional[str]) -> str:
    """Extract canonical bare domain from URL for deduplication."""
    return canonical_domain(url)


def build_lead_row(
    business: dict[str, str],
    enrichment: dict[str, Any],
    niche: str,
    city: str,
) -> list[str]:
    """Constructs a 13-column Google Sheet lead row for outreach."""
    biz_name = (business.get("business_name") or "").strip()
    phone = (business.get("phone") or "N/A").strip()
    website = (business.get("website") or "N/A").strip()
    category = business.get("category")
    if not category:
        if niche.lower() == "hvac":
            category = "HVAC Services"
        elif niche.lower() == "autorepair":
            category = "Auto Repair"
        else:
            category = niche.title()

    owner = (enrichment.get("owner_name") or "").strip()
    if not owner or owner.upper() == "N/A":
        lead_name = "Practice / Business Manager"
    else:
        lead_name = owner

    raw_email = (enrichment.get("email") or "N/A").strip()
    email = raw_email if raw_email else "N/A"
    has_after_hours = bool(enrichment.get("has_after_hours_notice", False))

    lead_type, pain_point, hook = generate_voice_ai_hook(
        niche=niche,
        business_name=biz_name,
        city=city,
        owner_name=owner if owner.upper() != "N/A" else "",
        has_after_hours_notice=has_after_hours,
    )

    clean_city = city.strip().title()
    loc_display = CITY_STATE_MAP.get(clean_city, clean_city)
    title_subject = f"{category} - {loc_display}"

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return [
        "B2B Directory / Web",        # 1. Platform
        lead_name,                    # 2. Name / Username
        biz_name,                     # 3. Business / Company
        email,                        # 4. Email
        phone,                        # 5. Phone Number
        website,                      # 6. Website URL
        website,                      # 7. Post / Source URL
        title_subject,                # 8. Title / Subject
        lead_type,                    # 9. Lead Type / Intent
        pain_point,                   # 10. Pain Point / Snippet
        hook,                         # 11. Recommended Outreach Hook
        now_str,                      # 12. Date Captured
        "Ready for Outreach",         # 13. Outreach Status
    ]


def extract_existing_keys(existing_records: list[list[str]]) -> tuple[set[str], set[str]]:
    """Extracts existing phone numbers and website domains from Google Sheet rows for deduplication."""
    dedup = LeadDeduplicator()
    dedup.load_existing_records(existing_records)
    return dedup.seen_phones, dedup.seen_domains


def scrape_leads(
    limit: int = 50,
    niches: Optional[list[str]] = None,
    cities: Optional[list[str]] = None,
    existing_phones: Optional[set[str]] = None,
    existing_websites: Optional[set[str]] = None,
    deduplicator: Optional[LeadDeduplicator] = None,
    dry_run: bool = False,
    enable_agent_reach: Optional[bool] = None,
) -> list[list[str]]:
    """Discovers, enriches, and formats B2B Voice AI leads across niches and cities.

    Args:
        limit: Total number of fresh leads to harvest (default: 50).
        niches: List of target business niches. Defaults to DEFAULT_NICHES.
        cities: List of target metro cities. Defaults to DEFAULT_METRO_CITIES.
        existing_phones: Set of existing phone keys to skip (from Google Sheet).
        existing_websites: Set of existing website keys to skip (from Google Sheet).
        deduplicator: Dedicated LeadDeduplicator instance for multi-key checking.
        dry_run: Flag indicating local dry-run execution.
        enable_agent_reach: Whether to fetch intent leads via Agent-Reach (defaults to True in prod, False in dry_run).

    Returns:
        List of 13-column lead rows ready for Google Sheet outreach.
    """
    target_niches = niches or DEFAULT_NICHES
    target_cities = cities or DEFAULT_METRO_CITIES

    dedup = deduplicator or LeadDeduplicator()
    if existing_phones:
        dedup.seen_phones.update(existing_phones)
    if existing_websites:
        dedup.seen_domains.update(existing_websites)

    harvested_leads: list[list[str]] = []

    # Optional: fetch high-intent post/social leads via Agent-Reach adapter
    should_run_agent_reach = (
        enable_agent_reach if enable_agent_reach is not None else (not dry_run)
    )
    if should_run_agent_reach:
        try:
            intent_target = min(10, max(2, limit // 5)) if limit >= 5 else 0
            if intent_target > 0:
                agent_reach_candidates = fetch_agent_reach_intent_leads(limit=intent_target)
                for cand in agent_reach_candidates:
                    if len(harvested_leads) >= limit:
                        break
                    if dedup.is_duplicate(cand):
                        continue

                    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                    c_niche = (cand.get("niche") or "Voice AI").title()
                    c_city = cand.get("city") or "Target Market"
                    intent_row = [
                        cand.get("platform") or "Agent-Reach / Web",
                        cand.get("author") or "Practice / Business Manager",
                        cand.get("business_name") or "Local Business",
                        cand.get("email") or "N/A",
                        cand.get("phone") or "N/A",
                        cand.get("website") or "N/A",
                        cand.get("source_url") or cand.get("website") or "N/A",
                        f"{c_niche} - {c_city}",
                        cand.get("lead_intent") or "Voice AI Inbound & Scheduling Intent",
                        cand.get("pain_point") or "High inbound inquiry volume with after-hours missed opportunities.",
                        cand.get("recommended_hook") or "Pitch 24/7 AI Voice receptionist to convert missed customer inquiries.",
                        now_str,
                        "Ready for Outreach",
                    ]
                    dedup.register_lead(cand)
                    harvested_leads.append(intent_row)
        except Exception as exc:
            logger.debug("Agent-Reach intent harvest skipped/failed: %s", exc)

    # Build rotating (niche, city) execution schedule
    rotation_pairs: list[tuple[str, str]] = []
    for c_offset in range(len(target_cities)):
        for n_idx, niche in enumerate(target_niches):
            city = target_cities[(c_offset + n_idx) % len(target_cities)]
            pair = (niche, city)
            if pair not in rotation_pairs:
                rotation_pairs.append(pair)

    logger.info(
        "Beginning B2B lead harvest. Target: %d leads across %d niche-city combinations.",
        limit,
        len(rotation_pairs),
    )

    per_niche_target = (
        max(1, limit // len(target_niches)) if len(target_niches) > 1 else limit
    )
    niche_counts: dict[str, int] = {n: 0 for n in target_niches}

    for pass_idx in (1, 2, 3, 4):
        if len(harvested_leads) >= limit:
            break

        for niche, city in rotation_pairs:
            if len(harvested_leads) >= limit:
                break

            if pass_idx == 1 and niche_counts[niche] >= per_niche_target:
                continue

            needed = limit - len(harvested_leads)
            fetch_limit = min(max(needed + 2, 5), 15)

            logger.info(
                "Searching niche '%s' in city '%s' (batch fetch limit: %d, pass: %d)...",
                niche,
                city,
                fetch_limit,
                pass_idx,
            )

            try:
                candidates = fetch_niche_businesses(niche, city, limit=fetch_limit)
            except Exception as exc:
                logger.warning("Error fetching businesses for %s in %s: %s", niche, city, exc)
                continue

            for cand in candidates:
                if len(harvested_leads) >= limit:
                    break

                biz_name = cand.get("business_name", "")
                phone = cand.get("phone", "")
                website = cand.get("website", "")

                lead_dict = {
                    "business_name": biz_name,
                    "phone": phone,
                    "website": website,
                    "city": city,
                    "niche": niche,
                    "url": website,
                }

                # Ironclad multi-key deduplication check
                if dedup.is_duplicate(lead_dict):
                    logger.debug("Skipping duplicate lead: %s (%s)", biz_name, phone)
                    continue

                # Enrich contact details (email, owner name, after-hours notice)
                enrichment_timeout = 4 if dry_run else 5
                try:
                    enrichment = enrich_business_contact(website, timeout=enrichment_timeout)
                except Exception as exc:
                    logger.debug("Enrichment error for %s: %s", website, exc)
                    enrichment = {"email": "N/A", "owner_name": "N/A", "has_after_hours_notice": False}

                # Build full 13-column outreach row
                lead_row = build_lead_row(
                    business=cand,
                    enrichment=enrichment,
                    niche=niche,
                    city=city,
                )

                # Register lead in deduplicator
                dedup.register_lead(lead_dict)

                harvested_leads.append(lead_row)
                niche_counts[niche] = niche_counts.get(niche, 0) + 1

                logger.info(
                    "[%d/%d] Harvested: %s (%s) | Phone: %s | Email: %s",
                    len(harvested_leads),
                    limit,
                    biz_name,
                    niche,
                    phone,
                    lead_row[3],
                )

                if pass_idx == 1 and niche_counts[niche] >= per_niche_target:
                    break

    logger.info("Harvest completed. Total fresh leads collected: %d", len(harvested_leads))
    return harvested_leads


def get_sheet():
    """Authenticates with Google Sheets using GCP_SA_KEY and SPREADSHEET_ID."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as err:
        raise ImportError(
            "gspread and google-auth are required to connect to Google Sheets. "
            "Please run: pip install gspread google-auth"
        ) from err

    sa_json = os.environ.get("GCP_SA_KEY", "")
    sheet_id = os.environ.get("SPREADSHEET_ID", "")

    if not sa_json or not sa_json.strip():
        raise ValueError(
            "GCP_SA_KEY secret is missing or empty. "
            "Please configure GCP_SA_KEY in your environment or GitHub Secrets."
        )
    if not sheet_id or not sheet_id.strip():
        raise ValueError(
            "SPREADSHEET_ID secret is missing or empty. "
            "Please configure SPREADSHEET_ID in your environment or GitHub Secrets."
        )

    sa_json = sa_json.strip()
    sheet_id = sheet_id.strip()

    if (sa_json.startswith('"') and sa_json.endswith('"')) or (
        sa_json.startswith("'") and sa_json.endswith("'")
    ):
        sa_json = sa_json[1:-1].strip()

    sa_info = None
    try:
        sa_info = json.loads(sa_json)
        logger.info("Successfully parsed GCP_SA_KEY as raw JSON.")
    except json.JSONDecodeError as direct_err:
        try:
            decoded_bytes = base64.b64decode(sa_json)
            decoded_str = decoded_bytes.decode("utf-8")
            sa_info = json.loads(decoded_str)
            logger.info("Successfully decoded and parsed GCP_SA_KEY from Base64.")
        except Exception:
            preview = sa_json[:20] + "..." if len(sa_json) > 20 else sa_json
            raise ValueError(
                f"GCP_SA_KEY is neither valid JSON nor valid Base64 JSON.\n"
                f"Received length={len(sa_json)} characters. Preview='{preview}'.\n"
                f"JSON Error: {direct_err}."
            ) from direct_err

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_info(sa_info, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).sheet1


def main():
    """Main CLI entry point for Voice AI Lead Harvester."""
    parser = argparse.ArgumentParser(
        description="Voice AI B2B Lead Harvester - High-call volume business discovery and outreach generator."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run discovery and enrichment locally without connecting to or updating Google Sheets.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Total number of fresh leads to harvest (default: 50).",
    )
    parser.add_argument(
        "--niches",
        nargs="*",
        default=None,
        help="Specific niches to target (e.g. --niches dental hvac legal).",
    )
    parser.add_argument(
        "--cities",
        nargs="*",
        default=None,
        help="Specific metro cities to target (e.g. --cities Austin Dallas Miami).",
    )
    args = parser.parse_args()

    try:
        if args.dry_run:
            print("=== Starting Voice AI Lead Harvester (DRY RUN) ===", flush=True)
            leads = scrape_leads(
                limit=args.limit,
                niches=args.niches,
                cities=args.cities,
                dry_run=True,
            )

            print(
                f"\n[DRY RUN COMPLETE] Harvested {len(leads)} high-quality B2B leads:\n",
                flush=True,
            )
            for idx, lead in enumerate(leads, start=1):
                print(f"--- Lead #{idx} ---")
                print(f"Company:       {lead[2]}")
                print(f"Contact Name:  {lead[1]}")
                print(f"Phone Number:  {lead[4]}")
                print(f"Website URL:   {lead[5]}")
                print(f"Email:         {lead[3]}")
                print(f"Title/Subject: {lead[7]}")
                print(f"Lead Intent:   {lead[8]}")
                print(f"Pain Point:    {lead[9]}")
                print(f"Outreach Hook: {lead[10]}")
                print(f"Date Captured: {lead[11]}")
                print(f"Status:        {lead[12]}")
                print()
            return

        # Production run with Google Sheets synchronization
        print("=== Starting Voice AI Lead Harvester ===", flush=True)
        sheet = get_sheet()
        existing_records = sheet.get_all_values()
        deduplicator = LeadDeduplicator()

        # Check and initialize headers
        if not existing_records:
            print("Sheet is empty. Adding outreach-ready headers...", flush=True)
            sheet.append_row(SHEET_HEADERS)
        else:
            first_row = existing_records[0]
            if len(first_row) < len(SHEET_HEADERS) or first_row[0] != SHEET_HEADERS[0]:
                print(
                    "Updating Google Sheet header row to complete outreach schema...",
                    flush=True,
                )
                for col_idx, header_val in enumerate(SHEET_HEADERS, start=1):
                    sheet.update_cell(1, col_idx, header_val)

            deduplicator.load_existing_records(existing_records)
            print(
                f"Indexed existing records: {len(deduplicator.seen_phones)} phones, "
                f"{len(deduplicator.seen_domains)} websites, {len(deduplicator.seen_signatures)} signatures.",
                flush=True,
            )

        # Harvest fresh deduplicated leads
        leads = scrape_leads(
            limit=args.limit,
            niches=args.niches,
            cities=args.cities,
            deduplicator=deduplicator,
            dry_run=False,
        )

        if leads:
            print(f"Syncing {len(leads)} fresh leads to Google Sheet in single batch...", flush=True)
            sheet.append_rows(leads)
            print(
                f"Successfully added {len(leads)} fresh, outreach-ready leads to Google Sheets!",
                flush=True,
            )
        else:
            print(
                "No new leads found during this run cycle or all candidates already exist in the sheet.",
                flush=True,
            )
            if len(existing_records) <= 1:
                now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                verification_lead = [
                    "B2B Directory / Web",
                    "Practice / Business Manager",
                    "GetQualify AI Demo",
                    "contact@getqualify.io",
                    "+1 (800) 555-0199",
                    "https://getqualify.io",
                    "https://getqualify.io",
                    "Dental Practice - Austin, TX",
                    "Dental Practice - Inbound Patient Intake & After-Hours Receptionist",
                    "Dental offices lose 30-40% of emergency patient inquiries after 5 PM.",
                    "Pitch an after-hours AI voice receptionist to capture missed patient appointments 24/7.",
                    now_str,
                    "Ready for Outreach",
                ]
                sheet.append_row(verification_lead)
                print(
                    "Added verification test lead to confirm write permissions.",
                    flush=True,
                )

        print("=== Lead Harvesting Complete ===", flush=True)

    except Exception as exc:
        print(f"FATAL ERROR in Lead Harvester: {exc}", flush=True)
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
