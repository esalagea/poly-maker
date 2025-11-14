# Log Formatting Improvements

## Changes Made

Updated the event logs for TRADE and ORDER events to use a prettier, more readable table format similar to the trading state summaries.

## Trade Event Format

### Before (hard to read):
```
TRADE EVENT FOR:  0x5b627c7b2f82ea92dfb69650a87724664ad771d33ff838c11907efa71c5a4d61 ID:  9783975c-7fc4-47aa-a484-fb0ad28ad768 STATUS:  CONFIRMED  SIDE:  SELL   MAKER OUTCOME:    TAKER OUTCOME:  No  PROCESSED SIDE:  sell  SIZE:  50.0 PRICE:  0.09
```

### After (nicely formatted):
```
================================================================================
TRADE EVENT: 0x5b627c7b2f82ea92dfb69650a87724664ad771d33ff838c
--------------------------------------------------------------------------------
ID                   9783975c-7fc4-47aa-a484-fb0ad28ad768
STATUS               CONFIRMED
SIDE (raw)           SELL
SIDE (processed)     SELL
MAKER OUTCOME        N/A
TAKER OUTCOME        No
SIZE                 50.00
PRICE                $0.090
TOKEN                0x5b627c7b2f82ea...
================================================================================
```

## Order Event Format

### Before (hard to read):
```
ORDER EVENT FOR:  0x5b627c7b2f82ea92dfb69650a87724664ad771d33ff838c11907efa71c5a4d61  STATUS:  LIVE  TYPE:  GTC  SIDE:  buy  ORIGINAL SIZE:  50  SIZE MATCHED:  0
```

### After (nicely formatted):
```
================================================================================
ORDER EVENT: 0x5b627c7b2f82ea92dfb69650a87724664ad771d33ff838c
--------------------------------------------------------------------------------
STATUS               LIVE
TYPE                 GTC
SIDE                 BUY
ORIGINAL SIZE        50.00
SIZE MATCHED         0.00
REMAINING SIZE       50.00
PRICE                $0.090
TOKEN                0x5b627c7b2f82ea...
================================================================================
```

## Features

✅ **Clear visual separation** with `=` and `-` dividers
✅ **Left-aligned labels** with consistent 20-character width for easy scanning
✅ **Properly formatted values** (2 decimal places for sizes, 3 for prices)
✅ **Calculated REMAINING SIZE** field for quick reference (ORDER events)
✅ **Distinguishes raw vs processed side** to help debug token flipping logic (TRADE events)
✅ **Shows both maker and taker outcomes** for clarity
✅ **Truncated token IDs** for readability (first 16 chars)
✅ **Uppercase SIDE** for consistency
✅ **Similar style** to the market position logs for consistency

## Files Modified

- `poly_data/data_processing.py`:
  - Updated TRADE event logging (line ~125)
  - Updated ORDER event logging (line ~175)

---
*Implemented on: November 14, 2025*

