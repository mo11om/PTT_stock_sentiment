#!/usr/bin/env python3
"""
PTT Bull/Bear Slang Miner
Discovers slang terms correlated with market movements using differential scoring.
"""

import sys
import os
from datetime import datetime, date, timedelta, time
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

import jieba
import pandas as pd
import yfinance as yf

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_db, Post, MarketData


# Taiwan market constants
MARKET_CLOSE_TIME = time(13, 30)
BULL_THRESHOLD = 0.5   # >= +0.5% is BULL
BEAR_THRESHOLD = -2  # <= -0.5% is BEAR


# PTT Slang Seed Dictionary - pre-load into jieba
PTT_SLANG_SEEDS = [
    # Bullish slang
    "歐印", "睏霸數錢", "飛向宇宙", "噴", "起飛", "噴到外太空", "發財", 
    "漲停", "紅通通", "財富自由", "噴出", "上看", "衝",
    # Bearish slang
    "丸子", "完蛋", "綠光", "畢業", "睡公園", "崩", "跳水",
    "死魚", "被套", "割韭菜", "跌停", "綠光罩頂", "慘", "GG", "掰掰",
    # Neutral/descriptive
    "外資", "投信", "自營商", "台積電", "鴻海", "聯發科"
]

# Initialize jieba with PTT slang
for word in PTT_SLANG_SEEDS:
    jieba.add_word(word)


class MarketOracle:
    """
    Fetches ^TWII and labels dates as BULL/BEAR based on percentage change.
    
    BULL: Daily return >= +0.5%
    BEAR: Daily return <= -0.5%
    NEUTRAL: Otherwise
    """
    
    def __init__(self, bull_threshold: float = BULL_THRESHOLD, bear_threshold: float = BEAR_THRESHOLD):
        self.bull_threshold = bull_threshold
        self.bear_threshold = bear_threshold
        self.market_labels: Dict[date, str] = {}
    
    def load_from_db(self) -> int:
        """Load market data from database and label each day."""
        with get_db() as db:
            records = db.query(MarketData).order_by(MarketData.date).all()
            
            for record in records:
                # Calculate daily return percentage
                daily_return = ((record.close - record.open) / record.open) * 100
                
                if daily_return >= self.bull_threshold:
                    label = "BULL"
                elif daily_return <= self.bear_threshold:
                    label = "BEAR"
                else:
                    label = "NEUTRAL"
                
                self.market_labels[record.date] = label
        
        return len(self.market_labels)
    
    def get_label(self, d: date) -> Optional[str]:
        """Get market label for a specific date."""
        return self.market_labels.get(d)
    
    def get_stats(self) -> Dict[str, int]:
        """Get count of each label."""
        stats = {"BULL": 0, "BEAR": 0, "NEUTRAL": 0}
        for label in self.market_labels.values():
            stats[label] += 1
        return stats


def calculate_trading_day(publish_time: datetime) -> date:
    """
    Calculate the effective trading day for a post.
    - Posts after 13:30 belong to NEXT trading day
    - Weekends shift to Monday
    """
    post_date = publish_time.date()
    post_time = publish_time.time()
    
    if post_time > MARKET_CLOSE_TIME:
        effective_date = post_date + timedelta(days=1)
    else:
        effective_date = post_date
    
    # Skip weekends
    weekday = effective_date.weekday()
    if weekday == 5:  # Saturday
        effective_date += timedelta(days=2)
    elif weekday == 6:  # Sunday
        effective_date += timedelta(days=1)
    
    return effective_date


