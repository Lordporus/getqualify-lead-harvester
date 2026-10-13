"""Voice AI Pitch Hook & Value Proposition Generator.

Translates discovered local business niches into high-converting, personalized
cold outreach angles and operational pain points tailored for B2B Voice AI sales.
Populates Google Sheets lead rows with operational lead types, pain point snippets,
and customized outreach hooks.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

# Canonical niche registry containing structured hooks and value propositions
NICHE_PROFILES: Dict[str, Dict[str, Any]] = {
    "dental": {
        "lead_type": "Dental Practice - Inbound Patient Intake & After-Hours Receptionist",
        "default_target": "dental practices",
        "pain_point_standard": (
            "Dental offices lose 30-40% of emergency patient inquiries and scheduling "
            "calls that occur after 5 PM or during busy lunch hours. High patient lifetime "
            "value ($1,200+) makes missed new patient calls exceptionally costly."
        ),
        "pain_point_with_biz": (
            "Dental offices like {biz} lose 30-40% of emergency patient inquiries and scheduling "
            "calls that occur after 5 PM or during busy lunch hours. High patient lifetime "
            "value ($1,200+) makes uncaptured calls exceptionally costly."
        ),
        "pain_point_after_hours": (
            "While {biz} lists emergency or after-hours care, manual on-call routing causes delays. "
            "Dental offices lose 30-40% of emergency inquiries and booking calls after 5 PM, risking high-LTV patients ($1,200+)."
        ),
        "hook_standard": (
            "Pitch {target} an after-hours AI voice receptionist that syncs with "
            "Dentrix/calendar to capture missed patient appointments 24/7 without extra payroll."
        ),
        "hook_after_hours": (
            "Pitch {target} an AI voice receptionist to upgrade after-hours emergency intake, "
            "syncing with Dentrix/calendar to capture new patient bookings 24/7 without staff burnout."
        ),
    },
    "medical": {
        "lead_type": "Medical Clinic - Patient Intake & Prescription Triage Receptionist",
        "default_target": "medical clinics",
        "pain_point_standard": (
            "High call volumes for appointment scheduling, prescription refills, and routine "
            "triage overwhelm front-desk clinic staff, resulting in long hold times, patient "
            "frustration, and dropped bookings."
        ),
        "pain_point_with_biz": (
            "High call volumes for appointment scheduling, prescription refills, and routine triage "
            "overwhelm front-desk staff at clinics like {biz}, resulting in long hold times, patient "
            "frustration, and dropped appointments."
        ),
        "pain_point_after_hours": (
            "While {biz} maintains after-hours triage, clinical staff remain overburdened with routine "
            "refill and booking inquiries, leading to delayed patient care and front-desk turnover."
        ),
        "hook_standard": (
            "Pitch {target} an intelligent Voice AI intake assistant that answers patient FAQs, "
            "automates appointment scheduling, routes urgent triage calls, and handles "
            "cancellation rebooking 24/7."
        ),
        "hook_after_hours": (
            "Pitch {target} a HIPAA-ready Voice AI assistant to streamline after-hours patient intake, "
            "automate routine prescription refill questions, and instantly rebook cancellations 24/7."
        ),
    },
    "hvac": {
        "lead_type": "HVAC & Plumbing - 24/7 Emergency Dispatch & Call Capture",
        "default_target": "contractors",
        "pain_point_standard": (
            "During seasonal weather extremes and after hours, homeowners with HVAC or plumbing "
            "emergencies immediately call a competitor if a call goes to voicemail while field techs are busy."
        ),
        "pain_point_with_biz": (
            "HVAC and plumbing contractors like {biz} lose high-ticket emergency dispatch jobs "
            "when inbound calls hit voicemail during seasonal weather spikes or after-hours technician runs."
        ),
        "pain_point_after_hours": (
            "While {biz} advertises emergency on-call service, missed or delayed callback responses "
            "cause urgent homeowners to call competing dispatchers who answer live on ring one."
        ),
        "hook_standard": (
            "Pitch {target} a 24/7 Voice AI dispatch assistant that immediately answers emergency "
            "calls on the first ring, pre-qualifies job details, and dispatches on-call technicians "
            "before competitors can respond."
        ),
        "hook_after_hours": (
            "Pitch {target} an automated 24/7 Voice AI dispatch receptionist to capture every emergency "
            "heating/cooling call live on ring one and route jobs directly to on-call technicians."
        ),
    },
    "legal": {
        "lead_type": "Law Firm - 24/7 Client Intake & Pre-Qualification Assistant",
        "default_target": "law firms",
        "pain_point_standard": (
            "Prospective legal clients rarely leave voicemails—they immediately retain the next available "
            "attorney who answers live. Playing telephone tag with unvetted leads delays intake and wastes "
            "valuable billable hours."
        ),
        "pain_point_with_biz": (
            "Law firms like {biz} lose lucrative new client retainers when prospective claimants call after "
            "hours or get placed on hold, immediately signing with competing practices."
        ),
        "pain_point_after_hours": (
            "While {biz} provides after-hours contact options, unvetted voicemail inquiries require hours "
            "of follow-up telephone tag, losing time-sensitive retainers to faster-responding firms."
        ),
        "hook_standard": (
            "Pitch {target} a 24/7 Voice AI legal intake assistant that instantly pre-qualifies "
            "prospective case claims, screens unviable inquiries, and books qualified retainer "
            "consultations directly onto attorney calendars."
        ),
        "hook_after_hours": (
            "Pitch {target} a 24/7 Voice AI intake assistant to pre-qualify and lock in urgent new "
            "retainer inquiries after hours before prospective claimants contact competing firms."
        ),
    },
    "autorepair": {
        "lead_type": "Auto Repair & Mechanic - Service Estimate Intake & Status Line",
        "default_target": "auto repair shops",
        "pain_point_standard": (
            "Service advisors and mechanics lose 1-2 billable hours daily to repetitive 'Is my car ready?' "
            "status calls and quote requests, interrupting active bay work and delaying vehicle turnaround."
        ),
        "pain_point_with_biz": (
            "Auto repair shops like {biz} lose 1-2 billable hours daily to repetitive 'Is my car ready?' "
            "status calls and quote requests, constantly interrupting technicians and advisors on the floor."
        ),
        "pain_point_after_hours": (
            "While {biz} offers key-drop or after-hours drop-off, vehicle owners cannot get instant status "
            "or scheduling confirmations, creating morning front-counter bottlenecks."
        ),
        "hook_standard": (
            "Pitch {target} an automated Voice AI service assistant that provides instant vehicle repair "
            "status lookups, books diagnostic drop-offs, and captures estimate inquiries 24/7 without "
            "interrupting mechanics in the bay."
        ),
        "hook_after_hours": (
            "Pitch {target} an automated Voice AI service advisor to handle evening status lookups and "
            "capture morning drop-off bookings 24/7 so technicians start wrenching immediately at opening."
        ),
    },
    "general": {
        "lead_type": "Local Service Business - 24/7 Front Desk & Call Capture Receptionist",
        "default_target": "service businesses",
        "pain_point_standard": (
            "Local service businesses lose up to 40% of inbound sales inquiries when calls go unanswered "
            "during busy hours or after close, as customers immediately contact the next competitor."
        ),
        "pain_point_with_biz": (
            "Local service businesses like {biz} miss high-intent customer inquiries when calls go "
            "unanswered during peak hours or after close, driving prospective clients to local competitors."
        ),
        "pain_point_after_hours": (
            "While {biz} has after-hours contact channels, slow response times cause high-intent "
            "prospects to browse and purchase from immediate-responding competitors."
        ),
        "hook_standard": (
            "Pitch {target} a 24/7 Voice AI receptionist to answer customer FAQs, pre-qualify service "
            "inquiries, and schedule appointments directly into the calendar without extra payroll."
        ),
        "hook_after_hours": (
            "Pitch {target} a 24/7 Voice AI answering service to capture after-hours customer calls "
            "live on ring one, answer inquiries, and book consultations directly into the calendar."
        ),
    },
}


def normalize_niche(niche: str | None) -> str:
    """Normalize user or directory niche terms to canonical registry keys.

    Args:
        niche: Raw niche string, e.g. 'dental', 'dentist', 'clinic', 'plumber', 'lawyer'.

    Returns:
        One of 'dental', 'medical', 'hvac', 'legal', 'autorepair', or 'general'.
    """
    if not niche:
        return "general"

    s = niche.strip().lower()
    # Normalize separators
    s_clean = re.sub(r"[_\-\/\s]+", " ", s)

    # Dental
    if any(k in s_clean for k in ("dental", "dentist", "orthodont", "teeth")):
        return "dental"

    # Medical / Clinic
    if any(
        k in s_clean
        for k in (
            "medical",
            "clinic",
            "doctor",
            "physician",
            "health",
            "urgent care",
            "pediatric",
            "dermatol",
            "chiropract",
        )
    ):
        return "medical"

    # HVAC / Plumbing
    if any(
        k in s_clean
        for k in (
            "hvac",
            "plumb",
            "heating",
            "air condition",
            "cooling",
            "furnace",
            "climate",
        )
    ):
        return "hvac"

    # Legal / Law Firm
    if any(
        k in s_clean
        for k in ("legal", "lawyer", "attorney", "law firm", "law office", "litigat")
    ):
        return "legal"

    # Auto Repair / Mechanic
    if any(
        k in s_clean
        for k in (
            "autorepair",
            "auto repair",
            "mechanic",
            "car repair",
            "automotive",
            "body shop",
            "transmission",
            "car_repair",
        )
    ):
        return "autorepair"

    return "general"


def _format_target(
    business_name: str = "",
    city: str = "",
    owner_name: str = "",
    default_target: str = "the business",
) -> str:
    """Construct a clean, natural outreach target phrase."""
    b_name = business_name.strip() if business_name else ""
    c_name = city.strip() if city else ""
    o_name = owner_name.strip() if owner_name and owner_name.upper() != "N/A" else ""

    if o_name and b_name and c_name:
        return f"{o_name} at {b_name} in {c_name}"
    elif o_name and b_name:
        return f"{o_name} at {b_name}"
    elif o_name and c_name:
        return f"{o_name} in {c_name}"
    elif o_name:
        return o_name
    elif b_name and c_name:
        return f"{b_name} in {c_name}"
    elif b_name:
        return b_name
    elif c_name:
        return f"{default_target} in {c_name}"
    else:
        return default_target


def generate_voice_ai_hook(
    niche: str,
    business_name: str,
    city: str = "",
    owner_name: str = "",
    has_after_hours_notice: bool = False,
) -> Tuple[str, str, str]:
    """Generate high-converting Voice AI outreach angles and operational pain points.

    Args:
        niche: Business industry (e.g. 'dental', 'medical', 'hvac', 'legal', 'autorepair').
        business_name: Target company or clinic name.
        city: Target city or metro area (optional).
        owner_name: Doctor / attorney / owner name if enriched (optional).
        has_after_hours_notice: True if website already advertises after-hours care (optional).

    Returns:
        tuple[str, str, str]:
            1. lead_type: Standardized operational role description.
            2. pain_point_snippet: Concise bottleneck statement tailored to the niche and business.
            3. recommended_hook: Personalized outreach pitch tailored to the business and city.
    """
    canon_niche = normalize_niche(niche)
    profile = NICHE_PROFILES.get(canon_niche, NICHE_PROFILES["general"])

    lead_type = profile["lead_type"]
    default_target = profile.get("default_target", "the business")

    target = _format_target(
        business_name=business_name,
        city=city,
        owner_name=owner_name,
        default_target=default_target,
    )

    biz_name_clean = business_name.strip() if business_name else ""

    # Select pain point snippet based on after-hours notice and business context
    if has_after_hours_notice and biz_name_clean:
        pain_point = profile["pain_point_after_hours"].format(biz=biz_name_clean)
    elif biz_name_clean:
        pain_point = profile["pain_point_with_biz"].format(biz=biz_name_clean)
    else:
        pain_point = profile["pain_point_standard"]

    # Select recommended hook
    if has_after_hours_notice:
        hook = profile["hook_after_hours"].format(target=target)
    else:
        hook = profile["hook_standard"].format(target=target)

    return (lead_type, pain_point, hook)


def main() -> None:
    """CLI test utility for generating Voice AI hooks."""
    parser = argparse.ArgumentParser(
        description="Generate tailored Voice AI hooks and pain points for B2B leads."
    )
    parser.add_argument(
        "--niche",
        default="dental",
        help="Business industry (dental, medical, hvac, legal, autorepair)",
    )
    parser.add_argument(
        "--business",
        default="Apex Dental",
        help="Target company or practice name",
    )
    parser.add_argument(
        "--city",
        default="Austin",
        help="Target city or metropolitan area",
    )
    parser.add_argument(
        "--owner",
        default="",
        help="Doctor / owner / manager name",
    )
    parser.add_argument(
        "--after-hours",
        action="store_true",
        help="Flag if business already advertises after-hours coverage",
    )
    args = parser.parse_args()

    lead_type, snippet, hook = generate_voice_ai_hook(
        niche=args.niche,
        business_name=args.business,
        city=args.city,
        owner_name=args.owner,
        has_after_hours_notice=args.after_hours,
    )

    print(
        json.dumps(
            {
                "niche": args.niche,
                "business_name": args.business,
                "city": args.city,
                "lead_type": lead_type,
                "pain_point_snippet": snippet,
                "recommended_hook": hook,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
