## Summary

**YES, it is possible to calculate profit/loss when an order gets filled!**

The system already tracks the necessary data:
- ✅ Current position (size and average entry price)
- ✅ Trade details (size, price, side)
- ✅ Token information

This document explains how to calculate PnL and what improvements are needed.

---

## Current State Analysis

### Available Data When Trade is Filled

When a trade event occurs with `status == 'MATCHED'`, we have access to:

**From the trade event** (`row` in `process_user_data()`):
```python
{
    'id': '9783975c-7fc4-47aa-a484-fb0ad28ad768',
    'market': '0x5b627c7b2f82ea92dfb69650a87724664ad771d33ff838c11907efa71c5a4d61',
    'asset_id': token,           # Token ID (Yes or No)
    'side': 'BUY' or 'SELL',     # Order side
    'status': 'MATCHED',         # Trade matched
    'price': 0.09,               # Execution price
    'size': 50.0,                # Size filled
    'outcome': 'Yes' or 'No',    # Which outcome
    'maker_orders': [...]        # Maker order details
}
```

**From global state** (`global_state.positions[token]`):
```python
{
    'size': 50.0,        # Current position size (positive = long, negative = short)
    'avgPrice': 0.085    # Average entry price for current position
}
```

**This is called at** (line 162 in `data_processing.py`):
```python
elif row['status'] == 'MATCHED':
    add_to_performing(col, row['id'])
    log_message(market, "Matched. Performing is ", len(global_state.performing[col]))
    
    # THIS IS WHERE WE UPDATE POSITION
    set_position(token, side, size, price)
    
    log_message(market, "Position after matching is ", global_state.positions[str(token)])
```

---

## How to Calculate PnL

### Key Insight: Only SELL Orders Realize PnL

**Simple rule:** 
- **BUY orders** = Opening/adding to position → **NO PnL calculation needed**
- **SELL orders** = Closing/reducing position → **ALWAYS calculate PnL**

The `set_position()` function (line 101 in `data_utils.py`) updates the position. We only need to capture the position BEFORE `SELL` trades to calculate PnL.

### PnL Calculation Logic (SIMPLIFIED)

#### For BUY Orders: Skip PnL Calculation
```python
Previous position: 0 or any size
New trade: BUY 50 @ $0.50

Action: Skip PnL calculation entirely
New position: Updated with weighted average price
```

#### For SELL Orders: Always Calculate PnL

**Case 1: Selling with No Position (Should Never Happen)**
```python
Previous position: size = 0
New trade: SELL 50 @ $0.55

PnL: $0 (nothing to close)
Note: This shouldn't happen in practice - can't sell what you don't have
```

**Case 2: Partially Closing Position**
```python
Previous position: 50 @ $0.45 (long)
New trade: SELL 30 @ $0.55

Closed size: 30
PnL: 30 × ($0.55 - $0.45) = +$3.00 (PROFIT)
New position: 20 @ $0.45 (still long)
```

**Case 3: Fully Closing Position**
```python
Previous position: 50 @ $0.45 (long)
New trade: SELL 50 @ $0.55

Closed size: 50
PnL: 50 × ($0.55 - $0.45) = +$5.00 (PROFIT)
New position: 0 @ $0.00 (flat)
```

