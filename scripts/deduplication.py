"""Ironclad Multi-Key Deduplication Engine for Lead Harvesting.

Tracks historical and in-flight leads across 4 distinct keys:
1. Standardized 10-digit Phone Key
2. Canonical Root Domain
3. Normalized Company + City Signature (and Normalized Company Name)
4. Canonical Source / Post URL
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


def canonical_domain(url: Optional[str]) -> str:
    """Extract canonical root domain from any URL or string.

    Strips http/https, www., query parameters, and trailing paths.
    Returns lowercase domain (e.g., 'apexdental.com').
    Returns empty string if invalid or N/A.
    """
    if not url or not isinstance(url, str):
        return ""
    cleaned = url.strip()
    if cleaned.lower() in ("n/a", "none", "null", "undefined", ""):
        return ""

    if not cleaned.startswith(("http://", "https://")):
        cleaned = "https://" + cleaned

    try:
        parsed = urllib.parse.urlparse(cleaned)
        host = (parsed.netloc or parsed.path).split("/")[0].split(":")[0].lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def canonical_phone(phone: Optional[str]) -> str:
    """Extract standardized 10-digit numeric phone key.

    Reduces any notation (+1 512-555-0199, 512.555.0199, 15125550199)
    to the last 10 digits.
    Returns empty string if invalid or less than 10 digits.
    """
    if not phone or not isinstance(phone, str):
        return ""
    cleaned = phone.strip()
    if cleaned.lower() in ("n/a", "none", "null", "undefined", ""):
        return ""
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) >= 10:
        return digits[-10:]
    return ""


def lead_signature(company: Optional[str], city: Optional[str] = "") -> str:
    """Generate normalized (company_name, city) signature.

    Strips state abbreviations, punctuation, and lowercases.
    """
    c_name = re.sub(r"[^\w\s]", "", (company or "").lower()).strip()
    if not c_name:
        return ""
    raw_city = (city or "").split(",")[0].strip()
    c_city = re.sub(r"[^\w\s]", "", raw_city.lower()).strip()
    return f"{c_name}::{c_city}" if c_city else c_name


class LeadDeduplicator:
    """Manages multi-key deduplication against Google Sheets and in-batch records."""

    def __init__(self) -> None:
        self.seen_phones: Set[str] = set()
        self.seen_domains: Set[str] = set()
        self.seen_signatures: Set[str] = set()
        self.seen_companies: Set[str] = set()
        self.seen_urls: Set[str] = set()

    def canonical_domain(self, url: Optional[str]) -> str:
        return canonical_domain(url)

    def canonical_phone(self, phone: Optional[str]) -> str:
        return canonical_phone(phone)

    def lead_signature(self, company: Optional[str], city: Optional[str] = "") -> str:
        return lead_signature(company, city)

    def load_existing_records(self, records: List[List[Any]]) -> None:
        """Ingest existing Google Sheet rows into deduplication lookup sets.

        Supports both 13-column target schema and older 5-column schemas.
        """
        if not records or len(records) <= 1:
            return

        # Skip header row (index 0)
        for row in records[1:]:
            if not row or not isinstance(row, list):
                continue

            # Target 13-column schema indices:
            # Col 2: Business/Company (index 2)
            # Col 4: Phone (index 4)
            # Col 5: Website URL (index 5)
            # Col 6: Source URL (index 6)
            # Col 7: Title/Subject (index 7, often contains City)
            if len(row) >= 7:
                company = str(row[2]).strip() if len(row) > 2 else ""
                phone = str(row[4]).strip() if len(row) > 4 else ""
                website = str(row[5]).strip() if len(row) > 5 else ""
                src_url = str(row[6]).strip() if len(row) > 6 else ""
                title = str(row[7]).strip() if len(row) > 7 else ""

                p_key = canonical_phone(phone)
                if p_key:
                    self.seen_phones.add(p_key)

                d_key = canonical_domain(website)
                if d_key:
                    self.seen_domains.add(d_key)

                if src_url:
                    self.seen_urls.add(src_url.strip().lower())

                # City extracted from title if present (e.g. "Dental Clinic - Austin, TX")
                city = ""
                if " - " in title:
                    city = title.split(" - ")[-1]

                if company:
                    clean_co = re.sub(r"[^\w\s]", "", company.lower()).strip()
                    if clean_co:
                        self.seen_companies.add(clean_co)
                    sig = lead_signature(company, city)
                    if sig:
                        self.seen_signatures.add(sig)

            # Fallback for legacy 5-column schema:
            # Col 3: URL (index 3)
            elif len(row) > 3:
                url_cand = str(row[3]).strip()
                if url_cand.startswith("http"):
                    self.seen_urls.add(url_cand.lower())
                    d_key = canonical_domain(url_cand)
                    if d_key:
                        self.seen_domains.add(d_key)

        logger.info(
            "Loaded existing records: %d phones, %d domains, %d signatures, %d URLs",
            len(self.seen_phones),
            len(self.seen_domains),
            len(self.seen_signatures),
            len(self.seen_urls),
        )

    def is_duplicate(self, lead: Dict[str, Any]) -> bool:
        """Check if incoming lead matches any of the deduplication keys."""
        if not lead or not isinstance(lead, dict):
            return False

        # Key 1: Phone check
        phone = lead.get("phone") or lead.get("phone_number") or ""
        p_key = canonical_phone(phone)
        if p_key and p_key in self.seen_phones:
            return True

        # Key 2: Canonical Domain check
        website = lead.get("website") or lead.get("website_url") or ""
        d_key = canonical_domain(website)
        if d_key and d_key in self.seen_domains:
            return True

        # Key 3: Post / Source URL check
        url = lead.get("url") or lead.get("post_url") or lead.get("source_url") or ""
        if url and url.strip().lower() in self.seen_urls:
            return True

        # Key 4: Company + City signature check
        company = lead.get("business_name") or lead.get("company") or ""
        city = lead.get("city") or ""
        sig = lead_signature(company, city)
        if sig and sig in self.seen_signatures:
            return True

        # Key 5: Exact clean company name match (if company name is distinct)
        clean_co = re.sub(r"[^\w\s]", "", (company or "").lower()).strip()
        if clean_co and len(clean_co) >= 6 and clean_co in self.seen_companies:
            return True

        return False

    def register_lead(self, lead: Dict[str, Any]) -> None:
        """Register newly harvested lead to prevent in-batch duplicates."""
        if not lead or not isinstance(lead, dict):
            return

        phone = lead.get("phone") or lead.get("phone_number") or ""
        p_key = canonical_phone(phone)
        if p_key:
            self.seen_phones.add(p_key)

        website = lead.get("website") or lead.get("website_url") or ""
        d_key = canonical_domain(website)
        if d_key:
            self.seen_domains.add(d_key)

        url = lead.get("url") or lead.get("post_url") or lead.get("source_url") or ""
        if url:
            self.seen_urls.add(url.strip().lower())

        company = lead.get("business_name") or lead.get("company") or ""
        city = lead.get("city") or ""
        if company:
            clean_co = re.sub(r"[^\w\s]", "", company.lower()).strip()
            if clean_co:
                self.seen_companies.add(clean_co)
        sig = lead_signature(company, city)
        if sig:
            self.seen_signatures.add(sig)
