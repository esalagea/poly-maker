# Volatility Markets Spreadsheet - Calculation & Filtering

## Summary

The **"Volatility Markets"** spreadsheet contains markets that have:
1. ✅ **Geometric Mean reward ≥ 0.75** (per $100)
2. ✅ **Volatility Sum < 20** (sum of 24h, 7d, 14d annualized volatility)

These markets are considered **stable** and **profitable** for market making.

---

## Key Concepts

### What Are "Rewards"?

**Rewards** are incentives paid by Polymarket to liquidity providers (market makers) who place orders on their order books.

#### Why Does Polymarket Pay Rewards?

1. **Liquidity Attraction** - Incentivize traders to provide buy/sell orders
2. **Better Markets** - More liquidity = tighter spreads = better user experience
3. **Market Stability** - Consistent liquidity makes prices more stable
4. **Bootstrapping** - Help new/unpopular markets get initial liquidity

#### How Rewards Work

**Basic Model**:
- You place a limit order (bid or ask) on a market
- Your order sits in the order book providing liquidity
- Polymarket pays you daily rewards in USDC based on:
  - How close your order is to the midpoint (closer = better)
  - How much liquidity you provide (size of your order)
  - The total liquidity in the market (your share)
  - The daily reward budget for that market

**Example**:
```
Market: "Will it rain tomorrow?"
Current price: $0.50 (50% probability)
Your bid: $0.49 @ $100 size
Daily reward budget: $10 USDC

If you're the only liquidity provider and maintain your order all day:
You might earn: $2-5 in rewards per day

Return: 2-5% per day on your $100 capital (if order never fills)
Annualized: 730% - 1,825% APY (if sustained)
```

#### Reward Formula Components

**1. Distance Score (S)**
```python
s = abs(your_price - midpoint)  # How far from middle
S = ((max_spread - s) / max_spread) ** 2  # Squared proximity score
```
- Orders closer to midpoint get higher scores
- Squared formula heavily favors very close orders
- Orders beyond max_spread get score of 0

**2. Quality Score (Q)**
```python
Q = S * your_liquidity_size
```
- Combines proximity and size
- Bigger orders at good prices = higher quality

**3. Your Share of Rewards**
```python
your_reward = (your_Q / total_Q) * daily_budget / 2
```
- Your quality vs total quality in market
- Divided by 2 (rewards split between bid and ask sides)

**4. Per $100 Metric**
```python
reward_per_100 = your_reward / your_size * 100
```
- Normalized to $100 for easy comparison
- This is what's displayed in the spreadsheets

#### Reward Examples

**Example 1: Tight Spread Market**
```
Market: "Biden vs Trump - who wins?"
Midpoint: $0.50
Max spread: 2% ($0.01)
Daily reward budget: $50

Your bid: $0.495 (0.5% from midpoint)
Your size: $100
Other liquidity: $1,000 total

Calculation:
- s = |0.495 - 0.50| = 0.005
- S = ((0.01 - 0.005) / 0.01)^2 = 0.25
- Q = 0.25 * 100 = 25
- Total_Q = ~250 (estimate)
- Your reward = (25 / 250) * 50 / 2 = $2.50/day
- Reward per $100 = $2.50 / 100 * 100 = $2.50

Result: $2.50 per $100 per day (2.5% daily return)
```

**Example 2: Wide Spread Market**
```
Market: "Will aliens land in 2025?"
Midpoint: $0.05
Max spread: 10% ($0.05)
Daily reward budget: $20

Your bid: $0.045 (0.5% from midpoint)
Your size: $100
Other liquidity: $200 total

Calculation:
- s = |0.045 - 0.05| = 0.005
- S = ((0.05 - 0.005) / 0.05)^2 = 0.81
- Q = 0.81 * 100 = 81
- Total_Q = ~200
- Your reward = (81 / 200) * 20 / 2 = $4.05/day
- Reward per $100 = $4.05

Result: $4.05 per $100 per day (4% daily return)
```

**Example 3: Geometric Mean (gm_reward_per_100)**

This is the primary metric used for ranking markets:

```
Market: "Will it snow in NYC?"
Best bid reward: $1.20 per $100/day
Best ask reward: $1.80 per $100/day

Geometric mean = sqrt(1.20 * 1.80) = sqrt(2.16) = $1.47
Arithmetic mean = (1.20 + 1.80) / 2 = $1.50

Why use geometric mean?
- More conservative (penalizes imbalanced markets)
- Better represents "typical" return if trading both sides
- If one side has $0 reward, GM = $0 (AM would still show value)
```

#### Important Reward Constraints

**1. Minimum Position Size**
```
min_size = 20 (from rewards API)
```
- Must maintain at least $20 position to earn rewards
- Smaller positions = no rewards
- **Note**: This is DIFFERENT from minimum order size ($5 for Polymarket API)

