# 🌊 Slang Mining Flow & Algorithm

This document outlines the **end-to-end flow** of the PTT Sentiment Agent and the mathematical **algorithm** used to discover new market slang.

---

## 🔁 1. The Agent Flow (Lifecycle)

The `src/agent/bot.py` orchestrator manages the lifecycle of data from raw text to actionable slang tokens.

### Phase 1: Ingestion (The Scraper)
*   **Source**: PTT Stock Board (Web).
*   **Action**: Scrapes threads Newest $\to$ Oldest.
*   **Smart Stop**: Stops immediately upon finding a `PostID` that already exists in the local SQLite DB.
*   **Output**: Raw `Post` records in `ptt_sentiment.db`.

### Phase 2: Analysis (The Engine)
*   **Input**: Unanalyzed `Post` records.
*   **Normalization**: Applies existing Slang Dictionary (e.g., "All-in" $\to$ Bullish).
*   **Scoring**: Computes Weighted Sentiment Score ($S = \text{Base} \times \log(\text{Push} - \text{Boo})$).
*   **Alignment**: Shifts datestamps to the **Effective Trading Day** (Post-13:30 $\to$ T+1).
*   **Output**: `Sentiment` records linked to Posts.

### Phase 3: Discovery (The Miner)
*   **Input**: Historical `Post` text + `MarketData` (^TWII performance).
*   **Trigger**: Runs after sentiment analysis is complete.
*   **Logic**: Using the **Differential Scoring Algorithm** (see below) to find words that correlate with Bull/Bear days.
*   **Output**: A list of candidate "New Slang" terms.

### Phase 4: Feedback Loop
*   **Validation**: Human reviews the high-polarity candidates.
*   **Injection**: Valid terms are added to `src/analysis/engine.py`.
*   **Re-Run**: The Engine now recognizes these new terms in future posts.

---

## 🧮 2. The Slang Mining Algorithm

The core innovation is the **Differential Polarity Scorer**, which identifies words that appear predominantly during specific market conditions.

### Step A: The Oracle (Labeling)
We first label every historical day $t$ based on ^TWII performance:

$$
\text{Label}(t) = 
\begin{cases} 
\textbf{BULL} & \text{if } \Delta\%(t) \ge +0.5\% \text{ (Red Chart)} \\
\textbf{BEAR} & \text{if } \Delta\%(t) \le -0.5\% \text{ (Green Chart)} \\
\textbf{NEUTRAL} & \text{otherwise}
\end{cases}
$$

### Step B: Tokenization
We use `jieba` to segment Chinese text, pre-loaded with known financial terms to prevent over-segmentation.

### Step C: Polarity Calculation
For every unique token $w$, we calculate a **Polarity Score** $P(w)$ from $-1.0$ to $+1.0$:

$$
P(w) = \frac{\text{Freq}_{\text{Bull}}(w) - \text{Freq}_{\text{Bear}}(w)}{\text{Freq}_{\text{Bull}}(w) + \text{Freq}_{\text{Bear}}(w)}
$$

### Interpretation
*   **High Positive ($> 0.5$)**: **Bullish Slang**. The word is used when users are euphoric (e.g., "Moon", "Lambo").
*   **High Negative ($< -0.5$)**: **Bearish Slang**. The word is used when users are panicked (e.g., "Rooftop", "Graduate").
*   **Near Zero ($\approx 0$)**: **Noise**. Common stopwords or neutral entities (e.g., "TSMC", "Dividend").

---

## 📊 3. Example Data Flow

| Stage | Data State | Example |
| :--- | :--- | :--- |
| **Raw Text** | User Post | "OMG market is crashing, I am going to sleep in the park!" |
| **Tokenized** | List[str] | `["OMG", "market", "crashing", "sleep", "park"]` |
| **Market Context** | Label | Date = **BEAR** (TWII -2.5%) |
| **Miner Stats** | Counters | `freq_bear["park"] += 1` |
| **Result** | Polarity | `park` score becomes **-0.95** (Strong Bearish) |

---
*Generated for PTT Sentiment Alpha Agent*
