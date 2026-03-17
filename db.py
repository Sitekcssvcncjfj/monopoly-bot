import sqlite3
from contextlib import closing
import json
import time

DB_PATH = "monopoly.db"

def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with closing(db()) as conn:
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS games (
            chat_id INTEGER PRIMARY KEY,
            started INTEGER DEFAULT 0,
            turn_idx INTEGER DEFAULT 0,
            state TEXT DEFAULT 'lobby',              -- lobby|turn|buy|auction|trade_pending|trade_setup
            pending_user INTEGER,
            pending_pos INTEGER,
            panel_message_id INTEGER,
            last_action TEXT DEFAULT '',
            updated_at INTEGER DEFAULT 0
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            chat_id INTEGER,
            user_id INTEGER,
            name TEXT,
            money INTEGER,
            position INTEGER,
            alive INTEGER,
            in_jail INTEGER,
            jail_turns INTEGER,
            doubles_count INTEGER,
            PRIMARY KEY(chat_id, user_id)
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            chat_id INTEGER,
            position INTEGER,
            owner_id INTEGER,
            houses INTEGER DEFAULT 0,
            hotel INTEGER DEFAULT 0,
            mortgaged INTEGER DEFAULT 0,
            PRIMARY KEY(chat_id, position)
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS auctions (
            chat_id INTEGER PRIMARY KEY,
            pos INTEGER,
            bidders_json TEXT,
            current_idx INTEGER DEFAULT 0,
            highest_bid INTEGER DEFAULT 0,
            highest_user INTEGER,
            passed_json TEXT DEFAULT '[]',
            updated_at INTEGER DEFAULT 0
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            chat_id INTEGER PRIMARY KEY,
            proposer_id INTEGER,
            target_id INTEGER,
            offer_pos INTEGER,
            request_pos INTEGER,
            cash_delta INTEGER DEFAULT 0,   -- proposer -> target (+) / target -> proposer (-)
            status TEXT DEFAULT 'pending',
            updated_at INTEGER DEFAULT 0
        )
        """)
        conn.commit()

# ---- game ----

def create_game(chat_id: int):
    now = int(time.time())
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM games WHERE chat_id=?", (chat_id,))
        c.execute("DELETE FROM players WHERE chat_id=?", (chat_id,))
        c.execute("DELETE FROM properties WHERE chat_id=?", (chat_id,))
        c.execute("DELETE FROM auctions WHERE chat_id=?", (chat_id,))
        c.execute("DELETE FROM trades WHERE chat_id=?", (chat_id,))
        c.execute("""
            INSERT INTO games(chat_id, started, turn_idx, state, pending_user, pending_pos, panel_message_id, last_action, updated_at)
            VALUES(?, 0, 0, 'lobby', NULL, NULL, NULL, '', ?)
        """, (chat_id, now))
        conn.commit()

def game_exists(chat_id: int) -> bool:
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM games WHERE chat_id=?", (chat_id,))
        return c.fetchone() is not None

def get_game(chat_id: int):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT chat_id, started, turn_idx, state, pending_user, pending_pos, panel_message_id, last_action, updated_at
            FROM games WHERE chat_id=?
        """, (chat_id,))
        r = c.fetchone()
        if not r:
            return None
        return {
            "chat_id": r[0],
            "started": bool(r[1]),
            "turn_idx": r[2],
            "state": r[3],
            "pending_user": r[4],
            "pending_pos": r[5],
            "panel_message_id": r[6],
            "last_action": r[7] or "",
            "updated_at": r[8] or 0
        }

def update_game(chat_id: int, **kwargs):
    if not kwargs:
        return
    kwargs["updated_at"] = int(time.time())
    keys = []
    vals = []
    for k, v in kwargs.items():
        keys.append(f"{k}=?")
        vals.append(v)
    vals.append(chat_id)
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute(f"UPDATE games SET {', '.join(keys)} WHERE chat_id=?", vals)
        conn.commit()

def delete_game(chat_id: int):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM games WHERE chat_id=?", (chat_id,))
        c.execute("DELETE FROM players WHERE chat_id=?", (chat_id,))
        c.execute("DELETE FROM properties WHERE chat_id=?", (chat_id,))
        c.execute("DELETE FROM auctions WHERE chat_id=?", (chat_id,))
        c.execute("DELETE FROM trades WHERE chat_id=?", (chat_id,))
        conn.commit()

# ---- players ----

def add_player(chat_id: int, user_id: int, name: str, start_money: int):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM players WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        if c.fetchone():
            return False
        c.execute("""
            INSERT INTO players(chat_id, user_id, name, money, position, alive, in_jail, jail_turns, doubles_count)
            VALUES(?, ?, ?, ?, 0, 1, 0, 0, 0)
        """, (chat_id, user_id, name, start_money))
        conn.commit()
        return True

