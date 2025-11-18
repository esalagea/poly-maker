# PnL Tracking Implementation

## Date: November 18, 2025

## Summary

Implemented **Step 1: Capture Position BEFORE SELL Trades** to enable real-time profit/loss tracking on closed positions.

---

## Changes Made

### 1. Added `calculate_pnl()` Function

**Location:** `poly_data/trading_utils.py`

**Purpose:** Calculate realized PnL for SELL trades only.

**Function Signature:**
```python
def calculate_pnl(prev_position, trade_side, trade_size, trade_price):
    """
    Calculate realized PnL for SELL trades only.

    Args:
        prev_position: {'size': float, 'avgPrice': float}
        trade_side: 'buy' or 'sell'
        trade_size: float
        trade_price: float

    Returns:
        dict: {
            'realized_pnl': float,      # Profit/loss in USD
            'closed_size': float,       # How much was closed
            'pnl_per_unit': float,      # PnL per unit
            'is_closing': bool          # True if closing position
        }
    """
```

**Logic:**
- **BUY trades:** Return zero PnL (no closing)
- **SELL trades with no position:** Return zero PnL (nothing to close)
- **SELL trades with position:** Calculate realized PnL based on average entry price

**Formula:**
```
closed_size = min(position_size, trade_size)
pnl_per_unit = exit_price - entry_price
realized_pnl = closed_size * pnl_per_unit
```

---

### 2. Modified Trade Processing

**Location:** `poly_data/data_processing.py`

**Changes:**
1. Added imports:
   - `get_position` from `poly_data.data_utils`
   - `calculate_pnl` from `poly_data.trading_utils`

2. Updated `MATCHED` status handler:
   - Capture position BEFORE `set_position()` for SELL trades
   - Calculate PnL using `calculate_pnl()`
   - Log detailed PnL information for closing trades

**Code Flow:**
```python
if side.lower() == 'sell':
    # Step 1: Capture position before trade
    prev_position = get_position(token)
    
    # Step 2: Calculate PnL
    pnl_info = calculate_pnl(prev_position, side.lower(), size, price)

# Step 3: Update position (as before)
set_position(token, side, size, price)

# Step 4: Log PnL if closing position
if pnl_info and pnl_info['is_closing']:
    # Log detailed P&L analysis
```

---

## New Log Format

When a SELL trade closes a position, the bot now logs:

```
================================================================================
TRADE CLOSED - PROFIT
--------------------------------------------------------------------------------
Side                 SELL       Size: 50.00 @ $0.510
--------------------------------------------------------------------------------
POSITION BEFORE:
  Size                      50.00
  Avg Price             $0.490
--------------------------------------------------------------------------------
P&L ANALYSIS:
  Closed Size               50.00
  Entry Price           $0.490
  Exit Price            $0.510
  P&L per Unit          $0.020
  Realized P&L          +$1.00 (PROFIT)
================================================================================
```

**Benefits:**
- ✅ Immediate visibility into trade profitability
- ✅ Clear entry/exit prices
- ✅ Per-unit and total PnL
- ✅ PROFIT/LOSS/BREAK-EVEN status

---

## Example Scenarios

### Scenario 1: Full Position Close (Profit)

**Trade Sequence:**
1. BUY 50 @ $0.45 → Position: 50 @ $0.45 (no PnL logged)
2. SELL 50 @ $0.55 → Position: 0 @ $0.00

**Logged PnL:**
```
Closed Size:     50.00
Entry Price:     $0.450
Exit Price:      $0.550
P&L per Unit:    $0.100
Realized P&L:    +$5.00 (PROFIT)
```

### Scenario 2: Partial Position Close (Loss)

**Trade Sequence:**
1. BUY 100 @ $0.60 → Position: 100 @ $0.60 (no PnL logged)
2. SELL 30 @ $0.55 → Position: 70 @ $0.60

**Logged PnL:**
```
Closed Size:     30.00
Entry Price:     $0.600
Exit Price:      $0.550
P&L per Unit:    -$0.050
Realized P&L:    -$1.50 (LOSS)
```

### Scenario 3: Multiple Buys, Then Sell (Weighted Average)

**Trade Sequence:**
1. BUY 50 @ $0.40 → Position: 50 @ $0.40 (no PnL logged)
2. BUY 50 @ $0.50 → Position: 100 @ $0.45 (weighted avg, no PnL logged)
3. SELL 100 @ $0.52 → Position: 0 @ $0.00

