"""Auto-map scan_keys output to database files.

Run after scan_keys.py to build the key cache. It walks every .db file
in the WeChat data directory and tries each candidate key against it.
"""
import sys, os, json, shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

CFG = config.load()
DB_BASE = f"{CFG['wechat_data_dir']}/{CFG['wxid']}_{CFG['db_suffix']}/db_storage"
KEYS_CACHE = CFG["keys_cache"]
DECRYPT_DIR = CFG["decrypt_script_dir"]
TMP_DIR = CFG["output_dir"] + "/tmp"

sys.path.insert(0, DECRYPT_DIR)
from decrypt_db import try_decrypt_with_keys

os.makedirs(TMP_DIR, exist_ok=True)

KEYS_FILE = os.path.join(DECRYPT_DIR, "found_keys.txt")
if not os.path.exists(KEYS_FILE):
    print(f"Error: {KEYS_FILE} not found. Run scan_keys.py first.")
    sys.exit(1)

keys_hex = []
with open(KEYS_FILE) as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) >= 3 and len(parts[-1]) == 64:
            keys_hex.append(parts[-1])

print(f"Loaded {len(keys_hex)} candidate keys")

db_files = []
for root, dirs, files in os.walk(DB_BASE):
    for fn in files:
        if not fn.endswith(".db"):
            continue
        full = os.path.join(root, fn)
        rel = os.path.relpath(full, DB_BASE).replace("\\", "/")
        db_files.append((full, rel))

print(f"Found {len(db_files)} DB files in db_storage")

success = 0
mapping = {}
for full_path, rel_path in db_files:
    safe_name = rel_path.replace("/", "_")
    tmp_path = os.path.join(TMP_DIR, safe_name)
    shutil.copy2(full_path, tmp_path)
    for ext in ["-wal", "-shm"]:
        w = full_path + ext
        if os.path.exists(w):
            shutil.copy2(w, tmp_path + ext)

    result_path, hex_key, idx = try_decrypt_with_keys(tmp_path, keys_hex)
    if result_path:
        mapping[rel_path] = {"key": hex_key}
        success += 1
        print(f"  OK {rel_path} -> key#{idx}")
    else:
        print(f"  FAIL {rel_path} -> NO MATCH")

    os.remove(tmp_path)
    for ext in ["-wal", "-shm"]:
        w = tmp_path + ext
        if os.path.exists(w):
            os.remove(w)

print(f"\nMatched {success}/{len(db_files)} databases")

with open(KEYS_CACHE, "w") as f:
    json.dump(mapping, f, indent=2)

print(f"Saved key cache to {KEYS_CACHE}")
