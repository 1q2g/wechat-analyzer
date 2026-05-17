"""Parse merge-forward (combined) messages in WeChat.

Merge-forward messages (local_type=81604378673) contain XML with embedded
messages from multiple original senders. This tool decompresses and extracts
the individual messages with their original sender names and timestamps.
"""
import sqlite3, zstandard, json, os, sys, shutil, re
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

CFG = config.load()
BJT = timezone(timedelta(hours=8))
DB_BASE = f"{CFG['wechat_data_dir']}/{CFG['wxid']}_{CFG['db_suffix']}/db_storage"
DECRYPT_DIR = CFG["decrypt_script_dir"]
KEYS_CACHE = CFG["keys_cache"]
TMP_DIR = CFG["output_dir"] + "/tmp"

sys.path.insert(0, DECRYPT_DIR)
from decrypt_db import decrypt_db

os.makedirs(TMP_DIR, exist_ok=True)
dctx = zstandard.ZstdDecompressor()

with open(KEYS_CACHE) as f:
    keys = json.load(f)

FORWARD_TYPE = 81604378673
msg_keys = {k: v for k, v in keys.items() if "message" in k.replace("\\", "/") and "fts" not in k}


def extract_forward(xml_bytes):
    """Parse merge-forward XML and return list of (sender, time, text)."""
    try:
        text = xml_bytes.decode("utf-8", errors="replace")
        root = ET.fromstring(text)
        items = []
        title_el = root.find(".//title")
        title = title_el.text if title_el is not None else ""
        for item in root.findall(".//dataitem"):
            name = item.findtext("sourcename", "")
            st = item.findtext("sourcetime", "")
            desc = item.findtext("datadesc", "")
            items.append((name, st, desc))
        return title, items
    except Exception as e:
        return f"[parse error: {e}]", []


for rel, ki in msg_keys.items():
    src = os.path.join(DB_BASE, rel.replace("\\", "/"))
    if not os.path.exists(src):
        continue
    safe = rel.replace("\\", "_").replace("/", "_")
    tmp = os.path.join(TMP_DIR, safe)
    shutil.copy2(src, tmp)
    for ext in ["-wal", "-shm"]:
        w = src + ext
        if os.path.exists(w):
            shutil.copy2(w, tmp + ext)
    out = tmp + ".decrypted.db"
    decrypt_db(tmp, bytes.fromhex(ki["key"]), output_path=out)

    conn = sqlite3.connect(out)
    c = conn.cursor()
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for t in [x for x in tables if x.startswith("Msg_")]:
        c.execute(f"PRAGMA table_info({t})")
        cols = [r[1] for r in c.fetchall()]
        if "local_type" not in cols or "message_content" not in cols:
            continue
        rows = c.execute(
            f"SELECT create_time, message_content, local_type, real_sender_id FROM {t} "
            f"WHERE local_type={FORWARD_TYPE} ORDER BY rowid DESC LIMIT 10"
        ).fetchall()
        for row in rows:
            mc = row[1]
            if not isinstance(mc, bytes) or mc[:4] != b"\x28\xb5\x2f\xfd":
                continue
            try:
                dec = dctx.decompress(mc, max_output_size=10 * 1024 * 1024)
                title, items = extract_forward(dec)
                print(f"\n[Forward] sender_id={row[3]} time={row[0]} title={title}")
                print(f"  Messages:")
                for name, st, desc in items:
                    print(f"    [{st}] {name}: {desc[:200]}")
            except Exception as e:
                print(f"  Decompress error: {e}")
    conn.close()