def get_players(chat_id: int):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT user_id, name, money, position, alive, in_jail, jail_turns, doubles_count
            FROM players WHERE chat_id=?
            ORDER BY rowid
        """, (chat_id,))
        rows = c.fetchall()
        return [{
            "user_id": r[0],
            "name": r[1],
            "money": r[2],
            "position": r[3],
            "alive": bool(r[4]),
            "in_jail": bool(r[5]),
            "jail_turns": r[6],
            "doubles_count": r[7],
        } for r in rows]

def get_player(chat_id: int, user_id: int):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT user_id, name, money, position, alive, in_jail, jail_turns, doubles_count
            FROM players WHERE chat_id=? AND user_id=?
        """, (chat_id, user_id))
        r = c.fetchone()
        if not r:
            return None
        return {
            "user_id": r[0], "name": r[1], "money": r[2], "position": r[3],
            "alive": bool(r[4]), "in_jail": bool(r[5]), "jail_turns": r[6], "doubles_count": r[7]
        }

def update_player(chat_id: int, user_id: int, **kwargs):
    if not kwargs:
        return
    keys = []
    vals = []
    for k, v in kwargs.items():
        keys.append(f"{k}=?")
        vals.append(v)
    vals.extend([chat_id, user_id])
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute(f"UPDATE players SET {', '.join(keys)} WHERE chat_id=? AND user_id=?", vals)
        conn.commit()

# ---- properties ----

def get_properties(chat_id: int):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("SELECT position, owner_id, houses, hotel, mortgaged FROM properties WHERE chat_id=?", (chat_id,))
        rows = c.fetchall()
        return {
            r[0]: {"owner_id": r[1], "houses": r[2], "hotel": r[3], "mortgaged": r[4]}
            for r in rows
        }

def set_property_owner(chat_id: int, position: int, owner_id: int):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO properties(chat_id, position, owner_id, houses, hotel, mortgaged)
            VALUES(?, ?, ?, 0, 0, 0)
            ON CONFLICT(chat_id, position) DO UPDATE SET owner_id=excluded.owner_id
        """, (chat_id, position, owner_id))
        conn.commit()

def update_property(chat_id: int, position: int, **kwargs):
    if not kwargs:
        return
    keys = []
    vals = []
    for k, v in kwargs.items():
        keys.append(f"{k}=?")
        vals.append(v)
    vals.extend([chat_id, position])
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute(f"UPDATE properties SET {', '.join(keys)} WHERE chat_id=? AND position=?", vals)
        conn.commit()

def delete_properties_of_player(chat_id: int, owner_id: int):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM properties WHERE chat_id=? AND owner_id=?", (chat_id, owner_id))
        conn.commit()

# ---- auction ----

def start_auction(chat_id: int, pos: int, bidders: list[int]):
    now = int(time.time())
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM auctions WHERE chat_id=?", (chat_id,))
        c.execute("""
            INSERT INTO auctions(chat_id, pos, bidders_json, current_idx, highest_bid, highest_user, passed_json, updated_at)
            VALUES(?, ?, ?, 0, 0, NULL, '[]', ?)
        """, (chat_id, pos, json.dumps(bidders), now))
        conn.commit()

def get_auction(chat_id: int):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT chat_id, pos, bidders_json, current_idx, highest_bid, highest_user, passed_json, updated_at
            FROM auctions WHERE chat_id=?
        """, (chat_id,))
        r = c.fetchone()
        if not r:
            return None
        return {
            "chat_id": r[0],
            "pos": r[1],
            "bidders": json.loads(r[2]),
            "current_idx": r[3],
            "highest_bid": r[4],
            "highest_user": r[5],
            "passed": json.loads(r[6] or "[]"),
            "updated_at": r[7] or 0
        }

def update_auction(chat_id: int, **kwargs):
    if not kwargs:
        return
    kwargs["updated_at"] = int(time.time())
    keys = []
    vals = []
    for k, v in kwargs.items():
        if k in ("bidders", "passed"):
            v = json.dumps(v)
            k = f"{k}_json"
        keys.append(f"{k}=?")
        vals.append(v)
    vals.append(chat_id)
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute(f"UPDATE auctions SET {', '.join(keys)} WHERE chat_id=?", vals)
        conn.commit()

def clear_auction(chat_id: int):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM auctions WHERE chat_id=?", (chat_id,))
        conn.commit()

# ---- trade ----

def create_trade(chat_id: int, proposer_id: int, target_id: int, offer_pos: int, request_pos: int, cash_delta: int):
    now = int(time.time())
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM trades WHERE chat_id=?", (chat_id,))
        c.execute("""
            INSERT INTO trades(chat_id, proposer_id, target_id, offer_pos, request_pos, cash_delta, status, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (chat_id, proposer_id, target_id, offer_pos, request_pos, cash_delta, now))
        conn.commit()

def get_trade(chat_id: int):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT chat_id, proposer_id, target_id, offer_pos, request_pos, cash_delta, status, updated_at
            FROM trades WHERE chat_id=?
        """, (chat_id,))
        r = c.fetchone()
        if not r:
            return None
        return {
            "chat_id": r[0],
            "proposer_id": r[1],
            "target_id": r[2],
            "offer_pos": r[3],
            "request_pos": r[4],
            "cash_delta": r[5],
            "status": r[6],
            "updated_at": r[7] or 0
        }

def clear_trade(chat_id: int):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM trades WHERE chat_id=?", (chat_id,))
        conn.commit()