**2. Maximum Spread**
```
max_spread = 3% (example)
```
- Orders beyond this distance don't earn rewards
- Forces liquidity providers to stay reasonably close to midpoint
- Varies by market

**3. Reward Accrual**
- Rewards calculated continuously (every second)
- Paid out periodically (daily/weekly by Polymarket)
- Must keep order in book to earn (filled orders stop earning)

---

### What Is "Annualized Volatility"?

**Annualized volatility** measures how much a market's price fluctuates over time, scaled to a yearly basis.

#### Why Annualize?

To compare volatility across different time periods fairly:
```
1-hour volatility: 2.5
24-hour volatility: 8.3
7-day volatility: 12.1

Which market is more volatile? Hard to tell!

Annualized (all on same scale):
1-hour annualized: 332
24-hour annualized: 8.3
7-day annualized: 12.1

Now it's clear: Short-term is much more volatile!
```

#### How It's Calculated

**Step 1: Fetch Price History**
```python
# Get 1-minute price data
GET https://clob.polymarket.com/prices-history?interval=1m&market={token_id}&fidelity=10

Response:
{
  "history": [
    {"t": 1700000000, "p": 0.45},
    {"t": 1700000060, "p": 0.46},
    {"t": 1700000120, "p": 0.45},
    ...
  ]
}
```

**Step 2: Calculate Log Returns**
```python
# Log return = ln(price[i] / price[i-1])
price[0] = 0.45
price[1] = 0.46
log_return[1] = ln(0.46 / 0.45) = ln(1.0222) = 0.0220

Why log returns?
- Additive (can sum them)
- Symmetric (up 10% then down 10% = log sum ≈ 0)
- Better statistical properties
```

**Step 3: Calculate Standard Deviation**
```python
# For a specific time window (e.g., 24 hours)
volatility = std(log_returns)

Example with 24 hours of 1-minute data (1,440 points):
log_returns = [0.0220, -0.0110, 0.0050, ...]
volatility = 0.0150  # Standard deviation
```

**Step 4: Annualize**
```python
# Scale to yearly basis
annualized = volatility * sqrt(periods_per_year)

For 1-minute data:
periods_per_year = 60 min/hr * 24 hr/day * 252 trading_days = 362,880
annualized = 0.0150 * sqrt(362,880) = 0.0150 * 602.4 = 9.04

Result: Annualized volatility = 9.04
```

#### Volatility Examples

**Example 1: Stable Market - "Will sun rise tomorrow?"**

```
Price stays around $0.99 all day

Time    Price   Log Return
10:00   0.990   -
10:01   0.991   0.0010
10:02   0.990  -0.0010
10:03   0.991   0.0010
...

24-hour volatility calculation:
- Mean log return ≈ 0
- Std dev = 0.0008
- Annualized = 0.0008 * sqrt(362,880) = 0.48

Result: Very stable (volatility < 1)
```

**Example 2: Moderate Market - "Who wins election?"**

```
Price fluctuates based on polls

Time    Price   Log Return
10:00   0.450   -
10:01   0.452   0.0044
10:02   0.448  -0.0089
10:03   0.451   0.0067
...

24-hour volatility:
- Std dev = 0.0120
- Annualized = 0.0120 * 602.4 = 7.23

Result: Moderate volatility (5-10 range)
```

**Example 3: Volatile Market - "Breaking news market"**

```
Price swings wildly on news

Time    Price   Log Return
10:00   0.300   -
10:01   0.350   0.1542
10:02   0.320  -0.0896
10:03   0.380   0.1716
...

1-hour volatility:
- Std dev = 0.0850
- Annualized = 0.0850 * 602.4 = 51.2

Result: High volatility (> 20)
```

#### Interpreting Volatility Values

**Prediction Markets Context**:
```
< 5     Very stable (e.g., "sun will rise")
5-10    Stable (e.g., "established candidate lead")
10-15   Moderate (e.g., "competitive race")
15-20   Moderately high (e.g., "uncertain outcome")
20-30   High (e.g., "breaking news market")
> 30    Very high (e.g., "rapidly developing situation")
```

**Traditional Finance Comparison**:
```
S&P 500 typical volatility: 15-20
Individual stocks: 20-40
Crypto assets: 60-100+

Prediction markets: 5-30 (similar to stocks)
```

#### Volatility Sum Explained

**Why Sum Three Time Windows?**

```python
volatility_sum = 24_hour + 7_day + 14_day
```

**Purpose**: Capture different types of volatility

1. **24-hour volatility** - Short-term noise/reactions
   - Captures intraday price swings
   - Sensitive to breaking news
   - Example: Market reacts to a poll

2. **7-day volatility** - Medium-term trends
   - Captures weekly patterns
   - More stable than 24h
   - Example: Gradual sentiment shifts

3. **14-day volatility** - Long-term stability
   - Captures fundamental volatility
   - Smooths out temporary spikes
   - Example: Underlying market uncertainty

**Example Comparison**:

