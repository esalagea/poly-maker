# Hard-Stop vs Scoring Conditions Analysis

## Date: November 18, 2025

---

## Current State

### ✅ Already Implemented as Hard-Stops

1. **Missing Order Book Data** (lines 19-26)
   - **Hard-Stop:** Return immediately with score=0
   - **Why Correct:** Cannot trade without order book data - this is fundamental

2. **Excessive Volatility** (lines 29-38)
   - **Hard-Stop:** Return immediately with score=0 if `3_hour > volatility_threshold`
   - **Why Correct:** Absolute risk threshold - protects from catastrophic losses

### 📊 Currently Scoring-Only (7 Conditions)

All other conditions contribute to a cumulative score (0-100) rather than hard-failing.

---

## Analysis: Which Conditions Should Be Hard-Stops?

### Evaluation Criteria

A condition should be a **hard-stop** if:
1. ✅ **Binary safety issue** - Trading would be dangerous/impossible, not just suboptimal
2. ✅ **No compensating factors** - Other good qualities cannot offset this risk
3. ✅ **Immediate consequence** - The risk materializes quickly and predictably
4. ✅ **Clear threshold** - There's an objective line between "acceptable" and "unacceptable"

A condition should be **scoring-only** if:
1. ✅ **Gradual risk** - More of it is worse, but small amounts are tolerable
2. ✅ **Can be compensated** - Other positive factors can balance the negative
3. ✅ **Subjective threshold** - Different strategies might have different preferences
4. ✅ **Context-dependent** - Sometimes acceptable, sometimes not

---

## Condition-by-Condition Analysis

### 1. Spread Check (Currently: Scoring, 20 points)

**Current Logic:**
- ≤2% spread → 20 points (excellent)
- ≤5% spread → 15 points (good)
- ≤10% spread → 8 points (fair)
- >10% spread → 0 points (poor)

**Should it be a hard-stop?**

**❌ NO - Keep as scoring**

**Reasoning:**
- **Gradual risk:** 11% spread is only slightly worse than 10%
- **Can compensate:** Wide spread might be acceptable if rewards are high
- **Context-dependent:** Low-liquidity markets naturally have wider spreads
- **Market-specific:** Some markets justify wider spreads (e.g., far-future events)

**However:** Consider a **soft hard-stop** at extreme values (e.g., >25% spread)

**Recommendation:**
```python
# Add extreme spread hard-stop
if spread_pct > 25:  # Catastrophically wide spread
    return pd.DataFrame([{
        "market": market,
        "suitable": False,
        "score": 0,
        "recommendation": "POOR - Spread too wide",
        "reason": f"Spread {spread_pct:.1f}% exceeds maximum (25%)"
    }])
```

**Priority:** ⚠️ MEDIUM - Useful for extreme cases but not critical

---

### 2. Liquidity Balance (Currently: Scoring, 20 points)

**Current Logic:**
- Balance ratio ≥0.7 → 20 points
- Balance ratio ≥0.5 → 15 points
- Balance ratio ≥0.3 → 8 points
- Balance ratio <0.3 → 0 points

**Should it be a hard-stop?**

**⚠️ MAYBE - Consider hard-stop at extreme imbalance**

**Reasoning:**

**Why it SHOULD be a hard-stop:**
- **Execution risk:** Severe imbalance (e.g., 95% bids, 5% asks) means you can buy but cannot sell
- **Adverse selection:** Extreme imbalance often signals informed trading (someone knows something)
- **Getting stuck:** You could accumulate a position you cannot exit
- **Immediate risk:** The imbalance exists NOW, not gradually

**Why it SHOULD stay scoring:**
- **Temporary condition:** Imbalance can resolve quickly
- **Natural fluctuation:** Markets have temporary imbalances all the time
- **Strategy-dependent:** Some strategies exploit imbalances

**Recommendation:**
```python
# Hard-stop on EXTREME imbalance
if balance_ratio < 0.1:  # 90/10 or worse
    return pd.DataFrame([{
        "market": market,
        "suitable": False,
        "score": 0,
        "recommendation": "POOR - Liquidity severely imbalanced",
        "reason": f"Balance ratio {balance_ratio:.2f} indicates one-sided market"
    }])
```

**Priority:** 🔴 HIGH - Protects from getting stuck in positions

---

