import poly_data.global_state as global_state
import pandas as pd
from sortedcontainers import SortedDict

def analyze_market_quality(market, row, params):
    """
    Analyze if a market is suitable for market making

    Args:
        market: market identifier
        row: pandas Series with market data including volatility, spreads, etc.
        params: dict with analysis parameters like min_total_liquidity

    Returns:
        pandas DataFrame with single row containing analysis results
    """
    bids = global_state.all_data[market]['bids']
    asks = global_state.all_data[market]['asks']
    min_total_liquidity = params['min_total_liquidity']

    blocker_issues_count = 0

    if not bids or not asks:
        return pd.DataFrame([{
            "market": market,
            "suitable": False,
            "score": 0,
            "recommendation": "POOR - Missing bids or asks",
            "reason": "Missing order book data"
        }])

    # Hard-fail on excessive volatility (absolute threshold check)
    volatility_threshold = params.get('volatility_threshold', 300)
    if row['3_hour'] > volatility_threshold:
        return pd.DataFrame([{
            "market": market,
            "suitable": False,
            "score": 0,
            "recommendation": "POOR - Volatility too high",
            "reason": f"3-hour volatility ({row['3_hour']}) exceeds threshold ({volatility_threshold})"
        }])

    # Get tick size from row
    tick_size = row['tick_size']

    # Sort prices
    sorted_bids = list(reversed(list(bids.items())))  # Highest first
    sorted_asks = list(asks.items())  # Lowest first

    best_bid_price, best_bid_size = sorted_bids[0]
    best_ask_price, best_ask_size = sorted_asks[0]

    # 1. Calculate spread metrics
    spread = best_ask_price - best_bid_price
    mid_price = (best_bid_price + best_ask_price) / 2
    spread_pct = (spread / mid_price) * 100

    # Compare with expected spread from row
    expected_spread = row['spread']
    spread_vs_expected = spread / expected_spread if expected_spread > 0 else 0

    # 2. Check liquidity balance
    total_bid_liquidity = sum(bids.values())
    total_ask_liquidity = sum(asks.values())
    total_liquidity = total_bid_liquidity + total_ask_liquidity

    # Calculate balance ratio (closer to 1.0 = better balanced)
    if total_ask_liquidity > 0 and total_bid_liquidity > 0:
        balance_ratio = min(total_bid_liquidity, total_ask_liquidity) / max(total_bid_liquidity, total_ask_liquidity)
    else:
        balance_ratio = 0

    # 3. Check depth at multiple levels
    bid_levels = len([price for price, size in sorted_bids if size > 0])
    ask_levels = len([price for price, size in sorted_asks if size > 0])

    # 4. Check top-of-book liquidity relative to trade size
    trade_size = row['trade_size']
    min_size = row['min_size']
    top_book_liquidity = best_bid_size + best_ask_size

    # 5. Calculate liquidity within 2-3 ticks of best prices
    near_bid_liquidity = sum([size for price, size in sorted_bids
                              if price >= best_bid_price - (2 * tick_size)])
    near_ask_liquidity = sum([size for price, size in sorted_asks
                              if price <= best_ask_price + (2 * tick_size)])

    # 6. Check for reasonable price gaps
    bid_gaps = []
    for i in range(1, min(len(sorted_bids), 5)):
        gap = sorted_bids[i-1][0] - sorted_bids[i][0]
        bid_gaps.append(gap)

    ask_gaps = []
    for i in range(1, min(len(sorted_asks), 5)):
        gap = sorted_asks[i][0] - sorted_asks[i-1][0]
        ask_gaps.append(gap)

    avg_bid_gap = sum(bid_gaps) / len(bid_gaps) if bid_gaps else 0
    avg_ask_gap = sum(ask_gaps) / len(ask_gaps) if ask_gaps else 0

    # 7. Volatility analysis
    volatility_1h = row['1_hour']
    volatility_24h = row['24_hour']
    volatility_7d = row['7_day']
    # Convert from string to float for comparison (field is stored as string in spreadsheet)
    try:
        volatility_reward_ratio = float(row['volatility/reward'])
    except (ValueError, TypeError):
        volatility_reward_ratio = 0