**Market A: Temporarily Volatile**
```
24h: 15.0  (news event today)
7d:   6.5  (usually calm)
14d:  5.0  (stable long-term)
Sum: 26.5  → Would be EXCLUDED (> 20)

Analysis: Recent spike, but fundamentally stable
Could be worth monitoring for when it settles
```

**Market B: Consistently Stable**
```
24h:  4.5
7d:   5.2
14d:  4.8
Sum: 14.5  → INCLUDED (< 20)

Analysis: Stable across all timeframes
Ideal for market making
```

**Market C: Consistently Volatile**
```
24h: 12.0
7d:  15.0
14d: 18.0
Sum: 45.0  → EXCLUDED (> 20)

Analysis: Fundamentally uncertain/volatile
Too risky for safe market making
```

#### Real-World Volatility Example

**Market**: "Will Biden win 2024 election?"

```
Date        Event                   Price   24h_vol  7d_vol  14d_vol  Sum
Jan 1       Normal trading         0.52     5.2     6.1     5.8      17.1 ✅
Jan 15      Debate performance     0.48     12.3    7.2     6.5      26.0 ❌
Jan 22      Market stabilizes      0.47     6.8     8.1     7.2      22.1 ❌
Feb 1       Back to normal         0.46     5.5     6.9     6.8      19.2 ✅

Analysis:
- Jan 1: Market is stable, good for making
- Jan 15: Temporary spike excludes from Volatility Markets
- Jan 22: Still excluded (7d captures recent volatility)
- Feb 1: Back to acceptable levels
```

---

## How Volatility Markets is Calculated

### Script: `update_markets.py`

**Function**: `fetch_and_process_data(ONLY_SELECTED_MARKETS)`

**Location**: Line 256

### Step-by-Step Process

#### 1. **Fetch All Markets from Polymarket API**

```python
# Line 275
all_df = get_all_markets(client)
```

**What this does**:
- Calls Polymarket's sampling markets API
- Retrieves all active prediction markets
- Returns a DataFrame with basic market information

**Data included**:
- Question, tokens, condition_id
- Rewards configuration (min_size, max_spread, rates)
- Market metadata (end_date_iso, market_slug, neg_risk)

#### 2. **Process Each Market for Rewards Data**

```python
# Line 277-286
if ONLY_SELECTED_MARKETS and len(sel_df) > 0:
    # Filter to only selected markets
    selected_questions = sel_df['question'].tolist()
    filtered_df = all_df[all_df['question'].isin(selected_questions)]
    all_results = get_all_results(filtered_df, client)
else:
    # Process all markets
    all_results = get_all_results(all_df, client)
```

**What this does** (`get_all_results` in `find_markets.py`):
- For each market, fetches order book snapshot
- Calculates best bid/ask
- Calculates expected rewards using Polymarket's formula:
  - `gm_reward_per_100` - Geometric mean of bid & ask rewards per $100
  - `sm_reward_per_100` - Arithmetic mean of bid & ask rewards per $100
  - `bid_reward_per_100`, `ask_reward_per_100` - Individual side rewards

**Formula for rewards** (simplified):
```python
# Proximity to midpoint matters
s = abs(price - midpoint)
S = ((max_spread - s) / max_spread) ** 2

# Quality factor based on existing liquidity
Q = S * size

# Reward per $100 for that price level
reward = (Q / total_Q) * daily_rate / 2 / size * (100 / price)
```

#### 3. **Filter Markets by Reward Threshold**

```python
# Line 288
m_data, all_markets = get_markets(all_results, sel_df, maker_reward=0.75)
```

**What this does** (`get_markets` in `find_markets.py`, line 334):
```python
making_markets = s_df[~new_df['question'].isin(sel_df['question'])]
making_markets = making_markets.sort_values('gm_reward_per_100', ascending=False)
making_markets = making_markets[making_markets['gm_reward_per_100'] >= maker_reward]
```

**Filtering logic**:
- ✅ Include markets with `gm_reward_per_100 >= 0.75`
- ✅ Exclude markets already in "Selected Markets" (unless ONLY_SELECTED_MARKETS=True)
- ✅ Sort by `gm_reward_per_100` descending

**Result**: Markets with good reward potential

#### 4. **Add Volatility Data**

```python
# Line 291
new_df = add_volatility_to_df(all_markets)
```

**What this does** (`add_volatility_to_df` in `find_markets.py`, line 283):

For each market:
1. Fetches 1-minute price history from Polymarket API
   ```python
   res = requests.get(f'https://clob.polymarket.com/prices-history?interval=1m&market={token1}&fidelity=10')
   ```

2. Calculates log returns
   ```python
   price_df['log_return'] = np.log(price_df['p'] / price_df['p'].shift(1))
   ```

