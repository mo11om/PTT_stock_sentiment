#!/usr/bin/env python3
"""
PTT Stock Sentiment Analysis Pipeline
Analyzes PTT Stock board data and correlates with TWII market movements.
"""

import json
import math
import os
import re
from datetime import datetime, timedelta
from glob import glob
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import yfinance as yf
from textblob import TextBlob


class PTTDecoder:
    """Decodes PTT stock market slang into sentiment tokens."""
    
    # Bullish terms mapping
    BULLISH_TERMS = {
        "睏霸數錢": ("EXTREME_BULL", 1.0),
        "飛向宇宙": ("BULL_MOMENTUM", 0.7),
        "歐印": ("HIGH_CONVICTION_BUY", 0.8),
        "噴": ("BULL_MOMENTUM", 0.7),
        "爆": ("BULL_MOMENTUM", 0.7),
        "起飛": ("BULL_MOMENTUM", 0.7),
        "噴到外太空": ("EXTREME_BULL", 1.0),
        "發財": ("BULL_MOMENTUM", 0.6),
        "漲停": ("EXTREME_BULL", 0.9),
        "紅的": ("BULLISH", 0.5),
        "紅色": ("BULLISH", 0.5),
        "紅通通": ("BULL_MOMENTUM", 0.6),
    }
    
    # Bearish terms mapping
    BEARISH_TERMS = {
        "丸子": ("PANIC_SELL", -0.8),
        "完蛋": ("PANIC_SELL", -0.8),
        "睡公園": ("BANKRUPTCY_RISK", -0.9),
        "畢業": ("STOP_LOSS_EXIT", -0.6),
        "綠光罩頂": ("MARKET_CRASH", -1.0),
        "崩": ("PANIC_SELL", -0.8),
        "跳水": ("PANIC_SELL", -0.8),
        "死魚": ("BEARISH_STAGNANT", -0.4),
        "被套": ("BEARISH_WARNING", -0.5),
        "割韭菜": ("BEARISH_WARNING", -0.5),
        "跌停": ("MARKET_CRASH", -0.9),
        "綠的": ("BEARISH", -0.5),
        "綠色": ("BEARISH", -0.5),
        "一片綠": ("MARKET_CRASH", -0.7),
    }
    
    # Inversion patterns
    INVERSION_PATTERNS = [
        (r"好自為之.*?多軍", "BEARISH_WARNING", -0.5),
        (r"多軍.*?好自為之", "BEARISH_WARNING", -0.5),
    ]
    
    @classmethod
    def decode(cls, text: str) -> dict:
        """
        Decode PTT slang and return sentiment analysis.
        
        Returns:
            dict with 'tokens' (list of found tokens) and 'score' (aggregate score)
        """
        tokens = []
        total_score = 0.0
        matches = 0
        
        # Check bullish terms
        for term, (token, weight) in cls.BULLISH_TERMS.items():
            count = text.count(term)
            if count > 0:
                tokens.append(token)
                total_score += weight * count
                matches += count
        
        # Check bearish terms
        for term, (token, weight) in cls.BEARISH_TERMS.items():
            count = text.count(term)
            if count > 0:
                tokens.append(token)
                total_score += weight * count
                matches += count
        
        # Check inversion patterns
        for pattern, token, weight in cls.INVERSION_PATTERNS:
            if re.search(pattern, text):
                tokens.append(token)
                total_score += weight
                matches += 1
        
        # Calculate average score
        avg_score = total_score / max(matches, 1)
        
        return {
            "tokens": list(set(tokens)),
            "score": avg_score,
            "raw_score": total_score,
            "matches": matches
        }


