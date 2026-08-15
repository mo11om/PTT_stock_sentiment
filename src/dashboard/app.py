#!/usr/bin/env python3
"""
PTT Sentiment Alpha Dashboard
Streamlit app with Z-Score visualization and Taiwan color logic.
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


@st.cache_data(ttl=300)
def load_sentiment_data():
    """Load sentiment data with effective_date."""
    with get_db() as db:
        results = db.query(
            Post.id,
            Post.title,
            Post.publish_time,
            Post.push_count,
            Post.boo_count,
            Sentiment.raw_score,
            Sentiment.effective_date,
            Sentiment.analyzed_at
        ).join(Sentiment, Post.id == Sentiment.post_id).all()
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame([
            {
                "post_id": r[0],
                "title": r[1],
                "publish_time": r[2],
                "push_count": r[3],
                "boo_count": r[4],
                "raw_score": r[5],
                "effective_date": r[6],
                "analyzed_at": r[7]
            }
            for r in results
        ])
        
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


def calculate_daily_sentiment_with_zscore(sentiment_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate sentiment by effective_date and compute Z-Score.
    Z-Score = (Today_Avg - Rolling_Mean) / Rolling_Std
    """
    if sentiment_df.empty:
        return pd.DataFrame()
    
    daily = sentiment_df.groupby('effective_date').agg({
        'raw_score': 'mean',
        'post_id': 'count',
        'push_count': 'sum',
        'boo_count': 'sum'
    }).reset_index()
    
    daily.columns = ['date', 'avg_sentiment', 'post_count', 'total_push', 'total_boo']
    daily = daily.sort_values('date')
    
    # Calculate 20-day rolling Z-Score
    rolling_window = 20
    daily['rolling_mean'] = daily['avg_sentiment'].rolling(window=rolling_window, min_periods=3).mean()
    daily['rolling_std'] = daily['avg_sentiment'].rolling(window=rolling_window, min_periods=3).std()
    
    # Z-Score calculation
    daily['z_score'] = (daily['avg_sentiment'] - daily['rolling_mean']) / daily['rolling_std']
    daily['z_score'] = daily['z_score'].fillna(0)
    
    return daily


def get_sentiment_signal(sentiment_df: pd.DataFrame, days: int = 3) -> str:
    """Calculate sentiment signal based on recent Z-Score."""
    if sentiment_df.empty:
        return "NEUTRAL"
    
    recent = sentiment_df.sort_values('date', ascending=False).head(days)
    
    if 'z_score' in recent.columns:
        avg_z = recent['z_score'].mean()
    else:
        avg_z = recent['avg_sentiment'].mean() if 'avg_sentiment' in recent.columns else 0
    
    if avg_z > 0.5:
        return "BULLISH"
    elif avg_z < -0.5:
        return "BEARISH"
    return "NEUTRAL"


def _compute_streak_spine(
    daily_sentiment: pd.DataFrame,
    market_df: pd.DataFrame,
    z_threshold: float = 0.5,
) -> pd.DataFrame:
    """
    Full, unfiltered one-row-per-trading-day spine shared by the streak table
    and the lag correlation chart: date, close, z_score, avg_sentiment,
    direction (Bullish/Bearish/Neutral, bucketed off the 20-day rolling
    Z-Score), and streak_length (how many consecutive trading days sentiment
    has stayed in the same direction up to and including that day).

    A day resets the streak only when sentiment flips sign. Both no-post days
    and neutral days are skipped entirely when counting the streak — they
    neither extend it nor break it, so a bullish streak carries straight
    through a neutral or quiet day and keeps counting from where it left off.
    """
    if market_df is None or market_df.empty or daily_sentiment is None or daily_sentiment.empty:
        return pd.DataFrame()

    spine = market_df[['date', 'close']].copy()
    spine['date'] = pd.to_datetime(spine['date'])
    spine = spine.sort_values('date').reset_index(drop=True)

    sent = daily_sentiment[['date', 'avg_sentiment', 'z_score']].copy()
    sent['date'] = pd.to_datetime(sent['date'])

    df = spine.merge(sent, on='date', how='left')

    def _direction(v):
        if pd.isna(v):
            return None
        if v > z_threshold:
            return 'Bullish'
        if v < -z_threshold:
            return 'Bearish'
        return 'Neutral'

    df['direction'] = df['z_score'].apply(_direction)

    # Streak length is computed only over days classified Bullish/Bearish;
    # no-post days AND neutral days are both dropped before the run-length
    # count, so neither extends nor breaks the streak — a Bullish run carries
    # straight through them and keeps counting once it resumes, then the
    # result is mapped back onto the full calendar.
    has_data = df[df['direction'].isin(['Bullish', 'Bearish'])].copy()
    streak_id = (has_data['direction'] != has_data['direction'].shift()).cumsum()
    has_data['streak_length'] = has_data.groupby(streak_id).cumcount() + 1
    df['streak_length'] = has_data['streak_length']

    return df