3. Calculates **annualized volatility** for multiple time windows:
   ```python
   def calculate_annualized_volatility(df, hours):
       # Filter to time window
       end_time = df['t'].max()
       start_time = end_time - pd.Timedelta(hours=hours)
       window_df = df[df['t'] >= start_time]
       
       # Calculate standard deviation of log returns
       volatility = window_df['log_return'].std()
       
       # Annualize: std * sqrt(minutes_per_year)
       # 60 minutes/hour * 24 hours/day * 252 trading days/year
       annualized_volatility = volatility * np.sqrt(60 * 24 * 252)
       
       return round(annualized_volatility, 2)
   ```

**Time windows calculated**:
- `1_hour` - 1-hour annualized volatility
- `3_hour` - 3-hour annualized volatility
- `6_hour` - 6-hour annualized volatility
- `12_hour` - 12-hour annualized volatility
- `24_hour` - 24-hour annualized volatility
- `7_day` - 7-day annualized volatility
- `14_day` - 14-day annualized volatility
- `30_day` - 30-day annualized volatility

**Additional data**:
- `volatility_price` - Current price from price history

#### 5. **Calculate Composite Volatility Metrics**

```python
# Line 292
new_df['volatility_sum'] = new_df['24_hour'] + new_df['7_day'] + new_df['14_day']

# Line 295
new_df['volatility/reward'] = ((new_df['gm_reward_per_100'] / new_df['volatility_sum']).round(2)).astype(str)
```

**Metrics**:

1. **`volatility_sum`**
   - Sum of 24-hour + 7-day + 14-day annualized volatility
   - Represents **total risk** across short, medium, and long-term
   - Lower is better (more stable market)

2. **`volatility/reward`**
   - Ratio: `gm_reward_per_100 / volatility_sum`
   - Represents **reward per unit of risk**
   - Higher is better (more reward for given risk level)
   - **Note**: This is actually **reward/volatility**, not volatility/reward!

#### 6. **Filter Markets for Volatility Markets Tab**

```python
# Line 303-305
volatility_df = new_df.copy()
volatility_df = volatility_df[new_df['volatility_sum'] < 20]
volatility_df = volatility_df.sort_values('gm_reward_per_100', ascending=False)
```

**CRITICAL FILTER**: **`volatility_sum < 20`**

This is the key condition for inclusion in the Volatility Markets spreadsheet!

**What this means**:
- Market must have combined volatility (24h + 7d + 14d) less than 20
- Represents **stable** markets with relatively low price movement
- These are "safe" markets for market making

**Sorting**:
- Sort by `gm_reward_per_100` descending
- Shows highest-reward stable markets first

#### 7. **Update Google Sheets**

```python
# Line 312-315
if len(new_df) > 50 or ONLY_SELECTED_MARKETS:
    update_sheet(new_df, wk_all)          # All Markets tab
    update_sheet(volatility_df, wk_vol)   # Volatility Markets tab
    update_sheet(m_data, wk_full)         # Full Markets tab
```

**Updates three tabs**:
1. **All Markets** - All markets with `gm_reward_per_100 >= 0.75`
2. **Volatility Markets** - Markets with `volatility_sum < 20` (STABLE)
3. **Full Markets** - Raw data from API

---

## Conditions for Inclusion in Volatility Markets

### Summary Table

| Condition | Threshold | Description |
|-----------|-----------|-------------|
| **Geometric Mean Reward** | ≥ 0.75 | Minimum expected reward per $100 |
| **Volatility Sum** | < 20 | Maximum combined volatility (24h + 7d + 14d) |
| **Market Active** | Yes | Market must be in Polymarket's sampling API |
| **Has Rewards** | Yes | Market must have maker rewards enabled |
| **Order Book** | Must exist | Market must have bids and asks |

### Detailed Conditions

#### 1. **Reward Threshold** ✅

```python
# In get_markets() - find_markets.py line 334
making_markets = making_markets[making_markets['gm_reward_per_100'] >= 0.75]
```

**Requirement**: `gm_reward_per_100 >= 0.75`

**What this means**:
- Expected to earn at least $0.75 per $100 invested per day
- Based on geometric mean of best bid and ask rewards
- Calculated using Polymarket's reward formula

**Why this threshold**:
- Filters out low-reward markets
- Ensures profitability after fees and slippage
- Configurable via `maker_reward` parameter

#### 2. **Volatility Threshold** ✅

```python
# In fetch_and_process_data() - update_markets.py line 303
volatility_df = volatility_df[new_df['volatility_sum'] < 20]
```

**Requirement**: `volatility_sum < 20`

**Where**: `volatility_sum = 24_hour + 7_day + 14_day`

**What this means**:
- Combined annualized volatility across 3 time periods must be < 20
- Example acceptable: 5 + 8 + 6 = 19 ✅
- Example rejected: 10 + 15 + 12 = 37 ❌

**Why this threshold**:
- Filters out highly volatile markets
- Reduces risk of adverse price movements
- Makes market making safer and more predictable

