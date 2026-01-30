#!/usr/bin/env python3
"""
PTT Sentiment Alpha - Pipeline Orchestrator
Runs the complete data pipeline: Scrape -> Analyze -> Sync Market Data -> Maintenance
"""

import os
import sys
from datetime import datetime

# Ensure project root is in path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from src.database import init_db, vacuum_db
from src.scraper.ptt_scraper import PTTScraper
from src.analysis.engine import SentimentEngine, sync_market_data


def run_pipeline(max_pages: int = 5, run_vacuum: bool = True, backfill: bool = False):
    """
    Execute the full PTT Sentiment Alpha pipeline.
    
    Steps:
    1. Initialize database (create tables if needed)
    2. Run scraper (incremental - only new posts, or backfill mode)
    3. Run sentiment analysis (only unanalyzed posts)
    4. Sync market data (only missing dates)
    5. Maintenance (VACUUM to optimize storage)
    """
    print("=" * 70)
    print("  PTT Sentiment Alpha - Pipeline Orchestrator")
    print(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if backfill:
        print("  Mode: BACKFILL (scraping all pages)")
    print("=" * 70)
    
    # Step 0: Initialize database
    print("\n[Step 0] Initializing database...")
    init_db()
    
    # Step 1: Run Scraper
    print("\n[Step 1] Running PTT Scraper...")
    scraper = PTTScraper(max_pages=max_pages, backfill=backfill)
    new_posts = scraper.run()
    
    # Step 2: Run Sentiment Analysis
    print("\n[Step 2] Running Sentiment Analysis...")
    engine = SentimentEngine()
    analyzed_posts = engine.run()
    
    # Step 3: Sync Market Data
    print("\n[Step 3] Syncing Market Data...")
    market_records = sync_market_data()
    
    # Step 4: Maintenance - VACUUM
    if run_vacuum:
        print("\n[Step 4] Running maintenance (VACUUM)...")
        try:
            vacuum_db()
        except Exception as e:
            print(f"  ⚠️ Vacuum failed (non-critical): {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("  PIPELINE SUMMARY")
    print("=" * 70)
    print(f"  ✓ Scraped {new_posts} new posts")
    print(f"  ✓ Analyzed {analyzed_posts} posts")
    print(f"  ✓ Added {market_records} market data records")
    print(f"  ✓ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print("\n💡 To view the dashboard, run:")
    print("   streamlit run src/dashboard/app.py")
    print()
    
    return {
        "new_posts": new_posts,
        "analyzed_posts": analyzed_posts,
        "market_records": market_records
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="PTT Sentiment Alpha Pipeline")
    parser.add_argument("--pages", type=int, default=5, help="Max pages to scrape (default: 5)")
    parser.add_argument("--no-vacuum", action="store_true", help="Skip VACUUM step")
    parser.add_argument("--backfill", action="store_true", help="Backfill mode: scrape all pages, skip existing posts")
    args = parser.parse_args()
    
    run_pipeline(max_pages=args.pages, run_vacuum=not args.no_vacuum, backfill=args.backfill)

