#!/usr/bin/env python3
"""
PTT Sentiment Analysis Engine
Processes posts with trading day logic and Taiwan stock slang normalization.
"""

import re
import sys
import os
from datetime import datetime, date, timedelta, time
from typing import Optional, List, Tuple

import yfinance as yf

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_db, Post, Sentiment, MarketData


# Taiwan market constants
MARKET_CLOSE_TIME = time(13, 30)  # 13:30 local time


def calculate_trading_day(publish_time: datetime) -> date:
    """
    Calculate the effective trading day for a post.
    
    Rules:
    - If post is after 13:30, it belongs to NEXT trading day
    - If effective_date is Saturday/Sunday, shift to next Monday
    """
    post_date = publish_time.date()
    post_time = publish_time.time()
    
    # If after market close, post affects NEXT day
    if post_time > MARKET_CLOSE_TIME:
        effective_date = post_date + timedelta(days=1)
    else:
        effective_date = post_date
    
    # Skip weekends -> shift to Monday
    weekday = effective_date.weekday()
    if weekday == 5:  # Saturday
        effective_date += timedelta(days=2)
    elif weekday == 6:  # Sunday
        effective_date += timedelta(days=1)
    
    return effective_date


class SlangNormalizer:
    """Normalizes Taiwanese stock slang with negation logic."""
    
    # Bearish slang patterns -> -1.0
    BEARISH_SLANG = {
        "丸子": -1.0,
        "完蛋": -1.0,
        "綠光": -0.8,
        "畢業": -0.9,
        "睡公園": -1.0,
        "崩": -0.8,
        "跳水": -0.8,
        "死魚": -0.5,
        "被套": -0.6,
        "割韭菜": -0.7,
        "跌停": -1.0,
        "綠的": -0.5,
        "綠色": -0.5,
        "一片綠": -0.9,
        "綠光罩頂": -1.0,
        "慘": -0.6,
        "GG": -0.7,
        "掰掰": -0.5,
    }
    
    # Bullish slang patterns -> +1.0
    BULLISH_SLANG = {
        "睏霸數錢": 1.0,
        "歐印": 0.9,
        "飛向宇宙": 1.0,
        "噴": 0.7,
        "爆": 0.7,
        "起飛": 0.8,
        "噴到外太空": 1.0,
        "發財": 0.6,
        "漲停": 1.0,
        "紅的": 0.5,
        "紅色": 0.5,
        "紅通通": 0.7,
        "上看": 0.6,
        "衝": 0.5,
        "噴出": 0.7,
        "財富自由": 0.8,
    }
    
    # Negation patterns that flip sentiment
    NEGATION_PREFIXES = ["不要", "別", "不是", "沒有", "不會"]
    NEGATION_SUFFIXES = ["好自為之", "保重", "小心"]
    
    @classmethod
    def normalize(cls, text: str) -> Tuple[float, List[str]]:
        """
        Normalize slang and calculate sentiment score.
        Returns (score, token_list).
        """
        total_score = 0.0
        tokens = []
        match_count = 0
        
        # Check for each slang term
        for slang, score in cls.BEARISH_SLANG.items():
            count = text.count(slang)
            if count > 0:
                # Check for negation
                final_score = score
                for neg in cls.NEGATION_PREFIXES:
                    if neg + slang in text:
                        final_score = -score  # Flip
                        tokens.append(f"NEG:{slang}")
                        break
                else:
                    tokens.append(f"bearish:{slang}")
                
                total_score += final_score * count
                match_count += count
        
        for slang, score in cls.BULLISH_SLANG.items():
            count = text.count(slang)
            if count > 0:
                final_score = score
                
                # Check prefix negation
                for neg in cls.NEGATION_PREFIXES:
                    if neg + slang in text:
                        final_score = -score
                        tokens.append(f"NEG:{slang}")
                        break
                else:
                    # Check suffix negation (e.g., "歐印好自為之" = sarcastic warning)
                    for neg_suffix in cls.NEGATION_SUFFIXES:
                        if slang in text:
                            # Find position and check what follows
                            idx = text.find(slang)
                            following = text[idx + len(slang):idx + len(slang) + 10]
                            if any(s in following for s in cls.NEGATION_SUFFIXES):
                                final_score = -score * 0.5  # Partial flip
                                tokens.append(f"WARN:{slang}")
                                break
                    else:
                        tokens.append(f"bullish:{slang}")
                
                total_score += final_score * count
                match_count += count
        
        # Normalize to -1 to 1 range
        if match_count > 0:
            normalized_score = max(-1.0, min(1.0, total_score / match_count))
        else:
            normalized_score = 0.0
        
        return normalized_score, tokens