# 8. Reward analysis
    rewards_daily_rate = row['rewards_daily_rate']
    gm_reward_per_100 = row['gm_reward_per_100']

    # Scoring criteria
    issues = []
    score = 0

    # 1. Spread check (weight: 20 points)
    if spread_pct <= 2:
        score += 20
    elif spread_pct <= 5:
        score += 15
    elif spread_pct <= 10:
        score += 8
    else:
        issues.append(f"Spread too wide: {spread_pct:.1f}%")

    # 2. Liquidity balance (weight: 20 points)
    if balance_ratio >= 0.7:
        score += 20
    elif balance_ratio >= 0.5:
        score += 15
    elif balance_ratio >= 0.3:
        score += 8
    else:
        issues.append(f"Poor liquidity balance: {balance_ratio:.2f}")

    # 3. Total liquidity (weight: 15 points)
    if total_liquidity >= min_total_liquidity:
        score += 15
    elif total_liquidity >= min_total_liquidity * 0.5:
        score += 10
    else:
        issues.append(f"Low total liquidity: {total_liquidity:.0f}")

    # 4. Market depth (weight: 15 points)
    min_levels = min(bid_levels, ask_levels)
    if min_levels >= 5:
        score += 15
    elif min_levels >= 3:
        score += 10
    elif min_levels >= 2:
        score += 5
    else:
        issues.append(f"Insufficient depth: {min_levels} levels")

    # 5. Top of book vs trade size (weight: 10 points)
    if top_book_liquidity >= trade_size * 3:
        score += 10
    elif top_book_liquidity >= trade_size * 2:
        score += 8
    elif top_book_liquidity >= trade_size:
        score += 5
    else:
        issues.append(f"Thin top-of-book vs trade size: {top_book_liquidity:.0f} vs {trade_size}")

    # 6. Price continuity (weight: 10 points)
    max_reasonable_gap = tick_size * 3
    if avg_bid_gap <= max_reasonable_gap and avg_ask_gap <= max_reasonable_gap:
        score += 10
    elif avg_bid_gap <= max_reasonable_gap * 2 and avg_ask_gap <= max_reasonable_gap * 2:
        score += 5
    else:
        issues.append(f"Large price gaps: bid={avg_bid_gap:.3f}, ask={avg_ask_gap:.3f}")

    # 7. Volatility vs reward (weight: 10 points)
    # Note: volatility/reward is actually reward/volatility ratio (higher = better)
    if volatility_reward_ratio >= 2:
        score += 10
    elif volatility_reward_ratio >= 1:
        score += 8
    elif volatility_reward_ratio >= 0.5:
        score += 5
    else:
        issues.append(f"Poor reward/volatility ratio: {volatility_reward_ratio:.3f}")

    # Final recommendation
    if score >= 80:
        recommendation = "EXCELLENT"
    elif score >= 60:
        recommendation = "GOOD"
    elif score >= 40:
        recommendation = "FAIR"
    else:
        recommendation = "POOR"

    # Create results dataframe
    results = pd.DataFrame([{
        "market": market,
        "question": row['question'],
        "market_slug": row['market_slug'],
        "score": score,
        "recommendation": recommendation,
        "suitable": score >= 40,

        # Spread metrics
        "spread": spread,
        "spread_pct": spread_pct,
        "expected_spread": expected_spread,
        "spread_vs_expected": spread_vs_expected,

        # Liquidity metrics
        "total_bid_liquidity": total_bid_liquidity,
        "total_ask_liquidity": total_ask_liquidity,
        "total_liquidity": total_liquidity,
        "balance_ratio": balance_ratio,
        "bid_levels": bid_levels,
        "ask_levels": ask_levels,

        # Best prices and sizes
        "best_bid": best_bid_price,
        "best_ask": best_ask_price,
        "best_bid_size": best_bid_size,
        "best_ask_size": best_ask_size,
        "top_book_liquidity": top_book_liquidity,
        "near_bid_liquidity": near_bid_liquidity,
        "near_ask_liquidity": near_ask_liquidity,

        # Price continuity
        "avg_bid_gap": avg_bid_gap,
        "avg_ask_gap": avg_ask_gap,

        # Trading parameters
        "trade_size": trade_size,
        "min_size": min_size,
        "tick_size": tick_size,

        # Volatility metrics
        "volatility_1h": volatility_1h,
        "volatility_24h": volatility_24h,
        "volatility_7d": volatility_7d,
        "volatility_reward_ratio": volatility_reward_ratio,

        # Reward metrics
        "rewards_daily_rate": rewards_daily_rate,
        "gm_reward_per_100": gm_reward_per_100,

        # Issues
        "issues_count": len(issues),
        "issues": "; ".join(issues) if issues else "None"
    }])

    return results