### 3. Total Liquidity (Currently: Scoring, 15 points)

**Current Logic:**
- Total liquidity ≥ min_total_liquidity → 15 points
- Total liquidity ≥ 50% of min → 10 points
- Total liquidity <50% of min → 0 points

**Should it be a hard-stop?**

**✅ YES - Should be hard-stop at critical minimum**

**Reasoning:**

**Why it SHOULD be a hard-stop:**
- **Execution impossible:** If total liquidity < your trade size, you literally cannot trade
- **Slippage risk:** Insufficient liquidity guarantees poor fills
- **Market manipulation:** Thin markets are easily manipulated
- **Binary threshold:** Either there's enough liquidity to trade or there isn't
- **No compensation:** No amount of good spread or balance helps if you can't execute

**Calculation:**
```
Minimum required liquidity = trade_size * 2  (for both buy and sell)
```

If total liquidity is less than this, you cannot operate.

**Recommendation:**
```python
# Hard-stop on insufficient liquidity
required_liquidity = trade_size * 2  # Need liquidity for both sides
if total_liquidity < required_liquidity:
    return pd.DataFrame([{
        "market": market,
        "suitable": False,
        "score": 0,
        "recommendation": "POOR - Insufficient liquidity",
        "reason": f"Total liquidity {total_liquidity:.0f} below minimum {required_liquidity:.0f}"
    }])
```

**Priority:** 🔴 HIGH - Fundamental requirement for trading

---

### 4. Market Depth (Currently: Scoring, 15 points)

**Current Logic:**
- ≥5 price levels → 15 points
- ≥3 price levels → 10 points
- ≥2 price levels → 5 points
- <2 price levels → 0 points

**Should it be a hard-stop?**

**⚠️ MAYBE - Consider hard-stop at 1 level**

**Reasoning:**

**Why it SHOULD be a hard-stop:**
- **Execution risk:** Only 1 price level means no backup if that level disappears
- **Fragile market:** Single level can vanish instantly
- **Binary safety:** 1 level = extremely dangerous, 2 levels = much safer

**Why it SHOULD stay scoring:**
- **Gradual improvement:** 2 vs 3 vs 5 levels is a smooth gradient
- **Dynamic:** Levels can appear/disappear quickly
- **Some markets operate fine with 2-3 levels

**Recommendation:**
```python
# Hard-stop on single price level
min_levels = min(bid_levels, ask_levels)
if min_levels < 2:  # Only 1 level (or 0, but that's caught earlier)
    return pd.DataFrame([{
        "market": market,
        "suitable": False,
        "score": 0,
        "recommendation": "POOR - Market too shallow",
        "reason": f"Only {min_levels} price level(s) - market too fragile"
    }])
```

**Priority:** 🟡 MEDIUM - Good protection but not critical (2 levels might be enough)

---

### 5. Top-of-Book vs Trade Size (Currently: Scoring, 10 points)

**Current Logic:**
- Top book ≥ 3× trade_size → 10 points
- Top book ≥ 2× trade_size → 8 points
- Top book ≥ 1× trade_size → 5 points
- Top book < 1× trade_size → 0 points

**Should it be a hard-stop?**

**✅ YES - Should be hard-stop when top book < trade_size**

**Reasoning:**

**Why it SHOULD be a hard-stop:**
- **Guaranteed slippage:** If best bid/ask can't fill your order, you WILL get worse prices
- **Partial fills:** Your order gets split across multiple price levels
- **Adverse movement:** Large order relative to top book moves the market against you
- **Binary threshold:** Either top book can handle your size or it can't
- **Immediate consequence:** This happens on EVERY trade

**This is critical for market making:**
- You need to place orders of size `trade_size`
- If top book can't absorb that, your fills will be poor
- You'll be constantly taking worse prices

**Recommendation:**
```python
# Hard-stop when top book cannot handle trade size
if top_book_liquidity < trade_size:
    return pd.DataFrame([{
        "market": market,
        "suitable": False,
        "score": 0,
        "recommendation": "POOR - Top book too thin",
        "reason": f"Top book liquidity {top_book_liquidity:.0f} below trade size {trade_size:.0f}"
    }])
```

**Priority:** 🔴 HIGH - Direct impact on every trade execution

---

### 6. Price Continuity (Currently: Scoring, 10 points)

