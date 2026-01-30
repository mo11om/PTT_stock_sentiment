"""
Adapters for PTT Sentiment Alpha Agent
Non-destructive wrappers around existing modules.
"""

import sys
import os

# Ensure project root in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class ScraperAdapter:
    """Wrapper for PTTScraper that runs scraping without modifying original code."""
    
    def __init__(self, max_pages: int = 5):
        self.max_pages = max_pages
    
    def run(self) -> int:
        """Run the scraper and return new post count."""
        from src.scraper.ptt_scraper import PTTScraper
        
        scraper = PTTScraper(max_pages=self.max_pages)
        return scraper.run()


class MinerAdapter:
    """Wrapper for SlangMiner that runs analysis and saves results."""
    
    def run(self):
        """Run slang mining and save to database."""
        from src.analysis.slang_miner import SlangMiner
        
        miner = SlangMiner()
        results = miner.run()
        miner.print_report(results)
        
        return results


class SentimentAdapter:
    """Wrapper for SentimentEngine."""
    
    def run(self) -> int:
        """Run sentiment analysis on unanalyzed posts."""
        from src.analysis.engine import SentimentEngine
        
        engine = SentimentEngine()
        return engine.run()
