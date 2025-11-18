# Spreadsheet Tabs Explanation - Full Markets vs All Markets

## Quick Summary

| Tab | Content | Filters | Volatility Data | Purpose |
|-----|---------|---------|-----------------|---------|
| **Full Markets** | ALL markets from API | None (raw data) | ❌ No | Raw data dump |
| **All Markets** | Markets with good rewards + volatility | `gm_reward >= 0.75` | ✅ Yes | Discovery with full analysis |
| **Volatility Markets** | Stable markets with good rewards | `gm_reward >= 0.75` AND `volatility_sum < 20` | ✅ Yes | Safe trading candidates |

---

## Full Markets Tab

### What It Contains

**Full Markets** = `m_data` = **ALL processed markets with basic reward calculations**

This is the **raw data dump** with NO filtering.

### Data Flow

```python
# In update_markets.py, line 290
m_data, all_markets = get_markets(all_results, sel_df, maker_reward=0.75)

# In find_markets.py, line 315
all_data = new_df.copy()  # This becomes m_data
return all_data, all_markets

# In update_markets.py, line 315
update_sheet(m_data, wk_full)  # Save to Full Markets tab
```

### What Data Is Included

**Source**: `all_results` = Results from `process_single_row()` for each market

**Processing**:
1. Takes ALL markets from `get_all_results()`
2. Adds calculated reward metrics
3. Formats columns
4. NO reward filtering applied
5. NO volatility calculation
6. NO volatility filtering

**Columns** (from line 311 in find_markets.py):
```python
[
    'question',           # Market question
    'answer1',           # Yes outcome
    'answer2',           # No outcome
    'neg_risk',          # Negative risk flag
    'spread',            # Bid-ask spread (snapshot)
    'best_bid',          # Best bid price (snapshot)
    'best_ask',          # Best ask price (snapshot)
    'rewards_daily_rate', # Total daily USDC reward budget
    'bid_reward_per_100', # Expected bid reward per $100
    'ask_reward_per_100', # Expected ask reward per $100
    'gm_reward_per_100',  # Geometric mean reward (PRIMARY METRIC)
    'sm_reward_per_100',  # Arithmetic mean reward
    'min_size',          # Minimum position for rewards
    'max_spread',        # Maximum spread for rewards
    'tick_size',         # Minimum price increment
    'market_slug',       # URL identifier
    'token1',            # Yes token ID
    'token2',            # No token ID
    'condition_id'       # Condition ID
]
```

### Filters Applied

**NONE** - This is completely unfiltered data!

```python
# In find_markets.py, line 313-314
new_df = new_df.replace([np.inf, -np.inf], 0)
all_data = new_df.copy()  # No filtering, just copy
```

### What's NOT Included

❌ **No volatility data** (1h, 3h, 6h, 12h, 24h, 7d, 14d, 30d)
❌ **No volatility_sum**
❌ **No volatility/reward ratio**
❌ **No volatility_price**

**Why?** Fetching volatility requires API calls for price history (expensive/slow). Full Markets shows raw data before volatility analysis.

### Sorting

**Sorted by**: `rewards_daily_rate` descending (line 312 in find_markets.py)

This shows markets with the highest total reward budgets first.

### Use Cases

1. **Debugging** - See raw API data before processing
2. **Complete inventory** - Every market scanned
3. **Finding hidden gems** - Markets that might have low GM reward but other interesting properties
4. **Data export** - Complete dataset for external analysis
5. **Historical tracking** - All markets at time of scan

### Example Data

```
question: "Will it snow in NYC tomorrow?"
answer1: "Yes"
answer2: "No"
spread: 0.02
best_bid: 0.45
best_ask: 0.47
rewards_daily_rate: 50
bid_reward_per_100: 0.60
ask_reward_per_100: 0.65
gm_reward_per_100: 0.62  ❌ Below 0.75 threshold
sm_reward_per_100: 0.63
min_size: 20
max_spread: 3
tick_size: 0.01

Status:
✅ INCLUDED in Full Markets (no filter)
❌ EXCLUDED from All Markets (reward too low)
❌ EXCLUDED from Volatility Markets (reward too low)
```

---

## All Markets Tab

### What It Contains

**All Markets** = `all_markets` with volatility = **Markets worth considering + volatility analysis**

This shows markets that **pass the reward threshold** with **complete volatility data**.

### Data Flow

