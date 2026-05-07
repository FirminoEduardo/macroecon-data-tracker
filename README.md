# MacroEcon Data Tracker

An end-to-end data engineering pipeline that correlates geopolitical tension scores with Brent crude oil prices, built entirely on Azure.

---

## Overview

This project collects two data sources daily and stores them in Azure for analytical querying:

- **GDELT Tone Score** — sentiment index derived from global news coverage of Middle East geopolitical tensions. A more negative value indicates higher tension.
- **Brent Crude Price** — daily closing price of the Brent crude oil futures contract (ticker: `BZ=F`), sourced via yfinance.

The analytical objective is to observe whether increases in geopolitical tension correlate with increases in oil prices.

---

## Architecture

The pipeline follows a medallion architecture (Bronze/Gold) and runs fully on Azure.

```
GDELT API ─────┐
               ├──► Azure Functions ──► ADLS Gen2 (Bronze) ──► Azure Functions ──► ADLS Gen2 (Gold) ──► Synapse Serverless ──► Metabase
yfinance API ──┘     (Extraction)        Raw JSON               (Transformation)     Parquet                (vw_combined)         Dashboard
```

| Layer | Service | Role |
|---|---|---|
| Extraction | Azure Functions — Timer Trigger (01:00 UTC) | Calls GDELT and yfinance APIs daily |
| Bronze | ADLS Gen2 — `bronze` container | Stores raw JSON files partitioned by date |
| Transformation | Azure Functions — Timer Trigger (01:30 UTC) | Joins sources, applies forward fill, outputs Parquet |
| Gold | ADLS Gen2 — `gold` container | Stores cleaned Parquet files partitioned by date |
| Analytics | Azure Synapse Analytics Serverless | SQL view over Gold Parquet files |
| Visualization | Metabase (Docker) | Dashboard correlating tension vs. price |

### Bronze Storage Structure

```
bronze/
├── yfinance/
│   └── {year}/{month}/{day}/brent.json
└── gdelt/
    └── {year}/{month}/{day}/tone.json
```

### Gold Storage Structure

```
gold/
└── combined/
    └── ano={year}/mes={month}/dia={day}/data.parquet
```

---

## Dashboard

![MacroEcon Dashboard](docs/dashboard.png)

The dashboard displays Brent crude price (left axis) and GDELT Tone Score (right axis) over the same time series, allowing visual inspection of their correlation.

---

## Data Schema

**Bronze — yfinance** (`brent.json`):
```json
{
  "fonte": "yfinance",
  "ticker": "BZ=F",
  "data": "2026-04-23",
  "preco_fechamento_usd": 105.07
}
```

**Bronze — GDELT** (`tone.json`):
```json
{
  "fonte": "gdelt",
  "query": "Middle East conflict geopolitical tension",
  "data": "2026-04-23",
  "tone_score_medio": -0.8219,
  "total_registros_horarios": 82
}
```

**Gold — Combined** (`data.parquet`):

| Column | Type | Description |
|---|---|---|
| `data` | string | Reference date (YYYY-MM-DD) |
| `brent_preco_usd` | float | Brent closing price in USD |
| `brent_forward_fill` | boolean | True if price was carried forward from a prior trading day |
| `gdelt_tone_score` | float | Average tone score for the day (negative = more tension) |
| `gdelt_total_registros` | integer | Number of hourly GDELT records used in the average |

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Azure over AWS | Career focus on Azure ecosystem |
| No PySpark or Databricks | Data volume is two records per day — Spark is unjustifiable at this scale |
| No FRED API | Monthly frequency is incompatible with a daily pipeline |
| Synapse Serverless over Dedicated Pool | Near-zero cost, queries run directly over the Data Lake without data movement |
| GDELT `timelinetone` mode | Only mode that returns tone values — `artlist` does not expose the tone field |
| Forward fill for weekends | Oil markets close on weekends; GDELT continues publishing. Friday's price is carried forward to Saturday and Sunday to maintain join integrity |
| `sleep(6)` + retry with backoff | GDELT rate limit discovered empirically at approximately 1 request per 5 seconds |
| Metabase via Docker | No Windows dependency — runs cross-platform and connects to Synapse Serverless via SQL Server driver |

---

## Azure Resources

| Resource | Name | Type |
|---|---|---|
| Resource Group | `macroecon-rg` | Resource Group (Central US) |
| Data Lake | `macroecondatalake` | ADLS Gen2 |
| Function App | `macroecon-extractor` | Azure Functions (Python 3.11, Flex Consumption) |
| Synapse Workspace | `macroecon-synapse` | Azure Synapse Analytics |

---

## Local Development

### Prerequisites

- Python 3.11
- Azure Functions Core Tools v4
- Docker (for Metabase)
- Azure CLI

### Setup

```bash
git clone https://github.com/FirminoEduardo/macroecon-data-tracker.git
cd macroecon-data-tracker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configure `local.settings.json`:
```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "<macroeconstorage_connection_string>",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "ADLS_CONNECTION_STRING": "<macroecondatalake_connection_string>",
    "PYTHONPATH": "/path/to/.venv/lib/python3.11/site-packages"
  }
}
```

### Running locally

```bash
# Start the function host
func start

# Trigger extraction manually (separate terminal)
curl -X POST "http://localhost:7071/admin/functions/extraction_timer" \
  -H "Content-Type: application/json" \
  -d "{}"

# Trigger transformation manually
curl -X POST "http://localhost:7071/admin/functions/transformation_timer" \
  -H "Content-Type: application/json" \
  -d "{}"
```

### Deploy to Azure

```bash
func azure functionapp publish macroecon-extractor
```

---

## Tech Stack

- Python 3.11
- Azure Functions
- Azure Data Lake Storage Gen2
- Azure Synapse Analytics Serverless
- Metabase (Docker)
- yfinance
- GDELT API v2
- pandas / pyarrow