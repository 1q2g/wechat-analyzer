"""Analyze yesterday's unread/unreplied messages.

Uses MD5-based session identification to map Msg tables to contacts,
then identifies messages that may need a response.
"""
import sqlite3, zstandard, json, os, sys, shutil, hashlib, re
from datetime import datetime, timezone, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

CFG = config.load()
BJT = timezone(timedelta(hours=8))
DB_BASE = f"{CFG['wechat_data_dir']}/{CFG['wxid']}_{CFG['db_suffix']}/db_storage"
DECRYPT_DIR = CFG["decrypt_script_dir"]
KEYS_CACHE = CFG["keys_cache"]
TMP_DIR = CFG["output_dir"] + "/tmp"

sys.path.insert(0, DECRYPT_DIR)
from decrypt_db import decrypt_db, try_decrypt_with_keys

os.makedirs(TMP_DIR, exist_ok=True)
dctx = zstandard.ZstdDecompressor()

with open(KEYS_CACHE) as f:
    keys = json.load(f)


def decrypt_db_file(src_rel, key_hex):
    src = os.path.join(DB_BASE, src_rel.replace("\\", "/"))
    if not os.path.exists(src):
        return None
    safe = src_rel.replace("\\", "_").replace("/", "_")
    tmp = os.path.join(TMP_DIR, safe)
    shutil.copy2(src, tmp)
    for ext in ["-wal", "-shm"]:
        w = src + ext
        if os.path.exists(w):
            shutil.copy2(w, tmp + ext)
    out = tmp + ".decrypted.db"
    decrypt_db(tmp, bytes.fromhex(key_hex), output_path=out)
    return out


def extract_content(mc):
    if isinstance(mc, str):
        return mc.strip()
    if not isinstance(mc, bytes) or not mc:
        return ""
    if mc[:4] == b"\x28\xb5\x2f\xfd":
        try:
            dec = dctx.decompress(mc, max_output_size=10 * 1024 * 1024)
            text = dec.decode("utf-8", errors="replace")
            m = re.search(r"<title>([^<]*)</title>", text)
            return m.group(1) if m else ""
        except Exception:
            return ""
    try:
        return mc.decode("utf-8", errors="replace")[:500]
    except Exception:
        return ""


def build_md5_wxid_map():
    """Build MD5(wxid) -> wxid mapping from Name2Id tables."""
    md5_map = {}
    msg_db_keys = {k: v for k, v in keys.items() if "message" in k.replace("\\", "/") and "fts" not in k}
    for rel, ki in msg_db_keys.items():
        dp = decrypt_db_file(rel, ki["key"])
        if not dp:
            continue
        try:
            conn = sqlite3.connect(dp)
            c = conn.cursor()
            try:
                for row in c.execute("SELECT * FROM Name2Id"):
                    uname = row[0]
                    if uname:
                        md5_map[hashlib.md5(uname.encode()).hexdigest()] = uname
            except Exception:
                pass
            conn.close()
        except Exception:
            pass
    return md5_map


def determine_self_sender_id():
    """Find the most frequent sender_id across all message DBs (= the account owner)."""
    counts = defaultdict(int)
    msg_db_keys = {k: v for k, v in keys.items() if "message" in k.replace("\\", "/") and "fts" not in k}
    for rel, ki in msg_db_keys.items():
        dp = decrypt_db_file(rel, ki["key"])
        if not dp:
            continue
        try:
            conn = sqlite3.connect(dp)
            c = conn.cursor()
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for t in [x for x in tables if x.startswith("Msg_")]:
                try:
                    for row in c.execute(f"SELECT real_sender_id FROM {t} WHERE real_sender_id IS NOT NULL LIMIT 1000"):
                        counts[row[0]] += 1
                except Exception:
                    pass
            conn.close()
        except Exception:
            pass
    if not counts:
        return 0
    return max(counts, key=counts.get)


def main():
    yesterday = datetime.now(BJT) - timedelta(days=1)
    start_ts = yesterday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    end_ts = yesterday.replace(hour=23, minute=59, second=59, microsecond=0).timestamp()

    print(f"Analyzing date: {yesterday.strftime('%Y-%m-%d')}")
    md5_map = build_md5_wxid_map()
    self_id = determine_self_sender_id()
    print(f"Self sender_id: {self_id}")

    msg_db_keys = {k: v for k, v in keys.items() if "message" in k.replace("\\", "/") and "fts" not in k}
    unread = []

    for rel, ki in msg_db_keys.items():
        dp = decrypt_db_file(rel, ki["key"])
        if not dp:
            continue
        try:
            conn = sqlite3.connect(dp)
            c = conn.cursor()
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for t in [x for x in tables if x.startswith("Msg_")]:
                hash_part = t[4:]
                wxid = md5_map.get(hash_part, "?")
                c.execute(f"PRAGMA table_info({t})")
                cols = [r[1] for r in c.fetchall()]
                if "create_time" not in cols or "real_sender_id" not in cols or "message_content" not in cols:
                    continue
                rows = c.execute(
                    f"SELECT create_time, message_content, local_type, real_sender_id, sort_seq FROM {t} "
                    f"WHERE create_time >= ? AND create_time <= ? ORDER BY sort_seq ASC",
                    (int(start_ts), int(end_ts)),
                ).fetchall()
                if not rows:
                    continue

                # Check if last message is from the other person (potentially unread)
                last = rows[-1]
                if last[3] != self_id:
                    unread.append({
                        "wxid": wxid,
                        "time": datetime.fromtimestamp(int(last[0]), tz=BJT).strftime("%Y-%m-%d %H:%M:%S"),
                        "content": extract_content(last[1])[:200],
                        "type": last[2],
                    })
            conn.close()
        except Exception as e:
            print(f"  Error {rel}: {e}")

    print(f"\n=== Unreplied messages ({len(unread)} contacts) ===\n")
    for u in unread:
        print(f"[{u['time']}] {u['wxid'][:20]}: {u['content']}")
        print()

    date_str = yesterday.strftime("%Y%m%d")
    out = os.path.join(CFG["output_dir"], f"unread_{date_str}.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# Unread Messages ({yesterday.strftime('%Y-%m-%d')})\n\n")
        for u in unread:
            f.write(f"- **{u['wxid'][:20]}** ({u['time']}): {u['content']}\n")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