```python
# In update_markets.py, line 290
m_data, all_markets = get_markets(all_results, sel_df, maker_reward=0.75)

# In find_markets.py, lines 318-321
making_markets = s_df[~new_df['question'].isin(sel_df['question'])]
making_markets = making_markets.sort_values('gm_reward_per_100', ascending=False)
making_markets = making_markets[making_markets['gm_reward_per_100'] >= maker_reward]  # FILTER!
all_markets = get_combined_markets(new_df, making_markets, sel_df)

# In update_markets.py, line 293
new_df = add_volatility_to_df(all_markets)  # ADD VOLATILITY!

# In update_markets.py, line 308
new_df = new_df.sort_values('gm_reward_per_100', ascending=False)

# In update_markets.py, line 313
update_sheet(new_df, wk_all)  # Save to All Markets tab
```

### What Data Is Included

**Step 1 - Reward Filtering**:
```python
making_markets = making_markets[making_markets['gm_reward_per_100'] >= 0.75]
```

Only markets with **`gm_reward_per_100 >= 0.75`** are included.

**Step 2 - Combine with Selected Markets**:
```python
# If you have Selected Markets, include them too
old_markets = new_df[new_df['question'].isin(sel_df['question'])]
all_markets = pd.concat([old_markets, new_markets])
```

Ensures your currently selected markets are always shown (even if rewards drop below 0.75).

**Step 3 - Add Volatility Data**:
```python
new_df = add_volatility_to_df(all_markets)
new_df['volatility_sum'] = new_df['24_hour'] + new_df['7_day'] + new_df['14_day']
new_df['volatility/reward'] = (new_df['gm_reward_per_100'] / new_df['volatility_sum']).round(2)
```

Fetches price history and calculates volatility for all time windows.

**Columns** (from line 297-300 in update_markets.py):
```python
[
    # Market Info
    'question',
    'answer1',
    'answer2',
    
    # Price/Spread Info
    'spread',
    'best_bid',
    'best_ask',
    'volatility_price',  # ✅ Current price from history
    
    # Reward Metrics
    'rewards_daily_rate',
    'gm_reward_per_100',  # PRIMARY SORT KEY
    'sm_reward_per_100',
    'bid_reward_per_100',
    'ask_reward_per_100',
    
    # Volatility Metrics (✅ ADDED!)
    'volatility_sum',     # 24h + 7d + 14d
    'volatility/reward',  # Reward per unit risk
    '1_hour',            # 1-hour annualized volatility
    '3_hour',            # 3-hour annualized volatility
    '6_hour',            # 6-hour annualized volatility
    '12_hour',           # 12-hour annualized volatility
    '24_hour',           # 24-hour annualized volatility
    '7_day',             # 7-day annualized volatility
    '30_day',            # 30-day annualized volatility
    
    # Configuration
    'min_size',
    'max_spread',
    'tick_size',
    'neg_risk',
    
    # Identifiers
    'market_slug',
    'token1',
    'token2',
    'condition_id'
]
```

### Filters Applied

**PRIMARY FILTER**: `gm_reward_per_100 >= 0.75`

```python
# In find_markets.py, line 320
making_markets = making_markets[making_markets['gm_reward_per_100'] >= maker_reward]
```

**Additional Logic**:
- Excludes markets already in "Selected Markets" (to show new opportunities)
- Then combines with Selected Markets (to show all profitable ones)
- Deduplicates by question

### Sorting

**Sorted by**: `gm_reward_per_100` descending (line 308 in update_markets.py)

Shows highest-reward markets first, regardless of volatility.

### Use Cases

1. **Market discovery** - Find new profitable markets
2. **Reward comparison** - See all markets with good rewards
3. **Volatility assessment** - Check if high-reward markets are too volatile
4. **Opportunity scanning** - Browse all potentially profitable options
5. **Risk analysis** - Compare rewards vs volatility across markets

### Example Data

```
question: "Will Trump announce candidacy this week?"
gm_reward_per_100: 2.50  ✅ Above threshold
volatility_sum: 35.8     ⚠️ High volatility!
volatility/reward: 0.07   ⚠️ Low ratio
24_hour: 15.2
7_day: 12.5
14_day: 8.1

Status:
❌ NOT in Full Markets (might be if scanned all markets)
✅ INCLUDED in All Markets (good reward)
❌ EXCLUDED from Volatility Markets (too volatile)

Interpretation:
- Great rewards (2.5% per day)
- But very volatile (sum = 35.8)
- High risk doesn't justify reward (ratio = 0.07)
- NOT recommended for safe market making
```

---

## Volatility Markets Tab

### What It Contains

**Volatility Markets** = Filtered subset of All Markets = **Safe + profitable markets**

