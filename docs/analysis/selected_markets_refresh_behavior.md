# Selected Markets Spreadsheet - Refresh Behavior

## Summary

The "Selected Markets" spreadsheet is read **periodically at two different intervals** depending on which script is running:

### In the Trading Bot (`main.py`):
- **Initial load**: Once at startup
- **Periodic refresh**: Every **30 seconds** (via `update_markets()` called in the background thread)

### In the Market Data Updater (`update_markets.py`):
- **Periodic refresh**: Every **5 minutes** (300 seconds)

## Detailed Explanation

### Trading Bot Flow (`main.py`)

#### 1. Startup (One-time)
```python
def main():
    global_state.client = PolymarketClient()
    update_once()  # ← Calls update_markets() which reads Selected Markets
```

#### 2. Background Thread (Continuous)
```python
def update_periodically():
    while True:
        time.sleep(5)  # Update every 5 seconds
        
        # Update positions and orders every cycle
        update_positions(avgOnly=True)
        update_orders()

        # Update market data every 12th cycle (60 seconds)
        if i % 12 == 0:
            update_markets()  # ← Re-reads Selected Markets here
```

**Refresh rate**: Every **60 seconds** (12 cycles × 5 seconds)

### How Markets Are Loaded

**File**: `poly_data/utils.py` → `get_sheet_df()`

```python
def get_sheet_df():
    spreadsheet = get_spreadsheet()
    
    # Read Selected Markets
    wk = spreadsheet.worksheet('Selected Markets')
    df = pd.DataFrame(wk.get_all_records())
    df = df[df['question'] != ""].reset_index(drop=True)
    
    # Read All Markets  
    wk2 = spreadsheet.worksheet('All Markets')
    df2 = pd.DataFrame(wk2.get_all_records())
    
    # MERGE: Only keeps markets that exist in BOTH sheets
    result = df.merge(df2, on='question', how='inner')
    
    return result, hyperparams
```

**Key Point**: The system does an **inner merge** between Selected Markets and All Markets. This means:
- Only markets that appear in **both** sheets will be traded
- If you add a market to Selected Markets but it's not in All Markets, it will be ignored
- If a market exists in All Markets but not Selected Markets, it won't be traded

### Market Data Updater Flow (`update_markets.py`)

```python
def fetch_and_process_data(ONLY_SELECTED_MARKETS):
    # Re-read Selected Markets at the START of each iteration
    sel_df = get_sel_df(spreadsheet, "Selected Markets")
    
    all_df = get_all_markets(client)  # Fetch all markets from API
    
    if ONLY_SELECTED_MARKETS and len(sel_df) > 0:
        # Filter to only process selected markets
        selected_questions = sel_df['question'].tolist()
        filtered_df = all_df[all_df['question'].isin(selected_questions)]
        all_results = get_all_results(filtered_df, client)
    else:
        all_results = get_all_results(all_df, client)

# Main loop
while True:
    fetch_and_process_data(ONLY_SELECTED_MARKETS)
    time.sleep(60 * 5)  # ← Wait 5 minutes
```

**Refresh rate**: Every **5 minutes** (300 seconds)

## What Happens If You Modify Selected Markets?

### Scenario 1: Adding a New Market

1. You add a market to "Selected Markets" sheet
2. **Trading bot** will pick it up within **60 seconds**
3. It will start trading on that market if:
   - ✅ The market exists in "All Markets" sheet
   - ✅ The market has valid token IDs
   - ✅ All required fields are populated

### Scenario 2: Removing a Market

1. You remove a market from "Selected Markets" sheet
2. **Trading bot** will detect the change within **60 seconds**
3. It will **stop trading** on that market:
   - WebSocket subscriptions will continue (tokens list already set)
   - But `perform_trade()` won't execute because market won't be in `global_state.df`
   - Existing orders will remain open (you need to cancel manually or let them fill)

### Scenario 3: Modifying Market Parameters

If you change parameters like `trade_size`, `min_size`, `stop_loss_threshold`, etc.:
1. Changes will be picked up within **60 seconds**
2. New orders will use the updated parameters
3. Existing orders will not be affected until they're replaced

### Scenario 4: Market Disappeared from All Markets

If a market is in "Selected Markets" but gets removed from "All Markets":
1. After the next refresh, it will be excluded from trading (inner merge)
2. The bot will stop managing orders for that market
3. You won't get an error, but the market will be silently ignored

## Current Limitations

### WebSocket Token List Not Updated

**Important**: The `global_state.all_tokens` list is built at startup and only refreshed every 60 seconds via `update_markets()`. However, the WebSocket connection uses the token list from when it was created.

```python
# WebSockets use token list from connection time
await asyncio.gather(
    connect_market_websocket(global_state.all_tokens),  # ← Fixed at connection time
    connect_user_websocket()
)
```

**Implication**: If you add a completely new market:
- The trading bot will try to trade it after 60 seconds
- But it won't receive live order book updates until WebSocket reconnects
- WebSockets auto-reconnect on errors, which will pick up new tokens

## Recommendations

### To Add a Market Dynamically:

1. ✅ Add market to "Selected Markets" sheet
2. ✅ Ensure market exists in "All Markets" sheet
3. ✅ Wait 60 seconds for trading bot to pick it up
4. ⚠️ Optionally restart bot to ensure WebSocket subscribes to new token

### To Remove a Market Dynamically:

1. ✅ Remove market from "Selected Markets" sheet
2. ✅ Wait 60 seconds for trading bot to stop managing it
3. ⚠️ Manually cancel any open orders if needed (or let them fill)

### To Modify Parameters:

1. ✅ Update values in "Selected Markets" sheet
2. ✅ Wait 60 seconds for changes to take effect
3. ✅ Monitor logs to confirm new parameters are being used

## Code References

### Key Files:
- `main.py` - Main trading bot entry point
- `poly_data/data_utils.py` - `update_markets()` function
- `poly_data/utils.py` - `get_sheet_df()` function that reads sheets
- `update_markets.py` - Market data updater script

### Key Functions:
- `update_markets()` - Refreshes market data from Google Sheets
- `get_sheet_df()` - Reads and merges Selected Markets + All Markets
- `update_periodically()` - Background thread that calls update_markets() every 60 seconds

---
*Documented on: November 14, 2025*

