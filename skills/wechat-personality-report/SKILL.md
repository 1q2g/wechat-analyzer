---
name: wechat-personality-report
version: 1.0.0
description: "Generate personality analysis PDF reports from WeChat chat history. Includes MBTI, communication style, emotion analysis."
metadata:
  triggers:
    - "/personality-report <nickname> — generate personality PDF for a contact"
  requires:
    files:
      - "./config.json"
    packages:
      - reportlab
      - faker
---

# wechat-personality-report (v1.0)

Generate personality analysis PDF reports from WeChat chat history.

## Workflow

```
Contact nickname
    → contact.db → get wxid
    → MD5(wxid) → locate Msg table
    → extract ~1 year of chat history
    → multi-dimensional analysis
    → desensitize data
    → generate PDF report
```

## Analysis Dimensions

1. **Data Overview**: total messages, monthly/periodic distribution, avg message length
2. **MBTI**: E/I, S/N, T/F, J/P with evidence from message content
3. **Expressive vs Reserved** (浓人/淡人): 6-dimension score (emotion, social energy, expression richness, initiative, positivity, life density)
4. **Communication Style**: short/long sentence preference, tone characteristics
5. **Topic & Life Portrait**: work, sports, food, pets, travel, family percentages
6. **Emotion & Energy**: positive/negative sentiment ratio, energy curve
7. **Relationship Closeness**: 6-dimension star rating

## Quick Start

```bash
# Install extra dependencies
pip install reportlab faker

# Run
/personality-report <contact_nickname>
```

## Data Desensitization

All reports are desensitized before saving using faker:
- Real names → fake names
- wxid → masked
- Phone numbers → randomized
- Personality traits and message style are preserved

## PDF Specs

| Element | Spec |
|---|---|
| Page | A4, 2cm margins |
| Title font | 28pt, dark blue |
| Body | 10pt, 1.5x line spacing |
| Colors | Dark blue #1a1a2e + red accents |

> **Disclaimer**: This is not a professional psychological assessment. The analysis is for entertainment purposes based on chat data patterns.
