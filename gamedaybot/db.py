import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

_DB_PATH = None


def _get_db_path():
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = os.environ.get('DB_PATH', 'guilds.db')
    return _DB_PATH


def _connect():
    return sqlite3.connect(_get_db_path())


def init_db():
    """Create the guilds table if it doesn't exist, and migrate existing tables."""
    with _connect() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id            TEXT PRIMARY KEY,
                channel_id          TEXT,
                league_id           TEXT,
                league_year         INTEGER DEFAULT 2026,
                espn_s2             TEXT,
                swid                TEXT,
                timezone            TEXT DEFAULT 'America/New_York',
                monitor_report      INTEGER DEFAULT 1,
                daily_waiver        INTEGER DEFAULT 0,
                top_half_scoring    INTEGER DEFAULT 0,
                scoreboard_morning  INTEGER DEFAULT 1,
                scoreboard_evening  INTEGER DEFAULT 1,
                close_scores        INTEGER DEFAULT 1,
                period_recap        INTEGER DEFAULT 1
            )
        ''')
        # Migrate existing tables that predate these columns
        existing = {row[1] for row in conn.execute("PRAGMA table_info(guilds)")}
        for col, default in [
            ('scoreboard_morning', 1),
            ('scoreboard_evening', 1),
            ('close_scores', 1),
            ('period_recap', 1),
        ]:
            if col not in existing:
                conn.execute(f'ALTER TABLE guilds ADD COLUMN {col} INTEGER DEFAULT {default}')
        conn.commit()


def get_guild_config(guild_id):
    """Return config dict for a guild, or None if not configured."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            'SELECT * FROM guilds WHERE guild_id = ?', (str(guild_id),)
        ).fetchone()
    return dict(row) if row else None


def save_guild_config(guild_id, **kwargs):
    """Insert or update config for a guild."""
    guild_id = str(guild_id)
    existing = get_guild_config(guild_id)

    if existing:
        if not kwargs:
            return
        set_clause = ', '.join(f'{k} = ?' for k in kwargs)
        values = list(kwargs.values()) + [guild_id]
        with _connect() as conn:
            conn.execute(
                f'UPDATE guilds SET {set_clause} WHERE guild_id = ?', values
            )
            conn.commit()
    else:
        kwargs['guild_id'] = guild_id
        cols = ', '.join(kwargs.keys())
        placeholders = ', '.join('?' for _ in kwargs)
        with _connect() as conn:
            conn.execute(
                f'INSERT INTO guilds ({cols}) VALUES ({placeholders})',
                list(kwargs.values())
            )
            conn.commit()


def get_all_guild_configs():
    """Return a list of config dicts for all configured guilds."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM guilds WHERE league_id IS NOT NULL').fetchall()
    return [dict(row) for row in rows]


def delete_guild_config(guild_id):
    """Remove a guild's configuration."""
    with _connect() as conn:
        conn.execute('DELETE FROM guilds WHERE guild_id = ?', (str(guild_id),))
        conn.commit()
