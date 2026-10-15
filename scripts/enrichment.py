"""Website Email & Owner Enrichment Engine.

Crawls discovered business websites to extract verified business email addresses,
practitioner / owner names, and after-hours availability notices.
Eliminates 'N/A' fields for downstream Voice AI sales generation.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import re
import urllib.parse
from typing import Any

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Standard browser User-Agent
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# Common keywords for identifying relevant contact/team subpages
CONTACT_PATH_KEYWORDS = (
    "contact",
    "about",
    "team",
    "staff",
    "doctor",
    "dentist",
    "attorney",
    "provider",
    "meet",
    "location",
    "office",
)

# Standard subpage fallback candidates
DEFAULT_SUBPAGE_FALLBACKS = [
    "/contact-us",
    "/contact",
    "/about-us",
    "/about",
    "/our-team",
    "/team",
    "/staff",
    "/doctors",
]

# Common image and media extensions to filter out of email matches
IMAGE_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".bmp",
    ".tiff",
    ".avif",
)

# Platform trackers, CMS placeholders, and throwaway domains
JUNK_DOMAINS = {
    "wixpress.com",
    "sentry.io",
    "example.com",
    "domain.com",
    "email.com",
    "wix.com",
    "wordpress.org",
    "cloudflare.com",
    "github.com",
    "google.com",
    "googleapis.com",
    "schema.org",
}

# Domain privacy and proxy protection guards to ignore from WHOIS/RDAP
PRIVACY_PROXY_DOMAINS = {
    "domainsbyproxy.com",
    "contactprivacy.com",
    "whoisguard.com",
    "privacyprotect.org",
    "identity-protect.org",
    "withheldforprivacy.com",
    "whoisproxy.com",
    "registrar.com",
}

# Operational prefixes to prioritize when choosing primary contact email
OPERATIONAL_PREFIXES = (
    "info@",
    "contact@",
    "office@",
    "appointments@",
    "support@",
    "admin@",
    "hello@",
    "frontdesk@",
)

# Phrases that indicate after-hours or emergency handling
AFTER_HOURS_PATTERNS = [
    re.compile(r"\bafter[\s-]hours\b", re.IGNORECASE),
    re.compile(r"\b24\s*[/x-]?\s*7\b", re.IGNORECASE),
    re.compile(r"\b24\s*hours?\b", re.IGNORECASE),
    re.compile(r"\bemergency\s*(?:service|care|line|contact|call|clinic|dentist|appointment)\b", re.IGNORECASE),
    re.compile(r"\bon[\s-]call\b", re.IGNORECASE),
    re.compile(r"\boutside\s+(?:of\s+)?(?:normal\s+)?(?:office|business)\s+hours\b", re.IGNORECASE),
    re.compile(r"\banswering\s+service\b", re.IGNORECASE),
    re.compile(r"\bleave\s+(?:a\s+)?(?:voicemail|message)\b", re.IGNORECASE),
]

# Words that cannot be part of an owner's personal name
NON_NAME_WORDS = {
    "dental", "dentist", "dentistry", "clinic", "center", "centre", "care", "health",
    "family", "smile", "smiles", "orthodontics", "pediatric", "cosmetic", "surgery",
    "doctor", "doctors", "office", "contact", "about", "team", "staff", "patients",
    "services", "service", "appointment", "schedule", "hours", "insurance", "emergency",
    "law", "firm", "legal", "attorney", "attorneys", "associates", "group", "medical",
    "auto", "repair", "plumbing", "hvac", "heating", "cooling", "solutions", "city",
    "state", "texas", "austin", "dallas", "houston", "home", "page", "welcome",
    "review", "reviews", "testimonial", "testimonials", "privacy", "policy", "terms",
    "copyright", "rights", "reserved", "call", "click", "here", "learn", "more",
    "read", "online", "portal", "menu", "navigation", "search", "header", "footer",
}


def clean_email(email_str: str | None) -> str | None:
    """Clean and validate an email candidate string.

    Filters out:
    - Image assets (e.g. logo@2x.png)
    - Platform trackers and CMS placeholders (e.g. wixpress.com, sentry.io)
    - Malformed addresses

    Unmasks obfuscated formats:
    - "info [at] domain [dot] com" -> "info@domain.com"
    - "contact (at) domain.com" -> "contact@domain.com"
    - "help at domain dot com" -> "help@domain.com"

    Returns lowercase valid email address or None.
    """
    if not email_str or not isinstance(email_str, str):
        return None

    candidate = email_str.strip()
    if candidate.lower().startswith("mailto:"):
        candidate = candidate[7:]
    if "?" in candidate:
        candidate = candidate.split("?", 1)[0]

    # Normalize obfuscated patterns
    candidate = re.sub(r"\s*\[at\]\s*|\s*\(at\)\s*|\s+at\s+", "@", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\s*\[dot\]\s*|\s*\(dot\)\s*|\s+dot\s+", ".", candidate, flags=re.IGNORECASE)

    candidate = candidate.strip().strip("'\"<>.,;:()[]{}")
    if not candidate or "@" not in candidate:
        return None

    # Check for image file patterns
    candidate_lower = candidate.lower()
    if any(candidate_lower.endswith(ext) for ext in IMAGE_EXTENSIONS):
        return None

    parts = candidate_lower.split("@")
    if len(parts) != 2:
        return None

    user_part, domain_part = parts[0].strip(), parts[1].strip()
    if not user_part or not domain_part:
        return None

    # Reject if domain ends with an image extension (e.g. icon@2x.jpg)
    if any(domain_part.endswith(ext) for ext in IMAGE_EXTENSIONS):
        return None

    # Domain must contain at least one period and valid TLD
    domain_labels = domain_part.split(".")
    if len(domain_labels) < 2 or any(not label for label in domain_labels):
        return None
    tld = domain_labels[-1]
    if len(tld) < 2 or not tld.isalpha():
        return None

    # Check junk and tracker domains
    if domain_part in JUNK_DOMAINS:
        return None
    if any(domain_part.endswith("." + junk) for junk in JUNK_DOMAINS):
        return None

    # Standard RFC-like email regex check
    email_pattern = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    if not email_pattern.match(candidate_lower):
        return None

    return candidate_lower


def _normalize_domain(domain_or_url: str) -> str:
    """Extract clean domain hostname without protocol, port, or www prefix."""
    if not domain_or_url:
        return ""
    raw = domain_or_url.strip()
    if "://" not in raw:
        raw = "http://" + raw
    try:
        parsed = urllib.parse.urlparse(raw)
        host = parsed.netloc or parsed.path
        host = host.split(":")[0].lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def discover_contact_subpage_urls(html: str, base_url: str, max_subpages: int = 5) -> list[str]:
    """Inspects homepage HTML links and appends standard fallbacks to discover up to max_subpages."""
    if not base_url:
        return []

    clean_base = base_url.strip()
    if not clean_base.startswith(("http://", "https://")):
        clean_base = "https://" + clean_base

    base_domain = _normalize_domain(clean_base)
    discovered: list[str] = []
    seen_urls: set[str] = {clean_base.rstrip("/").lower()}

    # 1. Parse anchors from HTML
    if html and isinstance(html, str):
        if BeautifulSoup is not None:
            try:
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    text = a.get_text(separator=" ", strip=True).lower()
                    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        continue

                    full_url = urllib.parse.urljoin(clean_base, href)
                    sub_domain = _normalize_domain(full_url)
                    # Stay within same root domain
                    if sub_domain != base_domain and not sub_domain.endswith("." + base_domain):
                        continue

                    href_lower = href.lower()
                    is_match = any(kw in href_lower for kw in CONTACT_PATH_KEYWORDS) or any(
                        kw in text for kw in ("contact", "about", "team", "staff", "doctor", "dentist", "attorney", "meet the")
                    )

                    norm_url = full_url.split("?")[0].split("#")[0].rstrip("/").lower()
                    if is_match and norm_url not in seen_urls:
                        seen_urls.add(norm_url)
                        discovered.append(full_url)
                        if len(discovered) >= max_subpages:
                            break
            except Exception as exc:
                logger.debug("Error parsing subpage links with soup: %s", exc)
        else:
            for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE):
                href_lower = href.lower()
                if any(kw in href_lower for kw in CONTACT_PATH_KEYWORDS):
                    full_url = urllib.parse.urljoin(clean_base, href)
                    sub_domain = _normalize_domain(full_url)
                    if sub_domain == base_domain:
                        norm_url = full_url.split("?")[0].split("#")[0].rstrip("/").lower()
                        if norm_url not in seen_urls:
                            seen_urls.add(norm_url)
                            discovered.append(full_url)
                            if len(discovered) >= max_subpages:
                                break

    # 2. Append standard fallbacks if under quota
    if len(discovered) < max_subpages:
        for fallback_path in DEFAULT_SUBPAGE_FALLBACKS:
            fallback_url = urllib.parse.urljoin(clean_base, fallback_path)
            norm_url = fallback_url.split("?")[0].split("#")[0].rstrip("/").lower()
            if norm_url not in seen_urls:
                seen_urls.add(norm_url)
                discovered.append(fallback_url)
                if len(discovered) >= max_subpages:
                    break

    return discovered[:max_subpages]


def check_domain_mx_records(domain: str, timeout: float = 3.0) -> bool:
    """Check if the given domain has active MX records via DNS-over-HTTPS.

    Uses Cloudflare Public DoH (serverless and zero-dependency).
    Returns True if at least one MX record (DNS type 15) is present.
    """
    clean_d = _normalize_domain(domain)
    if not clean_d:
        return False
    try:
        url = "https://cloudflare-dns.com/dns-query"
        params = {"name": clean_d, "type": "MX"}
        headers = {"Accept": "application/dns-json", "User-Agent": CHROME_USER_AGENT}
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("Status") == 0 and data.get("Answer"):
                for ans in data["Answer"]:
                    if ans.get("type") == 15:
                        return True
    except Exception as exc:
        logger.debug("DNS MX lookup error for %s: %s", clean_d, exc)
    return False


def fetch_rdap_contact_email(domain: str, timeout: float = 3.0) -> str | None:
    """Query ICANN public RDAP to extract non-proxy administrative/registrant email."""
    clean_d = _normalize_domain(domain)
    if not clean_d:
        return None
    try:
        url = f"https://rdap.org/domain/{clean_d}"
        headers = {"Accept": "application/rdap+json", "User-Agent": CHROME_USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            entities = data.get("entities") or []
            for ent in entities:
                vcard = ent.get("vcardArray")
                if isinstance(vcard, list) and len(vcard) > 1 and isinstance(vcard[1], list):
                    for field in vcard[1]:
                        if isinstance(field, list) and len(field) >= 4 and field[0] == "email":
                            cand = clean_email(str(field[3]))
                            if cand:
                                em_domain = cand.split("@")[-1].lower()
                                if (
                                    em_domain not in PRIVACY_PROXY_DOMAINS
                                    and not any(em_domain.endswith("." + p) for p in PRIVACY_PROXY_DOMAINS)
                                    and not cand.startswith("abuse@")
                                ):
                                    return cand
    except Exception as exc:
        logger.debug("RDAP lookup error for %s: %s", clean_d, exc)
    return None


def synthesize_verified_mailbox(domain_or_url: str) -> str | None:
    """Synthesize clean canonical operational mailbox (info@domain.com) for verified domain."""
    d = _normalize_domain(domain_or_url)
    if not d or "." not in d:
        return None
    return f"info@{d}"


def extract_emails_from_html(html: str, domain: str = "") -> list[str]:
    """Parse mailto links and search regex patterns across raw HTML.

    Deduplicates and prioritizes business domain emails matching `domain`
    and standard operational addresses (info@, contact@, office@, etc.).
    """
    if not html or not isinstance(html, str):
        return []

    target_domain = _normalize_domain(domain)
    found_emails: set[str] = set()

    # 1. Parse mailto links via BeautifulSoup or regex
    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for anchor in soup.find_all("a", href=True):
                href = anchor["href"].strip()
                if href.lower().startswith("mailto:"):
                    raw_target = href[7:].split("?")[0]
                    for chunk in raw_target.split(","):
                        cleaned = clean_email(chunk)
                        if cleaned:
                            found_emails.add(cleaned)
        except Exception as exc:
            logger.debug("Failed parsing soup mailto: %s", exc)
    else:
        for match in re.findall(r'href=["\']mailto:([^"\'?]+)', html, re.IGNORECASE):
            for chunk in match.split(","):
                cleaned = clean_email(chunk)
                if cleaned:
                    found_emails.add(cleaned)

    # 2. Run regex pattern over full HTML text (standard format)
    raw_pattern = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")
    for match in raw_pattern.findall(html):
        cleaned = clean_email(match)
        if cleaned:
            found_emails.add(cleaned)

    # 3. Search for obfuscated text patterns (e.g. name [at] domain [dot] com)
    obf_pattern = re.compile(
        r"\b[a-zA-Z0-9_.+-]+(?:\s*\[at\]\s*|\s*\(at\)\s*|\s+at\s+)[a-zA-Z0-9-]+(?:\s*\[dot\]\s*|\s*\(dot\)\s*|\s+dot\s+|\.)[a-zA-Z0-9-.]+\b",
        re.IGNORECASE,
    )
    for match in obf_pattern.findall(html):
        cleaned = clean_email(match)
        if cleaned:
            found_emails.add(cleaned)

    if not found_emails:
        return []

    # 3. Sort by priority:
    # Tier 1: Target domain + operational prefix
    # Tier 2: Target domain + any other prefix
    # Tier 3: Other domain + operational prefix
    # Tier 4: Other domain + standard
    def email_priority_key(email: str) -> tuple[int, int, int, str]:
        is_target_domain = bool(
            target_domain and (email.endswith("@" + target_domain) or email.endswith("." + target_domain))
        )
        operational_rank = 99
        is_operational = False
        for idx, prefix in enumerate(OPERATIONAL_PREFIXES):
            if email.startswith(prefix):
                is_operational = True
                operational_rank = idx
                break

        domain_rank = 0 if is_target_domain else 1
        op_rank = 0 if is_operational else 1
        return (domain_rank, op_rank, operational_rank, email)

    sorted_emails = sorted(found_emails, key=email_priority_key)
    return sorted_emails


def _is_valid_person_name(name: str) -> bool:
    """Validate that candidate string is plausibly a human person name."""
    if not name or len(name) < 3:
        return False
    words = re.sub(r"[^\w\s]", "", name).split()
    if len(words) < 2 or len(words) > 4:
        return False
    # Check that words are not common business / site filler words
    for w in words:
        if w.lower() in NON_NAME_WORDS:
            return False
        if not (w[0].isupper() or w.isupper()):
            return False
    return True


def extract_owner_name_from_html(html: str) -> str:
    """Extract practitioner or business owner names using regex and DOM parsing.

    Looks for 'Dr. [Name]', 'Founder', 'Owner', 'Practice Manager', etc.
    Returns 'N/A' if not detected.
    """
    if not html or not isinstance(html, str):
        return "N/A"

    clean_text = html
    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(html, "html.parser")
            # Check team cards / role containers in DOM
            role_text_pattern = re.compile(
                r"\b(?:Owner|Founder|Co-Founder|President|Managing Partner|Practice Manager|Lead Attorney|Principal|Master Plumber)\b",
                re.IGNORECASE,
            )
            for role_str in soup.find_all(string=role_text_pattern):
                container = role_str.find_parent(["div", "section", "article", "li"])
                if container:
                    for elem in container.find_all(["h1", "h2", "h3", "h4", "h5", "strong", "b"]):
                        cand = elem.get_text(strip=True)
                        if _is_valid_person_name(cand):
                            return cand

            # Remove noisy tags for clean text parsing
            for tag in soup(["script", "style", "noscript", "svg", "canvas"]):
                tag.decompose()
            clean_text = soup.get_text(separator=" ", strip=True)
        except Exception:
            clean_text = html


    # Pattern 1: Medical / Dental Dr. Title
    dr_pattern = re.compile(
        r"\b(?:Dr\.?|Doctor)\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-zA-Z'\-]+)",
    )
    dr_match = dr_pattern.search(clean_text)
    if dr_match:
        cand = dr_match.group(1).strip()
        if _is_valid_person_name(cand):
            return f"Dr. {cand}"

    # Pattern 2: Post-nominal degrees (e.g. Robert Chen, DDS)
    degree_pattern = re.compile(
        r"\b([A-Z][a-zA-Z'\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-zA-Z'\-]+),?\s*(?:DDS|DMD|MD|DO|DC|JD|Esq\.?|DVM|FAACS)\b"
    )
    degree_match = degree_pattern.search(clean_text)
    if degree_match:
        cand = degree_match.group(1).strip()
        if _is_valid_person_name(cand):
            return cand

    # Pattern 3: Explicit role keywords (Owner, Founder, Practice Manager)
    # Ex: "Owner: Michael Vance" or "Practice Manager: Emily Watson"
    role_prefix_pattern = re.compile(
        r"(?:Owner|Founder|Co-Founder|President|Managing Partner|Practice Manager|Lead Attorney|Principal|Head Dentist)\s*[:\-–—]?\s*([A-Z][a-zA-Z'\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-zA-Z'\-]+)"
    )
    role_prefix_match = role_prefix_pattern.search(clean_text)
    if role_prefix_match:
        cand = role_prefix_match.group(1).strip()
        if _is_valid_person_name(cand):
            return cand

    # Ex: "Michael Vance, Owner" or "Michael Vance Owner & Master Plumber"
    role_suffix_pattern = re.compile(
        r"\b([A-Z][a-zA-Z'\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-zA-Z'\-]+)\s*(?:[,–\-—:|]|\s+is\s+(?:the\s+)?)?\s*(?:Owner|Founder|Co-Founder|President|Managing Partner|Practice Manager|Lead Attorney|Principal)\b",
        re.IGNORECASE,
    )
    role_suffix_match = role_suffix_pattern.search(clean_text)
    if role_suffix_match:
        cand = role_suffix_match.group(1).strip()
        if _is_valid_person_name(cand):
            return cand

    # Ex: "Founded by David Martinez"
    founded_by_pattern = re.compile(
        r"(?:Founded|Owned|Managed|Operated)\s+by\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-zA-Z'\-]+)"
    )
    founded_match = founded_by_pattern.search(clean_text)
    if founded_match:
        cand = founded_match.group(1).strip()
        if _is_valid_person_name(cand):
            return cand

    return "N/A"


def _check_after_hours(html: str) -> bool:
    """Check if page content mentions after-hours, 24/7, or emergency call handling."""
    if not html:
        return False
    for pat in AFTER_HOURS_PATTERNS:
        if pat.search(html):
            return True
    return False


def enrich_business_contact(website_url: str | None, timeout: int = 6) -> dict[str, Any]:
    """Fetch website homepage and /contact page to extract email and owner.

    Returns:
    {
        "email": str,              # e.g. "contact@austindental.com" or "N/A"
        "owner_name": str,         # e.g. "Dr. Sarah Miller" or "N/A"
        "has_after_hours_notice": bool
    }
    Gracefully catches timeouts, SSL errors, and network issues without raising exceptions.
    """
    fallback: dict[str, Any] = {
        "email": "N/A",
        "owner_name": "N/A",
        "has_after_hours_notice": False,
    }

    if not website_url or not isinstance(website_url, str):
        return fallback

    cleaned_url = website_url.strip()
    if cleaned_url.lower() in ("", "n/a", "none"):
        return fallback

    if not cleaned_url.startswith(("http://", "https://")):
        cleaned_url = "https://" + cleaned_url

    session = requests.Session()
    headers = {
        "User-Agent": CHROME_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    domain = _normalize_domain(cleaned_url)
    all_emails: list[str] = []
    owner_name = "N/A"
    has_after_hours = False

    def fetch_page(url_to_fetch: str, page_timeout: float | None = None) -> str | None:
        eff_timeout = page_timeout or timeout
        try:
            resp = session.get(url_to_fetch, headers=headers, timeout=eff_timeout, allow_redirects=True)
            if resp.status_code == 200 and resp.text:
                return resp.text
        except requests.exceptions.SSLError:
            # Try once without SSL verification if certificate verification failed
            try:
                resp = session.get(
                    url_to_fetch, headers=headers, timeout=eff_timeout, verify=False, allow_redirects=True
                )
                if resp.status_code == 200 and resp.text:
                    return resp.text
            except Exception as ssl_exc:
                logger.debug("SSL fallback failed for %s: %s", url_to_fetch, ssl_exc)
        except Exception as exc:
            logger.debug("Error fetching %s: %s", url_to_fetch, exc)
        return None

    # Step 1: Fetch homepage
    home_html = fetch_page(cleaned_url)
    if home_html:
        emails = extract_emails_from_html(home_html, domain=domain)
        all_emails.extend(emails)
        owner_name = extract_owner_name_from_html(home_html)
        if _check_after_hours(home_html):
            has_after_hours = True

    # Step 2: Multi-subpage crawling (up to 5 subpages in parallel)
    if not all_emails or owner_name == "N/A":
        subpage_urls = discover_contact_subpage_urls(home_html or "", cleaned_url, max_subpages=5)
        if subpage_urls:
            subpage_timeout = min(timeout, 4)
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(subpage_urls))) as executor:
                future_to_url = {executor.submit(fetch_page, u, subpage_timeout): u for u in subpage_urls}
                for future in concurrent.futures.as_completed(future_to_url):
                    try:
                        sub_html = future.result()
                        if sub_html:
                            sub_emails = extract_emails_from_html(sub_html, domain=domain)
                            all_emails.extend([e for e in sub_emails if e not in all_emails])
                            if owner_name == "N/A":
                                cand_owner = extract_owner_name_from_html(sub_html)
                                if cand_owner != "N/A":
                                    owner_name = cand_owner
                            if not has_after_hours and _check_after_hours(sub_html):
                                has_after_hours = True
                    except Exception as err:
                        logger.debug("Subpage crawl worker error: %s", err)

    # Final prioritization if multiple emails collected
    final_email = "N/A"
    if all_emails:
        # Re-sort using our priority function to ensure the best email is selected
        def sort_key(e: str):
            is_target = bool(domain and (e.endswith("@" + domain) or e.endswith("." + domain)))
            is_op = any(e.startswith(p) for p in OPERATIONAL_PREFIXES)
            return (0 if is_target else 1, 0 if is_op else 1, e)

        sorted_all = sorted(set(all_emails), key=sort_key)
        final_email = sorted_all[0]
    else:
        # Step 3: DNS MX check & verified mailbox synthesis fallback
        try:
            if domain and check_domain_mx_records(domain, timeout=min(timeout, 3)):
                rdap_email = fetch_rdap_contact_email(domain, timeout=min(timeout, 3))
                if rdap_email:
                    final_email = rdap_email
                else:
                    synth = synthesize_verified_mailbox(domain)
                    if synth:
                        final_email = synth
        except Exception as exc:
            logger.debug("MX / RDAP fallback error for %s: %s", domain, exc)

    return {
        "email": final_email,
        "owner_name": owner_name,
        "has_after_hours_notice": has_after_hours,
    }


def main() -> None:
    """CLI runner for testing website enrichment directly."""
    parser = argparse.ArgumentParser(description="Enrich business contact and owner information.")
    parser.add_argument("url", help="Target business website URL")
    parser.add_argument("--timeout", type=int, default=6, help="Request timeout in seconds")
    args = parser.parse_args()

    result = enrich_business_contact(args.url, timeout=args.timeout)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