**Interpretation**:
- `volatility_sum = 5-10`: Very stable (rare)
- `volatility_sum = 10-15`: Stable (ideal)
- `volatility_sum = 15-20`: Acceptable
- `volatility_sum > 20`: Too risky (excluded)

#### 3. **Market Must Be Active** ✅

**Requirement**: Market appears in `get_all_markets()` results

**What this means**:
- Market is in Polymarket's sampling markets API
- Market is open for trading
- Market has not been resolved/closed

#### 4. **Must Have Maker Rewards** ✅

**Requirement**: Market has `rewards.rates` with non-zero rate

**What this means**:
- Polymarket is offering liquidity rewards for this market
- Rewards are in USDC (checks for specific token address)
- Has `min_size` and `max_spread` configuration

#### 5. **Must Have Order Book** ✅

**Requirement**: Can fetch order book with at least one bid and ask

**What this means**:
- Market has active liquidity
- Can calculate `best_bid` and `best_ask`
- Can calculate reward potential

---

## Volatility/Reward Field Explained

### Current Implementation (INCORRECT NAMING)

```python
# Line 295
new_df['volatility/reward'] = ((new_df['gm_reward_per_100'] / new_df['volatility_sum']).round(2)).astype(str)
```

**Formula**: `reward / volatility`

**What it represents**:
- **Reward per unit of risk**
- Higher = Better (more reward for same volatility)
- Example: 1.5 / 10 = 0.15 → For every 1 unit of volatility, you get 0.15 reward

### Correct Interpretation

This field should be named **`reward/volatility`**, not `volatility/reward`!

**Why higher is better**:
- You WANT high reward relative to volatility
- Example comparisons:
  - Market A: reward=2, volatility=10 → ratio=0.20 ✅ Better
  - Market B: reward=2, volatility=20 → ratio=0.10 ❌ Worse
  - Market B has same reward but double the risk

**Used in Quality Scoring**:
```python
# In analyze_market_quality() - analysis_utils.py line 127
if volatility_reward_ratio >= 2:    # HIGH reward/volatility (best)
    score += 10
elif volatility_reward_ratio >= 0.1:  # MEDIUM
    score += 8
elif volatility_reward_ratio >= 0.2:  # LOW (note: logic error here!)
    score += 5
else:
    issues.append(f"High volatility vs reward: {volatility_reward_ratio:.3f}")
```

**Note**: There's a logic error in the quality scoring (line 127-134) where the thresholds are in wrong order. Should be:
- `>= 0.2`: 10 points (highest reward/volatility)
- `>= 0.1`: 8 points
- `>= 0.05`: 5 points
- `< 0.05`: Too risky

---

## How Volatility Markets Differs from All Markets

| Aspect | All Markets | Volatility Markets |
|--------|-------------|-------------------|
| **Reward Filter** | `gm_reward_per_100 >= 0.75` | `gm_reward_per_100 >= 0.75` |
| **Volatility Filter** | None | **`volatility_sum < 20`** |
| **Purpose** | All profitable markets | **Stable** profitable markets |
| **Risk Level** | Any | **Low to Medium** |
| **Market Count** | ~100-500 | ~20-100 (subset) |
| **Sorting** | By `gm_reward_per_100` | By `gm_reward_per_100` |

**Key Difference**: Volatility Markets is a **filtered subset** of All Markets, showing only the stable ones.

---

## Update Frequency

### Script Execution

```python
# Line 323-329
if __name__ == "__main__":
    while True:
        try:
            fetch_and_process_data(ONLY_SELECTED_MARKETS)
            time.sleep(60 * 5)  # Sleep for 5 minutes
        except Exception as e:
            traceback.print_exc()
```

**Update Cycle**:
- Runs every **5 minutes**
- Fetches fresh data from Polymarket API
- Recalculates volatility from recent price history
- Updates all three spreadsheet tabs

**Data Freshness**:
- Volatility: Based on latest available price history
- Rewards: Current reward rates from API
- Order book: Snapshot at time of calculation

---

## Columns in Volatility Markets Spreadsheet

Based on line 297-300:

