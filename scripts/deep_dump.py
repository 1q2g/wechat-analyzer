"""Debug tool: decompress and dump raw message content for analysis."""
import sqlite3, zstandard, os, sys, shutil, json

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

dctx = zstandard.ZstdDecompressor()


with open(KEYS_CACHE) as f:
    keys = json.load(f)

msg_keys = {k: v for k, v in keys.items() if "message" in k.replace("\\", "/") and "fts" not in k and "resource" not in k}

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
        if "message_content" not in cols:
            continue
        rows = c.execute(
            f"SELECT create_time, message_content, local_type, rowid FROM {t} "
            f"WHERE create_time > 0 ORDER BY rowid DESC LIMIT 5"
        ).fetchall()
        for row in rows:
            mc = row[1]
            print(f"[{rel}] {t} type={row[2]} create_time={row[0]} rowid={row[3]}")
            print(f"  message_content: type={type(mc).__name__} len={len(mc) if mc else 0}")
            if isinstance(mc, str):
                print(f"  >>> TEXT: {mc[:300]}")
            elif isinstance(mc, bytes):
                print(f"  hex[:40]: {mc[:40].hex()}")
                if mc[:4] == b"\x28\xb5\x2f\xfd":
                    try:
                        dec = dctx.decompress(mc, max_output_size=10 * 1024 * 1024)
                        print(f"  >>> ZSTD ({len(dec)} bytes): {dec[:300]}")
                    except Exception as e:
                        print(f"  ZSTD FAIL: {e}")
                else:
                    try:
                        print(f"  >>> UTF-8: {mc.decode('utf-8', errors='replace')[:300]}")
                    except Exception as e:
                        print(f"  DECODE FAIL: {e}")
            print()
    conn.close()
