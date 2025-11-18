# Data Flow: min_size from Polymarket API

## Summary

The `min_size` field comes from Polymarket's **Sampling Markets API** via the `py_clob_client` library. It represents the **minimum position size required to earn maker rewards** on that market.

## Complete Data Flow

### 1. API Call (`data_updater/find_markets.py:24`)

```python
def get_all_markets(client):
    cursor = ""
    all_markets = []
    
    while True:
        try:
            # THIS IS WHERE THE API CALL HAPPENS
            markets = client.get_sampling_markets(next_cursor = cursor)
            markets_df = pd.DataFrame(markets['data'])
            # ...
```

**What this does:**
- Calls `py_clob_client.ClobClient.get_sampling_markets()`
- This makes an HTTP request to Polymarket's REST API
- Returns paginated market data including rewards information

### 2. API Response Structure

The API returns data in this format (for each market):
```json
{
  "question": "Will X happen?",
  "tokens": [...],
  "rewards": {
    "min_size": 20,           // ← Minimum position size for earning rewards
    "max_spread": 5,          // ← Maximum spread percentage for rewards
    "rates": [
      {
        "asset_address": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "rewards_daily_rate": 100
      }
    ]
  },
  "neg_risk": true,
  "market_slug": "...",
  "condition_id": "...",
  "minimum_tick_size": 0.01   // ← Minimum price increment (NOT order size)
}
```

**⚠️ IMPORTANT**: The **minimum order size** for placing orders is **NOT** included in this API response. This information is only discovered when:
1. You attempt to place an order that's too small
2. The API rejects it with an error message like: `"Size (3) lower than the minimum: 5"`
3. There is no documented API endpoint that provides minimum order size per market

### 3. Data Extraction (`data_updater/find_markets.py:123`)

```python
def process_single_row(row, client):
    ret = {}
    ret['question'] = row['question']
    ret['neg_risk'] = row['neg_risk']
    
    ret['answer1'] = row['tokens'][0]['outcome']
    ret['answer2'] = row['tokens'][1]['outcome']
    
    # EXTRACTION HAPPENS HERE
    ret['min_size'] = row['rewards']['min_size']        # ← Extract min_size
    ret['max_spread'] = row['rewards']['max_spread']
    
    # Extract rewards rate
    rate = 0
    for rate_info in row['rewards']['rates']:
        if rate_info['asset_address'].lower() == '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'.lower():
            rate = rate_info['rewards_daily_rate']
            break
    
    ret['rewards_daily_rate'] = rate
    # ...
```

**What this does:**
- Processes each market returned by the API
- Extracts `min_size` from `row['rewards']['min_size']`
- `row` is a DataFrame row containing the API response data

### 4. Data Processing (`data_updater/find_markets.py:218`)

```python
def get_all_results(all_df, client):
    all_results = []
    
    for idx, row in all_df.iterrows():
        try:
            # Process each market
            result = process_single_row(row, client)  # ← Creates dict with min_size
            all_results.append(result)
        except:
            print("error fetching market")
    
    return all_results
```

### 5. DataFrame Creation (`data_updater/find_markets.py:300`)

```python
def get_markets(all_results, sel_df, maker_reward=1):
    new_df = pd.DataFrame(all_results)  # ← Converts list of dicts to DataFrame
    new_df['spread'] = abs(new_df['best_ask'] - new_df['best_bid'])
    # ...
    
    # DataFrame now has 'min_size' column from all_results
    new_df = new_df[['question', 'answer1', 'answer2', 'neg_risk', 'spread', 
                     'best_bid', 'best_ask', 'rewards_daily_rate', 
                     'bid_reward_per_100', 'ask_reward_per_100', 
                     'gm_reward_per_100', 'sm_reward_per_100', 
                     'min_size',  # ← min_size is included in the column selection
                     'max_spread', 'tick_size', 'market_slug', 
                     'token1', 'token2', 'condition_id']]
```

### 6. Spreadsheet Update (`update_markets.py:298`)

```python
def fetch_and_process_data(ONLY_SELECTED_MARKETS):
    # ...
    all_results = get_all_results(filtered_df, client)
    m_data, all_markets = get_markets(all_results, sel_df, maker_reward=0.75)
    
    new_df = add_volatility_to_df(all_markets)
    # ...
    
    # min_size is included in the column selection
    new_df = new_df[['question', 'answer1', 'answer2', 'spread', 
                     'rewards_daily_rate', 'gm_reward_per_100', 
                     'sm_reward_per_100', 'bid_reward_per_100', 
                     'ask_reward_per_100', 'volatility_sum', 
                     'volatility/reward', 
                     'min_size',  # ← min_size flows through to spreadsheet
                     '1_hour', '3_hour', ...]]
```

### 7. Used in Trading Bot (`update_markets.py:192`)

