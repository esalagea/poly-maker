# Fixed: PolyApiException Not Logged Through Custom Logging

## Problem Identified

The exception `PolyApiException[status_code=400, error_message={'error': 'not enough balance / allowance'}]` was appearing in the console output but **NOT** in your custom market logs.

## Root Cause

**File**: `poly_data/polymarket_client.py`, line 135 (original)

**The Issue**: The exception was being caught and printed with `print(ex)` instead of using your custom `log_message()` function:

```python
try:
    resp = self.client.post_order(signed_order)
    return resp
except Exception as ex:
    print(ex)  # ❌ Goes to stdout, not to your logging system
    return {}
```

This happened in the `create_order()` method when calling `self.client.post_order(signed_order)`.

## Where This Exception Occurs

The exception is thrown when:
1. Stop loss triggers and tries to SELL tokens
2. The local position shows tokens available (due to the position tracking bug we fixed earlier)
3. The actual blockchain balance is 0 (tokens already sold)
4. The API rejects the order with "not enough balance / allowance"

## Fix Applied

### 1. Added Imports
```python
from poly_data.log_utils import log_message
from poly_data.data_utils import get_market_from_token
```

### 2. Replaced print() with log_message()
```python
try:
    resp = self.client.post_order(signed_order)
    return resp
except Exception as ex:
    # Get market identifier from token for logging
    market = get_market_from_token(str(marketId))
    if market:
        log_message(market, f"ERROR creating {action} order for token {str(marketId)[:16]}... @ ${price:.3f} size {size:.2f}: {ex}")
    else:
        log_message("UNKNOWN_MARKET", f"ERROR creating {action} order for token {str(marketId)[:16]}... @ ${price:.3f} size {size:.2f}: {ex}")
    return {}
```

## What You'll See Now

### Before (console output only):
```
PolyApiException[status_code=400, error_message={'error': 'not enough balance / allowance'}]
```

### After (in your market logs):
```
ERROR creating SELL order for token 1397209900709394... @ $0.080 size 50.00: PolyApiException[status_code=400, error_message={'error': 'not enough balance / allowance'}]
```

## Benefits

✅ **Full context in logs** - Includes action (BUY/SELL), token ID, price, and size
✅ **Market association** - Error logged to the correct market log file
✅ **Easier debugging** - All trading activity in one place
✅ **Consistent logging** - Uses your custom logging mechanism like all other messages
✅ **Better visibility** - Won't get lost in console output

## Related Fix

Combined with the position tracking fix (30-second delay + keeping trades in "performing" until CONFIRMED), these exceptions should stop occurring because the system will no longer attempt to sell tokens that don't exist.

## Other Locations

Note: There are also `print(ex)` statements in `data_updater/trading_utils.py` but those appear to be in a separate utility module that may not be actively used in the main trading loop. Let me know if you want those fixed as well.

---
*Fixed on: November 14, 2025*

