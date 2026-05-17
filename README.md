# WeChat Analyzer

Extract, analyze, and visualize WeChat chat history with AI-powered insights.

> **⚠️ Disclaimer**: This project is for **educational and research purposes only**. Using it may violate WeChat's Terms of Service. Use at your own risk. Always respect others' privacy.

## Features

- **Export** chat messages from WeChat 4.x encrypted databases
- **Decrypt** SQLCipher databases with per-database keys (auto-mapped)
- **Extract** message content — plain text, ZSTD-compressed XML/protobuf
- **Analyze** chat patterns, communication style, and behavior
- **Generate** personality insight PDF reports (MBTI, communication style, etc.)
- **Identify** contacts via MD5 session mapping
- **Parse** merge-forward (combined) messages
- **Schedule** hourly exports via Windows Task Scheduler

## Architecture

```
Weixin.exe (WeChat 4.x)
    │
    ▼ scan_keys.py          ← from weixin-decrypte-script
    │
    ▼ map_keys.py           ← match keys to databases
    │
    ▼ wechat_export.py      ← decrypt + extract + export to Markdown
    │
    ▼ (scheduled task)      ← Windows Task Scheduler (optional)
    │
    ▼ Claude Code / AI      ← read, summarize, analyze
```

## Prerequisites

- **Windows 10/11** 64-bit (required for WeChat and memory scanning)
- **WeChat 4.x** (tested on 4.1.9.55)
- **Python 3.10+**
- **[weixin-decrypte-script](https://github.com/yourwechat/weixin-decrypte-script)** (external tool for key extraction)

## Installation

```bash
# 1. Clone this repo
git clone https://github.com/YOUR_USERNAME/wechat-analyzer.git
cd wechat-analyzer

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Set up weixin-decrypte-script (external dependency)
#    Clone it separately and note the path

# 4. Create your config
cp config.example.json config.json
```

### Configuration

Edit `config.json`:

```json
{
  "wxid": "wxid_your_account",
  "db_suffix": "_00e5",
  "wechat_data_dir": "C:/Users/you/xwechat_files",
  "decrypt_script_dir": "C:/Users/you/weixin-decrypte-script",
  "output_dir": "./exports",
  "keys_cache": "./keys_cache.json"
}
```

**How to find your wxid**: Look in `C:/Users/<you>/xwechat_files/` — you'll see directories named `wxid_*_<suffix>`. That's your wxid.

The `db_suffix` is the trailing part of that directory name (e.g., `_00e5`, `_e5b1`).

## Usage

### 1. Extract Keys

WeChat must be **running and logged in**.

```bash
# Go to weixin-decrypte-script directory
cd /path/to/weixin-decrypte-script
python scan_keys.py

# Back to wechat-analyzer
cd /path/to/wechat-analyzer
python scripts/map_keys.py
```

### 2. Export Recent Messages

```bash
python scripts/wechat_export.py
```

Exports the last hour of messages (automatic time window: 7:00-23:00). Output goes to `exports/wechat_YYYYMMDD_HHMM.md`.

### 3. Extract Specific Contact

```bash
# Find a contact
python scripts/find_contact.py "nickname"

# Extract their chat history (last 30 days)
python scripts/extract_target.py wxid_xxx 30
```

### 4. Analyze Unread Messages

```bash
python scripts/yesterday_unread.py
```

### 5. Debug Content

```bash
# Dump raw message content
python scripts/deep_dump.py

# Parse merge-forward messages
python scripts/deep_forward.py
```

### 6. Personality Report

```bash
# Via Claude Code (if installed as skill)
/personality-report <nickname>
```

## Message Types

| local_type | Meaning | Content Extraction |
|---|---|---|
| 1 | Text | Direct string or ZSTD → decode |
| 3 | Image | Not visible |
| 34 | Voice | Not visible |
| 43 | Video | Not visible |
| 49 | App/Link | Not visible |
| 4294967345 | AI reply | ZSTD → XML `<title>` |
| 81604378673 | Merge-forward | ZSTD → XML `<recorditem>` |

## How It Works

### Database Decryption

WeChat 4.x uses SQLCipher with **per-database encryption keys**. Each database file has its own key, stored in process memory. The workflow:

1. `scan_keys.py` reads WeChat process memory to extract candidate keys
2. `map_keys.py` tries each key against every `.db` file and saves the mapping

### Session Mapping

Msg table names encode the contact ID: `Msg_` + `MD5(wxid)`. This allows mapping database tables directly to contacts without needing the contact database.

## Scheduling (Windows)

```bash
# Create hourly task
schtasks /create /tn "WeChatExport" /tr "python C:\path\to\wechat_export.py" /sc hourly /mo 1

# Or use Task Scheduler GUI for fine-grained control
```

## Project Structure

```
wechat-analyzer/
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── config.py              # Config loader
├── config.example.json    # Config template
├── scripts/
│   ├── wechat_export.py   # Main export
│   ├── map_keys.py        # Key mapping
│   ├── find_contact.py    # Contact search
│   ├── extract_target.py  # Targeted extraction
│   ├── deep_dump.py       # Debug tool
│   ├── deep_forward.py    # Merge-forward parser
│   ├── yesterday_unread.py# Unread analysis
│   └── verify_md5.py      # MD5 verification
└── skills/
    ├── wechat-digest/
    │   └── SKILL.md       # Claude Code skill
    └── wechat-personality-report/
        └── SKILL.md       # Claude Code skill
```

## Limitations

- WeChat 4.x only (process name is `Weixin.exe`, not `WeChat.exe`)
- Relies on process memory scanning for keys (offsets may change with WeChat updates)
- Multimedia content (images, voice, video) cannot be extracted
- Requires Windows (for WeChat and memory scanning)

## Credits

- **[weixin-decrypte-script](https://github.com/yourwechat/weixin-decrypte-script)** — Core key extraction and database decryption engine
- All contributors and researchers in the WeChat data analysis community

## License

MIT
