# -*- coding: utf-8 -*-

import sqlite3
import logging
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from config import DATABASE_FILE, REFERRAL_REWARD

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection():
    """Database connection context manager"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def init_database():
    """Create users table if not exists"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    coins INTEGER DEFAULT 0,
                    referrals INTEGER DEFAULT 0,
                    invited_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_invited_by 
                ON users(invited_by)
            """)
            
            logger.info("Database initialized successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def add_user(telegram_id: int, username: str, first_name: str, invited_by: Optional[int] = None) -> bool:
    """Add new user to database if not exists"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,))
            if cursor.fetchone():
                return False
            
            cursor.execute("""
                INSERT INTO users (telegram_id, username, first_name, invited_by, coins, referrals)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (telegram_id, username, first_name, invited_by, 0, 0))
            
            if invited_by is not None:
                try:
                    cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (invited_by,))
                    if cursor.fetchone():
                        cursor.execute("""
                            UPDATE users 
                            SET coins = coins + ?, referrals = referrals + 1,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE telegram_id = ?
                        """, (REFERRAL_REWARD, invited_by))
                except Exception as e:
                    logger.error(f"Error updating referrer: {e}")
                    pass
            
            logger.info(f"User {telegram_id} added successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error adding user {telegram_id}: {e}")
        return False


def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Get user data from database"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting user {telegram_id}: {e}")
        return None


def update_user_coins(telegram_id: int, coins: int) -> bool:
    """Update user coins"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET coins = ?, updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            """, (coins, telegram_id))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating coins for {telegram_id}: {e}")
        return False


def get_top_referrals(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top users by referrals count"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT telegram_id, username, first_name, referrals, coins
                FROM users
                ORDER BY referrals DESC, coins DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting top referrals: {e}")
        return []


def get_top_coins(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top users by coins count"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT telegram_id, username, first_name, referrals, coins
                FROM users
                ORDER BY coins DESC, referrals DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting top coins: {e}")
        return []


def get_referral_count(telegram_id: int) -> int:
    """Get number of users invited by this user"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE invited_by = ?", (telegram_id,))
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error getting referral count for {telegram_id}: {e}")
        return 0