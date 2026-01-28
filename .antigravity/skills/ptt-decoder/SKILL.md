# Skill: PTT Stock Slang Decoder

## Description
Translates Taiwanese stock market slang into standard financial sentiment tokens.

## Instructions
When analyzing text from PTT (Taiwan), apply these transformation rules BEFORE sentiment scoring:

### 1. Bullish Terms (Positive)
| Slang | Translation | Token |
|-------|-------------|-------|
| 睏霸數錢 | Sleep & count money | [EXTREME_BULL] |
| 飛向宇宙 | Fly to universe | [BULL_MOMENTUM] |
| 歐印 | All-in | [HIGH_CONVICTION_BUY] |
| 噴 | Surge/Pump | [BULL_MOMENTUM] |
| 爆 | Explode (upward) | [BULL_MOMENTUM] |
| 起飛 | Take off | [BULL_MOMENTUM] |
| 噴到外太空 | Surge to outer space | [EXTREME_BULL] |

### 2. Bearish Terms (Negative)
| Slang | Translation | Token |
|-------|-------------|-------|
| 丸子 | Meatball (sounds like 完了) | [PANIC_SELL] |
| 完蛋 | Finished/Done for | [PANIC_SELL] |
| 睡公園 | Sleep in park (homeless) | [BANKRUPTCY_RISK] |
| 畢業 | Graduate (exit/stop loss) | [STOP_LOSS_EXIT] |
| 綠光罩頂 | Green light covers top | [MARKET_CRASH] |
| 崩 | Collapse | [PANIC_SELL] |
| 跳水 | Dive/Plunge | [PANIC_SELL] |
| 死魚 | Dead fish (no volume) | [BEARISH_STAGNANT] |
| 被套 | Trapped (bag holder) | [BEARISH_WARNING] |
| 割韭菜 | Cut leeks (retail slaughter) | [BEARISH_WARNING] |

### 3. Inversion Rules
- If a user says "好自為之" (good luck/take care) to "多軍" (bulls/longs), mark as [BEARISH_WARNING]
- Sarcastic use of bullish terms (look for quotation marks or "反串") should be inverted

### 4. Taiwan Market Color Logic
> **CRITICAL**: Taiwan uses INVERTED color logic compared to US markets!
> - 🔴 **Red = UP** (positive, bullish)
> - 🟢 **Green = DOWN** (negative, bearish)
>
> When processing color references in PTT stock discussions:
> - "紅的" / "紅色" / "紅通通" = BULLISH
> - "綠的" / "綠色" / "一片綠" = BEARISH

### 5. Sentiment Token Weights
| Token | Weight |
|-------|--------|
| [EXTREME_BULL] | +1.0 |
| [BULL_MOMENTUM] | +0.7 |
| [HIGH_CONVICTION_BUY] | +0.8 |
| [BEARISH_WARNING] | -0.5 |
| [STOP_LOSS_EXIT] | -0.6 |
| [PANIC_SELL] | -0.8 |
| [BANKRUPTCY_RISK] | -0.9 |
| [MARKET_CRASH] | -1.0 |
| [BEARISH_STAGNANT] | -0.4 |

## Usage
```python
from skills.ptt_decoder import decode_ptt_sentiment

text = "這支股票要飛向宇宙了！歐印！"
sentiment = decode_ptt_sentiment(text)
# Returns: {"tokens": ["BULL_MOMENTUM", "HIGH_CONVICTION_BUY"], "score": 0.75}
```
