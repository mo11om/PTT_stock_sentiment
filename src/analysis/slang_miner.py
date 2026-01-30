#!/usr/bin/env python3
"""
PTT Slang Miner - Regime Discovery Engine
Identifies slang words dominating specific market regimes (30-day trend).
"""

import sys
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple, Optional
from collections import Counter

import jieba
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_db, Post, MarketData, SlangCandidate


# Configuration Constants
LOOKBACK_DAYS = 30      # Compare today vs. 30 days ago
THRESHOLD_PCT = 0.05    # 5% change required to trigger a regime
MIN_FREQUENCY = 3       # Minimum total occurrences to be considered

# Chinese Stopwords (common words that don't carry sentiment)
STOPWORDS = {
    # Common particles
    "的", "了", "是", "我", "你", "他", "她", "它", "們", "這", "那", "有", "在",
    "和", "與", "或", "但", "不", "也", "都", "就", "會", "能", "可以", "要",
    "去", "來", "到", "說", "做", "給", "從", "被", "把", "讓", "對", "為",
    # Numbers and time
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "百", "千", "萬",
    "今天", "明天", "昨天", "現在", "之前", "之後", "時候",
    # Stock-specific common words (neutral)
    "股票", "公司", "台股", "大盤", "指數", "成交量", "收盤", "開盤",
    "請問", "謝謝", "問題", "請益", "閒聊", "標的", "新聞", "心得",
    # PTT specific
    "Re", "作者", "標題", "時間", "推文",
}

# PTT Slang Seeds - pre-load into jieba for better segmentation
PTT_SLANG_SEEDS = [
    "歐印", "睏霸數錢", "飛向宇宙", "噴", "起飛", "噴到外太空", "發財",
    "漲停", "紅通通", "財富自由", "噴出", "上看", "衝",
    "丸子", "完蛋", "綠光", "畢業", "睡公園", "崩", "跳水",
    "死魚", "被套", "割韭菜", "跌停", "綠光罩頂", "慘", "GG", "掰掰",
    "外資", "投信", "自營商", "法人", "散戶", "主力",
]

# Initialize jieba with PTT slang
for word in PTT_SLANG_SEEDS:
    jieba.add_word(word)


