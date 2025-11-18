# Answer: Is Minimum Order Size Available in Polymarket API?

## Direct Answer: **NO**

The **minimum order size** for placing orders is **NOT** available in the Polymarket Sampling Markets API response.

## What IS Available in the API Response:

### ✅ Available Fields:

1. **`rewards.min_size`** (e.g., 20)
   - Minimum **position size** to earn maker rewards
   - This is about rewards eligibility, NOT order placement

2. **`minimum_tick_size`** (e.g., 0.01)
   - Minimum **price increment**
   - Used for price levels, not order sizes

3. **`rewards.max_spread`** (e.g., 5.0)
   - Maximum spread percentage for earning rewards

### ❌ NOT Available:

1. **Minimum Order Size** (e.g., 5)
   - The minimum size required to place an order
   - This is enforced by order validation but not exposed in API

## Evidence from Code

Looking at `data_updater/find_markets.py:123`, we extract from API:

```python
ret['min_size'] = row['rewards']['min_size']        # From rewards.min_size
ret['max_spread'] = row['rewards']['max_spread']    # From rewards.max_spread
TICK_SIZE = row['minimum_tick_size']                # From minimum_tick_size
```

No field for minimum order size is extracted because it doesn't exist in the response.

## How We Know the Minimum Order Size

The minimum order size (5) is discovered ONLY when:

1. **Bot attempts to place an order** with size < 5
2. **API rejects it** with error message:
   ```
   PolyApiException[status_code=400, 
   error_message={'error': 'order 0x... is invalid. Size (3) lower than the minimum: 5'}]
   ```
3. We **parse the error message** to learn the minimum is 5

## Polymarket API Documentation Research

Based on available information:
- **Sampling Markets API**: Returns market data with rewards info
- **Order API**: Validates orders but doesn't expose minimums beforehand
- **No public endpoint**: That provides minimum order size per market

The minimum order size appears to be:
- **Hardcoded server-side** in Polymarket's order validation
- **Not exposed** in any API response
- **Discovered through rejection** when orders are too small

## Why This Matters

The bot currently:
1. ❌ Doesn't validate order size before submission
2. ❌ Gets rejected by API for orders < 5
3. ❌ Confuses `row['min_size']` (20, for rewards) with order minimum (5)

The bot should:
1. ✅ Hardcode `POLYMARKET_MIN_ORDER_SIZE = 5`
2. ✅ Validate before calling API: `if size < 5: return`
3. ✅ Handle small positions gracefully (don't try to sell 3 tokens)

## Confusion in Your Case

| Field | Value | Purpose | Available in API? |
|-------|-------|---------|-------------------|
| `row['min_size']` | 20 | Min position for rewards | ✅ Yes |
| Order minimum | 5 | Min size to place order | ❌ No |
| Your position | 3 | Actual tokens owned | N/A |

The bot tried to SELL 3 tokens, but:
- 3 < 5 (order minimum) → **API rejects**
- 3 < 20 (rewards minimum) → Won't earn rewards (but order would be allowed if ≥ 5)

---
*Analysis Date: November 17, 2025*

