# Missing `cancel_order` Method Fix

## Problem

The code was calling `client.cancel_order(order['id'])` in `trading.py`, but the `PolymarketClient` class didn't have a `cancel_order` method, causing this error:

```
Error checking orders before selective cancel for token 13972099007093945639289066975118952446928598912948776998483907198659692541222: 'PolymarketClient' object has no attribute 'cancel_order'
```

## Root Cause

**File**: `trading.py`, line 108

The code attempted to selectively cancel individual orders:
```python
for idx, order in orders_to_cancel.iterrows():
    client.cancel_order(order['id'])  # ❌ Method doesn't exist
```

The `PolymarketClient` only had:
- `cancel_all_asset()` - Cancel all orders for a token
- `cancel_all_market()` - Cancel all orders in a market

But no method to cancel a single order by ID.

## The Fix

Added the missing `cancel_order()` method to `PolymarketClient`:

**File**: `poly_data/polymarket_client.py`

```python
def cancel_order(self, order_id):
    """
    Cancel a single order by ID.
    
    Args:
        order_id (str): The order ID to cancel
        
    Returns:
        Response from the API
    """
    return self.client.cancel_orders([order_id])
```

This method wraps the underlying `py_clob_client`'s `cancel_orders()` method (which takes a list of order IDs) to cancel a single order.

## Where It's Used

The method is used in `trading.py` in the `cancel_orders_selective()` function when selectively canceling orders by side (buy/sell) instead of canceling all orders for a token.

### Usage Example:
```python
# Get orders to cancel (e.g., only SELL orders)
orders_to_cancel = existing_orders[existing_orders['side'] == 'SELL']

# Cancel each order individually
for idx, order in orders_to_cancel.iterrows():
    client.cancel_order(order['id'])  # ✅ Now works!
```

## Impact

✅ **Selective order cancellation now works** - You can cancel specific orders without canceling all orders for a token
✅ **Better control** - Allows more granular order management
✅ **Fallback still exists** - If selective cancellation fails, it still falls back to `cancel_all_asset()`

## Files Modified

- `poly_data/polymarket_client.py` - Added `cancel_order()` method

---
*Fixed on: November 14, 2025*