def build_streak_signal_table(
    daily_sentiment: pd.DataFrame,
    market_df: pd.DataFrame,
    min_streak: int = 3,
    max_streak: int = 10,
    m_range=range(3, 6),
    z_threshold: float = 0.5,
) -> pd.DataFrame:
    """
    Raw, ungrouped, one-row-per-trading-day table.

    The signal is not an average — it is how many consecutive trading days
    sentiment has stayed in the same direction (bullish or bearish) up to and
    including that day.
    Only rows whose streak length falls in [min_streak, max_streak] are kept,
    alongside the actual forward return % for every horizon in ``m_range``
    (e.g. 3d/4d/5d).
    """
    df = _compute_streak_spine(daily_sentiment, market_df, z_threshold)
    if df.empty:
        return df

    fwd_cols = []
    for m in m_range:
        col = f'fwd_{m}d_%'
        df[col] = (df['close'].shift(-m) - df['close']) / df['close'] * 100.0
        fwd_cols.append(col)

    df = df[(df['streak_length'] >= min_streak) & (df['streak_length'] <= max_streak)]
    df = df.dropna(subset=fwd_cols).reset_index(drop=True)
    if df.empty:
        return df

    for col in fwd_cols:
        df[col] = df[col].round(3)

    df['streak_length'] = df['streak_length'].astype(int)
    df['direction'] = df['direction'].map({'Bullish': '🔴 Bullish', 'Bearish': '🟢 Bearish'})

    out = df[['date', 'streak_length', 'direction'] + fwd_cols].sort_values('date', ascending=False)
    out = out.rename(columns={
        'date': 'Date',
        'streak_length': 'Continuous Days',
        'direction': 'Direction',
    })
    return out.reset_index(drop=True)


def compute_streak_edge_grid(
    daily_sentiment: pd.DataFrame,
    market_df: pd.DataFrame,
    min_streak: int = 3,
    max_streak: int = 10,
    m_range=range(3, 6),
) -> pd.DataFrame:
    """
    Average forward return % by (streak length × direction) rows and forward
    horizon (M) columns — e.g. "after 5 continuous Bullish days, what happens
    over the next 3/4/5 days on average?" Built from the same raw streak table
    as the main display, just grouped for a summary view.
    """
    table = build_streak_signal_table(daily_sentiment, market_df, min_streak, max_streak, m_range)
    if table.empty:
        return pd.DataFrame()

    fwd_cols = [c for c in table.columns if c.startswith('fwd_')]
    grouped = table.groupby(['Continuous Days', 'Direction'])[fwd_cols].agg(['mean', 'count'])
    grouped = grouped.sort_index(level=['Direction', 'Continuous Days'])
    means = grouped.xs('mean', axis=1, level=1).round(3)
    counts = grouped.xs('count', axis=1, level=1)[fwd_cols[0]]
    means.index = [f"{d} × {n} (n={counts.loc[(n, d)]})" for n, d in means.index]
    return means


