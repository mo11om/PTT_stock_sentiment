# PTT Sentiment Alpha: AI Context & Specification

> **Purpose**: This document serves as the single source of truth for AI agents (Cursor, Windsurf, Copilot) to understand the project architecture, constraints, and business logic.

---

## 1. Project Identity
**Name**: PTT Sentiment Alpha
**Goal**: Correlate retail sentiment from the PTT Stock Board with the Taiwan Weighted Index (^TWII) using a localized, high-performance Python pipeline.
**Architecture**: Local-First (No Docker), SQLite-based, Modular.

---

## 2. Technical Stack & Constraints

### Infrastructure
*   **Language**: Python 3.10+
*   **Database**: SQLite (`ptt_sentiment.db`)
    *   **CRITICAL**: MUST run in **WAL Mode** (`PRAGMA journal_mode=WAL`) to allow concurrent Scraper (Write) and Dashboard (Read).
*   **UI**: Streamlit + Plotly.

### Regional "Hard Rules" (Taiwan)
1.  **Color Logic**:
    *   🔴 **RED** (`#FF0000`) = **Bullish** / Up / Positive
    *   🟢 **GREEN** (`#00FF00`) = **Bearish** / Down / Negative
2.  **Market Hours**: 09:00 - 13:30 (UTC+8).
3.  **Trading Day Alignment**:
    *   Post Time > 13:30 → shifted to **Next Trading Day**.
    *   Weekends (Sat/Sun) → shifted to **Monday**.

---

## 3. Database Schema (SQLAlchemy)

### `Post` Table
*   `id` (PK, String): PTT ID (e.g., `M.161...`).
*   `title` (String), `content` (Text), `author` (String).
*   `publish_time` (DateTime): The actual crawl timestamp.
*   `push_count` (Int), `boo_count` (Int).

### `Sentiment` Table
*   `post_id` (PK, ForeignKey -> Post.id).
*   `raw_score` (Float): `[-1.0, 1.0]`. Base score derived from slang + interactions.
*   `z_score` (Float): **The Alpha Signal**. Rolling 20-day deviation from mean.
*   `effective_date` (Date): The calculated trading day (post-shift).
*   `tokens_found` (String): Debug string of matched slang terms.

### `MarketData` Table
*   `date` (PK, Date).
*   `open`, `high`, `low`, `close` (Float).
*   `volume` (Int).

---

## 4. Core Algorithms

### A. Slang Normalization (`SlangNormalizer`)
Uses a dictionary-based approach with negation handling.
*   **Bullish Tokens**: `歐印` (All-in), `飛向宇宙` (To the moon), `睏霸數錢`.
*   **Bearish Tokens**: `丸子` (Dead), `綠光` (Green light), `睡公園` (Homeless), `畢業`.
*   **Negation**: "不要" (Don't) before a token flips its sign.

### B. Weighted Sentiment Formula
$$ Score = \text{Base} \times \text{Weight} $$
*   **Base**: Mean of tokens found (-1 to +1).
*   **Weight**: $1 + \frac{Push - (Boo \times 1.5)}{50}$
*   *Note*: "Boos" (嘘) are weighted **1.5x** to capture strong negative analyst sentiment on PTT.

### C. Z-Score (The Signal)
$$ Z = \frac{S_{today} - \mu_{20}}{\sigma_{20}} $$
*   Compares the Daily Average Sentiment ($S_{today}$) against the 20-day Moving Average.
*   Used to filter out noise and identify true "Surges".

---

## 5. Directory Map

```text
/src
  ├── analysis/
  │   ├── engine.py        # Logic: calculate_trading_day, SlangNormalizer, SentimentEngine
  │   └── slang_miner.py   # Utility: Finds new slang words using TF-IDF
  ├── dashboard/
  │   └── app.py           # UI: Streamlit, dual-axis Chart (Red/Green)
  ├── database/
  │   ├── database.py      # Infra: create_engine, WAL setup
  │   └── models.py        # Schema: Post, Sentiment, MarketData classes
  └── scraper/
      └── ptt_scraper.py   # Ingestion: Incremental logic (Stop if ID exists)
root
  ├── run_pipeline.py      # Orchestrator: Scrape -> Analyze -> Sync
  └── requirements.txt     # Deps: sqlalchemy, streamlit, plotly, yfinance, requests
```

---

## 6. Execution Workflow
1.  **Ingest**: `run_pipeline.py` calls `PTTScraper` to fetch *only new* posts since last run.
2.  **Process**: `SentimentEngine` fetches unanalyzed posts, computes scores, and saves to DB.
3.  **Sync**: Fetches missing `^TWII` data from `yfinance`.
4.  **Visualize**: User launches `streamlit run src/dashboard/app.py` to view valid signals.
