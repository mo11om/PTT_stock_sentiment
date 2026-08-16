# 📈 PTT Sentiment Alpha

> **Local-first quant tool for correlating Taiwanese retail sentiment with market movement.**

---

## 🚀 Overview

Extract retail sentiment from **PTT Stock Board** and align with **^TWII** using:
- **Regime Discovery Slang Miner** - Find slang that dominates bull/bear market regimes
- **Trading Day Alignment** - 13:30 cutoff, weekend shifts
- **Z-Score Analysis** - Statistical outlier detection for alpha signals

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Database | SQLite 3 (WAL Mode) |
| ORM | SQLAlchemy 2.0 |
| NLP | jieba (Chinese tokenization) |
| Market Data | yfinance (^TWII) |
| Dashboard | Streamlit + Plotly |

---

## 📂 Architecture

```
src/
├── database/           # SQLite with WAL mode
│   └── models.py       # Post, Sentiment, MarketData, SlangCandidate
├── scraper/            # Incremental PTT crawler
│   └── ptt_scraper.py  # --backfill mode for historical data
├── analysis/
│   ├── engine.py       # Sentiment scoring + Z-score
│   └── slang_miner.py  # Regime Discovery Engine
├── agent/
│   └── bot.py          # Autonomous pipeline runner
└── dashboard/
    └── app.py          # Dual-axis visualization
```

---

## 🎯 Slang Miner Algorithm

```python
# Regime = 30-day price change
Regime = (Close[today] - Close[30 days ago]) / Close[30 days ago]

BULL_TREND: > +5%
BEAR_TREND: < -5%

# Polarity = differential frequency
Polarity = (bull_freq - bear_freq) / (bull_freq + bear_freq)
```

---

## 🏮 Taiwan Market Conventions

| Convention | Value |
|------------|-------|
| 🔴 RED | **Bullish** / Price Up |
| 🟢 GREEN | **Bearish** / Price Down |
| Market Hours | 09:00 - 13:30 (UTC+8) |
| Trading Day Cutoff | Posts after 13:30 → next day |

---

## ⚡ Quick Start

```bash
# Install
pip install -r requirements.txt

# Backfill market data (10 years)
python backfill_market.py

# Run pipeline with backfill
python run_pipeline.py --pages 50 --backfill

# Start from specific page (e.g., page 2000 for older posts)
python run_pipeline.py --pages 100 --backfill --start-page 2000

# Run agent bot
python -m src.agent.bot

# Launch dashboard
streamlit run src/dashboard/app.py
```

---

## 📊 Database Schema

| Table | Purpose |
|-------|---------|
| `posts` | Raw PTT thread data |
| `sentiments` | Computed scores + Z-score |
| `market_data` | TWII OHLCV |
| `slang_candidates` | Discovered slang with polarity |

---

## 👤 Author
[mo11om](https://github.com/mo11om)

---

## 🛡️ License
MIT. Built for research and educational purposes.
