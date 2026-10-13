# Task 3 Brief: Voice AI Pitch Hook & Value Proposition Generator

## Goal
Implement `scripts/hooks.py` to automatically generate personalized, high-converting outreach angles and pain point statements tailored to specific business niches (Dentists, Medical Clinics, HVAC, Legal, Auto Repair).

## Requirements
1. **File to Create:** `scripts/hooks.py`
2. **Test File to Create:** `tests/test_hooks.py`
3. **Functions to Implement:**
   - `generate_voice_ai_hook(niche: str, business_name: str, city: str = "") -> tuple[str, str, str]`:
     Returns 3 structured strings for Google Sheets:
     1. `lead_type` (str): e.g. `"Dental Practice - Inbound Patient Intake & After-Hours Receptionist"`
     2. `pain_point_snippet` (str): Concise operational pain point (e.g. `"Dental offices lose 30-40% of emergency patient inquiries and scheduling calls that occur after 5 PM or during busy lunch hours."`)
     3. `recommended_hook` (str): Outreach pitch tailored to the business and city (e.g. `"Pitch after-hours AI voice receptionist that syncs with Dentrix/calendar to capture missed patient appointments 24/7 without extra payroll."`)
   - Supports key high-call niches:
     - `dental`: Appointment booking, missed new patient calls, emergency after-hours answering.
     - `medical` / `clinic`: Patient intake, prescription refill questions, triage, cancellation rebooking.
     - `hvac` / `plumber`: 24/7 emergency dispatch, seasonal freeze/heatwave surge answering.
     - `legal` / `lawyer`: Instant client pre-qualification, case intake screening, 24/7 retainers.
     - `autorepair`: Repair status lookups, service estimate booking, mechanic interruption prevention.
     - Default/general fallback for other service businesses.
4. **Tests:**
   - Tests covering each niche mapping.
   - Tests ensuring output strings are non-empty and mention relevant value propositions.
5. **Validation:**
   Run tests with `python -m unittest tests/test_hooks.py`.
6. **Commit:**
   `git add scripts/hooks.py tests/test_hooks.py`
   `git commit -m "feat: implement niche-specific Voice AI pitch hook generator"`