This shows markets that **pass BOTH reward AND volatility thresholds**.

### Data Flow

```python
# In update_markets.py, line 303-305
volatility_df = new_df.copy()  # Start with All Markets data
volatility_df = volatility_df[new_df['volatility_sum'] < 20]  # FILTER by volatility!
volatility_df = volatility_df.sort_values('gm_reward_per_100', ascending=False)

# In update_markets.py, line 314
update_sheet(volatility_df, wk_vol)  # Save to Volatility Markets tab
```

### What Data Is Included

**Filters** (both must pass):
1. ✅ `gm_reward_per_100 >= 0.75` (inherited from All Markets)
2. ✅ `volatility_sum < 20` (NEW filter)

**Result**: Only stable, profitable markets

**Same columns as All Markets** - Full volatility data included

### Filters Applied

**TWO FILTERS**:
1. `gm_reward_per_100 >= 0.75` (from get_markets)
2. `volatility_sum < 20` (line 304 in update_markets.py)

### Sorting

**Sorted by**: `gm_reward_per_100` descending

Shows best risk-adjusted opportunities first.

### Use Cases

1. **Safe market selection** - Pre-filtered for stability
2. **Bot configuration** - Add directly to Selected Markets
3. **Low-risk trading** - Minimize adverse fill risk
4. **Automated operation** - Markets suitable for unattended bots
5. **Conservative strategy** - Focus on consistent returns

### Example Data

```
question: "Will Federal Reserve raise rates in March?"
gm_reward_per_100: 1.85   ✅ Good reward
volatility_sum: 16.14     ✅ Stable
volatility/reward: 0.11   ✅ Good ratio
24_hour: 5.12
7_day: 5.72
14_day: 5.30

Status:
❌ NOT in Full Markets (might be)
✅ INCLUDED in All Markets (good reward)
✅ INCLUDED in Volatility Markets (stable + good reward)

Interpretation:
- Good rewards (1.85% per day)
- Very stable (sum = 16.14)
- Good risk/reward ratio (0.11)
- ⭐ IDEAL for market making
```

---

## Comparison Table

| Aspect | Full Markets | All Markets | Volatility Markets |
|--------|-------------|-------------|-------------------|
| **Source** | `all_results` | `all_markets` | `volatility_df` |
| **Reward Filter** | ❌ None | ✅ >= 0.75 | ✅ >= 0.75 |
| **Volatility Filter** | ❌ None | ❌ None | ✅ < 20 |
| **Volatility Data** | ❌ No | ✅ Yes | ✅ Yes |
| **Market Count** | ~500-2000 | ~100-500 | ~20-100 |
| **Update Cost** | Low (no history) | High (fetch history) | High (fetch history) |
| **Sorting** | rewards_daily_rate | gm_reward_per_100 | gm_reward_per_100 |
| **Purpose** | Raw inventory | Discovery | Trading |
| **Risk Level** | Unknown | Mixed | Low |
| **Use Case** | Debugging/Export | Research/Scanning | Bot Configuration |

---

## Data Flow Diagram

```
START: Fetch all markets from Polymarket API
  ↓
get_all_markets() → all_df (~500-2000 markets)
  ↓
get_all_results() → Fetch order book for each market
  ↓
process_single_row() → Calculate rewards
  ↓
all_results (~500-2000 markets with reward data)
  ↓
get_markets() → Apply first filter
  ├─→ m_data (all_data) ────────────────────→ FULL MARKETS TAB
  │   ❌ No filters                              (raw data)
  │   ❌ No volatility
  │
  └─→ all_markets ──────────────────────────→ (intermediate)
      ✅ Filter: gm_reward >= 0.75
      ❌ No volatility yet
        ↓
      add_volatility_to_df() → Fetch price history
        ↓
      new_df (~100-500 markets) ────────────→ ALL MARKETS TAB
      ✅ Filter: gm_reward >= 0.75              (discovery)
      ✅ Has volatility data
        ↓
      Filter: volatility_sum < 20
        ↓
      volatility_df (~20-100 markets) ───────→ VOLATILITY MARKETS TAB
      ✅ Filter: gm_reward >= 0.75              (trading)
      ✅ Filter: volatility_sum < 20
      ✅ Has volatility data
```

---

## Key Insights

### Why Three Tabs?

**Full Markets**:
- **Speed**: No expensive volatility calculations
- **Completeness**: See everything scanned
- **Debugging**: Verify API data is correct

**All Markets**:
- **Balance**: Good rewards + full analysis
- **Discovery**: Find new opportunities
- **Comparison**: See high-reward volatile markets vs stable ones

