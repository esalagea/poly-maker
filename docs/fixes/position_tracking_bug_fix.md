# Position Tracking Bug - Analysis and Fix

## Problem Summary

Your assumption was **100% CORRECT**. The system was incorrectly tracking positions after trades, causing it to attempt selling the same tokens multiple times, resulting in:
```
PolyApiException[status_code=400, error_message={'error': 'not enough balance / allowance'}]
```

## Root Cause Analysis

### Timeline of Events (from log lines 63-172):

1. **Line 63**: Stop loss triggered to SELL 50.0 tokens
2. **Line 84**: Trade MATCHED, position correctly updated to 0.0 (trade ID: 4333450e-ad11-465a-8315-850bd01a17d9)
3. **Line 115**: System skips updates due to pending trades (correct behavior)
4. **Line 128**: **BUG OCCURS** - API update overwrites position from 0.0 back to 50.0
   ```
   "No trades are pending. Updating position from 0.0 to 50 and avgPrice to 0.1 using API"
   ```
5. **Line 136**: Position now incorrectly shows 50.0 again
6. **Line 140+**: Multiple stop loss triggers attempt to SELL 50.0 that don't exist
7. **Line 158**: Same trade event arrives with status "MINED"
8. **Line 172**: Same trade event arrives with status "CONFIRMED"

### Why This Happened

The bug occurred due to a **race condition** between local position updates and API position fetching:

```
Trade Status Flow:
MATCHED → position updated locally (0.0)
    ↓
MINED → removed from "performing" set
    ↓
[API still shows old position: 50.0]
    ↓
perform_trade() called → fetches from API
    ↓
5-second delay expired → API update allowed
    ↓
Local position OVERWRITTEN with stale API data (50.0)
    ↓
CONFIRMED → Trade finalized, but position already wrong
```

The problem: The blockchain/API takes time to update (10-30 seconds), but the code was only waiting 5 seconds before allowing API updates to override local position data.

## Fixes Applied

### Fix #1: Extended Trade Update Delay
**File**: `poly_data/data_utils.py`

**Changed**: Increased delay from 5 to 30 seconds
```python
# Before
if time.time() - global_state.last_trade_update[asset] < 5:

# After  
if time.time() - global_state.last_trade_update[asset] < 30:  # Increased to 30 seconds
```

**Why**: Gives blockchain and API enough time to update before we fetch positions from API, preventing stale data from overwriting correct local positions.

### Fix #2: Keep Trade in "Performing" Until Confirmed
**File**: `poly_data/data_processing.py`

**Changed**: Don't remove trade from `performing` set on MINED status
```python
# Before
elif row['status'] == 'MINED':
    remove_from_performing(col, row['id'])

# After
elif row['status'] == 'MINED':
    # Don't remove from performing yet - wait for CONFIRMED
    # This prevents API updates from overwriting the position
    log_message(market, f"Trade {row['id']} mined, waiting for confirmation")
    pass
```

**Why**: Keeps the trade marked as "pending" until CONFIRMED, which prevents `update_positions()` from fetching from API (it skips tokens with pending trades).

## How It Works Now

### Correct Flow After Fixes:

```
1. MATCHED arrives
   ├─ Update local position: 50 → 0
   ├─ Add to "performing" set
   └─ Set last_trade_update timestamp

2. MINED arrives
   ├─ Keep in "performing" set (CHANGED)
   └─ Log that we're waiting for confirmation

3. API updates attempted during this time
   ├─ Check: Is trade in "performing"? YES
   ├─ → Skip API update
   └─ OR
   ├─ Check: Last trade < 30 seconds ago? YES (CHANGED from 5)
   └─ → Skip API update

4. CONFIRMED arrives
   ├─ Remove from "performing" set
   ├─ 30 seconds have passed since trade
   └─ Future API updates now safe to apply
```

## Expected Behavior After Fix

✅ **Single stop loss execution** - Position correctly tracked as 0 after trade
✅ **No duplicate sell attempts** - System knows there's nothing left to sell
✅ **No "not enough balance" errors** - Won't try to sell non-existent tokens
✅ **Robust against delayed API updates** - 30-second buffer handles blockchain delays
✅ **Safe position reconciliation** - API updates only applied when safe

## Additional Context

The same trade event arrives THREE times with different statuses:
- **MATCHED**: Order matched, trade executing
- **MINED**: Transaction included in a block
- **CONFIRMED**: Transaction finalized (multiple block confirmations)

Only MATCHED should update the position. The other statuses are just confirmation that the trade is progressing through the blockchain.

## Testing Recommendations

Monitor logs for:
1. Position updates should only happen once per trade (at MATCHED status)
2. "Skipping update for {asset} because last trade update was less than 30 seconds ago" should appear during the delay period
3. No more "not enough balance / allowance" errors after successful trades
4. "Trade {id} mined, waiting for confirmation" should appear for MINED status

---
*Fixed on: November 14, 2025*

