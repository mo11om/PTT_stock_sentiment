 

# Phase 4: Slang Miner (Regime Discovery Engine)

**Role:** Senior Quant Engineer
**Target File:** `src/analysis/slang_miner.py`
**Dependencies:** `jieba`, `sqlalchemy`, `pandas`

**Objective:** Implement a mining engine that identifies slang words dominating specific market regimes. A "Regime" is defined by the price change between **Today** and **X Days Ago**.

## 1. Logic Specification

* **Configuration Constants:**
* `LOOKBACK_DAYS = 30` (Compare today vs. 30 days ago)
* `THRESHOLD_PCT = 0.05` (5% change required to trigger a regime)


* **Regime Labeling Algorithm:**
For every date  in `MarketData`:
1. Get  (Close Price Today) and  (Close Price 30 days ago).
2. Calculate Delta: .
3. **Label:**
* **`BULL_TREND`**: If .
* **`BEAR_TREND`**: If .
* **`NEUTRAL`**: If  (Ignore these days).




* **Scoring Algorithm (Differential Polarity):**
1. **Aggregation:** Collect all `Post.content` for days labeled `BULL_TREND` into `corpus_bull`, and `BEAR_TREND` into `corpus_bear`.
2. **Tokenization:** Use `jieba` to tokenize both corpora. Filter out single characters, numbers, and common stopwords.
3. **Frequency Calculation:**
* 
* 


4. **Polarity Score:**


5. **Filtering:** Discard words where  (too rare to matter).



## 2. Database Integration

* **Table:** Create/Update `SlangCandidate` model in `src/database/models.py`:
* `token` (String, PK)
* `score` (Float, -1.0 to 1.0)
* `bull_freq` (Float), `bear_freq` (Float)
* `last_updated` (DateTime)



## 3. Implementation Steps

1. Create `src/analysis/slang_miner.py`.
2. Implement `class SlangMiner`.
* Method `_label_days()`: Returns a dict `{date: 'BULL'|'BEAR'}`.
* Method `_tokenize_posts(regime_dict)`: Iterates DB posts and builds the two token counters.
* Method `run()`: Orchestrates the labeling, tokenization, scoring, and upserts results to SQLite.


3. Add a generic `STOPWORDS` list (e.g., "的", "了", "是", "我") to clean the noise.

**Action:** Generate the code for `src/analysis/slang_miner.py` and update `src/database/models.py` to include the new table.