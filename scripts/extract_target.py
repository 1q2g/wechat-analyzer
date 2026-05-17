"""Extract full chat history for a target wxid over a date range."""
import sqlite3, zstandard, json, os, sys, shutil, re
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

CFG = config.load()
BJT = timezone(timedelta(hours=8))
DB_BASE = f"{CFG['wechat_data_dir']}/{CFG['wxid']}_{CFG['db_suffix']}/db_storage"
DECRYPT_DIR = CFG["decrypt_script_dir"]
KEYS_CACHE = CFG["keys_cache"]
TMP_DIR = CFG["output_dir"] + "/tmp"
OUTPUT_DIR = CFG["output_dir"]

sys.path.insert(0, DECRYPT_DIR)
from decrypt_db import decrypt_db

os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

dctx = zstandard.ZstdDecompressor()


def load_keys():
    with open(KEYS_CACHE) as f:
        return json.load(f)


keys = load_keys()

MESSAGE_TYPE_MAP = {1: "text", 3: "image", 34: "voice", 43: "video", 49: "app", 10000: "system"}


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
            if m:
                return m.group(1)
        except Exception:
            pass
    try:
        return mc.decode("utf-8", errors="replace")
    except Exception:
        return ""


def main():
    import sys as _sys
    if len(_sys.argv) < 3:
        print("Usage: python extract_target.py <wxid> <days> [--all-dbs]")
        return

    target_wxid = _sys.argv[1]
    days = int(_sys.argv[2])
    search_all = "--all-dbs" in _sys.argv

    now = datetime.now(BJT)
    start_ts = (now - timedelta(days=days)).timestamp()
    end_ts = now.timestamp()

    msg_keys = {k: v for k, v in keys.items() if "message" in k.replace("\\", "/") and ("fts" not in k or search_all)}

    all_msgs = []
    for rel, ki in msg_keys.items():
        dec_path = decrypt_db_file(rel, ki["key"])
        if not dec_path:
            continue
        try:
            conn = sqlite3.connect(dec_path)
            c = conn.cursor()
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for t in [x for x in tables if x.startswith("Msg_")]:
                c.execute(f"PRAGMA table_info({t})")
                cols = [r[1] for r in c.fetchall()]
                if "create_time" not in cols or "real_sender_id" not in cols or "message_content" not in cols:
                    continue
                q = (
                    f"SELECT create_time, message_content, local_type, real_sender_id FROM {t} "
                    f"WHERE create_time >= ? AND create_time <= ? ORDER BY sort_seq ASC"
                )
                for row in c.execute(q, (int(start_ts), int(end_ts))):
                    all_msgs.append({
                        "time": datetime.fromtimestamp(int(row[0]), tz=BJT).strftime("%Y-%m-%d %H:%M:%S"),
                        "type": MESSAGE_TYPE_MAP.get(row[2], f"t{row[2]}"),
                        "sender_id": row[3],
                        "content": extract_content(row[1])[:500],
                    })
            conn.close()
        except Exception as e:
            print(f"  Error: {rel}: {e}")

    all_msgs.sort(key=lambda m: m["time"])
    print(f"Total messages: {len(all_msgs)}")

    if not all_msgs:
        return

    date_str = now.strftime("%Y%m%d_%H%M")
    safe_wxid = target_wxid.replace("@", "_")
    out = os.path.join(OUTPUT_DIR, f"chat_{safe_wxid}_{date_str}.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# Chat History: {target_wxid}\n\n")
        f.write(f"Range: {(now - timedelta(days=days)).strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}\n")
        for m in all_msgs:
            content = m["content"] or "*[content not visible]*"
            f.write(f"- **[{m['type']}]** ({m['time']}) s{m['sender_id']}: {content}\n")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
