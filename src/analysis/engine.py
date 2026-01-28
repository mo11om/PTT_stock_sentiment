#!/usr/bin/env python3
"""
PTT Sentiment Analysis Engine
Processes posts and calculates sentiment scores using Taiwan stock slang.
"""

import re
import sys
import os
from datetime import datetime, date, timedelta
from typing import Optional, List, Tuple

import yfinance as yf

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_db, Post, Sentiment, MarketData


class SlangNormalizer:
    """Normalizes Taiwanese stock slang into sentiment tokens."""
    
    # Bearish slang patterns -> BEARISH_PANIC
    BEARISH_SLANG = [
        "丸子", "完蛋", "綠光", "畢業", "睡公園", "崩", "跳水",
        "死魚", "被套", "割韭菜", "跌停", "綠的", "綠色", "一片綠",
        "綠光罩頂", "慘", "GG", "掰掰"
    ]
    
    # Bullish slang patterns -> BULLISH_CONFIDENCE  
    BULLISH_SLANG = [
        "睏霸數錢", "歐印", "飛向宇宙", "噴", "爆", "起飛",
        "噴到外太空", "發財", "漲停", "紅的", "紅色", "紅通通",
        "上看", "衝", "噴出", "財富自由"
    ]
    
    @classmethod
    def normalize(cls, text: str) -> Tuple[str, List[str]]:
        """
        Normalize slang in text and return (normalized_text, found_tokens).
        """
        normalized = text
        tokens = []
        
        # Replace bearish slang
        for slang in cls.BEARISH_SLANG:
            if slang in text:
                normalized = normalized.replace(slang, " BEARISH_PANIC ")
                tokens.append(f"bearish:{slang}")
        
        # Replace bullish slang
        for slang in cls.BULLISH_SLANG:
            if slang in text:
                normalized = normalized.replace(slang, " BULLISH_CONFIDENCE ")
                tokens.append(f"bullish:{slang}")
        
        return normalized, tokens


class SentimentEngine:
    """Engine for calculating sentiment scores from PTT posts."""
    
    def __init__(self):
        self.analyzed_count = 0
    
    def _calculate_base_sentiment(self, text: str) -> float:
        """
        Calculate base sentiment from normalized text.
        Returns value between -1.0 and 1.0.
        """
        # Count sentiment markers
        bullish_count = text.count("BULLISH_CONFIDENCE")
        bearish_count = text.count("BEARISH_PANIC")
        
        total = bullish_count + bearish_count
        if total == 0:
            return 0.0
        
        # Calculate ratio-based sentiment
        return (bullish_count - bearish_count) / total
    
    def _calculate_weighted_score(self, base_sentiment: float, push_count: int, boo_count: int) -> float:
        """
        Calculate weighted sentiment score.
        Formula: Base_Sentiment * (Push_Count - Boo_Count * 1.5)
        Normalized to -1.0 to 1.0 range.
        """
        interaction_weight = push_count - (boo_count * 1.5)
        
        # Normalize interaction weight (log scale to reduce extreme values)
        if interaction_weight > 0:
            weight_factor = min(1 + (interaction_weight / 50), 3.0)
        elif interaction_weight < 0:
            weight_factor = max(1 + (interaction_weight / 50), 0.3)
        else:
            weight_factor = 1.0
        
        raw_score = base_sentiment * weight_factor
        
        # Clamp to -1.0 to 1.0
        return max(-1.0, min(1.0, raw_score))
    
    def analyze_post(self, post: Post) -> Optional[float]:
        """
        Analyze a single post and return sentiment score.
        """
        # Combine title and content for analysis
        full_text = f"{post.title} {post.content or ''}"
        
        # Normalize slang
        normalized_text, tokens = SlangNormalizer.normalize(full_text)
        
        # Calculate sentiment
        base_sentiment = self._calculate_base_sentiment(normalized_text)
        weighted_score = self._calculate_weighted_score(
            base_sentiment, 
            post.push_count, 
            post.boo_count
        )
        
        return weighted_score, tokens
    
    def run(self) -> int:
        """
        Process all unanalyzed posts and save sentiment scores.
        Returns number of posts analyzed.
        """
        print("=" * 60)
        print("PTT Sentiment Analysis Engine")
        print("=" * 60)
        
        with get_db() as db:
            # Get posts without sentiment scores
            analyzed_ids = db.query(Sentiment.post_id).all()
            analyzed_ids = {row[0] for row in analyzed_ids}
            
            unanalyzed_posts = db.query(Post).filter(
                ~Post.id.in_(analyzed_ids) if analyzed_ids else True
            ).all()
            
            print(f"\n📊 Found {len(unanalyzed_posts)} posts to analyze")
            
            for post in unanalyzed_posts:
                try:
                    score, tokens = self.analyze_post(post)
                    
                    sentiment = Sentiment(
                        post_id=post.id,
                        score=score,
                        raw_score=score,
                        tokens_found=",".join(tokens) if tokens else None,
                        analyzed_at=datetime.now()
                    )
                    db.add(sentiment)
                    db.commit()  # Commit each sentiment individually
                    self.analyzed_count += 1
                    
                    print(f"   → {post.title[:40]}... Score: {score:.3f}")
                except Exception as e:
                    db.rollback()
                    print(f"   ⚠️ Error analyzing {post.id}: {e}")
        
        print(f"\n✓ Analyzed {self.analyzed_count} posts")
        return self.analyzed_count


def sync_market_data() -> int:
    """
    Sync TWII market data to database.
    Fetches missing data and stores in MarketData table.
    Returns number of new records added.
    """
    print("\n" + "=" * 60)
    print("Market Data Sync (^TWII)")
    print("=" * 60)
    
    symbol = "^TWII"
    new_records = 0
    
    with get_db() as db:
        # Get the latest date in database
        latest = db.query(MarketData).order_by(MarketData.date.desc()).first()
        
        if latest:
            start_date = latest.date + timedelta(days=1)
            print(f"   Latest data: {latest.date}")
        else:
            start_date = date.today() - timedelta(days=30)
            print(f"   No existing data, fetching last 30 days")
        
        # Fetch from yfinance
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date.isoformat(), end=date.today().isoformat())
            
            if df.empty:
                print("   No new market data available")
                return 0
            
            print(f"   Fetched {len(df)} data points from yfinance")
            
            for idx, row in df.iterrows():
                market_date = idx.date()
                
                # Check if exists
                existing = db.query(MarketData).filter(MarketData.date == market_date).first()
                if existing:
                    continue
                
                market_data = MarketData(
                    date=market_date,
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume']) if 'Volume' in row else None
                )
                db.add(market_data)
                new_records += 1
            
            print(f"\n✓ Added {new_records} new market data records")
            
        except Exception as e:
            print(f"❌ Error fetching market data: {e}")
    
    return new_records


def main():
    """Entry point for sentiment engine."""
    os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    engine = SentimentEngine()
    analyzed = engine.run()
    
    market_records = sync_market_data()
    
    print("\n" + "=" * 60)
    print(f"Summary: Analyzed {analyzed} posts, Added {market_records} market records")
    print("=" * 60)
    
    return analyzed, market_records


if __name__ == "__main__":
    main()
