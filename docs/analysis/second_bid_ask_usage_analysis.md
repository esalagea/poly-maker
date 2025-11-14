# Usage Analysis: `get_best_bid_ask_deets` - Second Best Bid/Ask Data

## Summary
**The second best bid/ask data is currently NOT USED anywhere in the active codebase.**

## Detailed Findings

### Function Definition
- **Location**: `/poly_data/trading_utils.py:29`
- **Returns**: Dictionary with fields including:
  - `second_best_bid` / `second_best_bid_size`
  - `second_best_ask` / `second_best_ask_size`

### Callers of `get_best_bid_ask_deets`:

1. **`trading.py:368`** - Main trading loop
   - **Uses**: `best_bid`, `best_bid_size`, `top_bid`, `best_ask`, `best_ask_size`, `top_ask`
   - **Does NOT use**: `second_best_bid`, `second_best_ask`, or their sizes
   - Passes data to `get_order_prices()` which also doesn't use second best values

2. **`trading.py:483`** - Market summary/display logic
   - **Uses**: `best_bid`, `best_ask`, `top_bid`, `top_ask`, `best_bid_size`, `best_ask_size`
   - **Does NOT use**: `second_best_bid`, `second_best_ask`, or their sizes
   - Passes data to `get_order_prices()` which also doesn't use second best values

3. **`trading.py:564`** - Risk management assessment
   - **Uses**: `best_bid`, `best_ask`, `bid_sum_within_n_percent`, `ask_sum_within_n_percent`
   - **Does NOT use**: `second_best_bid`, `second_best_ask`, or their sizes

### Historical Usage (Commented Out)

**`trading.py:824`** - Previously had logic to use `second_best_bid`:
```python
# elif best_bid_size < orders['buy']['size'] * 0.98 and abs(best_bid - second_best_bid) > 0.03:
#     print(f"Cancelling buy orders because best size is less than 90% of open orders and spread is too large")
#     global_state.client.cancel_all_asset(order['token'])
```

This logic was intended to:
- Cancel buy orders when the best bid size was too small relative to open orders
- AND when the gap between best and second best bid was significant (> 0.03)
- This would indicate thin liquidity that might disappear

## Refactoring Done

Updated the `if name == 'token2':` block in `poly_data/trading_utils.py` to properly handle cases where second best bid/ask data is missing:

**Default values when data is missing**:
- `second_best_bid` = `0` (value)
- `second_best_ask` = `float('inf')` (value)
- `second_best_bid_size` = `0` (size)
- `second_best_ask_size` = `0` (size)

## Conclusion

The refactoring to handle missing second best bid/ask data is safe and future-proof, but currently:
- ✅ The data is collected and returned
- ❌ No active code consumes this data
- 📝 There was historical usage for order cancellation logic (now commented out)

**Recommendation**: The second best bid/ask data could be useful if re-enabled for:
- Detecting thin liquidity conditions
- More sophisticated order placement strategies
- Risk management when the order book depth is shallow

---
*Documented on: November 14, 2025*