class SentimentAnalyzer:
    """Analyzes sentiment from PTT data."""
    
    def __init__(self, config_path: str = "config.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        
        self.raw_data_path = self.config["paths"]["raw_data"]
        self.output_path = self.config["paths"]["output"]
        os.makedirs(self.output_path, exist_ok=True)
    
    def load_latest_data(self) -> Optional[dict]:
        """Load the most recent scraped data file."""
        pattern = os.path.join(self.raw_data_path, "raw_ptt_data_*.json")
        files = sorted(glob(pattern), reverse=True)
        
        if not files:
            print(f"No data files found in {self.raw_data_path}")
            return None
        
        latest_file = files[0]
        print(f"Loading data from: {latest_file}")
        
        with open(latest_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def analyze_thread(self, thread: dict) -> dict:
        """Analyze sentiment for a single thread."""
        # Combine title, content, and comments for analysis
        text_parts = [thread.get("title", ""), thread.get("content", "")]
        
        comments = thread.get("comments", [])
        for comment in comments:
            text_parts.append(comment.get("content", ""))
        
        full_text = " ".join(text_parts)
        
        # Decode PTT slang
        ptt_result = PTTDecoder.decode(full_text)
        
        # Use TextBlob for general sentiment if no PTT terms found
        if ptt_result["matches"] == 0:
            try:
                # TextBlob works better with English, but can provide baseline
                blob = TextBlob(full_text)
                base_sentiment = blob.sentiment.polarity
            except Exception:
                base_sentiment = 0.0
            
            ptt_result["score"] = base_sentiment * 0.5  # Scale down TextBlob score
        
        # Calculate weighted score using push count
        push_count = max(abs(thread.get("push_count", 0)), 1)
        weighted_score = ptt_result["score"] * math.log(push_count + 1)
        
        return {
            "title": thread.get("title", ""),
            "push_count": thread.get("push_count", 0),
            "sentiment_score": ptt_result["score"],
            "weighted_score": weighted_score,
            "tokens": ptt_result["tokens"],
            "comment_count": len(comments),
            "date": thread.get("date", "")
        }
    
    def analyze_all(self, data: dict) -> pd.DataFrame:
        """Analyze all threads and return DataFrame."""
        results = []
        
        for thread in data.get("threads", []):
            result = self.analyze_thread(thread)
            results.append(result)
        
        df = pd.DataFrame(results)
        return df


class MarketCorrelator:
    """Correlates PTT sentiment with TWII market data."""
    
    def __init__(self, config_path: str = "config.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        
        self.output_path = self.config["paths"]["output"]
    
    def fetch_market_data(self) -> pd.DataFrame:
        """Fetch TWII market data from yfinance."""
        symbol = self.config["market"]["symbol"]
        period = self.config["market"]["period"]
        interval = self.config["market"]["interval"]
        
        print(f"Fetching market data: {symbol} ({period}, {interval})")
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        
        print(f"Retrieved {len(df)} data points")
        return df
    
    def create_visualization(self, sentiment_df: pd.DataFrame, market_df: pd.DataFrame) -> str:
        """Create visualization with market data and sentiment overlay."""
        # Set up the figure with Taiwan market colors (Red=Up, Green=Down)
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
        fig.patch.set_facecolor('#1a1a2e')
        
        for ax in [ax1, ax2, ax3]:
            ax.set_facecolor('#16213e')
            ax.tick_params(colors='white')
            ax.spines['bottom'].set_color('#555555')
            ax.spines['top'].set_color('#555555')
            ax.spines['left'].set_color('#555555')
            ax.spines['right'].set_color('#555555')
        
        # Plot 1: TWII Price with Taiwan color logic
        if not market_df.empty:
            colors = []
            for i in range(len(market_df)):
                if i == 0:
                    colors.append('#888888')  # Gray for first bar
                elif market_df['Close'].iloc[i] >= market_df['Close'].iloc[i-1]:
                    colors.append('#ff4444')  # RED for UP (Taiwan style)
                else:
                    colors.append('#00cc00')  # GREEN for DOWN (Taiwan style)
            
            ax1.bar(range(len(market_df)), market_df['Close'], color=colors, alpha=0.8)
            ax1.set_ylabel('TWII Price', color='white', fontsize=10)
            ax1.set_title('Taiwan Weighted Index (^TWII)', color='white', fontsize=12, fontweight='bold')
            
            # Add price line
            ax1.plot(range(len(market_df)), market_df['Close'], color='#ffd700', linewidth=1.5, alpha=0.8)
        
        # Plot 2: Sentiment Distribution
        if not sentiment_df.empty:
            sentiment_colors = ['#ff4444' if s > 0 else '#00cc00' for s in sentiment_df['sentiment_score']]
            ax2.bar(range(len(sentiment_df)), sentiment_df['weighted_score'], color=sentiment_colors, alpha=0.7)
            ax2.axhline(y=0, color='white', linestyle='--', alpha=0.5)
            ax2.set_ylabel('Weighted Sentiment', color='white', fontsize=10)
            ax2.set_title('PTT Stock Board Sentiment (Weighted by Push Count)', color='white', fontsize=12, fontweight='bold')
        
        # Plot 3: Sentiment Heatmap
        if not sentiment_df.empty:
            # Create heatmap data
            scores = sentiment_df['sentiment_score'].values
            scores_normalized = (scores - scores.min()) / (scores.max() - scores.min() + 1e-10)
            
            # Create gradient colormap: Green (bearish) -> Yellow -> Red (bullish)
            # Note: Inverted for Taiwan market!
            heatmap_data = scores_normalized.reshape(1, -1)
            
            im = ax3.imshow(heatmap_data, aspect='auto', cmap='RdYlGn', 
                           vmin=0, vmax=1, extent=[0, len(scores), 0, 1])
            ax3.set_ylabel('Sentiment\nHeatmap', color='white', fontsize=10)
            ax3.set_yticks([])
            ax3.set_xlabel('Thread Index', color='white', fontsize=10)
            ax3.set_title('Sentiment Heatmap (Red=Bullish, Green=Bearish - Taiwan Style)', 
                         color='white', fontsize=12, fontweight='bold')
            
            # Add colorbar
            cbar = fig.colorbar(im, ax=ax3, orientation='horizontal', pad=0.2, shrink=0.5)
            cbar.ax.tick_params(colors='white')
            cbar.set_label('Bearish ← → Bullish', color='white')
        
        # Adjust layout
        plt.tight_layout()
        
        # Add main title
        fig.suptitle('PTT Stock Sentiment vs TWII Market Analysis\n', 
                    color='white', fontsize=14, fontweight='bold', y=1.02)
        
        # Add legend/note
        fig.text(0.5, -0.02, 
                '⚠️ Taiwan Market: Red = Up (Bullish), Green = Down (Bearish)',
                ha='center', color='#ffd700', fontsize=10, style='italic')
        
        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sentiment_analysis_{timestamp}.png"
        filepath = os.path.join(self.output_path, filename)
        
        plt.savefig(filepath, dpi=150, bbox_inches='tight', 
                   facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()
        
        print(f"Visualization saved to: {filepath}")
        return filepath
    
    def generate_report(self, sentiment_df: pd.DataFrame) -> dict:
        """Generate analysis report."""
        if sentiment_df.empty:
            return {"error": "No data to analyze"}
        
        avg_sentiment = sentiment_df['sentiment_score'].mean()
        avg_weighted = sentiment_df['weighted_score'].mean()
        
        bullish_count = len(sentiment_df[sentiment_df['sentiment_score'] > 0])
        bearish_count = len(sentiment_df[sentiment_df['sentiment_score'] < 0])
        neutral_count = len(sentiment_df[sentiment_df['sentiment_score'] == 0])
        
        # Collect all tokens
        all_tokens = []
        for tokens in sentiment_df['tokens']:
            all_tokens.extend(tokens)
        
        token_counts = {}
        for token in all_tokens:
            token_counts[token] = token_counts.get(token, 0) + 1
        
        report = {
            "total_threads": len(sentiment_df),
            "average_sentiment": round(avg_sentiment, 4),
            "average_weighted_sentiment": round(avg_weighted, 4),
            "bullish_threads": bullish_count,
            "bearish_threads": bearish_count,
            "neutral_threads": neutral_count,
            "top_tokens": dict(sorted(token_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            "market_outlook": "BULLISH" if avg_sentiment > 0.1 else "BEARISH" if avg_sentiment < -0.1 else "NEUTRAL"
        }
        
        return report


def main():
    """Main analysis pipeline."""
    # Change to project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    os.chdir(project_root)
    
    print("=" * 60)
    print("PTT Stock Sentiment Analysis Pipeline")
    print("=" * 60)
    
    # Initialize components
    analyzer = SentimentAnalyzer()
    correlator = MarketCorrelator()
    
    # Load PTT data
    data = analyzer.load_latest_data()
    if not data:
        print("\n⚠️  No PTT data found. Please run the scraper first:")
        print("   python src/scraper/ptt_scraper.py")
        return
    
    print(f"\n📊 Loaded {len(data.get('threads', []))} threads")
    
    # Analyze sentiment
    print("\n🔍 Analyzing sentiment...")
    sentiment_df = analyzer.analyze_all(data)
    
    # Fetch market data
    print("\n📈 Fetching TWII market data...")
    market_df = correlator.fetch_market_data()
    
    # Generate visualization
    print("\n🎨 Generating visualization...")
    viz_path = correlator.create_visualization(sentiment_df, market_df)
    
    # Generate report
    print("\n📋 Generating report...")
    report = correlator.generate_report(sentiment_df)
    
    # Print summary
    print("\n" + "=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Total Threads Analyzed: {report['total_threads']}")
    print(f"Average Sentiment Score: {report['average_sentiment']}")
    print(f"Weighted Sentiment: {report['average_weighted_sentiment']}")
    print(f"Bullish / Bearish / Neutral: {report['bullish_threads']} / {report['bearish_threads']} / {report['neutral_threads']}")
    print(f"\n🎯 Market Outlook: {report['market_outlook']}")
    
    if report.get('top_tokens'):
        print("\n📌 Top Sentiment Tokens:")
        for token, count in list(report['top_tokens'].items())[:5]:
            print(f"   • {token}: {count}")
    
    print(f"\n✓ Visualization saved: {viz_path}")
    print("=" * 60)
    
    # Save report
    report_path = os.path.join(correlator.output_path, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"✓ Report saved: {report_path}")


if __name__ == "__main__":
    main()
