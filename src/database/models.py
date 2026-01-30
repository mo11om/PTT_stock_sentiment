"""
SQLAlchemy ORM models for PTT Sentiment Analysis
"""

from datetime import datetime, date
from sqlalchemy import String, Text, Integer, Float, DateTime, Date, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import Optional


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Post(Base):
    """Stores raw PTT thread data."""
    
    __tablename__ = "posts"
    
    # PTT Post ID (e.g., M.1611234567.A.123)
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    author: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    publish_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # Renamed for clarity
    push_count: Mapped[int] = mapped_column(Integer, default=0)
    boo_count: Mapped[int] = mapped_column(Integer, default=0)
    url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    # Relationship to sentiment
    sentiment: Mapped[Optional["Sentiment"]] = relationship("Sentiment", back_populates="post", uselist=False)
    
    def __repr__(self) -> str:
        return f"<Post(id={self.id}, title={self.title[:30]}...)>"


class MarketData(Base):
    """Stores daily TWSE OHLC data to prevent repeated API calls."""
    
    __tablename__ = "market_data"
    
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    def __repr__(self) -> str:
        return f"<MarketData(date={self.date}, close={self.close})>"


class Sentiment(Base):
    """Stores computed sentiment scores for posts."""
    
    __tablename__ = "sentiments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[str] = mapped_column(String(50), ForeignKey("posts.id"), nullable=False, unique=True)
    
    # Sentiment scores
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)  # Basic weighted sentiment
    z_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Normalized deviation score
    
    # Trading day logic
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)  # Calculated trading day
    
    # Metadata
    tokens_found: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    # Relationship to post
    post: Mapped["Post"] = relationship("Post", back_populates="sentiment")
    
    # Index for efficient date queries
    __table_args__ = (
        Index('idx_sentiment_effective_date', 'effective_date'),
    )
    
    def __repr__(self) -> str:
        return f"<Sentiment(post_id={self.post_id}, raw_score={self.raw_score}, effective_date={self.effective_date})>"


class SlangCandidate(Base):
    """Stores discovered slang terms with regime-based correlation scores."""
    
    __tablename__ = "slang_candidates"
    
    token: Mapped[str] = mapped_column(String(50), primary_key=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)  # -1.0 to +1.0
    bull_freq: Mapped[int] = mapped_column(Integer, default=0)
    bear_freq: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    def __repr__(self) -> str:
        return f"<SlangCandidate(token={self.token}, score={self.score:.2f})>"