def classify_sentiment(z_score: float, z_threshold: float = 0.5) -> str:
    """
    Bucket a daily sentiment reading into Bearish / Neutral / Bullish using the
    20-day rolling Z-Score rather than a fixed cutoff on the raw average.
    Raw avg_sentiment is skewed positive (PTT stock-board posts score bullish
    on average), so a fixed absolute band like ±0.05 barely ever classifies a
    day as Bearish. The Z-Score is relative to each day's own trailing
    baseline, so it stays balanced as that baseline drifts.
    """
    if pd.isna(z_score):
        return "Neutral"
    if z_score > z_threshold:
        return "Bullish"
    if z_score < -z_threshold:
        return "Bearish"
    return "Neutral"


def create_sentiment_calendar_heatmap(daily_sentiment: pd.DataFrame):
    """
    Calendar heatmap (week x weekday) of the daily sentiment bucket, based on
    the 20-day rolling Z-Score: Bearish (z < -0.5), Neutral (-0.5 to +0.5),
    Bullish (z > +0.5). Hover text still shows the raw avg_sentiment value.
    """
    if daily_sentiment.empty:
        return None

    df = daily_sentiment[['date', 'avg_sentiment', 'z_score']].copy()
    df['date'] = pd.to_datetime(df['date'])
    df['category'] = df['z_score'].apply(classify_sentiment)
    df['cat_code'] = df['category'].map({'Bearish': -1, 'Neutral': 0, 'Bullish': 1})
    df['weekday'] = df['date'].dt.strftime('%a')
    df['week'] = df['date'].dt.strftime('%Y-W%U')

    weekday_order = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    z_pivot = df.pivot_table(index='weekday', columns='week', values='cat_code', aggfunc='mean')
    z_pivot = z_pivot.reindex(weekday_order)
    sent_pivot = df.pivot_table(index='weekday', columns='week', values='avg_sentiment', aggfunc='mean')
    sent_pivot = sent_pivot.reindex(weekday_order)

    week_cols = sorted(z_pivot.columns.tolist())
    z_pivot = z_pivot[week_cols]
    sent_pivot = sent_pivot[week_cols]

    hover_text = [
        [f"{v:+.3f}" if pd.notna(v) else "no data" for v in row]
        for row in sent_pivot.values
    ]

    fig = go.Figure(data=go.Heatmap(
        z=z_pivot.values,
        x=z_pivot.columns,
        y=z_pivot.index,
        customdata=hover_text,
        hovertemplate="Week %{x}<br>%{y}<br>Avg sentiment: %{customdata}<extra></extra>",
        colorscale=[[0, '#00cc00'], [0.5, '#2a2a3e'], [1, '#ff4444']],
        zmin=-1, zmax=1,
        showscale=True,
        colorbar=dict(
            title="Signal",
            tickvals=[-1, 0, 1],
            ticktext=["🟢 Bearish", "⚪ Neutral", "🔴 Bullish"],
        ),
        xgap=2,
        ygap=2,
    ))
    fig.update_layout(
        template="plotly_dark",
        height=320,
        paper_bgcolor='#1a1a2e',
        plot_bgcolor='#16213e',
        xaxis_title="Week",
        yaxis_title="",
        xaxis=dict(showgrid=False, tickangle=-45),
        yaxis=dict(showgrid=False),
    )
    return fig