class SentimentEngine:
    """Engine for calculating sentiment scores with trading day logic."""
    
    def __init__(self):
        self.analyzed_count = 0
    
    def calculate_weighted_score(self, base_score: float, push_count: int, boo_count: int) -> float:
        """
        Calculate weighted sentiment score.
        Formula: Base_Sentiment * (Push_Count - Boo_Count * 1.5)
        """
        # Boos weighted 1.5x as negative signals
        interaction_weight = push_count - (boo_count * 1.5)
        
        # Normalize interaction weight
        if interaction_weight > 0:
            weight_factor = min(1 + (interaction_weight / 50), 3.0)
        elif interaction_weight < 0:
            weight_factor = max(1 + (interaction_weight / 50), 0.3)
        else:
            weight_factor = 1.0
        
        raw_score = base_score * weight_factor
        return max(-1.0, min(1.0, raw_score))
    
    def analyze_post(self, post: Post) -> Tuple[float, date, List[str]]:
        """
        Analyze a single post.
        Returns (raw_score, effective_date, tokens).
        """
        # Combine title and content
        full_text = f"{post.title} {post.content or ''}"
        
        # Normalize slang
        base_score, tokens = SlangNormalizer.normalize(full_text)
        
        # Calculate weighted score
        raw_score = self.calculate_weighted_score(
            base_score, 
            post.push_count, 
            post.boo_count
        )
        
        # Calculate effective trading day
        effective_date = calculate_trading_day(post.publish_time)
        
        return raw_score, effective_date, tokens
    
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
                    raw_score, effective_date, tokens = self.analyze_post(post)
                    
                    sentiment = Sentiment(
                        post_id=post.id,
                        raw_score=raw_score,
                        effective_date=effective_date,
                        tokens_found=",".join(tokens) if tokens else None,
                        analyzed_at=datetime.now()
                    )
                    db.add(sentiment)
                    db.commit()
                    self.analyzed_count += 1
                    
                    print(f"   → {post.title[:35]}... Score: {raw_score:.3f} | Date: {effective_date}")
                except Exception as e:
                    db.rollback()
                    print(f"   ⚠️ Error analyzing {post.id}: {e}")
        
        print(f"\n✓ Analyzed {self.analyzed_count} posts")
        return self.analyzed_count


def sync_market_data() -> int:
    """
    Sync TWII market data to database.
    Returns number of new records added.
    """
    print("\n" + "=" * 60)
    print("Market Data Sync (^TWII)")
    print("=" * 60)
    
    symbol = "^TWII"
    new_records = 0
    
    with get_db() as db:
        latest = db.query(MarketData).order_by(MarketData.date.desc()).first()
        
        if latest:
            start_date = latest.date + timedelta(days=1)
            print(f"   Latest data: {latest.date}")
        else:
            start_date = date.today() - timedelta(days=30)
            print(f"   No existing data, fetching last 30 days")
        
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date.isoformat(), end=date.today().isoformat())
            
            if df.empty:
                print("   No new market data available")
                return 0
            
            print(f"   Fetched {len(df)} data points from yfinance")
            
            for idx, row in df.iterrows():
                market_date = idx.date()
                
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
                db.commit()
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
