# Contributing to B2B Voice AI Lead Harvester

Thank you for your interest in contributing! This project is designed to provide an automated, outreach-ready lead generation pipeline for B2B Voice AI agencies and telephone automation platforms.

---

## Code of Conduct

All contributors and participants are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Local Development Workflow

### 1. Prerequisites
- Python 3.10+ (Python 3.11 recommended)
- `git`
- Virtual environment tool (`venv`)

### 2. Setup
```bash
# Clone your fork
git clone https://github.com/<your-username>/getqualify-lead-harvester.git
cd getqualify-lead-harvester

# Create and activate a virtual environment
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install git+https://github.com/Panniantong/agent-reach.git@94f06c1969dfc1834001269d79d3ad0972d9dee6 || true
pip install ruff bandit
```

### 3. Running the Pipeline Locally
Test the harvester without connecting to Google Sheets using `--dry-run`:
```bash
python scripts/scrape_leads.py --dry-run --limit 5
```

### 4. Running the Test Suite
Ensure all unit and integration tests pass before submitting changes:
```bash
python -m unittest discover tests
```

### 5. Running Linters & Security Scans
```bash
ruff check scripts/ tests/
bandit -r scripts/
```

---

## Pull Request Guidelines

1. **Create a Topic Branch:** Never commit directly to `main`. Use descriptive branch names (`feat/my-feature`, `fix/issue-id`).
2. **Keep Commits Atomic:** Write clear commit messages in conventional commit format (`feat:`, `fix:`, `docs:`, `chore:`).
3. **Never Commit Secrets:** Do not commit API keys, Google Cloud service account JSON keys, or private identifiers.
4. **Update Documentation:** Update `README.md` or relevant documentation when modifying features or CLI parameters.
5. **Open a Pull Request:** Submit your PR against the `main` branch with a clear description of the problem solved.
