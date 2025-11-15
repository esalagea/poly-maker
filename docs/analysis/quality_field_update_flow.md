# Quality Field Update Flow - Selected Markets Spreadsheet

## Summary

The `quality` field in the "Selected Markets" spreadsheet is updated **every time the trading bot evaluates a market** during its normal trading loop.

## Update Flow

### 1. Trading Bot Loop (`trading.py`)

Every time `perform_trade(market)` is called for a market:

```python
async def perform_trade(market):
    # Line 325: Analyze market quality
    market_quality_df = analyze_market_quality(market, row, params)
    
    # Line 326: Save quality data (which updates Selected Markets)
    save_market_quality_data(market_quality_df)
```

**Frequency**: 
- Triggered by WebSocket events (order book updates, trades)
- Potentially **multiple times per second** per market when market is active
- Rate-limited by the `save_market_quality_data` function

### 2. Quality Analysis (`poly_data/analysis_utils.py`)

The `analyze_market_quality()` function calculates a quality score (0-100) based on:
- Spread (20 points)
- Liquidity balance (20 points)
- Total liquidity (15 points)
- Market depth (15 points)
- Top of book liquidity (10 points)
- Price continuity (10 points)
- **Reward/volatility ratio (10 points)** ← Fixed to use correct logic

Returns a DataFrame with the score and other metrics.

### 3. Save Quality Data (`update_markets.py`)

#### Main Function: `save_market_quality_data()`

**Location**: `update_markets.py`, line 81

**What it does**:
1. Saves market quality to "Markets Quality" worksheet (historical record)
2. Calls `_update_selected_markets_quality()` to update the Selected Markets tab

**Rate Limiting**:
```python
# Check global timing constraint - must be at least 1 minute since last spreadsheet update
if last_spreadsheet_update is not None:
    time_since_last_global_update = current_time - last_spreadsheet_update
    if time_since_last_global_update.total_seconds() < 60:  # 60 seconds
        return  # Skip update
```

**Result**: The quality field is updated **at most once per minute** per market.

#### Helper Function: `_update_selected_markets_quality()`

**Location**: `update_markets.py`, line 170

**What it does**:
1. Extracts the `question` and `score` from the market quality DataFrame
2. Gets the "Selected Markets" worksheet from Google Sheets
3. Reads all data from the worksheet
4. Finds the row matching the question
5. Creates a `quality` column if it doesn't exist
6. Updates the quality value for that row
7. Writes the entire worksheet back to Google Sheets

**Code snippet**:
```python
def _update_selected_markets_quality(market_quality_df):
    # Extract question and score
    question = market_quality_df['question'].iloc[0]
    quality_score = market_quality_df.get('score', pd.Series([None])).iloc[0]
    
    # Get the Selected Markets worksheet
    wk_selected = spreadsheet.worksheet("Selected Markets")
    selected_df = get_as_dataframe(wk_selected)
    
    # Find matching question row
    matching_rows = selected_df[selected_df['question'] == question]
    
    if matching_rows.empty:
        return  # Question not found, skip
    
    # Update quality field
    row_index = matching_rows.index[0]
    if 'quality' not in selected_df.columns:
        selected_df['quality'] = ''
    selected_df.loc[row_index, 'quality'] = quality_score
    
    # Write back to Google Sheets
    update_sheet(selected_df, wk_selected)
```

## Complete Flow Diagram

```
WebSocket Event (order book update)
    ↓
perform_trade(market) triggered
    ↓
analyze_market_quality() calculates score (0-100)
    ↓
save_market_quality_data() called
    ↓
    ├─ Rate limit check (60 second minimum)
    ↓
    ├─ Save to "Markets Quality" worksheet (historical)
    ↓
    └─ Call _update_selected_markets_quality()
        ↓
        ├─ Read "Selected Markets" sheet
        ↓
        ├─ Find row matching question
        ↓
        ├─ Update 'quality' column with score
        ↓
        └─ Write entire sheet back to Google Sheets
```

## Update Frequency

### Per Market:
- **Maximum**: Once per minute (due to rate limiting)
- **Typical**: Once per minute when market is active
- **Minimum**: Only when market is traded/evaluated

### Overall:
- If you have 10 markets in "Selected Markets"
- Each could potentially update once per minute
- In practice: Updates happen when markets have activity

## Important Notes

### 1. Only Updates Markets in Selected Markets
The function silently returns if a market is not found in Selected Markets:
```python
if matching_rows.empty:
    return  # Question not found in Selected Markets, skip silently
```

### 2. Quality Column Auto-Created
If the `quality` column doesn't exist in the Selected Markets sheet, it's automatically created:
```python
if 'quality' not in selected_df.columns:
    selected_df['quality'] = ''
```

### 3. Rate Limiting
The global `last_spreadsheet_update` timestamp ensures we don't spam Google Sheets API:
- Minimum 60 seconds between any spreadsheet updates
- Applies across ALL markets
- Prevents API rate limit errors

### 4. Error Handling
The function has comprehensive error handling and will:
- Skip silently if worksheet not found
- Skip silently if question not found
- Print errors to console (not market logs)
- Never crash the trading bot

## When Quality is NOT Updated

The quality field will NOT be updated if:
1. ❌ Less than 60 seconds since last spreadsheet update (any worksheet)
2. ❌ Market not found in "Selected Markets" worksheet
3. ❌ "Selected Markets" worksheet doesn't exist
4. ❌ Question column doesn't exist in the worksheet
5. ❌ Market making is set to STOP (quality calculated but not saved)

## Viewing Quality Updates

### In Google Sheets:
1. Open "Selected Markets" worksheet
2. Look for the `quality` column (auto-created if missing)
3. Values range from 0-100 (higher is better)
4. Empty values mean market hasn't been evaluated yet or failed quality checks

### In Markets Quality Worksheet:
- Historical record of all quality calculations
- Includes timestamp (`last_updated` column)
- Contains detailed breakdown of scoring factors

## Code References

### Key Files:
- `trading.py` (line 326) - Calls `save_market_quality_data()`
- `update_markets.py` (line 81) - `save_market_quality_data()` function
- `update_markets.py` (line 170) - `_update_selected_markets_quality()` function
- `poly_data/analysis_utils.py` - `analyze_market_quality()` function

### Key Functions:
- `perform_trade()` - Main trading loop that triggers quality updates
- `analyze_market_quality()` - Calculates quality score (0-100)
- `save_market_quality_data()` - Saves to Markets Quality sheet and triggers Selected Markets update
- `_update_selected_markets_quality()` - Updates the quality column in Selected Markets

---
*Documented on: November 15, 2025*