class SlangMiner:
    """
    Mines slang terms from posts and calculates correlation with market direction.
    
    Differential Scoring: Polarity = (Bull_Freq - Bear_Freq) / (Bull_Freq + Bear_Freq)
    """
    
    def __init__(self, min_frequency: int = 3):
        self.oracle = MarketOracle()
        self.min_frequency = min_frequency
        
        # Word frequency counters
        self.bull_words: Dict[str, int] = defaultdict(int)
        self.bear_words: Dict[str, int] = defaultdict(int)
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize Chinese text using jieba."""
        # Segment text
        words = jieba.lcut(text)
        
        # Filter: keep words with length >= 2 (skip single chars and punctuation)
        words = [w.strip() for w in words if len(w.strip()) >= 2]
        
        return words
    
    def analyze(self) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
        """
        Analyze all posts and return top Bull/Bear slang terms.
        
        Returns:
            (bull_list, bear_list) - Each is [(word, polarity_score), ...]
        """
        print("=" * 60)
        print("PTT Slang Miner - Differential Scoring")
        print("=" * 60)
        
        # Load market labels
        n_days = self.oracle.load_from_db()
        stats = self.oracle.get_stats()
        print(f"\n📊 Market Data: {n_days} days")
        print(f"   BULL ({self.oracle.bull_threshold}%+): {stats['BULL']}")
        print(f"   BEAR ({self.oracle.bear_threshold}%-): {stats['BEAR']}")
        print(f"   NEUTRAL: {stats['NEUTRAL']}")
        
        # Process posts
        posts_processed = 0
        bull_posts = 0
        bear_posts = 0
        
        with get_db() as db:
            posts = db.query(Post).all()
            print(f"\n📝 Processing {len(posts)} posts...")
            
            for post in posts:
                # Calculate effective trading day
                effective_date = calculate_trading_day(post.publish_time)
                
                # Get market label for that day
                label = self.oracle.get_label(effective_date)
                if label is None or label == "NEUTRAL":
                    continue
                
                posts_processed += 1
                if label == "BULL":
                    bull_posts += 1
                else:
                    bear_posts += 1
                
                # Tokenize content
                text = f"{post.title} {post.content or ''}"
                tokens = self.tokenize(text)
                
                # Count word occurrences
                for word in set(tokens):  # Use set to count word once per post
                    if label == "BULL":
                        self.bull_words[word] += 1
                    elif label == "BEAR":
                        self.bear_words[word] += 1
        
        print(f"   Used {posts_processed} posts ({bull_posts} bull, {bear_posts} bear)")
        
        # Calculate differential scores
        all_words = set(self.bull_words.keys()) | set(self.bear_words.keys())
        word_scores: Dict[str, float] = {}
        
        for word in all_words:
            bull_freq = self.bull_words.get(word, 0)
            bear_freq = self.bear_words.get(word, 0)
            total = bull_freq + bear_freq
            
            # Lower minimum frequency for small datasets
            min_freq = max(1, self.min_frequency) if posts_processed < 50 else self.min_frequency
            if total < min_freq:
                continue
            
            # Differential scoring: +1.0 (pure bull) to -1.0 (pure bear)
            polarity = (bull_freq - bear_freq) / total
            word_scores[word] = polarity
        
        # Sort and get top Bull/Bear terms
        sorted_words = sorted(word_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Top bullish (highest positive polarity, including pure bull words)
        bull_list = [(w, s) for w, s in sorted_words if s > 0][:20]
        
        # Top bearish (most negative polarity)
        bear_list = [(w, s) for w, s in sorted_words if s < 0]
        bear_list = sorted(bear_list, key=lambda x: x[1])[:20]  # Most negative first
        
        # If no bear slang found but we have bear posts, show all bear-day words
        if not bear_list and bear_posts > 0:
            bear_only = [(w, -1.0) for w, freq in self.bear_words.items() if freq >= 1][:20]
            bear_list = bear_only
        
        # If no bull slang found but we have bull posts, show frequent bull-day words
        if not bull_list and bull_posts > 0:
            bull_only = [(w, 1.0) for w, freq in self.bull_words.items() if freq >= 2][:20]
            bull_list = bull_only
        
        print(f"\n✓ Found {len(bull_list)} bullish slang, {len(bear_list)} bearish slang")
        
        return bull_list, bear_list
    
    def print_report(self, bull_list: List[Tuple[str, float]], bear_list: List[Tuple[str, float]]):
        """Print formatted report of discovered slang."""
        print("\n" + "=" * 60)
        print("🔴 TOP BULLISH SLANG (correlated with market UP)")
        print("=" * 60)
        for i, (word, score) in enumerate(bull_list[:10], 1):
            bar = "█" * int(abs(score) * 20)
            print(f"  {i:2d}. {word:<12} +{score:.2f} {bar}")
        
        print("\n" + "=" * 60)
        print("🟢 TOP BEARISH SLANG (correlated with market DOWN)")
        print("=" * 60)
        for i, (word, score) in enumerate(bear_list[:10], 1):
            bar = "█" * int(abs(score) * 20)
            print(f"  {i:2d}. {word:<12} {score:.2f} {bar}")
    
    def save_to_db(self, bull_list: List[Tuple[str, float]], bear_list: List[Tuple[str, float]]) -> int:
        """Save discovered slang to MinedSlang table for use by sentiment engine."""
        from src.database import MinedSlang
        
        saved = 0
        with get_db() as db:
            # Save bullish slang
            for word, polarity in bull_list:
                existing = db.query(MinedSlang).filter(MinedSlang.word == word).first()
                if existing:
                    existing.polarity = polarity
                    existing.bull_freq = self.bull_words.get(word, 0)
                    existing.bear_freq = self.bear_words.get(word, 0)
                    existing.updated_at = datetime.now()
                else:
                    slang = MinedSlang(
                        word=word,
                        polarity=polarity,
                        bull_freq=self.bull_words.get(word, 0),
                        bear_freq=self.bear_words.get(word, 0)
                    )
                    db.add(slang)
                saved += 1
            
            # Save bearish slang
            for word, polarity in bear_list:
                existing = db.query(MinedSlang).filter(MinedSlang.word == word).first()
                if existing:
                    existing.polarity = polarity
                    existing.bull_freq = self.bull_words.get(word, 0)
                    existing.bear_freq = self.bear_words.get(word, 0)
                    existing.updated_at = datetime.now()
                else:
                    slang = MinedSlang(
                        word=word,
                        polarity=polarity,
                        bull_freq=self.bull_words.get(word, 0),
                        bear_freq=self.bear_words.get(word, 0)
                    )
                    db.add(slang)
                saved += 1
            
            db.commit()
        
        print(f"\n✓ Saved {saved} slang terms to database")
        return saved


def main():
    """Entry point for slang miner."""
    miner = SlangMiner(min_frequency=2)
    bull_list, bear_list = miner.analyze()
    miner.print_report(bull_list, bear_list)
    miner.save_to_db(bull_list, bear_list)
    return bull_list, bear_list


if __name__ == "__main__":
    main()
