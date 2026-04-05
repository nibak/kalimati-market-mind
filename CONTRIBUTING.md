# Contributing to kalimati-market-mind

Thank you for your interest in contributing! This project welcomes contributions of all kinds — bug fixes, new features, data improvements, and documentation.

---

## Ways to Contribute

- **Report a bug** — something broken or displaying incorrectly
- **Suggest a feature** — a chart, analysis, or data view you'd like to see
- **Improve the data** — corrections or additions to the commodity dataset
- **Fix or improve the code** — ETL pipeline, dashboard pages, ML models
- **Improve documentation** — README, code comments, setup instructions

---

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/kalimati-market-mind.git
   cd kalimati-market-mind
   ```
3. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. Run the ETL to build the database:
   ```bash
   python run_etl.py
   ```
5. Launch the dashboard to verify everything works:
   ```bash
   streamlit run app/dashboard/Home.py
   ```

---

## Making Changes

1. Create a new branch for your change:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes
3. Test locally — run the ETL and check the dashboard pages affected by your change
4. Commit with a clear message:
   ```bash
   git commit -m "Add monthly price comparison chart"
   ```
5. Push and open a Pull Request against the `main` branch

---

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Describe what you changed and why in the PR description
- If your change affects the dashboard, include a screenshot
- If your change affects the ETL or database schema, mention which years/sheets were tested

---

## Reporting Bugs

Open an issue and include:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Python version and OS

---

## Code Style

- Follow the existing code style (PEP 8)
- Use relative paths — no hardcoded absolute paths
- All chart month labels must use BS month names (via `app/utils/bs_calendar.py`)

---

## Questions?

Open an issue with the `question` label and we'll get back to you.
