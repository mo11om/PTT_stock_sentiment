#!/usr/bin/env python3
"""
PTT Sentiment Alpha Dashboard
Streamlit app for visualizing PTT sentiment vs TWII market data.
"""

import sys
import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_db, Post, Sentiment, MarketData


# Page config
st.set_page_config(
    page_title="PTT Sentiment Alpha",
    page_icon="📈",
    layout="wide"
)

# Custom CSS for Taiwan market colors
st.markdown("""
<style>
    .bullish { color: #ff4444; font-weight: bold; }
    .bearish { color: #00cc00; font-weight: bold; }
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .stMetric > div {
        background: #16213e;
        padding: 15px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_sentiment_data():
    """Load sentiment data from database."""
    with get_db() as db:
        results = db.query(
            Post.id,
            Post.title,
            Post.publish_date,
            Post.push_count,
            Post.boo_count,
            Sentiment.score,
            Sentiment.analyzed_at
        ).join(Sentiment, Post.id == Sentiment.post_id).all()
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame([
            {
                "post_id": r[0],
                "title": r[1],
                "publish_date": r[2],
                "push_count": r[3],
                "boo_count": r[4],
                "score": r[5],
                "analyzed_at": r[6]
            }
            for r in results
        ])
        
        df['date'] = pd.to_datetime(df['publish_date']).dt.date
        return df


@st.cache_data(ttl=300)
def load_market_data():
    """Load market data from database."""
    with get_db() as db:
        results = db.query(MarketData).order_by(MarketData.date).all()
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame([
            {
                "date": r.date,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume
            }
            for r in results
        ])
        return df


def calculate_daily_sentiment(sentiment_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate sentiment scores by date."""
    if sentiment_df.empty:
        return pd.DataFrame()
    
    daily = sentiment_df.groupby('date').agg({
        'score': 'mean',
        'post_id': 'count',
        'push_count': 'sum',
        'boo_count': 'sum'
    }).reset_index()
    
    daily.columns = ['date', 'avg_sentiment', 'post_count', 'total_push', 'total_boo']
    return daily


def get_sentiment_signal(sentiment_df: pd.DataFrame, days: int = 3) -> str:
    """Calculate sentiment signal based on recent data."""
    if sentiment_df.empty:
        return "NEUTRAL"
    
    # Sort by date descending and take top N days
    recent = sentiment_df.sort_values('date', ascending=False).head(days)
    avg = recent['avg_sentiment'].mean() if 'avg_sentiment' in recent.columns else recent['score'].mean()
    
    if avg > 0.15:
        return "BULLISH"
    elif avg < -0.15:
        return "BEARISH"
    return "NEUTRAL"


def create_dual_axis_chart(market_df: pd.DataFrame, sentiment_df: pd.DataFrame):
    """Create dual-axis chart with Taiwan color logic (Red=Up, Green=Down)."""
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3],
        subplot_titles=("TWII Price & Sentiment", "Daily Sentiment Score")
    )
    
    # Market data - candlestick with Taiwan colors
    if not market_df.empty:
        market_df['date'] = pd.to_datetime(market_df['date'])
        
        # Custom colors: Red for up, Green for down (Taiwan style)
        colors = ['#ff4444' if row['close'] >= row['open'] else '#00cc00' 
                  for _, row in market_df.iterrows()]
        
        fig.add_trace(
            go.Candlestick(
                x=market_df['date'],
                open=market_df['open'],
                high=market_df['high'],
                low=market_df['low'],
                close=market_df['close'],
                name="TWII",
                increasing_line_color='#ff4444',  # Red for up
                decreasing_line_color='#00cc00',  # Green for down
            ),
            row=1, col=1
        )
    
    # Sentiment data
    if not sentiment_df.empty:
        sentiment_df['date'] = pd.to_datetime(sentiment_df['date'])
        
        # Color bars based on sentiment (Red=Bullish, Green=Bearish)
        colors = ['#ff4444' if s > 0 else '#00cc00' for s in sentiment_df['avg_sentiment']]
        
        fig.add_trace(
            go.Bar(
                x=sentiment_df['date'],
                y=sentiment_df['avg_sentiment'],
                name="Sentiment",
                marker_color=colors,
                opacity=0.7
            ),
            row=2, col=1
        )
        
        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=2, col=1)
    
    # Layout
    fig.update_layout(
        template="plotly_dark",
        height=600,
        showlegend=True,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        xaxis_rangeslider_visible=False,
        paper_bgcolor='#1a1a2e',
        plot_bgcolor='#16213e',
    )
    
    fig.update_xaxes(showgrid=True, gridcolor='#333')
    fig.update_yaxes(showgrid=True, gridcolor='#333')
    
    return fig


def main():
    """Main dashboard entry point."""
    
    # Header
    st.title("📈 PTT Sentiment Alpha")
    st.markdown("**Taiwan Stock Market** | Red = Up (Bullish) 🔴 | Green = Down (Bearish) 🟢")
    st.divider()
    
    # Load data
    sentiment_df = load_sentiment_data()
    market_df = load_market_data()
    daily_sentiment = calculate_daily_sentiment(sentiment_df)
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_posts = len(sentiment_df) if not sentiment_df.empty else 0
        st.metric("Total Posts Analyzed", total_posts)
    
    with col2:
        avg_sentiment = sentiment_df['score'].mean() if not sentiment_df.empty else 0
        st.metric("Average Sentiment", f"{avg_sentiment:.3f}")
    
    with col3:
        signal = get_sentiment_signal(daily_sentiment)
        signal_color = "🔴" if signal == "BULLISH" else "🟢" if signal == "BEARISH" else "⚪"
        st.metric("Current Signal (3-day)", f"{signal_color} {signal}")
    
    with col4:
        if not market_df.empty:
            latest_close = market_df.iloc[-1]['close']
            prev_close = market_df.iloc[-2]['close'] if len(market_df) > 1 else latest_close
            change = ((latest_close - prev_close) / prev_close) * 100
            st.metric("TWII Close", f"{latest_close:,.2f}", f"{change:+.2f}%")
        else:
            st.metric("TWII Close", "N/A")
    
    st.divider()
    
    # Main chart
    if not market_df.empty or not daily_sentiment.empty:
        fig = create_dual_axis_chart(market_df, daily_sentiment)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data available. Please run the pipeline first.")
    
    # Recent posts table
    st.subheader("📝 Recent Analyzed Posts")
    
    if not sentiment_df.empty:
        recent = sentiment_df.sort_values('publish_date', ascending=False).head(20)[['title', 'score', 'push_count', 'boo_count', 'publish_date']]
        recent['sentiment'] = recent['score'].apply(
            lambda x: "🔴 Bullish" if x > 0.1 else "🟢 Bearish" if x < -0.1 else "⚪ Neutral"
        )
        st.dataframe(recent, use_container_width=True, hide_index=True)
    else:
        st.info("No posts analyzed yet.")
    
    # Footer
    st.divider()
    st.caption("⚠️ **Taiwan Market Color Logic**: Red = Up (Bullish), Green = Down (Bearish)")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
