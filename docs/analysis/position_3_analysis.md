# Position Analysis: Penn State vs Michigan State O/U 48.5 - Position of 3

## Summary

**The position of 3 is CORRECT**. This is not a tracking error. The bot ended up with exactly 3 tokens after a partial fill of a 20-token buy order.

## Complete Trading Timeline

### Initial State (15:23:41)
- **Position**: 0 Over, 0 Under
- **Action**: BUY order for 20 Over placed @ $0.54

### Trade #1: BUY 20 Over @ $0.54 (15:23:41)
```
TRADE EVENT ID: 5322ee1e-f368-4988-88a6-ff520725a5eb
STATUS: MATCHED
SIZE: 20.00
PRICE: $0.54
```
**Result**: Position = 20 Over @ $0.54 avg

### Trade #2: SELL 20 Over @ $0.51 (Stop Loss) (15:24:10)
```
TRADE EVENT ID: 9a087b72-681b-4832-9c79-7c99778b4c60
STATUS: MATCHED
SIDE: SELL (TAKER)
SIZE: 20.00
PRICE: $0.51
```
- **Trigger**: Stop loss activated (PnL: -1.85%, spread: 0.03)
- **Action**: Canceled SELL @ $0.56, created STOP LOSS SELL @ $0.51
- **Result**: Position = 0 Over @ $0.54 avg
- **Position after matching**: `{'size': 0.0, 'avgPrice': 0.54}`

### Period of Zero Position (15:24 - 18:43)
- Position remained at 0 for ~3 hours
- BUY orders placed @ $0.52 for 20 Over
- No fills during this period

### Trade #3: **PARTIAL FILL** - BUY 3 Over @ $0.52 (18:43:08)
```
TRADE EVENT ID: 6a3fcf3c-3502-4958-8627-d3c96c284431
STATUS: MATCHED
SIDE: BUY (MAKER)
SIZE: 3.00  ← Only 3 out of 20 filled!
PRICE: $0.52
```
**Result**: Position = 3 Over @ $0.52 avg
**Position after matching**: `{'size': 3.0, 'avgPrice': 0.52}`

### ORDER STATUS After Trade #3:
```
ORDER ID: 0xc3e0609e41f016dde0ded8536d6fc5345da3a504f4149d743adc35d5e441a3ac
ORIGINAL SIZE: 20.00
SIZE MATCHED: 3.00
REMAINING SIZE: 17.00  ← Still 17 tokens waiting to be filled
```

### Final State (18:43 onwards)
- **Position**: 3 Over @ $0.52
- **Open Orders**: BUY 17 @ $0.52 (remaining from original 20)
- **Problem**: Bot tries to create TAKE PROFIT SELL orders for 3 tokens

## The Error

```
ERROR creating SELL order for token 1887491033199978... @ $0.530 size 3.00: 
PolyApiException[status_code=400, error_message={'error': 'order 0xad887628da6366ef62f33ea31c371c7cbb4ab2e1a5a3b126f5b198cd5d8e5fd0 is invalid. Size (3) lower than the minimum: 5'}]
```

### Why This Happens:
1. ✅ Position tracking is **CORRECT** - We really have 3 tokens
2. ❌ **API Validation Error** - Polymarket requires minimum order size of 5 tokens
3. ❌ Bot doesn't check if position meets minimum order size before trying to sell

## Position Tracking Verification

Let me trace the math:

| Event | Action | Size | Position Calculation |
|-------|--------|------|---------------------|
| Trade #1 | BUY | +20 | 0 + 20 = **20** |
| Trade #2 | SELL | -20 | 20 - 20 = **0** |
| Trade #3 | BUY | +3 | 0 + 3 = **3** |

**Verification**: ✅ Math is correct. Position = 3.

## Why Did We Get a Partial Fill?

The buy order for 20 tokens @ $0.52 was placed and sat on the order book for ~3 hours. During that time:
- Only 3 tokens traded at that price level
- The order was partially filled (maker-side)
- The remaining 17 tokens stayed as an open order

This is **normal market behavior** - orders can be partially filled when there's insufficient liquidity at your price point.

## Root Cause of Error