```python
columns = [
    # Market Identification
    'question',           # Market question/title
    'answer1',           # Yes token outcome
    'answer2',           # No token outcome
    
    # Trading Metrics
    'spread',            # Current bid-ask spread (snapshot)
    'best_bid',          # Best bid price (snapshot)
    'best_ask',          # Best ask price (snapshot)
    'volatility_price',  # Current price from price history
    
    # Reward Metrics
    'rewards_daily_rate',     # Total daily reward rate
    'gm_reward_per_100',      # Geometric mean reward per $100 (PRIMARY SORT)
    'sm_reward_per_100',      # Arithmetic mean reward per $100
    'bid_reward_per_100',     # Expected bid-side reward per $100
    'ask_reward_per_100',     # Expected ask-side reward per $100
    
    # Volatility Metrics
    'volatility_sum',         # Sum of 24h + 7d + 14d volatility (FILTER KEY)
    'volatility/reward',      # Reward/volatility ratio (should be renamed!)
    '1_hour',                 # 1-hour annualized volatility
    '3_hour',                 # 3-hour annualized volatility
    '6_hour',                 # 6-hour annualized volatility
    '12_hour',                # 12-hour annualized volatility
    '24_hour',                # 24-hour annualized volatility
    '7_day',                  # 7-day annualized volatility
    '30_day',                 # 30-day annualized volatility
    
    # Configuration
    'min_size',          # Minimum position size for rewards
    'max_spread',        # Maximum allowed spread percentage
    'tick_size',         # Minimum price increment
    'neg_risk',          # Negative risk flag (TRUE/FALSE)
    
    # Identifiers
    'market_slug',       # URL-friendly market identifier
    'token1',            # Yes token ID (for API calls)
    'token2',            # No token ID
    'condition_id'       # Unique condition identifier
]
```

---

## Use Cases

### For Market Makers

**Goal**: Find stable markets with good rewards

**How to use Volatility Markets tab**:
1. ✅ Markets already filtered for stability (`volatility_sum < 20`)
2. ✅ Sorted by highest reward (`gm_reward_per_100`)
3. ✅ Can focus on top 10-20 markets
4. ✅ Lower risk of adverse price movements

### For Market Discoverers

**Goal**: Find any profitable market

**How to use All Markets tab**:
1. Includes high-volatility markets (higher risk, potentially higher reward)
2. Broader selection of markets
3. May include emerging/trending markets with temporary high volatility

---

## Example Market Flow

### Example: "Will Bitcoin hit $100k by end of 2025?"

#### 1. Initial API Data
```
question: "Will Bitcoin hit $100k by end of 2025?"
best_bid: 0.45
best_ask: 0.46
rewards_daily_rate: 100 USDC/day
```

#### 2. Reward Calculation
```
Calculate rewards at various price points...
bid_reward_per_100: $1.20
ask_reward_per_100: $1.30
gm_reward_per_100: $1.25  ✅ Passes (>= 0.75)
```

#### 3. Fetch Price History
```
Get 1-minute prices for last 30 days...
Calculate log returns...
```

#### 4. Volatility Calculation
```
24_hour: 8.5
7_day: 6.2
14_day: 5.8
volatility_sum: 20.5  ❌ FAILS (>= 20)
```

#### 5. Classification
```
✅ Included in "All Markets" (good reward)
❌ EXCLUDED from "Volatility Markets" (too volatile)
```

### Example 2: "Will it rain in NYC tomorrow?"

#### Reward & Volatility
```
gm_reward_per_100: $0.85  ✅ Passes reward threshold
24_hour: 3.2
7_day: 4.5
14_day: 3.8
volatility_sum: 11.5  ✅ PASSES (<20)
```

#### Classification
```
✅ Included in "All Markets"
✅ INCLUDED in "Volatility Markets" (stable + good reward)
```

---

## Summary

### Quick Reference

**Volatility Markets includes markets that are**:
1. ✅ Profitable (`gm_reward_per_100 >= 0.75`)
2. ✅ Stable (`volatility_sum < 20`)
3. ✅ Active (in Polymarket API)
4. ✅ Have maker rewards
5. ✅ Have functioning order books

**Volatility Sum Calculation**:
```python
volatility_sum = 24_hour + 7_day + 14_day
```
Where each component is annualized volatility of log returns.

**Volatility/Reward Field**:
- Actually calculates: `reward / volatility`
- Should be renamed to: `reward/volatility`
- Higher values = better (more reward per unit of risk)

**Update Frequency**:
- Every 5 minutes
- Fetches fresh data from Polymarket API
- Recalculates all metrics

---

## Visual Summary & Quick Reference

### Decision Tree: Will a Market Be Included?

```
START: Market exists in Polymarket API
  |
  ├─> Has maker rewards? 
  |     ├─> NO → ❌ EXCLUDED (no rewards)
  |     └─> YES → Continue
  |
  ├─> Fetch order book
  |     ├─> No bids/asks? → ❌ EXCLUDED (no liquidity)
  |     └─> Has bids/asks → Continue
  |
  ├─> Calculate gm_reward_per_100
  |     ├─> < 0.75? → ❌ EXCLUDED (rewards too low)
  |     └─> >= 0.75? → ✅ INCLUDED in "All Markets"
  |
  ├─> Fetch price history
  |     ├─> No history? → ❌ Can't calculate volatility
  |     └─> Has history → Continue
  |
  ├─> Calculate volatility_sum
  |     ├─> < 20? → ✅ INCLUDED in "Volatility Markets"
  |     └─> >= 20? → ❌ EXCLUDED from "Volatility Markets"
  |                   (but still in "All Markets")
```

### Threshold Reference Table

