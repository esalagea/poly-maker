# Fix: Incorrect Usage of `volatility/reward` in `analyze_market_quality`

## Issue Found

The `volatility/reward` ratio was being **incorrectly interpreted** in the `analyze_market_quality` function.

### How the Field is Calculated (in `update_markets.py`):
```python
volatility/reward = gm_reward_per_100 / volatility_sum
```

**Meaning**: Reward dollars earned per unit of volatility risk
- **Higher values** = Better (more reward per risk)
- **Example**: 3.5 = $3.50 reward per volatility unit

### The Bugs:

#### Bug #1: Inverted Logic
**Before (INCORRECT):**
```python
if volatility_reward_ratio <= 0.05:  # Low volatility relative to rewards
    score += 10
elif volatility_reward_ratio <= 0.1:
    score += 8
```
- This treated **lower values as better** ❌
- Gave highest scores to markets with low rewards relative to volatility
- Opposite of what the metric represents!

**After (CORRECT):**
```python
if volatility_reward_ratio >= 2.0:  # Excellent reward/risk ratio
    score += 10
elif volatility_reward_ratio >= 1.0:  # Good reward/risk ratio
    score += 8
elif volatility_reward_ratio >= 0.5:  # Fair reward/risk ratio
    score += 5
```
- Now treats **higher values as better** ✅
- Rewards markets with high rewards relative to volatility
- Correct interpretation!

#### Bug #2: Type Error
**Before:**
```python
volatility_reward_ratio = row['volatilty/reward']
```
- The field is stored as a **string** in the dataframe (`.astype(str)` in update_markets.py)
- Numeric comparisons would fail or behave incorrectly

**After:**
```python
try:
    volatility_reward_ratio = float(row['volatilty/reward'])
except (ValueError, TypeError):
    volatility_reward_ratio = 0
```
- Properly converts to float ✅
- Handles errors gracefully

## Impact

### Before Fix:
- Markets with **poor** reward/risk ratios (0.05) got 10 points
- Markets with **excellent** reward/risk ratios (3.0) got 0 points and an issue flag
- Quality scores were **inverted**

### After Fix:
- Markets with excellent reward/risk ratios (≥2.0) get 10 points
- Markets with good reward/risk ratios (≥1.0) get 8 points  
- Markets with fair reward/risk ratios (≥0.5) get 5 points
- Markets with poor reward/risk ratios (<0.5) get 0 points

## New Scoring Thresholds:

- **≥2.0**: Excellent (10 points) - $2+ reward per volatility unit
- **≥1.0**: Good (8 points) - $1+ reward per volatility unit
- **≥0.5**: Fair (5 points) - $0.50+ reward per volatility unit
- **<0.5**: Poor (0 points) - Less than $0.50 reward per volatility unit

## Column Name Fix

Also changed the column name from `'volatilty/reward'` (typo) to `'reward/volatility'` (correct) to:
- ✅ Accurately reflect the calculation (reward ÷ volatility)
- ✅ Fix the spelling error
- ✅ Make the metric more intuitive to understand

---
*Fixed on: November 14, 2025*

