#!/usr/bin/env python3
"""
PTT Sentiment Alpha - Agent Bot
Main entry point that orchestrates scraping, mining, and reporting.
"""

import sys
import os
from datetime import datetime

# Ensure project root in path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from src.database import init_db
from src.agent.adapters import ScraperAdapter, MinerAdapter, SentimentAdapter


def main():
    """Run the agent cycle: Scrape -> Mine Slang -> Analyze -> Report."""
    
    print("=" * 70)
    print("🤖 PTT Sentiment Alpha - Agent Bot")
    print(f"   Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Initialize database (create tables if needed)
    print("\n[1/4] Initializing database...")
    init_db()
    
    # Run scraper
    print("\n[2/4] Running scraper...")
    scraper = ScraperAdapter(max_pages=3)
    new_posts = scraper.run()
    
    # Run sentiment analysis
    print("\n[3/4] Running sentiment analysis...")
    sentiment = SentimentAdapter()
    analyzed = sentiment.run()
    
    # Run slang miner
    print("\n[4/4] Mining slang correlations...")
    miner = MinerAdapter()
    results = miner.run()
    
    # Final summary
    print("\n" + "=" * 70)
    print("📊 AGENT CYCLE COMPLETE")
    print("=" * 70)
    print(f"   ✓ Scraped: {new_posts} new posts")
    print(f"   ✓ Analyzed: {analyzed} posts")
    print(f"   ✓ Slang candidates: {len(results)}")
    print(f"   ✓ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


if __name__ == "__main__":
    main()
