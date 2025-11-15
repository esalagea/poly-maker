# Auto-populate trade_size Enhancement

## Change Summary

Enhanced the `_update_selected_markets_quality()` function to automatically populate the `trade_size` field in the "Selected Markets" spreadsheet when it's empty.

## What It Does

When updating the quality score for a market, the function now also:
1. Checks if the `trade_size` field is empty (null, '', or 0)
2. If empty and `min_size` is available from market data, sets `trade_size = min_size`
3. Logs when a trade_size is updated

## Implementation Details

**File**: `update_markets.py`
**Function**: `_update_selected_markets_quality()`

### Added Logic:
```python
# Extract min_size from market quality data
min_size = market_quality_df.get('min_size', pd.Series([None])).iloc[0]

# Handle invalid min_size values
if pd.isna(min_size) or min_size in [float('inf'), float('-inf')]:
    min_size = None

# Ensure trade_size column exists
if 'trade_size' not in selected_df.columns:
    selected_df['trade_size'] = ''

# Update trade_size only if it's empty and min_size is valid
current_trade_size = selected_df.loc[row_index, 'trade_size']
if (pd.isna(current_trade_size) or current_trade_size == '' or current_trade_size == 0) and min_size is not None:
    selected_df.loc[row_index, 'trade_size'] = min_size
    print(f"Updated trade_size for '{question}' to {min_size}")
```

## Behavior

### When trade_size is Updated:
- ✅ When `trade_size` field is empty (null)
- ✅ When `trade_size` field is blank ('')
- ✅ When `trade_size` field is 0
- ✅ AND `min_size` is available from market data

### When trade_size is NOT Updated:
- ❌ When `trade_size` already has a non-zero value (preserves user input)
- ❌ When `min_size` is not available or invalid
- ❌ When market is not found in Selected Markets

## Benefits

1. **Automatic initialization** - New markets get a sensible default trade size
2. **Preserves user overrides** - Doesn't overwrite existing non-zero values
3. **Based on market requirements** - Uses the actual minimum order size from the market
4. **Logged for visibility** - Prints when trade_size is auto-populated

## Use Case

When you add a new market to "Selected Markets":
1. Initially, `trade_size` is empty
2. Trading bot runs and analyzes the market
3. Function updates both `quality` score and `trade_size` (from `min_size`)
4. You see: `"Updated trade_size for 'Will X happen?' to 50"`
5. Now the market has both quality score and a starting trade size

If you later manually change `trade_size` to a different value, it won't be overwritten.

## Example Output

```
Market quality data saved for question: Will Trump win the 2024 election?
Updated trade_size for 'Will Trump win the 2024 election?' to 100
```

---
*Implemented on: November 15, 2025*