**Volatility Markets**:
- **Safety**: Pre-filtered for stability
- **Convenience**: Ready-to-trade markets
- **Focus**: Don't get distracted by risky high-reward markets

### Processing Cost

```
Full Markets:
- Scan 1000 markets
- Fetch 1000 order books
- Calculate rewards for 1000 markets
- Time: ~20 minutes
- API calls: ~1000

All Markets:
- Start with ~200 markets (after reward filter)
- Fetch price history for 200 markets
- Calculate volatility for 200 markets
- Time: ~10 minutes additional
- API calls: ~200

Volatility Markets:
- Filter All Markets (no additional cost)
- Time: instant
- API calls: 0

Total: ~30 minutes per update cycle
```

### Why Not Calculate Volatility for Everything?

**Reasons**:
1. **Time**: Would take hours for 1000+ markets
2. **API limits**: Risk rate limiting
3. **Unnecessary**: Most markets have terrible rewards anyway
4. **Efficiency**: Filter first, then deep analysis

### When to Use Each Tab

**Use Full Markets when**:
- 🔍 Debugging data issues
- 📊 Exporting complete dataset
- 🧪 Testing new filtering logic
- 📈 Looking for markets with unusual properties

**Use All Markets when**:
- 🎯 Finding new markets to trade
- 💰 Comparing reward levels
- ⚖️ Assessing risk vs reward tradeoffs
- 📊 Analyzing market characteristics

**Use Volatility Markets when**:
- ✅ Adding markets to your bot
- 🤖 Configuring automated trading
- 🛡️ Focusing on low-risk opportunities
- 💼 Building conservative portfolio

---

## Example Scenarios

### Scenario 1: Market Appears Only in Full Markets

```
Market: "Will aliens land tomorrow?"
gm_reward_per_100: 0.45 ❌

Found in:
✅ Full Markets (no filter)
❌ All Markets (reward too low)
❌ Volatility Markets (reward too low)

Why: Reward doesn't meet minimum threshold (< 0.75)
Action: Ignore - not profitable enough
```

### Scenario 2: Market in Full + All, Not in Volatility

```
Market: "Breaking news - will event happen?"
gm_reward_per_100: 3.50 ✅
volatility_sum: 45.0 ❌

Found in:
✅ Full Markets (no filter)
✅ All Markets (great reward)
❌ Volatility Markets (too volatile)

Why: High reward but unstable price
Action: Consider for experienced traders only
```

### Scenario 3: Market in All Three Tabs

```
Market: "Will GDP grow by 2%?"
gm_reward_per_100: 1.25 ✅
volatility_sum: 15.2 ✅

Found in:
✅ Full Markets (no filter)
✅ All Markets (good reward)
✅ Volatility Markets (stable + good reward)

Why: Passes all criteria
Action: ⭐ ADD TO SELECTED MARKETS ⭐
```

### Scenario 4: Market Not in Any Tab

```
Market: "Local event in small town"
Reason: No maker rewards configured

Found in:
❌ Full Markets (no rewards = filtered out in API)
❌ All Markets (not in Full)
❌ Volatility Markets (not in Full)

Why: Polymarket doesn't offer rewards
Action: Cannot trade for rewards
```

---

## Update Frequency

All three tabs update together:

```python
# Every 5 minutes (line 323-325 in update_markets.py)
while True:
    try:
        fetch_and_process_data(ONLY_SELECTED_MARKETS)
        time.sleep(60 * 5)  # 5 minutes
```

**Update process**:
1. Fetch all markets from API
2. Calculate rewards for all
3. Update **Full Markets** ← Fast
4. Filter by reward threshold
5. Calculate volatility for filtered set
6. Update **All Markets** ← Slower
7. Filter by volatility threshold
8. Update **Volatility Markets** ← Instant

**Total time per cycle**: ~30-40 minutes
**Spreadsheet updates**: Every 5 minutes (if processing completes)

---

## Summary

### Quick Decision Guide

**"I want to see..."**
- **Everything scanned** → Full Markets
- **All profitable markets with analysis** → All Markets  
- **Safe markets ready to trade** → Volatility Markets

**"I want to find..."**
- **New market opportunities** → All Markets
- **Markets for my bot** → Volatility Markets
- **Raw data for analysis** → Full Markets

**"I care about..."**
- **Maximum information** → All Markets (best balance)
- **Safety first** → Volatility Markets
- **Complete inventory** → Full Markets

---

*Documented on: November 18, 2025*

