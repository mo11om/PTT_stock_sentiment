# backfill_market.py
import yfinance as yf
from datetime import date, timedelta
from src.database import get_db, init_db, MarketData

init_db()

ticker = yf.Ticker("^TWII")
df = ticker.history(period="10y")  # or "2y", "5y", "max"

with get_db() as db:
    for idx, row in df.iterrows():
        market_date = idx.date()
        existing = db.query(MarketData).filter(MarketData.date == market_date).first()
        if existing:
            continue
        db.add(MarketData(
            date=market_date,
            open=float(row['Open']),
            high=float(row['High']),
            low=float(row['Low']),
            close=float(row['Close']),
            volume=int(row['Volume']) if 'Volume' in row else None
        ))
    db.commit()
    print(f"Added {len(df)} market records")