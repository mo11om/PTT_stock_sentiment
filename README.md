# PTT Stock Sentiment Analysis System 📈

A sophisticated end-to-end pipeline for scraping, decoding, and analyzing sentiment from the **PTT Stock board** (Taiwan's largest online community) and correlating it with the **Taiwan Weighted Index (^TWII)**.

---

## 🌟 Key Features

- **🚀 Automated PTT Scraper**: Bypasses the 18+ age gate and scrapes the latest threads, including titles, full content, and all push/boo comments.
- **🏮 PTT Slang Decoder**: A specialized engine that translates unique Taiwanese stock market slang (e.g., *睏霸數錢*, *歐印*, *丸子*) into accurate sentiment scores.
- **💹 Market Correlation**: Fetches real-time market data for the Taiwan Weighted Index (^TWII) using `yfinance` to correlate community sentiment with price movements.
- **🎨 Premium Visualizations**: Generates high-quality, dark-mode charts featuring:
    - TWII Price action (with Taiwan-style Red=Up/Green=Down logic).
    - Weighted sentiment distribution.
    - Sentiment heatmap for trend visualization.
- **📊 Detailed Reporting**: Produces JSON reports with top sentiment tokens, bullish/bearish ratios, and overall market outlook.

---

## 📁 Project Structure

```text
.
├── src/
│   ├── scraper/
│   │   └── ptt_scraper.py      # PTT web scraping logic
│   └── analysis/
│       └── analysis_pipeline.py # Sentiment analysis & visualization
├── data/
│   └── raw/                    # Storage for raw scraped JSON data
├── output/                     # Generated charts and reports (.png, .json)
├── config.json                 # Global configuration parameters
└── plan.md                     # Original project roadmap
```

---

## 🛠️ Installation & Setup

### 1. Requirements
Ensure you have Python 3.8+ installed.

### 2. Install Dependencies
```bash
pip install pandas yfinance matplotlib textblob beautifulsoup4 requests numpy
```

### 3. Configuration
Modify `config.json` to adjust scraping limits or market data parameters:
```json
{
    "ptt": {
        "pages_to_scrape": 5,
        "threads_limit": 50
    },
    "market": {
        "symbol": "^TWII",
        "period": "5d"
    }
}
```

---

## 🚀 How to Run

### Step 1: Scrape PTT Data
Run the scraper to collect the latest sentiment from the PTT Stock board.
```bash
python src/scraper/ptt_scraper.py
```
*Data will be saved to `data/raw/raw_ptt_data_[timestamp].json`.*

### Step 2: Run Analysis Pipeline
Process the scraped data, fetch market index, and generate the visualization.
```bash
python src/analysis/analysis_pipeline.py
```
*Outputs will be saved to the `output/` directory.*

---

## 🏮 The PTT Slang Dictionary

This system understands the nuances of Taiwanese market sentiment:

| Slang | Meaning | Sentiment |
| :--- | :--- | :--- |
| **歐印 (All-in)** | High conviction buy | 🟢 Bullish |
| **睏霸數錢 (Sleep & count money)** | Extreme confidence | 🟢 Bullish |
| **丸子/完蛋 (Meatball/Finished)** | Panic selling | 🔴 Bearish |
| **畢業 (Graduate)** | Stop loss / Exit market | 🔴 Bearish |
| **綠光罩頂 (Green light)** | Market crash (Green = Down in TW) | 🔴 Bearish |

---

## ⚠️ Important Note on Color Logic
In the Taiwan Stock Market:
- 🔴 **Red** indicates **UP** (Bullish)
- 🟢 **Green** indicates **DOWN** (Bearish)

The visualizations in this project strictly follow this convention to provide an authentic analysis experience.

---
*Created with 💙 by Antigravity*
