"""Find a WeChat contact by nickname across all databases.

Decrypts contact.db and searches for the given nickname in remark/nick_name fields.
Returns wxid and contact details.
"""
import sqlite3, json, os, sys, shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

CFG = config.load()
DB_BASE = f"{CFG['wechat_data_dir']}/{CFG['wxid']}_{CFG['db_suffix']}/db_storage"
DECRYPT_DIR = CFG["decrypt_script_dir"]
KEYS_CACHE = CFG["keys_cache"]
TMP_DIR = CFG["output_dir"] + "/tmp"

sys.path.insert(0, DECRYPT_DIR)
from decrypt_db import decrypt_db

os.makedirs(TMP_DIR, exist_ok=True)


def load_keys():
    with open(KEYS_CACHE) as f:
        return json.load(f)


keys = load_keys()


def find_db(rel_path):
    src = os.path.join(DB_BASE, rel_path.replace("\\", "/"))
    if not os.path.exists(src):
        return None
    rel_key = rel_path.replace("\\", "/")
    if rel_key not in keys:
        print(f"  No key for {rel_key}")
        return None
    safe = rel_key.replace("/", "_")
    tmp = os.path.join(TMP_DIR, safe)
    shutil.copy2(src, tmp)
    for ext in ["-wal", "-shm"]:
        w = src + ext
        if os.path.exists(w):
            shutil.copy2(w, tmp + ext)
    out = tmp + ".decrypted.db"
    decrypt_db(tmp, bytes.fromhex(keys[rel_key]["key"]), output_path=out)
    return out


def main():
    import sys as _sys
    if len(_sys.argv) < 2:
        print("Usage: python find_contact.py <nickname>")
        return

    query = _sys.argv[1]
    print(f"Searching for contact: {query}\n")

    # Try contact/contact.db
    db_path = find_db("contact/contact.db")
    if db_path:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tables:
            c.execute(f"PRAGMA table_info({t})")
            cols = [r[1] for r in c.fetchall()]
            if "remark" not in cols and "nick_name" not in cols:
                continue
            sql = (
                f"SELECT username, alias, remark, nick_name FROM {t} "
                f"WHERE remark LIKE '%{query}%' OR nick_name LIKE '%{query}%' "
                f"LIMIT 20"
            )
            rows = c.execute(sql).fetchall()
            for r in rows:
                print(f"  [{t}] username={r[0]}, alias={r[1]}, remark={r[2]}, nick_name={r[3]}")
        conn.close()

    # Also search session.db
    db_path = find_db("session/session.db")
    if db_path:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tables:
            c.execute(f"PRAGMA table_info({t})")
            cols = [r[1] for r in c.fetchall()]
            if "username" not in cols:
                continue
            rows = c.execute(f"SELECT * FROM {t} WHERE username LIKE '%{query}%' LIMIT 10").fetchall()
            if rows:
                print(f"\n  Session [{t}]:")
                for r in rows:
                    print(f"    {dict(zip(cols, r))}")
        conn.close()


if __name__ == "__main__":
    main()