**Case 4: Closing and Reversing (Rare - Shouldn't Happen in Market Making)**
```python
Previous position: 30 @ $0.45 (long)
New trade: SELL 50 @ $0.55

Closed size: 30 (close existing position)
PnL: 30 × ($0.55 - $0.45) = +$3.00 (PROFIT)
New position: -20 @ $0.55 (now short - unusual!)
```

#### Market Making Example (Typical Flow)
```python
Trade 1: BUY 50 @ $0.49 (maker order filled)
Position: 50 @ $0.49 (long)
PnL: $0

Trade 2: SELL 50 @ $0.51 (maker order filled)
Position: 0 @ $0.00 (flat)
PnL: 50 * ($0.51 - $0.49) = +$1.00 (PROFIT)
Plus: Maker rewards earned while orders were live
```

---

## PnL Calculation Formula

### General Formula

```python
def calculate_pnl(prev_position, trade_side, trade_size, trade_price):
    """
    Calculate realized PnL from a trade
    
    Args:
        prev_position: {'size': float, 'avgPrice': float}
        trade_side: 'buy' or 'sell'
        trade_size: float (always positive)
        trade_price: float
        
    Returns:
        dict: {
            'realized_pnl': float,      # Profit/loss in USD
            'closed_size': float,       # How much was closed
            'pnl_per_unit': float,      # PnL per unit closed
            'is_opening': bool,         # True if opening/adding
            'is_closing': bool,         # True if closing/reducing
            'is_reversing': bool        # True if closing and flipping
        }
    """
    prev_size = prev_position['size']
    prev_avg_price = prev_position['avgPrice']
    
    # Convert trade to signed size
    signed_trade_size = trade_size if trade_side == 'buy' else -trade_size
    
    # Determine if we're closing a position
    if prev_size == 0:
        # Opening new position
        return {
            'realized_pnl': 0.0,
            'closed_size': 0.0,
            'pnl_per_unit': 0.0,
            'is_opening': True,
            'is_closing': False,
            'is_reversing': False
        }
    
    elif (prev_size > 0 and signed_trade_size > 0) or \
         (prev_size < 0 and signed_trade_size < 0):
        # Adding to existing position (same direction)
        return {
            'realized_pnl': 0.0,
            'closed_size': 0.0,
            'pnl_per_unit': 0.0,
            'is_opening': True,
            'is_closing': False,
            'is_reversing': False
        }
    
    else:
        # Closing (at least partially)
        closed_size = min(abs(prev_size), abs(signed_trade_size))
        
        # Calculate PnL
        if prev_size > 0:
            # Was long, selling now
            pnl_per_unit = trade_price - prev_avg_price
        else:
            # Was short, buying now
            pnl_per_unit = prev_avg_price - trade_price
        
        realized_pnl = closed_size * pnl_per_unit
        
        is_reversing = abs(signed_trade_size) > abs(prev_size)
        
        return {
            'realized_pnl': realized_pnl,
            'closed_size': closed_size,
            'pnl_per_unit': pnl_per_unit,
            'is_opening': False,
            'is_closing': True,
            'is_reversing': is_reversing
        }
```

---

## Implementation Strategy

### Step 1: Capture Position BEFORE SELL Trades

Modify `process_user_data()` to capture position before calling `set_position()` (ONLY for SELL orders):

```python
elif row['status'] == 'MATCHED':
    add_to_performing(col, row['id'])
    
    # CAPTURE POSITION BEFORE UPDATE (only for SELL)
    prev_position = get_position(token) if side == 'sell' else None
    
    # UPDATE POSITION
    set_position(token, side, size, price)
    
    log_trade_with_pnl(market, row, prev_position, pnl_info)
```

### Step 2: Create Enhanced Logging Function

```python
def log_trade_with_pnl(market, trade_event, prev_position, pnl_info):
    """
    Log trade event with profit/loss analysis
    
    Args:
        market: Market identifier
        trade_event: Trade event data from websocket
        prev_position: Position before trade
        pnl_info: PnL calculation results
    """
    token = trade_event['asset_id']
    side = trade_event['side'].upper()
    size = float(trade_event['size'])
    price = float(trade_event['price'])
    
    # Get new position after update
    new_position = get_position(token)
    
    # Determine trade type
    trade_type = ""
    if pnl_info['is_opening'] and prev_position['size'] == 0:
        trade_type = "OPENING"
    elif pnl_info['is_opening'] and prev_position['size'] != 0:
        trade_type = "ADDING"
    elif pnl_info['is_reversing']:
        trade_type = "REVERSING"
    elif pnl_info['is_closing'] and new_position['size'] == 0:
        trade_type = "CLOSING (FLAT)"
    elif pnl_info['is_closing']:
        trade_type = "REDUCING"
    
    # Format PnL with color/symbols
    pnl = pnl_info['realized_pnl']
    pnl_symbol = "+" if pnl > 0 else ""
    pnl_status = "PROFIT" if pnl > 0 else ("LOSS" if pnl < 0 else "NEUTRAL")
    
    log_message(market,
        f"\n{'='*100}\n"
        f"TRADE EVENT - {trade_type}\n"
        f"{'-'*100}\n"
        f"{'Token':<20} {token[:20]}...\n"
        f"{'Side':<20} {side:<10} Size: {size:.2f} @ ${price:.3f}\n"
        f"{'-'*100}\n"
        f"POSITION BEFORE:\n"
        f"  {'Size':<18} {prev_position['size']:>10.2f}\n"
        f"  {'Avg Price':<18} ${prev_position['avgPrice']:>9.3f}\n"
        f"  {'Market Value':<18} ${prev_position['size'] * prev_position['avgPrice']:>9.2f}\n"
        f"{'-'*100}\n"
        f"POSITION AFTER:\n"
        f"  {'Size':<18} {new_position['size']:>10.2f}\n"
        f"  {'Avg Price':<18} ${new_position['avgPrice']:>9.3f}\n"
        f"  {'Market Value':<18} ${new_position['size'] * new_position['avgPrice']:>9.2f}\n"
        f"{'-'*100}\n"
        f"P&L ANALYSIS:\n"
        f"  {'Closed Size':<18} {pnl_info['closed_size']:>10.2f}\n"
        f"  {'Entry Price':<18} ${prev_position['avgPrice']:>9.3f}\n"
        f"  {'Exit Price':<18} ${price:>9.3f}\n"
        f"  {'P&L per Unit':<18} ${pnl_info['pnl_per_unit']:>9.3f}\n"
        f"  {'Realized P&L':<18} {pnl_symbol}${abs(pnl):>8.2f} ({pnl_status})\n"
        f"{'='*100}"
    )
```

### Step 3: Track Cumulative PnL

Add to `global_state.py`:

```python
# Track cumulative P&L per market
market_pnl = {}  # {market_id: {'realized_pnl': float, 'trade_count': int, 'wins': int, 'losses': int}}

# Track cumulative P&L per token
token_pnl = {}  # {token_id: {'realized_pnl': float, 'trade_count': int}}
```

Update function:

```python
def update_pnl_stats(market, token, pnl_info):
    """
    Update cumulative PnL statistics
    """
    pnl = pnl_info['realized_pnl']
    
    # Update market stats
    if market not in global_state.market_pnl:
        global_state.market_pnl[market] = {
            'realized_pnl': 0.0,
            'trade_count': 0,
            'wins': 0,
            'losses': 0,
            'largest_win': 0.0,
            'largest_loss': 0.0
        }
    
    if pnl != 0:  # Only count closing trades
        stats = global_state.market_pnl[market]
        stats['realized_pnl'] += pnl
        stats['trade_count'] += 1
        
        if pnl > 0:
            stats['wins'] += 1
            stats['largest_win'] = max(stats['largest_win'], pnl)
        else:
            stats['losses'] += 1
            stats['largest_loss'] = min(stats['largest_loss'], pnl)
    
    # Similar for token stats...
```

---

## Example Output

### Example 1: Successful Market Making Round Trip

```
================================================================================
TRADE EVENT - OPENING
--------------------------------------------------------------------------------
Token                0x4d4e6173befa...
Side                 BUY        Size: 50.00 @ $0.490
--------------------------------------------------------------------------------
POSITION BEFORE:
  Size                        0.00
  Avg Price              $0.000
  Market Value           $0.00
--------------------------------------------------------------------------------
POSITION AFTER:
  Size                       50.00
  Avg Price              $0.490
  Market Value          $24.50
--------------------------------------------------------------------------------
P&L ANALYSIS:
  Closed Size                 0.00
  Entry Price            $0.000
  Exit Price             $0.490
  P&L per Unit           $0.000
  Realized P&L           $0.00 (NEUTRAL)
================================================================================

... time passes, sell order fills ...

================================================================================
TRADE EVENT - CLOSING (FLAT)
--------------------------------------------------------------------------------
Token                0x4d4e6173befa...
Side                 SELL       Size: 50.00 @ $0.510
--------------------------------------------------------------------------------
POSITION BEFORE:
  Size                       50.00
  Avg Price              $0.490
  Market Value          $24.50
--------------------------------------------------------------------------------
POSITION AFTER:
  Size                        0.00
  Avg Price              $0.000
  Market Value           $0.00
--------------------------------------------------------------------------------
P&L ANALYSIS:
  Closed Size                50.00
  Entry Price            $0.490
  Exit Price             $0.510
  P&L per Unit           $0.020
  Realized P&L           +$1.00 (PROFIT)
================================================================================

MARKET SUMMARY: 0x5b627c7b...
  Total Realized P&L:  +$1.00
  Total Trades:        1
  Win Rate:            100.0%
  Largest Win:         +$1.00
  Average P&L:         +$1.00
```

### Example 2: Adverse Fill (Loss)

```
================================================================================
TRADE EVENT - CLOSING (FLAT)
--------------------------------------------------------------------------------
Token                0x4d4e6173befa...
Side                 SELL       Size: 50.00 @ $0.480
--------------------------------------------------------------------------------
POSITION BEFORE:
  Size                       50.00
  Avg Price              $0.490
  Market Value          $24.50
--------------------------------------------------------------------------------
POSITION AFTER:
  Size                        0.00
  Avg Price              $0.000
  Market Value           $0.00
--------------------------------------------------------------------------------
P&L ANALYSIS:
  Closed Size                50.00
  Entry Price            $0.490
  Exit Price             $0.480
  P&L per Unit          -$0.010
  Realized P&L           -$0.50 (LOSS)
================================================================================

MARKET SUMMARY: 0x5b627c7b...
  Total Realized P&L:  -$0.50
  Total Trades:        1
  Win Rate:            0.0%
  Largest Loss:        -$0.50
```

---

## Additional Improvements

### 1. Track Unrealized PnL

For open positions, calculate mark-to-market PnL:

```python
def calculate_unrealized_pnl(token):
    """
    Calculate unrealized P&L for open position using current market price
    """
    position = get_position(token)
    
    if position['size'] == 0:
        return 0.0
    
    # Get current market price (mid of best bid/ask)
    market = get_market_from_token(token)
    if market not in global_state.all_data:
        return 0.0
    
    bids = global_state.all_data[market]['bids']
    asks = global_state.all_data[market]['asks']
    
    if not bids or not asks:
        return 0.0
    
    best_bid = max(bids.keys())
    best_ask = min(asks.keys())
    current_price = (best_bid + best_ask) / 2
    
    # Calculate unrealized PnL
    if position['size'] > 0:
        # Long position
        unrealized_pnl = position['size'] * (current_price - position['avgPrice'])
    else:
        # Short position
        unrealized_pnl = abs(position['size']) * (position['avgPrice'] - current_price)
    
    return unrealized_pnl
```

### 2. Include Fees in PnL

Polymarket charges fees on trades. Include them:

```python
def calculate_fees(size, price, side):
    """
    Calculate trading fees
    
    Polymarket fee structure (as of 2024):
    - Maker: -0.02% (rebate)
    - Taker: 0.08% (fee)
    """
    notional = size * price
    
    # Assume maker for limit orders
    maker_rebate = notional * 0.0002
    
    return -maker_rebate  # Negative = we receive rebate
```

Then update PnL:

```python
realized_pnl = closed_size * pnl_per_unit
fees = calculate_fees(trade_size, trade_price, side)
net_pnl = realized_pnl - fees  # Subtract fees (or add rebate if negative)
```

### 3. Include Rewards in PnL

Market making rewards should be included in total PnL:

```python
# Track rewards received per market
market_rewards = {}  # {market: total_rewards_usd}

# Update when rewards are claimed
def record_rewards(market, amount_usd):
    if market not in market_rewards:
        market_rewards[market] = 0.0
    market_rewards[market] += amount_usd

# Include in summary
total_pnl = realized_pnl + rewards - fees
```

### 4. Performance Metrics

Calculate useful metrics:

```python
def get_market_metrics(market):
    """
    Calculate performance metrics for a market
    """
    stats = global_state.market_pnl.get(market, {})
    
    if stats['trade_count'] == 0:
        return None
    
    win_rate = stats['wins'] / stats['trade_count'] * 100
    avg_pnl = stats['realized_pnl'] / stats['trade_count']
    
    profit_factor = abs(stats['largest_win'] / stats['largest_loss']) if stats['largest_loss'] != 0 else float('inf')
    
    return {
        'total_pnl': stats['realized_pnl'],
        'trade_count': stats['trade_count'],
        'win_rate': win_rate,
        'avg_pnl': avg_pnl,
        'profit_factor': profit_factor,
        'largest_win': stats['largest_win'],
        'largest_loss': stats['largest_loss']
    }
```

---

## Challenges & Considerations

### 1. **FIFO vs Weighted Average**

Current implementation uses **weighted average cost** for position tracking. This is correct for calculating PnL.

Alternative: **FIFO (First In, First Out)** - More complex but may be required for tax reporting.

### 2. **Token Pairs (Yes/No)**

Remember that markets have two tokens (Yes and No). Need to track both:

```python
# Market has condition_id
# Token1 = Yes token
# Token2 = No token

# If we're long Yes, we're short No (implicitly)
# Need to track both positions separately
```

### 3. **Partial Fills**

Orders can fill partially over multiple trades. Current implementation handles this correctly by updating position incrementally.

### 4. **Maker vs Taker**

The code already identifies if user is maker or taker. This affects:
- Fees (maker gets rebate, taker pays)
- Rewards (only makers earn rewards)

### 5. **Time Period for Rewards**

Rewards accrue based on time orders are live. Hard to attribute to specific trades. Best approach:
- Track total rewards per market
- Show separately from trading PnL
- Calculate combined return

---

## Implementation Checklist

- [ ] Add `calculate_pnl()` function to `data_utils.py`
- [ ] Modify `process_user_data()` to capture position before trade
- [ ] Call `calculate_pnl()` for every MATCHED trade
- [ ] Create enhanced `log_trade_with_pnl()` function
- [ ] Add cumulative PnL tracking to `global_state.py`
- [ ] Update PnL stats after each trade
- [ ] Add unrealized PnL calculation
- [ ] Include fees in PnL calculation
- [ ] Add market summary logging (periodically)
- [ ] Export PnL data to spreadsheet or file for analysis

---

## Benefits of PnL Tracking

### 1. **Immediate Feedback**
- See if strategies are working in real-time
- Identify losing markets quickly
- Adjust parameters based on results

### 2. **Performance Analysis**
- Compare markets side-by-side
- Calculate win rate, average PnL
- Identify best/worst performing markets

### 3. **Risk Management**
- Set stop-loss per market (if cumulative loss > X, stop trading)
- Identify adverse fill patterns
- Adjust trade sizes based on performance

### 4. **Debugging**
- Verify position tracking is correct
- Catch bugs in trade processing
- Understand why bot is losing money

### 5. **Reporting**
- Generate daily/weekly PnL reports
- Track overall portfolio performance
- Export for tax purposes

---

## Conclusion

**YES, calculating profit/loss on fills is definitely possible and highly recommended!**

**What we have:**
✅ Position tracking (size + average price)
✅ Trade data (size, price, side)
✅ All necessary information

**What we need to add:**
1. Capture position BEFORE updating (simple)
2. Calculate PnL using formula (straightforward)
3. Enhanced logging (cosmetic)
4. Cumulative tracking (optional but useful)

**Estimated effort:** 2-3 hours for basic implementation

**Value:** EXTREMELY HIGH - Essential for understanding bot performance

---

## Next Steps

1. **Implement basic PnL calculation first** - Get realized PnL on every close
2. **Add enhanced logging** - Make it easy to see wins/losses
3. **Add cumulative tracking** - Track total PnL per market
4. **Add summary reports** - Periodic summary of performance
5. **Add unrealized PnL** - Show mark-to-market value
6. **Include fees and rewards** - Complete picture of profitability

Start with steps 1-2, then iterate based on what insights you need.

---

*Analysis completed: November 18, 2025*

