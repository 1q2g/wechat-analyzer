"""WeChat message exporter — decrypts and exports recent chat messages to Markdown.

Decrypts WeChat 4.x SQLite databases (SQLCipher), extracts message content
from the latest hour, and writes a Markdown file to the output directory.
Supports ZSTD-compressed protobuf/XML messages and plain-text fields.
"""
import sqlite3, zstandard, json, os, sys, shutil, subprocess, re
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

CFG = config.load()
BJT = timezone(timedelta(hours=8))
DB_BASE = f"{CFG['wechat_data_dir']}/{CFG['wxid']}_{CFG['db_suffix']}/db_storage"
DECRYPT_DIR = CFG["decrypt_script_dir"]
KEYS_CACHE = CFG["keys_cache"]
OUTPUT_DIR = CFG["output_dir"]
TMP_DIR = os.path.join(OUTPUT_DIR, "tmp")

os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

dctx = zstandard.ZstdDecompressor()


def log(msg):
    print(f"[{datetime.now(BJT).strftime('%H:%M:%S')}] {msg}")


def within_hours(start=7, end=23):
    h = datetime.now(BJT).hour
    return start <= h < end


def load_keys():
    if not os.path.exists(KEYS_CACHE):
        log("Running scan_keys.py...")
        r = subprocess.run(
            [sys.executable, f"{DECRYPT_DIR}/scan_keys.py"],
            capture_output=True, text=True, cwd=DECRYPT_DIR,
        )
        log(r.stdout[:500])
        log("Keys scanned. Run scripts/map_keys.py to build the key cache.")
        return None
    with open(KEYS_CACHE) as f:
        return json.load(f)


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
    sys.path.insert(0, DECRYPT_DIR)
    from decrypt_db import decrypt_db

    rawkey = bytes.fromhex(key_hex)
    return decrypt_db(tmp, rawkey, output_path=out)


def try_decode(data):
    if not data or not isinstance(data, bytes):
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("gbk")
    except UnicodeDecodeError:
        pass
    return ""


def extract_text_protobuf(data):
    """Extract text from protobuf (field type 2 = length-delimited strings)."""
    if not data or not isinstance(data, bytes):
        return ""
    result = []
    pos = 0
    while pos < len(data):
        try:
            tag, pos = _read_varint(data, pos)
        except Exception:
            break
        wt = tag & 0x07
        if wt == 0:
            _, pos = _read_varint(data, pos)
        elif wt == 1:
            pos += 8
        elif wt == 2:
            length, pos = _read_varint(data, pos)
            val = data[pos : pos + length]
            pos += length
            text = try_decode(val)
            if text and (text.isprintable() or any("一" <= c <= "鿿" for c in text)):
                result.append(text)
        elif wt == 5:
            pos += 4
        else:
            break
    return "\n".join(result)


def _read_varint(buf, pos):
    r = 0
    s = 0
    while pos < len(buf):
        b = buf[pos]
        r |= (b & 0x7F) << s
        pos += 1
        if not (b & 0x80):
            break
        s += 7
    return r, pos


MESSAGE_TYPE_MAP = {
    1: "text",
    3: "image",
    34: "voice",
    43: "video",
    49: "app",
    10000: "system",
}


def extract_content(mc):
    """Extract readable text from message_content."""
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
            return extract_text_protobuf(dec)
        except Exception:
            return ""
    return try_decode(mc)


def main():
    if not within_hours():
        log("Skipped: outside export window (7:00-23:00)")
        return

    keys = load_keys()
    if not keys:
        log("Error: cannot load keys cache")
        return

    msg_keys = {
        k: v
        for k, v in keys.items()
        if "message" in k.replace("\\", "/") and "fts" not in k and "resource" not in k
    }

    now = datetime.now(BJT)
    start_ts = (now - timedelta(hours=1)).timestamp()
    end_ts = now.timestamp()

    all_msgs = []
    for rel, ki in msg_keys.items():
        dec_path = decrypt_db_file(rel, ki["key"])
        if not dec_path:
            continue
        try:
            conn = sqlite3.connect(dec_path)
            c = conn.cursor()
            tables = [
                r[0]
                for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            ]
            for t in [x for x in tables if x.startswith("Msg_")]:
                c.execute(f"PRAGMA table_info({t})")
                cols = [r[1] for r in c.fetchall()]
                if "create_time" not in cols:
                    continue
                q = (
                    f"SELECT create_time, compress_content, message_content, "
                    f"local_type, real_sender_id FROM {t} "
                    f"WHERE create_time >= ? AND create_time <= ? ORDER BY sort_seq ASC"
                )
                for row in c.execute(q, (int(start_ts), int(end_ts))):
                    content = extract_content(row[2])
                    if not content and isinstance(row[1], bytes) and row[1][:4] == b"\x28\xb5\x2f\xfd":
                        try:
                            dec = dctx.decompress(row[1], max_output_size=10 * 1024 * 1024)
                            content = extract_text_protobuf(dec)
                        except Exception:
                            pass
                    ts = row[0]
                    time_str = (
                        datetime.fromtimestamp(int(ts), tz=BJT).strftime("%Y-%m-%d %H:%M:%S")
                        if ts
                        else "?"
                    )
                    all_msgs.append({
                        "time": time_str,
                        "type": MESSAGE_TYPE_MAP.get(row[3], f"t{row[3]}"),
                        "sender": str(row[4])[:8],
                        "content": content[:500],
                    })
            conn.close()
        except Exception as e:
            log(f"Error reading {rel}: {e}")

    all_msgs.sort(key=lambda m: m["time"])
    log(f"Exported {len(all_msgs)} messages")

    if not all_msgs:
        return

    date_str = datetime.now(BJT).strftime("%Y%m%d_%H%M")
    out = os.path.join(OUTPUT_DIR, f"wechat_{date_str}.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("# WeChat Chat History\n\n")
        f.write(f"Export time: {datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Messages: {len(all_msgs)}\n\n---\n\n")
        for m in all_msgs:
            content = m["content"] or "*[content not visible]*"
            f.write(f"- **[{m['type']}]** ({m['time']}) {m['sender']}: {content}\n")

    log(f"Saved: {out}")


if __name__ == "__main__":
    main()