| Metric | Threshold | Direction | Purpose |
|--------|-----------|-----------|---------|
| **gm_reward_per_100** | ≥ 0.75 | Higher is better | Minimum profitability |
| **volatility_sum** | < 20 | Lower is better | Maximum risk tolerance |
| **24_hour volatility** | - | Lower is better | Short-term stability |
| **7_day volatility** | - | Lower is better | Medium-term stability |
| **14_day volatility** | - | Lower is better | Long-term stability |
| **reward/volatility** | Higher is better | Higher is better | Risk-adjusted return |

### Market Classification Examples

| gm_reward | volatility_sum | All Markets | Volatility Markets | Why? |
|-----------|----------------|-------------|-------------------|------|
| 1.50 | 15.0 | ✅ YES | ✅ YES | Perfect: Good reward + stable |
| 0.50 | 10.0 | ❌ NO | ❌ NO | Too low reward |
| 2.00 | 25.0 | ✅ YES | ❌ NO | Good reward but too volatile |
| 5.00 | 50.0 | ✅ YES | ❌ NO | Great reward, way too risky |
| 0.75 | 19.9 | ✅ YES | ✅ YES | Minimum threshold (barely) |
| 0.74 | 15.0 | ❌ NO | ❌ NO | Just below reward threshold |
| 1.00 | 20.0 | ✅ YES | ❌ NO | Just above volatility threshold |
| 1.00 | 19.9 | ✅ YES | ✅ YES | Just below volatility threshold |

### Volatility Interpretation Guide

#### By volatility_sum Value

| volatility_sum | Classification | Market Making Difficulty | Example Markets |
|----------------|----------------|-------------------------|-----------------|
| 0-10 | Very Stable | Easy | "Will sun rise?", "Established facts" |
| 10-15 | Stable | Moderate | "Election with clear favorite" |
| 15-20 | Acceptable | Moderate-Hard | "Competitive election", "Economic indicator" |
| 20-30 | Volatile | Hard | "Breaking news market", "Uncertain event" |
| 30-50 | Very Volatile | Very Hard | "Crisis event", "Rapidly developing" |
| 50+ | Extremely Volatile | Nearly Impossible | "Rumors", "Flash events" |

#### By Individual Component

**24-hour volatility** (short-term):
```
< 5:  Calm day (normal)
5-10: Active trading (normal)
10-15: Volatile day (news/events)
15+:  Extreme (breaking news)
```

**7-day volatility** (medium-term):
```
< 5:  Very stable week
5-10: Stable market
10-15: Active market
15+:  Uncertain/developing
```

**14-day volatility** (long-term):
```
< 5:  Fundamentally stable
5-10: Normal market
10-15: Some uncertainty
15+:  High uncertainty
```

### Reward Interpretation Guide

| gm_reward_per_100 | Daily Return | Monthly Return | Annual Return* | Quality |
|-------------------|--------------|----------------|----------------|---------|
| 0.50 | 0.5% | ~15% | ~180% | Below threshold |
| 0.75 | 0.75% | ~22% | ~270% | Minimum acceptable |
| 1.00 | 1.0% | ~30% | ~365% | Good |
| 1.50 | 1.5% | ~45% | ~550% | Very good |
| 2.00 | 2.0% | ~60% | ~730% | Excellent |
| 3.00 | 3.0% | ~90% | ~1,095% | Outstanding |
| 5.00+ | 5.0%+ | ~150%+ | ~1,825%+ | Exceptional (usually volatile) |

*Assumes no fills and constant rewards (unrealistic, for comparison only)

### Risk-Reward Matrix

```
                    Low Reward        Medium Reward       High Reward
                    (< 1.0)          (1.0-2.0)           (> 2.0)
                    
Low Volatility      NOT WORTH IT     ⭐ IDEAL ⭐         🎯 BEST 🎯
(< 15)              (no profit)      (safe + profit)     (safe + high profit)
                    
Medium Volatility   NOT WORTH IT     ✅ GOOD             ✅ GOOD
(15-20)             (risky, no profit) (acceptable risk)  (risk justified)
                    
High Volatility     ❌ AVOID         ⚠️ CAUTION         ⚠️ RISKY
(> 20)              (bad on all counts) (risk > reward)   (gambling)
```

### Practical Action Guide

**If volatility_sum < 15 and gm_reward ≥ 1.0**:
```
✅ EXCELLENT OPPORTUNITY
- Add to Selected Markets immediately
- Configure with standard trade_size
- Monitor daily
- Expect stable, profitable operation
```

**If volatility_sum = 15-20 and gm_reward ≥ 1.5**:
```
✅ GOOD OPPORTUNITY
- Review price history manually
- Add to Selected Markets with caution
- Use smaller trade_size initially
- Monitor more frequently
- Watch for volatility spikes
```

**If volatility_sum = 15-20 and gm_reward = 0.75-1.0**:
```
⚠️ MARGINAL
- Only add if you need more markets
- Rewards barely justify risk
- Watch closely for better opportunities
```

