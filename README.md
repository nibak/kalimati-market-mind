# Kalimati Market Mind

An open-source data platform for exploring, visualizing, and forecasting agricultural commodity prices and supply volumes from the Kalimati Fruits & Vegetables Market — covering 21 years of historical data (BS 2060–2081).

---

## Prerequisites

- Python 3.9 or higher
- pip

---

## Data

The full historical dataset (BS 2060–2081, 21 years) is included in `documents/`.

> **Disclaimer:** The raw data files are sourced from the [Kalimati Fruits & Vegetables Market Development Board](https://kalimatimarket.gov.np), a public market institution under the Government of Nepal. They are included here solely for research, educational, and non-commercial purposes. All rights to the original data belong to the Kalimati Market Development Board. If you intend to use this data commercially, please obtain permission directly from the Board.

---

## Setup

### 1. Clone / navigate to the project

```bash
cd kalimati-market-mind
```

### 2. (Recommended) Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running the App

### Step 1 — Run the ETL pipeline (one-time setup)

This reads all 21 Excel files and loads them into a local SQLite database at `data/kalimati.db`.

```bash
python run_etl.py
```

Expected output:
```
Initializing database...
Running ETL pipeline...
Processing year 2060...
Processing year 2061...
...
Processing year 2081...
ETL complete.
  Commodities : 242
  Price rows  : 23,561
  Vol/month   : 20,004
  Vol/source  : 20,875
Done! Run: streamlit run app/dashboard/Home.py
```

> The ETL is **idempotent** — safe to re-run. It will not create duplicate records.

### Step 2 — Launch the dashboard

```bash
streamlit run app/dashboard/Home.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Dashboard Pages

| Page | What it shows |
|------|---------------|
| **Home** | KPI overview, commodity selector, price trend summary |
| **Price Analysis** | Dual-axis price/volume chart, seasonality heatmap, commodity comparison |
| **Supply Analysis** | Annual supply bar chart, monthly pattern, year-over-year comparison |
| **Geographic Supply** | Treemap of supply sources, domestic vs import pie chart, top-5 sources |
| **Forecasting** | SARIMA price forecast with confidence intervals, anomaly detection, seasonal pattern |

---

## Project Structure

```
storage-facility-plan/
├── app/
│   ├── db/database.py           # SQLite schema + connection
│   ├── etl/
│   │   ├── extractor.py         # Reads raw Excel files
│   │   ├── transformer.py       # Pivots wide → long format
│   │   └── loader.py            # Loads data into SQLite
│   ├── ml/
│   │   ├── forecasting.py       # SARIMA price forecasting
│   │   └── anomaly.py           # Z-score anomaly detection
│   ├── utils/commodity_mapper.py
│   └── dashboard/
│       ├── Home.py              # Main Streamlit entry point
│       └── pages/               # Dashboard sub-pages
├── data/kalimati.db             # Created after running ETL
├── documents/Kalimati Data/     # Raw Excel source files
├── requirements.txt
└── run_etl.py                   # ETL entry point
```

---

## Troubleshooting

**`ModuleNotFoundError`** — Make sure you activated the virtual environment and ran `pip install -r requirements.txt`.

**`FileNotFoundError` for Excel files** — Run all commands from the project root (`storage-facility-plan/`), not from inside a subdirectory.

**Dashboard shows no data** — Make sure `run_etl.py` completed successfully before launching Streamlit.

**SARIMA forecast takes long** — Normal for first run per commodity. Results are not cached between sessions; consider adding `st.cache_data` TTL if needed.