```python
def _update_selected_markets_quality(market_quality_df):
    # Extract min_size from the market quality DataFrame
    min_size = market_quality_df.get('min_size', pd.Series([None])).iloc[0]
    
    # Use it to populate trade_size if empty
    if (pd.isna(current_trade_size) or current_trade_size == '' or current_trade_size == 0) and min_size is not None:
        selected_df.loc[row_index, 'trade_size'] = min_size
```

## API Endpoint Details

### Polymarket Sampling Markets API

**Library**: `py_clob_client`
**Method**: `client.get_sampling_markets(next_cursor=None)`
**HTTP Endpoint**: Likely `https://clob.polymarket.com/sampling-markets` or similar
**Purpose**: Returns markets that are eligible for maker rewards

### Response Fields in `rewards` Object:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `min_size` | int | Minimum position size (in USDC) to earn maker rewards | 20 |
| `max_spread` | float | Maximum allowed spread percentage for rewards | 5.0 |
| `rates` | array | Array of reward rate objects for different assets | [...] |
| `rates[].asset_address` | string | Token address (USDC on Polygon) | 0x2791... |
| `rates[].rewards_daily_rate` | float | Daily reward amount in USDC | 100.0 |

## What min_size Actually Means

**`min_size` = 20** means:
- To earn maker rewards on this market, you need to maintain a position of **at least 20 USDC** worth of tokens
- This is NOT about order size - it's about position size for rewards eligibility
- You can place orders smaller than 20, but you won't earn rewards unless your position reaches 20

## Important Distinctions

### Three Different Size Concepts:

1. **`row['min_size']`** (from API `rewards.min_size`)
   - Minimum position size to earn maker rewards
   - Typically 20, 50, 100, etc.
   - Source: Polymarket Sampling Markets API
   - **✅ Available in API response**

2. **Polymarket Order Minimum** (from order validation)
   - Minimum order size to place on exchange
   - Appears to be around 5 USDC (based on error messages)
   - Source: Polymarket order validation (server-side)
   - **❌ NOT available in any API response**
   - **❌ NOT documented in public API docs**
   - Only discovered when orders are rejected

3. **`minimum_tick_size`** (from API)
   - Minimum price increment (e.g., 0.01)
   - Affects price levels, not sizes
   - Source: Polymarket market metadata
   - **✅ Available in API response**

### How to Find Minimum Order Size:

Since Polymarket doesn't provide `minimum_order_size` in the API:

1. **Trial and Error**: Attempt to place orders and catch rejection errors
2. **Error Message Parsing**: Extract the minimum from error messages like:
   ```
   "Size (3) lower than the minimum: 5"
   ```
3. **Hardcode Conservative Value**: Use a safe minimum (e.g., 5 or 10) for all markets
4. **Check Polymarket Documentation**: Look for official docs at:
   - https://docs.polymarket.com
   - https://gamma-api.polymarket.com/docs
   - Polymarket Discord/Support channels

## Recommended Fix for the Bot

Since the minimum order size is not available in the API, the bot should:

### 1. **Hardcode a Safe Minimum**
```python
# In CONSTANTS.py or similar
POLYMARKET_MIN_ORDER_SIZE = 5  # Based on observed API errors
```

### 2. **Validate Before Order Placement**
```python
def create_order(self, marketId, action, price, size, neg_risk=False):
    # Add validation BEFORE calling API
    if size < POLYMARKET_MIN_ORDER_SIZE:
        market = get_market_from_token(str(marketId))
        if market:
            log_message(market, f"Order size {size:.2f} is below minimum {POLYMARKET_MIN_ORDER_SIZE}, skipping order creation")
        return {}
    
    # Proceed with normal order creation
    order_args = OrderArgs(...)
    # ...
```

### 3. **Parse Error Messages to Learn Market-Specific Minimums**
```python
# In exception handler
except Exception as ex:
    error_str = str(ex)
    # Try to extract minimum from error message
    # "Size (3) lower than the minimum: 5"
    import re
    match = re.search(r'lower than the minimum: (\d+)', error_str)
    if match:
        actual_minimum = int(match.group(1))
        # Store this for future reference
        # Could cache per market if minimums vary
```

### 4. **Handle Small Positions Gracefully**
```python
if position < POLYMARKET_MIN_ORDER_SIZE:
    log_message(market, f"Position {position} below minimum order size, options:")
    log_message(market, f"  1. Wait for more fills to reach {POLYMARKET_MIN_ORDER_SIZE}")
    log_message(market, f"  2. Cancel remaining buy orders")
    log_message(market, f"  3. Hold position until market resolves")
    return  # Don't attempt to create order
```

## Verification

To verify this data flow, you can:

1. **Check the actual API response:**
```python
client = get_clob_client()
markets = client.get_sampling_markets()
print(markets['data'][0]['rewards'])
# Output will show: {'min_size': 20, 'max_spread': 5.0, 'rates': [...]}
```

2. **Check py_clob_client source code:**
```bash
pip show py-clob-client
# Then look at the installed package source
```

3. **Check Polymarket API documentation:**
- https://docs.polymarket.com (if available)
- The sampling markets endpoint documentation

---
*Documented on: November 17, 2025*