**If volatility_sum > 20 and gm_reward < 2.0**:
```
❌ AVOID
- Risk too high for reward level
- Focus on stable markets instead
```

**If volatility_sum > 20 and gm_reward > 3.0**:
```
⚠️ HIGH RISK / HIGH REWARD
- Only for experienced traders
- High reward suggests others see high risk too
- Expect frequent adverse fills
- May be profitable for skilled traders
- Not recommended for automated bot
```

### Common Patterns

**Pattern 1: News-Driven Spike**
```
Timeline:
Day 0: volatility_sum = 15 ✅ (included)
Day 1: Big news → 24h_vol = 30 → sum = 45 ❌ (excluded)
Day 3: Settles → 24h_vol = 10 → sum = 35 ❌ (still excluded, 7d captures spike)
Day 8: 7d window clears → sum = 18 ✅ (included again)

Lesson: News spikes exclude markets for ~1 week
```

**Pattern 2: Structural Volatility**
```
Timeline:
Day 0: volatility_sum = 28 ❌ (excluded)
Day 7: sum = 30 ❌ (excluded)
Day 14: sum = 25 ❌ (excluded)
Day 30: sum = 27 ❌ (excluded)

Lesson: Some markets are fundamentally volatile
Don't wait for them to become stable
```

**Pattern 3: Declining Rewards**
```
Week 1: gm_reward = 2.0 ✅ volatility_sum = 15 ✅
Week 2: gm_reward = 1.5 ✅ volatility_sum = 15 ✅
Week 3: gm_reward = 0.9 ✅ volatility_sum = 15 ✅
Week 4: gm_reward = 0.6 ❌ volatility_sum = 15 ✅

Lesson: Polymarket reduces rewards as liquidity improves
Markets can fall below threshold over time
Monitor reward levels regularly
```

---

## Formulas Summary

### Reward Calculations
```python
# Distance from midpoint
s = abs(your_price - midpoint)

# Proximity score (quadratic)
S = ((max_spread - s) / max_spread) ** 2

# Quality score
Q = S * your_liquidity_size

# Your share of daily rewards
your_reward = (your_Q / total_Q_in_market) * daily_reward_budget / 2

# Normalized per $100
reward_per_100 = (your_reward / your_size) * 100

# Geometric mean (used for ranking)
gm_reward_per_100 = sqrt(bid_reward_per_100 * ask_reward_per_100)

# Arithmetic mean (simpler average)
sm_reward_per_100 = (bid_reward_per_100 + ask_reward_per_100) / 2
```

### Volatility Calculations
```python
# Log returns (for each 1-minute interval)
log_return[i] = ln(price[i] / price[i-1])

# Standard deviation over time window
volatility = std_dev(log_returns_in_window)

# Annualize to yearly scale
annualized_volatility = volatility * sqrt(minutes_per_year)
# where minutes_per_year = 60 * 24 * 252 = 362,880

# Composite volatility metric
volatility_sum = 24_hour_vol + 7_day_vol + 14_day_vol

# Risk-adjusted return
reward_volatility_ratio = gm_reward_per_100 / volatility_sum
```

### Filter Conditions
```python
# For All Markets tab
if gm_reward_per_100 >= 0.75:
    include_in_all_markets()

# For Volatility Markets tab
if gm_reward_per_100 >= 0.75 and volatility_sum < 20:
    include_in_volatility_markets()
```

---

## Key Takeaways

### What Volatility Markets Shows You

1. **Pre-filtered for safety** - Only stable markets (volatility_sum < 20)
2. **Pre-filtered for profitability** - Only good rewards (≥ $0.75/$100/day)
3. **Sorted by reward** - Best opportunities at the top
4. **Ready to trade** - Can add directly to Selected Markets
5. **Lower risk** - Reduced chance of adverse fills

### What to Watch Out For

1. **Rewards can decline** - As liquidity increases, your share decreases
2. **Volatility can spike** - News events can suddenly exclude markets
3. **Competition** - Other bots compete for same rewards
4. **Fill risk** - Orders can still fill (just less likely in stable markets)
5. **Market resolution** - Markets close when events occur

### Best Practices

1. **Start with top markets** - Highest reward/volatility ratios
2. **Diversify** - Don't put all capital in one market
3. **Monitor daily** - Check for volatility spikes or reward changes
4. **Adjust quickly** - Remove markets that become volatile
5. **Use quality scores** - Supplement with real-time quality analysis

### Advanced Insights

1. **reward/volatility > 0.2** is excellent (high reward per risk)
2. **volatility_sum = 15-18** is sweet spot (stable but not trivial)
3. **Markets near 0.50 price** typically have best liquidity
4. **Extreme prices (< 0.10 or > 0.90)** often more volatile
5. **Long-dated markets** tend to be more stable than short-dated

---

*Documented on: November 18, 2025*

