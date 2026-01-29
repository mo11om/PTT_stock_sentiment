# 📈 PTT Sentiment Alpha: Local Production Build

> **Senior Architect Spec**: A high-performance, local data pipeline for correlating Taiwanese retail sentiment with market movement.

---

## 🚀 Overview
PTT Sentiment Alpha is a quant-oriented tool designed to extract retail sentiment from the **PTT Stock Board** and align it with the **Taiwan Weighted Index (^TWII)**. It features a robust, local-first architecture using SQLite with WAL mode to handle concurrent data ingestion and visualization.

### Core Value Proposition
- **Retail Signal Extraction**: Converts fragmented slang-heavy discussions into quantitative sentiment scores.
- **Trading Day Alignment**: Automatically shifts sentiment signals posts to the correct trading day (13:30 UTC+8 cutoff).
- **Z-Score Analysis**: Identifies statistical outliers in sentiment to generate "Alpha" signals.
- **Zero-Infra Setup**: Runs entirely on a local machine without Docker or external DB hosting.

---

## 🛠️ Tech Stack
- **Languages**: Python 3.10+
- **Database**: SQLite 3 (WAL Mode Enabled)
- **ORM**: SQLAlchemy 2.0
- **Analysis**: Pandas, NumPy
- **Scraping**: Requests, BeautifulSoup4
- **Market Data**: `yfinance` (^TWII)
- **UI/Viz**: Streamlit, Plotly (Taiwan-Standard Color Logic)

---

## 📂 System Architecture
The system is built as a modular pipeline:

```text
/home/mo1om/code/interest/stock/
├── src/
│   ├── database/         # Data Access Layer
│   │   ├── database.py   # Connection with WAL mode
│   │   └── models.py     # Schema: Post, Sentiment (Z-Score), MarketData
│   ├── scraper/          # Data Ingestion
│   │   └── ptt_scraper.py # Incremental crawler (Newest -> Oldest)
│   ├── analysis/         # Core Logic
│   │   └── engine.py     # Slang Normalization + Trading Day Shift + Z-Score
│   └── dashboard/        # Presentation
│       └── app.py        # Streamlit Dual-Axis Visualization
├── run_pipeline.py       # Orchestrator (Scrape -> Analyze -> Sync)
└── ptt_sentiment.db      # Local Persistent Store (SQLite)
```

---

## 🏮 Regional Constraints (CRITICAL)
This project adheres strictly to **Taiwan Stock Exchange (TWSE)** conventions:

1.  **Color Logic**:
    -   🔴 **RED** (`#FF0000`): **Bullish** / Price Up
    -   🟢 **GREEN** (`#00FF00`): **Bearish** / Price Down
2.  **Timezone**: `Asia/Taipei` (UTC+8)
3.  **Market Hours**: 09:00 - 13:30.
4.  **Effective Trading Day**:
    -   Posts published **after 13:30** are assigned to the **next trading day**.
    -   Weekends/Holidays are shifted to the next open market day (Monday).

---

## ⚙️ Module Implementation Details

### 1. Database (`src/database/`)
-   **WAL Mode**: Write-Ahead Logging is enabled to allow the Dashboard (Read) and Scraper (Write) to run concurrently.
-   **Schema**:
    -   `Post`: Raw text data and author info.
    -   `Sentiment`: Computed `raw_score` and `z_score`.
    -   `MarketData`: Daily OHLCV for ^TWII.

### 2. Analysis Engine (`src/analysis/`)
-   **Slang Dictionary**:
    -   **Bearish** (-1.0): "丸子" (Dead), "綠光" (Green Light), "睡公園" (Homeless).
    -   **Bullish** (+1.0): "睏霸數錢" (Rich), "歐印" (All-in), "飛向宇宙" (To the Moon).
-   **Negation Logic**: Handles patterns like "不要歐印" (Don't All-in) -> Flips score to Bearish.
-   **Alpha Signal**: Uses a **20-day Rolling Z-Score** to generate signals, filtering out daily noise.

### 3. Dashboard (`src/dashboard/`)
-   **Dual-Axis Chart**:
    -   Left: TWII Close Price (Line).
    -   Right: Sentiment Z-Score (Bar).
-   **Visuals**: Strict adherence to Red/Green color coding.

---

## ⚡ Quick Start

### 1. Installation
```bash
pip install -r requirements.txt
```

### 2. Run the Pipeline
Scrape new posts, calculate sentiment, and sync market prices:
```bash
python run_pipeline.py --pages 10
```

### 3. Launch Dashboard
Visualize the Alpha:
```bash
streamlit run src/dashboard/app.py
```

---

## 🛡️ License
MIT. Built for research and educational purposes.
