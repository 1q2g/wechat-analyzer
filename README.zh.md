# WeChat Analyzer

提取、分析、可视化微信聊天记录，结合 AI 进行深度分析。根据微信版本4.1.9.55进行测试，可依据聊天记录（个人/群聊/所有）进行多维度分析并支持给出pdf版本的分析报告。可以连接微信官方的clawbot直接在微信聊天窗口进行使用。

> **⚠️ 免责声明**：本项目仅用于**教育和研究目的**。使用本项目可能违反微信的服务条款，请自行承担风险。请始终尊重他人隐私。

## 功能特性

- **导出**微信 4.x 加密数据库中的聊天消息
- **解密**SQLCipher 数据库，每个数据库独立密钥（自动映射）
- **提取**消息内容 — 纯文本、ZSTD 压缩 XML/protobuf
- **分析**聊天模式、沟通风格和行为特征
- **生成**性格分析 PDF 报告（MBTI、沟通风格等）
- **识别**联系人 — 通过 MD5 会话映射
- **解析**合并转发消息
- **定时**导出 — 通过 Windows 任务计划程序（可选）

## 部分效果图
<img width="861" height="912" alt="fe3f378f886613a17d8b86e3209289d8" src="https://github.com/user-attachments/assets/2d4f5058-86a3-4d4d-b6b4-123d7d7aab33" />
<img width="1119" height="1002" alt="8a800749c7b5f11dc41801b26e79978b" src="https://github.com/user-attachments/assets/cd8adaa2-b754-43a8-a441-047343a38e2c" />


## 架构

```
Weixin.exe (微信 4.x)
    │
    ▼ scan_keys.py          ← 来自 weixin-decrypte-script
    │
    ▼ map_keys.py           ← 匹配密钥到数据库
    │
    ▼ wechat_export.py      ← 解密 + 提取 + 导出 Markdown
    │
    ▼ (计划任务)             ← Windows 任务计划程序（可选）
    │
    ▼ Claude Code / AI      ← 读取、摘要、分析
```

## 前置条件

- **Windows 10/11** 64 位（微信和内存扫描所需）
- **微信 4.x**（已在 4.1.9.55 上验证）
- **Python 3.10+**
- **[weixin-decrypte-script](https://github.com/yourwechat/weixin-decrypte-script)**（外部工具，用于密钥提取）

## 安装

```bash
# 1. 克隆本仓库
git clone https://github.com/1q2g/wechat-analyzer.git
cd wechat-analyzer

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 配置 weixin-decrypte-script（外部依赖）
#    单独克隆，记下路径

# 4. 创建配置文件
cp config.example.json config.json
```

### 配置

编辑 `config.json`：

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

**如何找到你的 wxid**：查看 `C:/Users/<你>/xwechat_files/` 目录，你会看到 `wxid_*_<后缀>` 格式的文件夹名，那就是你的 wxid。

`db_suffix` 是文件夹名的尾部（如 `_00e5`、`_e5b1`）。

## 使用指南

### 1. 提取密钥

微信必须**正在运行且已登录**。

```bash
# 进入 weixin-decrypte-script 目录
cd /path/to/weixin-decrypte-script
python scan_keys.py

# 回到 wechat-analyzer
cd /path/to/wechat-analyzer
python scripts/map_keys.py
```

### 2. 导出最近消息

```bash
python scripts/wechat_export.py
```

导出最近 1 小时的消息（自动时间窗口：7:00-23:00）。输出到 `exports/wechat_YYYYMMDD_HHMM.md`。

### 3. 提取特定联系人

```bash
# 查找联系人
python scripts/find_contact.py "昵称"

# 提取聊天记录（最近 30 天）
python scripts/extract_target.py wxid_xxx 30
```

### 4. 分析未回复消息

```bash
python scripts/yesterday_unread.py
```

### 5. 调试内容提取

```bash
# 导出原始消息内容
python scripts/deep_dump.py

# 解析合并转发消息
python scripts/deep_forward.py
```

### 6. 性格分析报告

```bash
# 通过 Claude Code（如果已安装为 skill）
/personality-report <联系人昵称>
```

## 消息类型

| local_type | 含义 | 内容提取方式 |
|---|---|---|
| 1 | 文字消息 | 直接字符串或 ZSTD → 解码 |
| 3 | 图片 | 不可见 |
| 34 | 语音 | 不可见 |
| 43 | 视频 | 不可见 |
| 49 | 小程序/链接 | 不可见 |
| 4294967345 | AI 回复 | ZSTD → XML `<title>` |
| 81604378673 | 合并转发 | ZSTD → XML `<recorditem>` |

## 工作原理

### 数据库解密

微信 4.x 使用 SQLCipher，**每个数据库文件使用独立的加密密钥**。密钥存储在进程内存中。工作流程：

1. `scan_keys.py` 读取微信进程内存，提取候选密钥
2. `map_keys.py` 将每个密钥尝试解密所有 `.db` 文件，保存匹配结果

### 会话映射

`Msg_*` 表名编码了联系人 ID：`Msg_` + `MD5(wxid)`。这允许直接通过数据库表名定位到对应联系人，无需联系人数据库。

## 定时任务（Windows）

```bash
# 创建每小时执行的任务
schtasks /create /tn "WeChatExport" /tr "python C:\path\to\wechat_export.py" /sc hourly /mo 1

# 或使用任务计划程序 GUI 进行更精细的控制
```

## 项目结构

```
wechat-analyzer/
├── README.md               # 英文文档
├── README.zh.md            # 中文文档
├── LICENSE
├── .gitignore
├── requirements.txt
├── config.py               # 配置加载器
├── config.example.json     # 配置模板
├── scripts/
│   ├── wechat_export.py    # 主导出脚本
│   ├── map_keys.py         # 密钥映射
│   ├── find_contact.py     # 联系人搜索
│   ├── extract_target.py   # 定向提取
│   ├── deep_dump.py        # 调试工具
│   ├── deep_forward.py     # 合并转发解析
│   ├── yesterday_unread.py # 未读分析
│   └── verify_md5.py       # MD5 验证
└── skills/
    ├── wechat-digest/
    │   └── SKILL.md        # Claude Code skill
    └── wechat-personality-report/
        └── SKILL.md        # Claude Code skill
```

## 已知限制

- 仅支持微信 4.x（进程名为 `Weixin.exe`，非 `WeChat.exe`）
- 依赖进程内存扫描获取密钥（微信更新后偏移量可能变化）
- 多媒体内容（图片、语音、视频）无法提取
- 需要 Windows 环境（微信和内存扫描所需）  

## 致谢

- **[weixin-decrypte-script](https://github.com/yourwechat/weixin-decrypte-script)** — 核心密钥提取和数据库解密引擎
- 微信数据分析社区的所有贡献者和研究者

## 许可证

MIT