**The bot has a design flaw**: It attempts to create SELL orders for any position size without checking against Polymarket's API minimum order size requirements.

### Understanding min_size Fields:

There are TWO different "min_size" concepts:

1. **`row['min_size']`** = **20** (from rewards API)
   - This is the **minimum position size to earn rewards**
   - Has nothing to do with order validation
   - Used to determine if a market is worth trading

2. **Polymarket API Order Minimum** = **5** (from API error)
   - This is the **minimum order size** enforced by the exchange
   - Orders below this size are rejected by the API
   - This is what's causing our error

### The Issue:
1. **Polymarket API requires**: Minimum order size = **5 tokens**
2. **Bot's position**: **3 tokens**
3. **Bot attempts**: **SELL 3 @ $0.53**
4. **API rejects**: `"Size (3) lower than the minimum: 5"`

### Why Manual Sell Works:
If you can sell size 3 manually through the UI:
- The UI might be using a different order type (market order vs limit order)
- The UI might aggregate your position with other orders
- The minimum might vary by order type or market conditions
- The error message might be misleading - it could be a different validation issue

## Recommended Fixes

### Fix #1: Check Position Against API Minimum Order Size

The bot needs to track Polymarket's actual minimum order size (appears to be 5) and validate before creating orders:

```python
POLYMARKET_MIN_ORDER_SIZE = 5  # Based on API error messages

if position < POLYMARKET_MIN_ORDER_SIZE:
    log_message(market, f"Position {position} is below Polymarket minimum order size {POLYMARKET_MIN_ORDER_SIZE}, skipping SELL order creation")
    return
```

### Fix #2: Handle Small Positions Differently

Options for positions below minimum order size:
1. **Wait for more fills**: Accumulate until position >= 5, then sell
2. **Cancel remaining buy orders**: Prevent further small fills
3. **Hold indefinitely**: Keep small position until market resolves
4. **Market order**: Try using a market order instead of limit order (may work for smaller sizes)

### Fix #3: Prevent Small Partial Fills

Consider modifying order placement logic:
- Set minimum fill size when placing orders (if supported by API)
- Only place orders when order book shows sufficient liquidity
- Use IOC (Immediate-or-Cancel) or FOK (Fill-or-Kill) order types if available
- Increase order sizes to reduce likelihood of tiny partial fills

### Fix #4: Investigate Actual API Constraints

The bot should:
1. Query the market metadata for actual minimum order size
2. Handle different minimums for different markets
3. Log the specific constraint that was violated
4. Gracefully handle positions that fall below minimums

## Log Evidence Summary

### Key Log Entries:

**Position = 20** (15:23:41):
```
Position after matching is  {'size': 20.0, 'avgPrice': 0.54}
```

**Position = 0** (15:24:10):
```
Position after matching is  {'size': 0.0, 'avgPrice': 0.54}
```

**Position = 3** (18:43:08):
```
Position after matching is  {'size': 3.0, 'avgPrice': 0.52}
```

**ORDER shows partial fill** (18:43:08):
```
ORIGINAL SIZE: 20.00
SIZE MATCHED: 3.00
REMAINING SIZE: 17.00
```

## Conclusion

✅ **Position tracking is CORRECT**
✅ **We really have 3 tokens** (from partial fill)
❌ **Polymarket API requires minimum order size of 5 tokens**
❌ **Bot doesn't validate order size against API minimums before submission**

### Key Clarifications:

1. **`row['min_size']` = 20**: This is the minimum position size to **earn rewards**, not the minimum order size
2. **API Minimum = 5**: This is Polymarket's minimum order size for order placement
3. **Manual UI**: If you can sell 3 tokens manually, it may use a different mechanism (market orders, different validation, etc.)

This is NOT a position tracking bug. This is a **business logic issue** where the bot doesn't validate order sizes against Polymarket API requirements before submitting them.

### Next Steps:

1. Research Polymarket's actual minimum order size requirements
2. Implement pre-submission validation of order sizes
3. Handle sub-minimum positions gracefully
4. Consider preventing small partial fills in the first place

---
*Analysis completed on: November 16, 2025*
*Updated on: November 16, 2025 - Clarified min_size vs API order minimums*