def create_dual_axis_chart(market_df: pd.DataFrame, sentiment_df: pd.DataFrame):
    """Create dual-axis chart: TWII price + Z-Score with Taiwan colors."""
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.65, 0.35],
        subplot_titles=("TWII Price", "Sentiment Z-Score (Red=Bullish, Green=Bearish)")
    )
    
    # Market data - candlestick with Taiwan colors
    if not market_df.empty:
        market_df = market_df.copy()
        market_df['date'] = pd.to_datetime(market_df['date'])
        
        fig.add_trace(
            go.Candlestick(
                x=market_df['date'],
                open=market_df['open'],
                high=market_df['high'],
                low=market_df['low'],
                close=market_df['close'],
                name="TWII",
                increasing_line_color='#ff4444',  # Red for up (Taiwan)
                decreasing_line_color='#00cc00',  # Green for down (Taiwan)
            ),
            row=1, col=1
        )
    
    # Z-Score data
    if not sentiment_df.empty and 'z_score' in sentiment_df.columns:
        sentiment_df = sentiment_df.copy()
        sentiment_df['date'] = pd.to_datetime(sentiment_df['date'])
        
        # Color bars: Red = Bullish (positive Z), Green = Bearish (negative Z)
        colors = ['#ff4444' if z > 0 else '#00cc00' for z in sentiment_df['z_score']]
        
        fig.add_trace(
            go.Bar(
                x=sentiment_df['date'],
                y=sentiment_df['z_score'],
                name="Z-Score",
                marker_color=colors,
                opacity=0.8
            ),
            row=2, col=1
        )
        
        # Add reference lines
        fig.add_hline(y=0, line_dash="solid", line_color="white", opacity=0.5, row=2, col=1)
        fig.add_hline(y=1, line_dash="dash", line_color="#ff6666", opacity=0.3, row=2, col=1)
        fig.add_hline(y=-1, line_dash="dash", line_color="#66cc66", opacity=0.3, row=2, col=1)
    
    # Layout
    fig.update_layout(
        template="plotly_dark",
        height=650,
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
    daily_sentiment = calculate_daily_sentiment_with_zscore(sentiment_df)
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_posts = len(sentiment_df) if not sentiment_df.empty else 0
        st.metric("Total Posts", total_posts)
    
    with col2:
        if not daily_sentiment.empty and 'z_score' in daily_sentiment.columns:
            latest_z = daily_sentiment.iloc[-1]['z_score']
            st.metric("Latest Z-Score", f"{latest_z:.2f}")
        else:
            st.metric("Latest Z-Score", "N/A")
    
    with col3:
        signal = get_sentiment_signal(daily_sentiment)
        signal_color = "🔴" if signal == "BULLISH" else "🟢" if signal == "BEARISH" else "⚪"
        st.metric("Signal (3-day)", f"{signal_color} {signal}")
    
    with col4:
        if not market_df.empty:
            latest_close = market_df.iloc[-1]['close']
            prev_close = market_df.iloc[-2]['close'] if len(market_df) > 1 else latest_close
            change = ((latest_close - prev_close) / prev_close) * 100
            st.metric("TWII Close", f"{latest_close:,.0f}", f"{change:+.2f}%")
        else:
            st.metric("TWII Close", "N/A")
    
    st.divider()

    tab_overview, tab_backtest = st.tabs(["📊 Overview", "🔮 Trend Backtest"])

    with tab_overview:
        # Main chart
        if not market_df.empty or not daily_sentiment.empty:
            fig = create_dual_axis_chart(market_df, daily_sentiment)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No data available. Please run the pipeline first.")

        # Sentiment calendar heatmap
        st.subheader("🗓️ Sentiment Calendar Heatmap")
        st.caption(
            "🟢 Bearish: Z-Score < -0.5 | ⚪ Neutral: -0.5 to +0.5 | 🔴 Bullish: Z-Score > +0.5 "
            "(20-day rolling Z-Score of daily avg_sentiment, not a fixed cutoff)"
        )
        heatmap_fig = create_sentiment_calendar_heatmap(daily_sentiment)
        if heatmap_fig is not None:
            st.plotly_chart(heatmap_fig, use_container_width=True)
        else:
            st.info("No sentiment data available for the heatmap.")

        # Recent posts table
        st.subheader("📝 Recent Analyzed Posts")

        if not sentiment_df.empty:
            recent = sentiment_df.sort_values('publish_time', ascending=False).head(20)
            display_df = recent[['title', 'raw_score', 'effective_date', 'push_count', 'boo_count']].copy()
            display_df['sentiment'] = display_df['raw_score'].apply(
                lambda x: "🔴 Bullish" if x > 0.1 else "🟢 Bearish" if x < -0.1 else "⚪ Neutral"
            )
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No posts analyzed yet.")

    with tab_backtest:
        st.subheader("🔮 Sentiment → Future Trend Backtest")
        st.caption(
            "The signal is a streak, not an average: how many trading days in a row "
            "sentiment stayed bullish or bearish. Trading days with no PTT posts, and "
            "neutral-sentiment days, are both skipped when counting — they don't break "
            "the streak, it just carries through them. Each row is one trading "
            "day where that streak fell in the selected range, plus what the TWII actually "
            "did over the selected forward horizons. Market-wide (^TWII index) only — there "
            "is no per-stock sentiment mapping. Past performance does not guarantee future results."
        )

        if daily_sentiment.empty or market_df.empty:
            st.warning("Not enough data to run the backtest. Please run the pipeline first.")
        else:
            c1, c2 = st.columns([2, 1])
            with c1:
                min_streak, max_streak = st.slider(
                    "Continuous same-direction days (streak length)",
                    min_value=2, max_value=15, value=(3, 10),
                )
            with c2:
                fwd_days = st.multiselect(
                    "Forward horizon(s) to show (days)",
                    options=list(range(1, 11)),
                    default=[3, 4, 5],
                )

            if not fwd_days:
                st.info("Select at least one forward horizon.")
            else:
                m_range = sorted(fwd_days)
                streak_table = build_streak_signal_table(
                    daily_sentiment, market_df, min_streak, max_streak, m_range=m_range
                )

                if streak_table.empty:
                    st.info("Not enough overlapping trading days for this streak-length range.")
                else:
                    bullish_days = (streak_table['Direction'] == "🔴 Bullish").sum()
                    bearish_days = (streak_table['Direction'] == "🟢 Bearish").sum()
                    first_fwd_col = f'fwd_{m_range[0]}d_%'
                    avg_fwd_first = streak_table[first_fwd_col].mean()

                    m1, m2, m3 = st.columns(3)
                    with m1:
                        st.metric("Matching trading days", len(streak_table))
                    with m2:
                        st.metric("Bullish / Bearish streak-days", f"{bullish_days} / {bearish_days}")
                    with m3:
                        st.metric(f"Avg {m_range[0]}d fwd return (all rows)", f"{avg_fwd_first:+.2f}%")

                    st.dataframe(streak_table, use_container_width=True, hide_index=True, height=500)

                    st.markdown(
                        "**Avg forward return by streak length** — e.g. after N continuous "
                        f"Bullish/Bearish days, what happened over the next {', '.join(str(m)+'d' for m in m_range)} on average."
                    )
                    grid = compute_streak_edge_grid(daily_sentiment, market_df, min_streak, max_streak, m_range=m_range)
                    if not grid.empty:
                        heat_fig = go.Figure(data=go.Heatmap(
                            z=grid.values,
                            x=grid.columns,
                            y=grid.index,
                            colorscale=[[0, '#00cc00'], [0.5, '#16213e'], [1, '#ff4444']],
                            zmid=0,
                            text=grid.values,
                            texttemplate="%{text:.2f}",
                            colorbar=dict(title="Avg Fwd Return %"),
                        ))
                        heat_fig.update_layout(
                            template="plotly_dark",
                            height=400,
                            paper_bgcolor='#1a1a2e',
                            plot_bgcolor='#16213e',
                            xaxis_title="Forward horizon",
                            yaxis_title="Direction × Continuous Days",
                        )
                        st.plotly_chart(heat_fig, use_container_width=True)

    # Footer
    st.divider()
    st.caption("⚠️ **Taiwan Market Color Logic**: Red = Up (Bullish), Green = Down (Bearish)")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
