# PTT Sentiment Alpha (Local Production Build) 📈

A robust, self-contained data pipeline and dashboard for correlating **PTT Stock Board** community sentiment with the **Taiwan Weighted Index (^TWII)**.

This system monitors Taiwan's largest online trading community, decodes specialized financial slang, and visualizes the correlation between social momentum and market movements using a modern SQLite-backed architecture.

---

## 🌟 Key Features

- **� Smart Incremental Scraper**: Optimized PTT scraper that only fetches new threads. It automatically stops when it encounters data already stored in the local database.
- **🗄️ SQLite + SQLAlchemy 2.0 Backend**: Moving beyond flat JSON files to a relational database for reliable storage of posts, sentiment scores, and market data.
- **🏮 Advanced Slang Decoding**: A specialized engine that translates unique Taiwanese "financial linguistics" (e.g., *睏霸數錢*, *歐印*, *丸子*) into quantifiable sentiment.
- **💹 Market Data Integration**: Automated synchronization with `yfinance` for ^TWII historical and real-time data.
- **📊 Real-time Dashboard**: A high-performance **Streamlit** dashboard featuring:
    - **Dual-Axis Charts**: Overnight sentiment scores vs. TWSE price action.
    - **Taiwan Color Logic**: Explicitly forced **Red = Up**, **Green = Down** matching local market standards.
    - **Alpha Signals**: Moving average sentiment indicators to identify potential market turns.

---

## 📁 Project Structure

```text
.
├── src/
│   ├── database/
│   │   ├── database.py      # SQLite connection & session management
│   │   └── models.py        # SQLAlchemy models (Post, MarketData, Sentiment)
│   ├── scraper/
│   │   └── ptt_scraper.py    # Incremental PTT scraping logic
│   ├── analysis/
│   │   └── engine.py         # Slang normalization & sentiment scoring
│   └── dashboard/
│       └── app.py            # Streamlit visualization interface
├── ptt_sentiment.db          # Local SQLite Database
├── run_pipeline.py           # Orchestration script (Cron-ready)
├── requirements.txt          # Python dependencies
└── config.json               # Pipeline configuration
```

---

## 🛠️ Installation & Setup

### 1. Requirements
- Python 3.10+
- `conda` or `venv` recommended.

### 2. Install Dependencies
```bash
pip install sqlalchemy streamlit yfinance beautifulsoup4 requests pandas plotly
```

### 3. Initialize & Run Pipeline
The `run_pipeline.py` script orchestrates the entire flow (Scrape -> Analyze -> Sync Market).
```bash
python run_pipeline.py
```

---

## 🚀 Usage

### Monitoring the Market
To launch the interactive dashboard and view the sentiment correlation:
```bash
streamlit run src/dashboard/app.py
```

### Automation
The system is designed to be "Cron-friendly". You can schedule `run_pipeline.py` to run every hour to keep your local database and sentiment signals up to date.

---

## 🏮 The PTT Sentiment Dictionary

| Term | Context | Logic | Signal |
| :--- | :--- | :--- | :--- |
| **歐印 (All-in)** | High conviction | `BULLISH_CONFIDENCE` | 🟢 Bullish |
| **睏霸數錢** | Profit taking/Confidence | `BULLISH_CONFIDENCE` | 🟢 Bullish |
| **丸子/完蛋** | Panic | `BEARISH_PANIC` | 🔴 Bearish |
| **畢業 (Graduate)** | Stop loss | `BEARISH_PANIC` | 🔴 Bearish |
| **綠光罩頂** | Market crash | `BEARISH_PANIC` | 🔴 Bearish |

---

## ⚠️ Regional Market Logic
This project respects the unique conventions of the Taiwan Stock Exchange:
- 🔴 **Red (紅)**: Price Increase (Bullish)
- 🟢 **Green (綠)**: Price Decrease (Bearish)

*Note: This is the opposite of many Western markets.*

---
*Created by Antigravity*
