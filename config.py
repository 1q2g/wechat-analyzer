"""Configuration loader for WeChat analyzer tools.

Copy config.example.json to config.json and update the values for your system.
"""
import json, os, sys

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load():
    if not os.path.exists(CONFIG_FILE):
        print(f"[ERROR] {CONFIG_FILE} not found.")
        print("Copy config.example.json to config.json and update with your settings.")
        sys.exit(1)
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    # resolve ~ to user home
    for k in ("decrypt_script_dir", "wechat_data_dir", "output_dir", "keys_cache"):
        if k in cfg:
            cfg[k] = os.path.expanduser(cfg[k])
    return cfg