**Current Logic:**
- Gaps ≤ 3× tick_size → 10 points
- Gaps ≤ 6× tick_size → 5 points
- Gaps > 6× tick_size → 0 points

**Should it be a hard-stop?**

**❌ NO - Keep as scoring**

**Reasoning:**
- **Gradual risk:** Larger gaps are worse, but not catastrophic
- **Can work around:** You can adjust your order prices to avoid gaps
- **Temporary condition:** Gaps can fill quickly as market evolves
- **Market-dependent:** Low-liquidity markets naturally have larger gaps

**Exception:** Crossed market (bid > ask) should be hard-stop, but that's caught earlier

**Priority:** ✅ KEEP AS SCORING - Not critical enough for hard-stop

---

### 7. Volatility vs Reward Ratio (Currently: Scoring, 10 points)

**Current Logic:**
- Ratio ≥ 2 → 10 points
- Ratio ≥ 1 → 8 points
- Ratio ≥ 0.5 → 5 points
- Ratio < 0.5 → 0 points

**Should it be a hard-stop?**

**❌ NO - Keep as scoring (already have absolute volatility hard-stop)**

**Reasoning:**
- **Already protected:** Absolute volatility threshold (hard-stop) handles extreme cases
- **Risk/reward tradeoff:** This is exactly the type of thing that should be scored
- **Strategy-dependent:** Some traders accept higher volatility for higher rewards
- **Gradual spectrum:** No clear binary threshold

**Current approach is correct:**
- Absolute volatility → Hard-stop (safety limit)
- Volatility/reward ratio → Scoring (quality assessment)

**Priority:** ✅ KEEP AS SCORING - Correct design

---

## Summary: Recommendations

### 🔴 HIGH PRIORITY - Should Be Hard-Stops

| Condition | Current | Should Be | Threshold | Why |
|-----------|---------|-----------|-----------|-----|
| **Total Liquidity** | Scoring | Hard-Stop | `< trade_size × 2` | Cannot execute trades |
| **Top Book vs Trade Size** | Scoring | Hard-Stop | `< trade_size` | Guaranteed slippage on every trade |
| **Liquidity Balance** | Scoring | Hard-Stop | `< 0.1` (extreme) | One-sided market, can't exit positions |

### 🟡 MEDIUM PRIORITY - Consider Hard-Stops

| Condition | Current | Should Be | Threshold | Why |
|-----------|---------|-----------|-----------|-----|
| **Market Depth** | Scoring | Hard-Stop | `< 2 levels` | Market too fragile |
| **Spread Width** | Scoring | Hard-Stop | `> 25%` (extreme) | Catastrophically wide |

### ✅ CORRECT AS-IS - Keep Scoring

| Condition | Current | Keep As | Why |
|-----------|---------|---------|-----|
| **Spread (normal range)** | Scoring | Scoring | Gradual risk, context-dependent |
| **Balance (normal range)** | Scoring | Scoring | Temporary fluctuations acceptable |
| **Liquidity (above minimum)** | Scoring | Scoring | More is better, but gradual |
| **Depth (2+ levels)** | Scoring | Scoring | 2 vs 5 levels is a gradient |
| **Top book (above minimum)** | Scoring | Scoring | More cushion is better |
| **Price Continuity** | Scoring | Scoring | Can work around gaps |
| **Volatility/Reward** | Scoring | Scoring | Already have absolute vol hard-stop |

---

## Implementation Priority Order

### Phase 1: Critical Safety (Implement ASAP) 🔴

These prevent you from getting stuck or suffering immediate losses:

1. **Top Book vs Trade Size** - Guarantees slippage
2. **Total Liquidity** - Cannot execute at all
3. **Extreme Liquidity Imbalance** - Cannot exit positions

### Phase 2: Additional Protection (Implement Soon) 🟡

These prevent edge cases and very risky situations:

4. **Market Depth < 2 levels** - Too fragile
5. **Extreme Spread > 25%** - Unreasonable costs

### Phase 3: Keep Current Approach ✅

These are correctly handled by scoring:
- Spread (normal range)
- Balance (normal range)
- Depth (2+ levels)
- Continuity
- Volatility/reward ratio

---

## Risk Assessment by Condition

### Critical Risks (Need Hard-Stops)

