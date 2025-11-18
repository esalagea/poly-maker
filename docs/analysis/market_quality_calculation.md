# Market Quality Calculation - Data Source Analysis

## Summary

Market Quality is calculated using **real-time order book data from WebSocket subscriptions**, NOT from the static data returned by `get_all_results()`. The quality calculation requires live, detailed order book information that is only available during active trading.

---

## How Market Quality is Calculated

### Function: `analyze_market_quality()`
**Location**: `poly_data/analysis_utils.py`

### Scoring System (0-100 points)

The quality score is calculated based on 7 criteria:

1. **Spread (20 points)** - How tight is the bid-ask spread
2. **Liquidity Balance (20 points)** - How balanced are bids vs asks
3. **Total Liquidity (15 points)** - Overall liquidity available
4. **Market Depth (15 points)** - Number of price levels with orders
5. **Top of Book Liquidity (10 points)** - Liquidity at best bid/ask vs trade size
6. **Price Continuity (10 points)** - Size of gaps between price levels
7. **Reward/Volatility Ratio (10 points)** - Reward potential vs risk

---

## Data Sources for Quality Calculation

### 1. Real-Time Order Book Data (from WebSocket)

**Source**: `global_state.all_data[market]`

This data structure contains:
```python
global_state.all_data[market] = {
    'asset_id': '0x...',  # Token ID for Yes token
    'bids': SortedDict({price: size, ...}),  # All bid prices and sizes
    'asks': SortedDict({price: size, ...})   # All ask prices and sizes
}
```

**How it's populated**:
1. Trading bot subscribes to market WebSocket (`websocket_handlers.py`, line 37)
2. WebSocket sends order book snapshots and updates
3. `process_data()` updates `global_state.all_data` (`data_processing.py`, line 15)
4. Order book is kept up-to-date with every price change event

**What data is used from the order book**:
- ✅ **All bid prices and sizes** - For calculating total liquidity, depth, gaps
- ✅ **All ask prices and sizes** - For calculating total liquidity, depth, gaps
- ✅ **Best bid/ask prices** - For spread calculation
- ✅ **Best bid/ask sizes** - For top-of-book liquidity
- ✅ **Near-bid/ask liquidity** - Orders within 2-3 ticks of best price
- ✅ **Price level gaps** - Continuity between consecutive price levels

**Specific metrics calculated**:
```python
# From analyze_market_quality()

# Spread metrics
spread = best_ask_price - best_bid_price
mid_price = (best_bid_price + best_ask_price) / 2
spread_pct = (spread / mid_price) * 100

# Liquidity metrics
total_bid_liquidity = sum(bids.values())  # Sum all bid sizes
total_ask_liquidity = sum(asks.values())  # Sum all ask sizes
balance_ratio = min(bids, asks) / max(bids, asks)

# Depth metrics
bid_levels = len([price for price, size in bids if size > 0])
ask_levels = len([price for price, size in asks if size > 0])

# Top-of-book
best_bid_size = bids[best_bid_price]
best_ask_size = asks[best_ask_price]
top_book_liquidity = best_bid_size + best_ask_size

# Near-book liquidity (within 2-3 ticks)
near_bid_liquidity = sum([size for price, size in bids 
                          if price >= best_bid_price - (2 * tick_size)])
near_ask_liquidity = sum([size for price, size in asks 
                          if price <= best_ask_price + (2 * tick_size)])

# Price continuity (gaps between levels)
bid_gaps = [bids[i-1].price - bids[i].price for i in range(1, 5)]
ask_gaps = [asks[i].price - asks[i-1].price for i in range(1, 5)]
avg_bid_gap = sum(bid_gaps) / len(bid_gaps)
avg_ask_gap = sum(ask_gaps) / len(ask_gaps)
```

### 2. Market Configuration Data (from Selected Markets spreadsheet)

**Source**: Row parameter passed to `analyze_market_quality()`

This data includes:
- ✅ `tick_size` - Minimum price increment
- ✅ `spread` - Expected spread from rewards API
- ✅ `trade_size` - Configured trade size for this market
- ✅ `min_size` - Minimum position size to earn rewards
- ✅ `volatility_*` - Volatility metrics (1h, 24h, 7d)
- ✅ `volatility/reward` - Reward/volatility ratio
- ✅ `rewards_daily_rate` - Daily reward rate
- ✅ `gm_reward_per_100` - Geometric mean reward per $100
- ✅ `question`, `market_slug` - Market identifiers

### 3. Analysis Parameters

**Source**: `params` dict passed to function

Contains:
- ✅ `min_total_liquidity` - Minimum acceptable liquidity threshold

---

## Can Quality be Calculated from `get_all_results()` Data?

### Answer: **NO - Missing Critical Real-Time Data**

### What `get_all_results()` Provides

The `process_single_row()` function in `find_markets.py` returns:

```python
{
    'question': str,
    'neg_risk': str,
    'answer1': str,
    'answer2': str,
    'min_size': float,
    'max_spread': float,
    'rewards_daily_rate': float,
    'best_bid': float,           # ⚠️ Single snapshot value
    'best_ask': float,           # ⚠️ Single snapshot value
    'midpoint': float,
    'tick_size': float,
    'bid_reward_per_100': float,
    'ask_reward_per_100': float,
    'sm_reward_per_100': float,
    'gm_reward_per_100': float,
    'end_date_iso': str,
    'market_slug': str,
    'token1': str,
    'token2': str,
    'condition_id': str
}
```

**Key limitation**: It fetches order book ONCE via `client.get_order_book(token1)` at scan time, but doesn't store the full order book data.

### Data Comparison Table

