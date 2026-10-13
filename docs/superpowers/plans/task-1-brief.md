# Task 1 Brief: B2B Business Discovery Engine

## Goal
Implement `scripts/b2b_discovery.py` to fetch real local businesses that receive high inbound call volume using free public directory APIs (OpenStreetMap / Overpass API with reliable public mirrors and fallback business directories) without any paid API keys or subscription requirements.

## Requirements
1. **File to Create:** `scripts/b2b_discovery.py`
2. **Test File to Create:** `tests/test_b2b_discovery.py`
3. **Functions to Implement:**
   - `normalize_phone(raw_phone: str) -> str`: Normalizes raw phone strings (e.g. `5125550199`, `+1-512-555-0199`, `(512) 555-0199`) to standard readable format `+1 (512) 555-0199` or standardized international/national format. If invalid or less than 10 digits, returns formatted cleaned digits or `"N/A"`.
   - `fetch_niche_businesses(niche_key: str, city: str, limit: int = 15) -> list[dict]`:
     Queries public OpenStreetMap / Overpass endpoints (e.g. `https://overpass-api.de/api/interpreter`, `https://lz4.overpass-api.de/api/interpreter`, or DuckDuckGo/local directory fallback) for target niches:
     - `dental`: `amenity=dentist`
     - `medical` or `clinic`: `amenity=doctors` or `amenity=clinic`
     - `hvac` or `plumber`: `craft=plumber` or `craft=hvac`
     - `legal` or `lawyer`: `office=lawyer`
     - `autorepair`: `shop=car_repair`
     Filters strictly for records with:
     - A valid business name (`tags.get('name')`)
     - A valid phone number (`tags.get('phone')` or `tags.get('contact:phone')`)
     - A valid website (`tags.get('website')` or `tags.get('contact:website')`)
     Returns list of dicts:
     ```python
     {
         "business_name": str,
         "phone": str,
         "website": str,
         "city": str,
         "niche": str,
         "category": str
     }
     ```
   - Must have fallback data/queries so it never crashes if an Overpass endpoint experiences network latency.
4. **Tests:**
   - Test `normalize_phone` with various formats.
   - Test `fetch_niche_businesses` return type, structure, and required keys.
5. **Validation:**
   Run tests with `python -m unittest tests/test_b2b_discovery.py`. Must pass 100%.
6. **Commit:**
   Commit changes with `git add scripts/b2b_discovery.py tests/test_b2b_discovery.py` and commit message `feat: implement B2B local business discovery engine`.
