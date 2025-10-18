from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class HelpMessage(Base):
    __tablename__ = 'help_messages'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, nullable=False, unique=True)
    message_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SeenArticle(Base):
    __tablename__ = 'seen_articles'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, nullable=False)
    article_identifier = Column(String(64), nullable=False)  # SHA256 hash
    source = Column(String(20), nullable=False)  # 'finnhub' or 'marketaux'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Index for faster lookups
    __table_args__ = (
        Index('idx_guild_article', 'guild_id', 'article_identifier'),
        Index('idx_guild_created', 'guild_id', 'created_at'),
    )

class GuildHeartbeat(Base):
    __tablename__ = 'guild_heartbeats'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, nullable=False, unique=True)
    last_heartbeat = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WatchlistItem(Base):
    __tablename__ = 'watchlist_items'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    guild_id = Column(Integer, nullable=False)
    symbol = Column(String(20), nullable=False)  # Stock symbol (e.g., AAPL, TSLA)
    company_name = Column(String(200))  # Optional company name
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Index for faster lookups and ensure no duplicates
    __table_args__ = (
        Index('idx_user_guild', 'user_id', 'guild_id'),
        Index('idx_user_guild_symbol', 'user_id', 'guild_id', 'symbol', unique=True),
    )

class DatabaseManager:
    def __init__(self, database_url='sqlite:///bot_data.db'):
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Create tables
        Base.metadata.create_all(bind=self.engine)
        
        # Clean up old articles on startup (keep last 500 per guild)
        self.cleanup_old_articles()
        
    def get_session(self):
        """Get a new database session"""
        return self.SessionLocal()
    
    def cleanup_old_articles(self):
        """Remove old articles, keeping only the most recent 500 per guild"""
        with self.get_session() as session:
            try:
                # Get all guilds that have articles
                guilds = session.query(SeenArticle.guild_id).distinct().all()
                
                for (guild_id,) in guilds:
                    # Get all articles for this guild, ordered by creation time (newest first)
                    articles = session.query(SeenArticle)\
                        .filter(SeenArticle.guild_id == guild_id)\
                        .order_by(SeenArticle.created_at.desc())\
                        .all()
                    
                    # If more than 500, delete the oldest ones
                    if len(articles) > 500:
                        articles_to_delete = articles[500:]
                        for article in articles_to_delete:
                            session.delete(article)
                
                session.commit()
            except Exception as e:
                print(f"Error during cleanup: {e}")
                session.rollback()
    
    # Help Messages methods
    def get_help_message_id(self, guild_id: int) -> int:
        """Get the stored help message ID for a guild"""
        with self.get_session() as session:
            help_msg = session.query(HelpMessage).filter(HelpMessage.guild_id == guild_id).first()
            return help_msg.message_id if help_msg else None
    
    def save_help_message_id(self, guild_id: int, message_id: int):
        """Save or update the help message ID for a guild"""
        with self.get_session() as session:
            try:
                help_msg = session.query(HelpMessage).filter(HelpMessage.guild_id == guild_id).first()
                
                if help_msg:
                    help_msg.message_id = message_id
                    help_msg.updated_at = datetime.utcnow()
                else:
                    help_msg = HelpMessage(guild_id=guild_id, message_id=message_id)
                    session.add(help_msg)
                
                session.commit()
            except Exception as e:
                print(f"Error saving help message ID: {e}")
                session.rollback()
    
    # Seen Articles methods
    def is_article_seen(self, guild_id: int, article_identifier: str) -> bool:
        """Check if an article has been seen in a guild"""
        with self.get_session() as session:
            article = session.query(SeenArticle)\
                .filter(SeenArticle.guild_id == guild_id)\
                .filter(SeenArticle.article_identifier == article_identifier)\
                .first()
            return article is not None
    
    def mark_article_seen(self, guild_id: int, article_identifier: str, source: str):
        """Mark an article as seen in a guild"""
        with self.get_session() as session:
            try:
                # Check if already exists
                existing = session.query(SeenArticle)\
                    .filter(SeenArticle.guild_id == guild_id)\
                    .filter(SeenArticle.article_identifier == article_identifier)\
                    .first()
                
                if not existing:
                    article = SeenArticle(
                        guild_id=guild_id,
                        article_identifier=article_identifier,
                        source=source
                    )
                    session.add(article)
                    session.commit()
                    
                    # Clean up old articles for this guild (keep only 500 most recent)
                    self.cleanup_guild_articles(session, guild_id)
            except Exception as e:
                print(f"Error marking article as seen: {e}")
                session.rollback()
    
    def cleanup_guild_articles(self, session, guild_id: int):
        """Clean up old articles for a specific guild"""
        try:
            articles = session.query(SeenArticle)\
                .filter(SeenArticle.guild_id == guild_id)\
                .order_by(SeenArticle.created_at.desc())\
                .all()
            
            if len(articles) > 500:
                articles_to_delete = articles[500:]
                for article in articles_to_delete:
                    session.delete(article)
                session.commit()
        except Exception as e:
            print(f"Error cleaning up guild articles: {e}")
            session.rollback()
    
    # Heartbeat methods
    def get_last_heartbeat(self, guild_id: int) -> datetime:
        """Get the last heartbeat time for a guild"""
        with self.get_session() as session:
            heartbeat = session.query(GuildHeartbeat)\
                .filter(GuildHeartbeat.guild_id == guild_id)\
                .first()
            return heartbeat.last_heartbeat if heartbeat else None
    
    def update_heartbeat(self, guild_id: int, timestamp: datetime):
        """Update the heartbeat time for a guild"""
        with self.get_session() as session:
            try:
                heartbeat = session.query(GuildHeartbeat)\
                    .filter(GuildHeartbeat.guild_id == guild_id)\
                    .first()
                
                if heartbeat:
                    heartbeat.last_heartbeat = timestamp
                    heartbeat.updated_at = datetime.utcnow()
                else:
                    heartbeat = GuildHeartbeat(guild_id=guild_id, last_heartbeat=timestamp)
                    session.add(heartbeat)
                
                session.commit()
            except Exception as e:
                print(f"Error updating heartbeat: {e}")
                session.rollback()

    # Watchlist methods
    def add_to_watchlist(self, user_id: int, guild_id: int, symbol: str, company_name: str = None) -> bool:
        """Add a company to user's watchlist. Returns True if added, False if already exists"""
        with self.get_session() as session:
            try:
                # Check if already exists
                existing = session.query(WatchlistItem)\
                    .filter(WatchlistItem.user_id == user_id)\
                    .filter(WatchlistItem.guild_id == guild_id)\
                    .filter(WatchlistItem.symbol == symbol.upper())\
                    .first()
                
                if existing:
                    return False  # Already exists
                
                # Add new item
                watchlist_item = WatchlistItem(
                    user_id=user_id,
                    guild_id=guild_id,
                    symbol=symbol.upper(),
                    company_name=company_name
                )
                session.add(watchlist_item)
                session.commit()
                return True
            except Exception as e:
                print(f"Error adding to watchlist: {e}")
                session.rollback()
                return False
    
    def remove_from_watchlist(self, user_id: int, guild_id: int, symbol: str) -> bool:
        """Remove a company from user's watchlist. Returns True if removed, False if not found"""
        with self.get_session() as session:
            try:
                item = session.query(WatchlistItem)\
                    .filter(WatchlistItem.user_id == user_id)\
                    .filter(WatchlistItem.guild_id == guild_id)\
                    .filter(WatchlistItem.symbol == symbol.upper())\
                    .first()
                
                if item:
                    session.delete(item)
                    session.commit()
                    return True
                return False
            except Exception as e:
                print(f"Error removing from watchlist: {e}")
                session.rollback()
                return False
    
    def get_user_watchlist(self, user_id: int, guild_id: int) -> list:
        """Get all watchlist items for a user in a guild"""
        with self.get_session() as session:
            try:
                items = session.query(WatchlistItem)\
                    .filter(WatchlistItem.user_id == user_id)\
                    .filter(WatchlistItem.guild_id == guild_id)\
                    .order_by(WatchlistItem.symbol)\
                    .all()
                
                return [{
                    'symbol': item.symbol,
                    'company_name': item.company_name,
                    'created_at': item.created_at
                } for item in items]
            except Exception as e:
                print(f"Error getting watchlist: {e}")
                return []
            
    def get_watchlist_count(self, user_id: int, guild_id: int) -> int:
        """Get count of items in user's watchlist"""
        with self.get_session() as session:
            return session.query(WatchlistItem)\
                .filter(WatchlistItem.user_id == user_id)\
                .filter(WatchlistItem.guild_id == guild_id)\
                .count()
        
# Global database manager instance
db_manager = DatabaseManager()