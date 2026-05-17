"""Verify MD5(username) = Msg table name pattern.

Scans all Name2Id tables and checks that every Msg table hash matches
the MD5 of a known wxid.
"""
import sqlite3, hashlib, json, os, sys, shutil

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

with open(KEYS_CACHE) as f:
    keys = json.load(f)

msg_db_keys = {k: v for k, v in keys.items() if "message" in k.replace("\\", "/") and "fts" not in k}

# Build MD5 -> wxid map
md5_to_wxid = {}
for rel, ki in msg_db_keys.items():
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
    try:
        for row in c.execute("SELECT * FROM Name2Id"):
            uname = row[0]
            if uname:
                md5_to_wxid[hashlib.md5(uname.encode()).hexdigest()] = uname
    except Exception as e:
        print(f"  No Name2Id in {rel}: {e}")
    conn.close()

print(f"Built MD5 map with {len(md5_to_wxid)} entries\n")

# Verify each Msg table
total = 0
matched = 0
for rel, ki in msg_db_keys.items():
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
        total += 1
        h = t[4:]
        if h in md5_to_wxid:
            matched += 1
        else:
            print(f"  UNMATCHED: {t} in {rel}")
    conn.close()

print(f"\nResult: {matched}/{total} Msg tables matched by MD5")
