---
name: wechat-digest
version: 1.3.0
description: "WeChat chat history export and AI analysis. Supports MD5 session identification, contact mapping, merge-forward parsing, unread analysis."
metadata:
  triggers:
    - "/wechat-digest — analyze latest exported WeChat chat records"
    - "/wechat-export — trigger a manual export"
  requires:
    files:
      - "./scripts/wechat_export.py"
      - "./scripts/map_keys.py"
      - "./config.json"
      - "./exports/"
---

# wechat-digest (v1.3)

WeChat chat export & AI analysis skill for WeChat 4.x (process name `Weixin.exe`).
Tested on version **4.1.9.55**.

## Architecture

```
Weixin.exe process memory
     │
     ▼ scan_keys.py (scans 19 SQLCipher keys from memory)
     │
     ▼ decrypt_db.py (decrypts databases with WAL support)
     │
     ▼ wechat_export.py (exports last 1hr messages to Markdown)
     │
     ▼ (optional) Windows Task Scheduler — hourly trigger
     │
     ▼ Claude Code reads → summary + merge-forward parse + behavior analysis
```

## Prerequisites

- Windows 10/11 64-bit
- WeChat 4.x logged in
- Python 3.10+
- Dependencies: `pycryptodome`, `zstandard`, `pymem`, `psutil`, `pywin32`
- [weixin-decrypte-script](https://github.com/yourwechat/weixin-decrypte-script)

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and edit config
cp config.example.json config.json
# Edit config.json with your wxid and paths

# 3. Scan keys (WeChat must be running)
cd /path/to/weixin-decrypte-script
python scan_keys.py

# 4. Map keys to databases
cd /path/to/wechat-analyzer
python scripts/map_keys.py

# 5. Run export
python scripts/wechat_export.py
```

## Project Structure

| Path | Purpose |
|---|---|
| `scripts/wechat_export.py` | Main export script |
| `scripts/map_keys.py` | Auto-map scanned keys to databases |
| `scripts/find_contact.py` | Search contacts by nickname |
| `scripts/extract_target.py` | Extract history for a specific wxid |
| `scripts/deep_dump.py` | Debug raw message content |
| `scripts/deep_forward.py` | Parse merge-forward messages |
| `scripts/yesterday_unread.py` | Analyze unread messages |
| `scripts/verify_md5.py` | Verify MD5->wxid session mapping |
| `config.py` | Configuration loader |
| `config.json` | **Your config (gitignored)** |
| `config.example.json` | Config template |
| `exports/` | Exported markdown files (gitignored) |
| `skills/wechat-digest/SKILL.md` | This file |

## Database Structure

| Database | Content |
|---|---|
| `contact/contact.db` | Contacts (nickname, remark, avatar) |
| `session/session.db` | Session list |
| `message/message_1.db` | Main message storage (Msg_* tables) |

## Session Identification

Msg table names = `Msg_` + `MD5(wxid)`. This maps database tables to contacts.

## Sender Identification

- `real_sender_id` is an internal numeric ID, **not** the wxid
- The most frequent sender_id across all Msg tables = the account owner
- In 1-on-1 chats, the other sender_id = the contact

## Content Extraction

1. `message_content` = `str` → use directly
2. `message_content` = `bytes` starting with ZSTD magic → decompress → try XML `<title>` → fallback protobuf
3. Text messages (local_type=1) are typically plain `str`

## AI Analysis Prompt

When analyzing exported records:

```
## 1. Summary
- Topics grouped by contact (chronological)
- Key information and decisions
- People involved and their roles

## 2. Behavior Analysis
- How the user handled messages (reply/forward/ignore/deferred)
- Information flow paths

## 3. Action Items
- Explicit todos
- Implicit follow-ups
- Time-sensitive items
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| scan_keys returns empty | WeChat version too new | Check weixin-decrypte-script updates |
| Decryption fails | Keys for wrong account | Delete keys_cache.json, re-scan and map keys |
| All content `[not visible]` | message_content is str but checked as bytes | Ensure `isinstance(mc, str)` is checked first |
| Contact not found | Nickname not in message DB | Check contact/contact.db first |