**Logged PnL:**
```
Closed Size:     100.00
Entry Price:     $0.450  (weighted average)
Exit Price:      $0.520
P&L per Unit:    $0.070
Realized P&L:    +$7.00 (PROFIT)
```

---

## Technical Details

### Why Only SELL Trades?

**BUY trades** open or add to positions → No PnL realization
**SELL trades** close or reduce positions → PnL is realized

This follows standard accounting principles (realized vs unrealized gains).

### Why Check `prev_size == 0`?

Edge case protection: If we try to SELL with no position, we can't realize any PnL.

This shouldn't happen in normal operation, but the check prevents errors if:
- Position tracking gets out of sync
- Manual trades are placed outside the bot
- WebSocket updates are missed

### Position Tracking

The `get_position()` function returns:
```python
{
    'size': float,      # Current position (positive = long)
    'avgPrice': float   # Weighted average entry price
}
```

If token not found in `global_state.positions`:
```python
{'size': 0, 'avgPrice': 0}
```

---

## Testing Recommendations

### 1. Manual Testing

Run the bot and verify PnL logs appear for SELL trades:

```bash
python main.py
# Wait for trades to execute
# Check log files for "TRADE CLOSED" messages
```

### 2. Verify PnL Calculations

Check that:
- ✅ BUY trades don't show PnL logs
- ✅ SELL trades show detailed PnL analysis
- ✅ PnL math is correct: `(exit_price - entry_price) × size`
- ✅ PROFIT/LOSS labels are correct

### 3. Edge Cases to Monitor

- SELL with no prior position (shouldn't happen)
- Partial closes (verify remaining position is correct)
- Multiple buys at different prices (verify weighted average)
- Very small positions (verify formatting handles small numbers)

---

## Known Limitations

### 1. Fees Not Included

Current implementation calculates PnL based on execution prices only.

**Missing:**
- Trading fees (taker fees)
- Maker rebates

**Impact:** Actual net PnL will be slightly lower due to fees.

**Future Enhancement:** Add fee calculation based on maker/taker role.

### 2. No Cumulative Tracking

Each trade logs PnL individually, but there's no running total.

**Missing:**
- Total PnL per market
- Total PnL per token
- Win rate statistics
- Largest win/loss tracking

**Future Enhancement:** Add cumulative PnL tracking (see Step 3 in trade_pnl_analysis.md).

### 3. No Unrealized PnL

Only shows PnL when positions are closed.

**Missing:**
- Mark-to-market PnL for open positions
- Current value vs entry value

**Future Enhancement:** Add unrealized PnL calculation using current market prices.

### 4. Rewards Not Included

Market maker rewards are separate from trading PnL.

**Missing:**
- Rewards earned while orders were live
- Total return (PnL + rewards)

**Future Enhancement:** Track and log rewards separately, then combine for total profitability.

---

## Next Steps

### Immediate (Completed ✅)
- ✅ Implement `calculate_pnl()` function
- ✅ Capture position before SELL trades
- ✅ Log PnL information

### Short Term (Recommended)
- [ ] Add fee calculation to PnL
- [ ] Test with real trades to verify accuracy
- [ ] Add cumulative PnL tracking per market
- [ ] Add summary statistics (win rate, avg PnL, etc.)

### Medium Term (Optional)
- [ ] Add unrealized PnL for open positions
- [ ] Track and include rewards in total profitability
- [ ] Export PnL data to spreadsheet
- [ ] Add daily/weekly PnL reports
- [ ] Implement per-market stop-loss based on cumulative PnL

### Long Term (Nice to Have)
- [ ] Historical PnL charts
- [ ] Performance comparison across markets
- [ ] Risk-adjusted return metrics (Sharpe ratio, etc.)
- [ ] Tax reporting export

---

## Files Modified

1. **poly_data/trading_utils.py**
   - Added `calculate_pnl()` function

2. **poly_data/data_processing.py**
   - Added imports: `get_position`, `calculate_pnl`
   - Modified `MATCHED` status handler to capture position and calculate PnL
   - Added detailed PnL logging for SELL trades

---

## References

- Design Document: `docs/analysis/trade_pnl_analysis.md`
- Related Functions:
  - `get_position()` in `poly_data/data_utils.py`
  - `set_position()` in `poly_data/data_utils.py`
  - `log_message()` in `poly_data/log_utils.py`

---

*Implementation completed: November 18, 2025*