**1. Top Book < Trade Size**
- **What happens:** Every trade gets split across multiple levels
- **Consequence:** Worse prices on 100% of trades
- **Financial impact:** Immediate and continuous
- **Can compensate?** No - this affects every execution

**2. Total Liquidity < Minimum**
- **What happens:** Cannot place orders of required size
- **Consequence:** Either don't trade or take massive slippage
- **Financial impact:** Makes trading impossible or unprofitable
- **Can compensate?** No - need basic liquidity to operate

**3. Extreme Imbalance (ratio < 0.1)**
- **What happens:** Market is 90%+ on one side
- **Consequence:** Can enter position but cannot exit
- **Financial impact:** Get stuck, forced to accept terrible prices
- **Can compensate?** No - being stuck is binary

### Moderate Risks (Consider Hard-Stops)

**4. Market Depth < 2 Levels**
- **What happens:** Only 1 price level per side
- **Consequence:** Market can disappear instantly
- **Financial impact:** High but not guaranteed
- **Can compensate?** Somewhat - quick reactions help

**5. Extreme Spread > 25%**
- **What happens:** Massive cost to cross spread
- **Consequence:** Need huge price moves to profit
- **Financial impact:** High but might be worth it for some markets
- **Can compensate?** Yes - if rewards are extraordinary

### Acceptable Risks (Keep Scoring)

All other conditions represent **gradual risk increases** that can be balanced against rewards and other factors.

---

## Code Structure Recommendation

```python
def analyze_market_quality(market, row, params):
    # PHASE 1: Hard-Stop Checks (Binary Pass/Fail)
    # - Order book exists
    # - Absolute volatility
    # - Total liquidity minimum
    # - Top book minimum
    # - Extreme imbalance
    # - [Optional] Extreme spread
    # - [Optional] Minimum depth
    
    # PHASE 2: Quality Scoring (0-100)
    # - Spread (normal range)
    # - Balance (normal range)
    # - Liquidity (above minimum)
    # - Depth (above minimum)
    # - Continuity
    # - Volatility/reward
    
    # PHASE 3: Final Decision
    # - If score >= min_market_quality → SUITABLE
    # - If score < min_market_quality → NOT SUITABLE
```

---

## Philosophy: Hard-Stop vs Scoring

### Use Hard-Stops For:
- **Safety limits** - Prevents dangerous situations
- **Binary requirements** - Either you can trade or you can't
- **Immediate risks** - Consequences happen on every trade
- **Non-compensable** - No other factor makes this acceptable

### Use Scoring For:
- **Quality assessment** - Better vs worse, not safe vs unsafe
- **Gradual spectrum** - Small differences matter
- **Context-dependent** - Sometimes acceptable, sometimes not
- **Compensable risks** - Can be offset by other positives

### Current Design is Good!
The function already does this well:
- **2 hard-stops** (order book, volatility)
- **7 scoring conditions** (everything else)

Recommendation is to add **3 more hard-stops** for critical safety, keeping most conditions as scoring.

---

## Testing Strategy

After implementing hard-stops:

### Test 1: Each Hard-Stop Individually
- Create market scenario that fails each hard-stop
- Verify: score=0, suitable=False
- Verify: No subsequent processing (immediate return)

### Test 2: Just Above Hard-Stop Thresholds
- Market barely passes hard-stop (e.g., liquidity = trade_size × 2.01)
- Verify: Passes hard-stop, proceeds to scoring
- Score might be low, but not hard-failed

### Test 3: Multiple Failing Conditions
- Market fails hard-stop AND has low score
- Verify: Hard-stop triggers first (immediate return)
- Should not see scoring logic execute

### Test 4: Good Market
- Market passes all hard-stops with room to spare
- Verify: Normal scoring behavior
- High-quality markets get high scores

---

## Final Recommendation Summary

**Implement 3 new hard-stops (HIGH PRIORITY):**

1. ✅ Total liquidity < trade_size × 2
2. ✅ Top book liquidity < trade_size  
3. ✅ Balance ratio < 0.1 (extreme imbalance)

**Consider 2 additional hard-stops (MEDIUM PRIORITY):**

4. ⚠️ Market depth < 2 levels
5. ⚠️ Spread > 25%

**Keep current scoring for everything else.**

This balances safety (preventing catastrophic situations) with flexibility (allowing varied market conditions).

---

*Analysis completed: November 18, 2025*