class SlangMiner:
    """
    Regime Discovery Slang Miner.
    
    Identifies slang words that dominate specific market regimes:
    - BULL_TREND: 30-day return > +5%
    - BEAR_TREND: 30-day return < -5%
    """
    
    def __init__(self, lookback_days: int = LOOKBACK_DAYS, threshold_pct: float = THRESHOLD_PCT):
        self.lookback_days = lookback_days
        self.threshold_pct = threshold_pct
        self.regime_labels: Dict[date, str] = {}
    
    def _label_days(self) -> Dict[date, str]:
        """
        Label each day in MarketData as BULL_TREND, BEAR_TREND, or NEUTRAL.
        
        Regime = (Close[today] - Close[today - lookback_days]) / Close[today - lookback_days]
        """
        print(f"\n📊 Labeling market regimes (lookback={self.lookback_days} days, threshold={self.threshold_pct*100:.0f}%)")
        
        with get_db() as db:
            # Get all market data sorted by date
            records = db.query(MarketData).order_by(MarketData.date).all()
            
            if len(records) < self.lookback_days:
                print(f"   ⚠️ Not enough data ({len(records)} days < {self.lookback_days} lookback)")
                return {}
            
            # Build date->close price lookup
            close_prices: Dict[date, float] = {r.date: r.close for r in records}
            dates = sorted(close_prices.keys())
            
            bull_count = 0
            bear_count = 0
            
            for d in dates:
                lookback_date = d - timedelta(days=self.lookback_days)
                
                # Find closest trading day to lookback_date
                lookback_close = None
                for offset in range(7):  # Check up to 7 days back for trading day
                    check_date = lookback_date - timedelta(days=offset)
                    if check_date in close_prices:
                        lookback_close = close_prices[check_date]
                        break
                
                if lookback_close is None:
                    continue
                
                # Calculate regime
                regime = (close_prices[d] - lookback_close) / lookback_close
                
                if regime > self.threshold_pct:
                    self.regime_labels[d] = "BULL_TREND"
                    bull_count += 1
                elif regime < -self.threshold_pct:
                    self.regime_labels[d] = "BEAR_TREND"
                    bear_count += 1
                # else: NEUTRAL - not stored
            
            print(f"   ✓ BULL_TREND: {bull_count} days | BEAR_TREND: {bear_count} days")
        
        return self.regime_labels
    
    def _tokenize_posts(self, regime_dict: Dict[date, str]) -> Tuple[Counter, Counter]:
        """
        Tokenize posts and build frequency counters for bull/bear regimes.
        
        Returns:
            (bull_counter, bear_counter) - Token frequencies for each regime
        """
        bull_counter: Counter = Counter()
        bear_counter: Counter = Counter()
        
        with get_db() as db:
            posts = db.query(Post).all()
            bull_posts = 0
            bear_posts = 0
            
            for post in posts:
                # Get effective date (use publish_time date, or calculate trading day)
                post_date = post.publish_time.date()
                
                # Check if this date is in a labeled regime
                regime = regime_dict.get(post_date)
                if regime is None:
                    continue
                
                # Tokenize content
                text = f"{post.title} {post.content or ''}"
                tokens = jieba.lcut(text)
                
                # Filter tokens
                filtered_tokens = []
                for token in tokens:
                    token = token.strip()
                    # Skip: single chars, stopwords, numbers, punctuation
                    if len(token) < 2:
                        continue
                    if token in STOPWORDS:
                        continue
                    if token.isdigit():
                        continue
                    filtered_tokens.append(token)
                
                # Count tokens
                if regime == "BULL_TREND":
                    bull_counter.update(filtered_tokens)
                    bull_posts += 1
                elif regime == "BEAR_TREND":
                    bear_counter.update(filtered_tokens)
                    bear_posts += 1
            
            print(f"\n📝 Tokenized {bull_posts} bull-regime posts, {bear_posts} bear-regime posts")
        
        return bull_counter, bear_counter
    
    def _calculate_polarity(self, bull_counter: Counter, bear_counter: Counter) -> List[Tuple[str, float, int, int]]:
        """
        Calculate polarity score for each token.
        
        Polarity = (bull_freq - bear_freq) / (bull_freq + bear_freq)
        
        Returns:
            List of (token, score, bull_freq, bear_freq) sorted by absolute score
        """
        all_tokens = set(bull_counter.keys()) | set(bear_counter.keys())
        results = []
        
        for token in all_tokens:
            bull_freq = bull_counter.get(token, 0)
            bear_freq = bear_counter.get(token, 0)
            total = bull_freq + bear_freq
            
            # Filter low frequency tokens
            if total < MIN_FREQUENCY:
                continue
            
            # Calculate polarity
            polarity = (bull_freq - bear_freq) / total
            results.append((token, polarity, bull_freq, bear_freq))
        
        # Sort by absolute polarity score
        results.sort(key=lambda x: abs(x[1]), reverse=True)
        
        return results
    
    def _save_to_db(self, results: List[Tuple[str, float, int, int]]) -> int:
        """Save top slang candidates to database."""
        saved = 0
        
        with get_db() as db:
            # Clear old candidates
            db.query(SlangCandidate).delete()
            
            # Insert new candidates (top 100)
            for token, score, bull_freq, bear_freq in results[:100]:
                candidate = SlangCandidate(
                    token=token,
                    score=score,
                    bull_freq=bull_freq,
                    bear_freq=bear_freq,
                    last_updated=datetime.now()
                )
                db.add(candidate)
                saved += 1
            
            db.commit()
        
        return saved
    
    def run(self) -> List[Tuple[str, float, int, int]]:
        """
        Run the complete slang mining pipeline.
        
        Returns:
            List of (token, score, bull_freq, bear_freq)
        """
        print("=" * 60)
        print("PTT Slang Miner - Regime Discovery Engine")
        print("=" * 60)
        
        # Step 1: Label days by regime
        regime_dict = self._label_days()
        if not regime_dict:
            print("❌ No regime labels available. Need more market data.")
            return []
        
        # Step 2: Tokenize posts by regime
        bull_counter, bear_counter = self._tokenize_posts(regime_dict)
        
        # Step 3: Calculate polarity scores
        results = self._calculate_polarity(bull_counter, bear_counter)
        
        # Step 4: Save to database
        saved = self._save_to_db(results)
        
        print(f"\n✓ Saved {saved} slang candidates to database")
        
        return results
    
    def print_report(self, results: List[Tuple[str, float, int, int]]):
        """Print formatted report of discovered slang."""
        # Separate bull and bear
        bull_slang = [(t, s, bf, rf) for t, s, bf, rf in results if s > 0][:15]
        bear_slang = [(t, s, bf, rf) for t, s, bf, rf in results if s < 0][:15]
        
        print("\n" + "=" * 60)
        print("🔴 TOP BULLISH SLANG (dominates BULL_TREND regime)")
        print("=" * 60)
        for i, (token, score, bf, rf) in enumerate(bull_slang, 1):
            bar = "█" * int(abs(score) * 20)
            print(f"  {i:2d}. {token:<12} +{score:.2f} (bull:{bf}, bear:{rf}) {bar}")
        
        print("\n" + "=" * 60)
        print("🟢 TOP BEARISH SLANG (dominates BEAR_TREND regime)")
        print("=" * 60)
        for i, (token, score, bf, rf) in enumerate(bear_slang, 1):
            bar = "█" * int(abs(score) * 20)
            print(f"  {i:2d}. {token:<12} {score:.2f} (bull:{bf}, bear:{rf}) {bar}")


def main():
    """Entry point for slang miner."""
    miner = SlangMiner()
    results = miner.run()
    miner.print_report(results)
    return results


if __name__ == "__main__":
    main()