| Quality Metric | Requires | Available in get_all_results()? |
|----------------|----------|--------------------------------|
| **Spread** | Best bid/ask at analysis time | ❌ Only has snapshot from scan time |
| **Liquidity Balance** | All bid/ask sizes | ❌ Not stored |
| **Total Liquidity** | Sum of all order sizes | ❌ Not stored |
| **Market Depth** | Count of price levels | ❌ Not stored |
| **Top-of-book Liquidity** | Best bid/ask sizes | ❌ Not stored |
| **Price Continuity** | Gaps between price levels | ❌ Not stored |
| **Reward/Volatility** | volatility/reward field | ✅ Yes (if added) |

### Why Real-Time Data is Essential

1. **Order book changes constantly** - Best bid/ask from 10 minutes ago is stale
2. **Liquidity fluctuates** - Need current liquidity to assess if market is tradeable
3. **Quality is time-sensitive** - A market can become illiquid within seconds
4. **Trading decisions need current data** - Can't make buy/sell decisions on old data

### Example Scenario

**Scan Time (get_all_results)**:
```
Best Bid: 0.45 (size: 1000)
Best Ask: 0.46 (size: 1000)
Spread: 1 tick
Quality: Would be EXCELLENT
```

**Trading Time (10 minutes later)**:
```
Best Bid: 0.42 (size: 50)
Best Ask: 0.49 (size: 30)
Spread: 7 ticks
Quality: Actually POOR
```

The quality score would be completely wrong if based on scan-time data.

---

## How Quality is Calculated in Practice

### Step-by-Step Flow

1. **Market Selection**
   - User adds market to "Selected Markets" spreadsheet
   - `main.py` reads the spreadsheet and subscribes to WebSocket

2. **WebSocket Subscription**
   ```python
   # websocket_handlers.py, line 37
   connect_market_websocket(chunk)  # chunk = list of token IDs
   ```

3. **Order Book Initialization**
   ```python
   # data_processing.py, line 15
   process_book_data(asset, json_data)
   # Populates global_state.all_data[market] with full order book
   ```

4. **Continuous Updates**
   ```python
   # websocket_handlers.py - receives updates
   # data_processing.py, line 25 - updates order book
   process_price_change(asset, asset_id, side, price_level, new_size)
   ```

5. **Trading Trigger**
   ```python
   # data_processing.py, line 50
   asyncio.create_task(perform_trade(asset))
   ```

6. **Quality Analysis**
   ```python
   # trading.py, line 325
   market_quality_df = analyze_market_quality(market, row, params)
   ```
   - Uses **current** order book from `global_state.all_data[market]`
   - Uses market config from spreadsheet row
   - Calculates quality score (0-100)

7. **Save Quality**
   ```python
   # trading.py, line 326
   save_market_quality_data(market_quality_df)
   ```
   - Saves to "Markets Quality" worksheet
   - Updates "Selected Markets" quality column (rate-limited to 1/minute)

---

## Could We Calculate a Simplified Quality Score?

### Possible: Yes, but with major limitations

If you wanted a **rough approximation** from `get_all_results()` data, you could:

1. **Calculate spread** - Using snapshot best bid/ask
2. **Use reward/volatility** - If volatility data is added
3. **Skip liquidity metrics** - Not available

**Result**: Quality score based on only 30 points out of 100 (spread + reward/volatility)

### Why This Isn't Useful

- ❌ Missing 70% of the quality factors
- ❌ Stale data - order book changes constantly
- ❌ Can't assess if market is actually tradeable
- ❌ Would give false confidence in low-quality markets
- ❌ Can't make real-time trading decisions

---

## Recommendation

### For Market Discovery (get_all_results)

**Goal**: Find potentially interesting markets

**Use these filters**:
- ✅ `gm_reward_per_100` - Reward potential
- ✅ `spread` - Expected spread
- ✅ `best_bid`, `best_ask` - Snapshot prices
- ✅ Volatility (if added to `add_volatility_to_df()`)
- ✅ `min_size` - Minimum position size

**Don't calculate full quality score** - The data isn't there

### For Trading Decisions (analyze_market_quality)

**Goal**: Assess if market is tradeable RIGHT NOW

**Use full quality calculation**:
- ✅ Real-time order book data
- ✅ Current liquidity and depth
- ✅ Live spread and balance
- ✅ Market configuration

**This is the only way to make safe trading decisions**

---

## Conclusion

### Key Findings

1. **Market Quality CANNOT be calculated from `get_all_results()` data** because it lacks:
   - Full order book (all price levels and sizes)
   - Real-time data (order book changes constantly)
   - Liquidity metrics (total liquidity, balance, depth)
   - Price continuity data (gaps between levels)

2. **Market Quality REQUIRES WebSocket subscription** to get:
   - Live order book snapshots and updates
   - Current best bid/ask with sizes
   - All price levels for depth analysis
   - Real-time liquidity information

3. **The two use cases are different**:
   - **`get_all_results()`** = Market discovery/screening
   - **`analyze_market_quality()`** = Trading suitability assessment

4. **Data flow is intentional**:
   - Scan many markets cheaply (get_all_results)
   - Subscribe to promising markets (WebSocket)
   - Calculate quality with live data (analyze_market_quality)
   - Make trading decisions (perform_trade)

### Why This Design Makes Sense

- 📊 **Efficient** - Don't subscribe to 1000s of markets
- 💰 **Cost-effective** - Minimize WebSocket connections
- ⚡ **Fast** - Real-time data only where needed
- 🎯 **Accurate** - Quality based on current conditions

---

*Documented on: November 18, 2025*

