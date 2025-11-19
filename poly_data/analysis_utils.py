import poly_data.global_state as global_state
import pandas as pd
from sortedcontainers import SortedDict


def _calculate_spread_metrics(context):
    """Calculate spread metrics and add to context."""
    best_bid_price = context['best_bid_price']
    best_ask_price = context['best_ask_price']

    spread = best_ask_price - best_bid_price
    mid_price = (best_bid_price + best_ask_price) / 2
    spread_pct = (spread / mid_price) * 100

    context['spread'] = spread
    context['mid_price'] = mid_price
    context['spread_pct'] = spread_pct


def _score_spread(context):
    """Score spread quality and check for blockers."""
    spread = context['spread']
    spread_pct = context['spread_pct']
    blocker_max_spread_pct = context['params'].get('blocker_max_spread_pct', 20)

    # Check for blocker conditions first
    if spread_pct > blocker_max_spread_pct:
        context['issues'].append(f"[BLOCKER] Spread too wide: {spread_pct:.1f}% (max {blocker_max_spread_pct}%)")
        context['blocker_issues_count'] += 1
    elif spread > 0.10:
        context['issues'].append(f"[BLOCKER] Absolute spread too wide: ${spread:.3f} (max $0.10)")
        context['blocker_issues_count'] += 1
    elif spread_pct <= 2:
        context['score'] += 20
    elif spread_pct <= 5:
        context['score'] += 15
    elif spread_pct <= 10:
        context['score'] += 8
    else:
        context['issues'].append(f"Spread too wide: {spread_pct:.1f}%")


def _calculate_liquidity_metrics(context):
    """Calculate liquidity metrics and add to context."""
    bids = context['bids']
    asks = context['asks']

    total_bid_liquidity = sum(bids.values())
    total_ask_liquidity = sum(asks.values())
    total_liquidity = total_bid_liquidity + total_ask_liquidity

    # Calculate balance ratio (closer to 1.0 = better balanced)
    if total_ask_liquidity > 0 and total_bid_liquidity > 0:
        balance_ratio = min(total_bid_liquidity, total_ask_liquidity) / max(total_bid_liquidity, total_ask_liquidity)
    else:
        balance_ratio = 0

    context['total_bid_liquidity'] = total_bid_liquidity
    context['total_ask_liquidity'] = total_ask_liquidity
    context['total_liquidity'] = total_liquidity
    context['balance_ratio'] = balance_ratio


def _score_liquidity_balance(context):
    """Score liquidity balance and check for blocker."""
    balance_ratio = context['balance_ratio']
    blocker_liquidity_balance = context['params'].get('blocker_liquidity_balance', 0.3)

    # Check for blocker condition first
    if balance_ratio < blocker_liquidity_balance:
        context['issues'].append(f"[BLOCKER] Liquidity severely imbalanced: {balance_ratio:.2f} (min {blocker_liquidity_balance:.2f})")
        context['blocker_issues_count'] += 1
    elif balance_ratio >= 0.7:
        context['score'] += 20
    elif balance_ratio >= 0.5:
        context['score'] += 15
    elif balance_ratio >= 0.4:
        context['score'] += 8
    else:
        context['issues'].append(f"Poor liquidity balance: {balance_ratio:.2f}")


def _score_total_liquidity(context):
    """Score total liquidity and check for blocker."""
    total_liquidity = context['total_liquidity']
    min_total_liquidity = context['params']['min_total_liquidity']
    blocker_min_total_liquidity = context['params'].get('blocker_min_total_liquidity', min_total_liquidity * 0.3)

    # Check for blocker condition first
    if total_liquidity < blocker_min_total_liquidity:
        context['issues'].append(f"[BLOCKER] Total liquidity too low: {total_liquidity:.0f} (min {blocker_min_total_liquidity:.0f})")
        context['blocker_issues_count'] += 1
    elif total_liquidity >= min_total_liquidity:
        context['score'] += 15
    elif total_liquidity >= min_total_liquidity * 0.5:
        context['score'] += 10
    else:
        context['issues'].append(f"Low total liquidity: {total_liquidity:.0f}")


def _calculate_depth_metrics(context):
    """Calculate market depth metrics and add to context."""
    sorted_bids = context['sorted_bids']
    sorted_asks = context['sorted_asks']

    bid_levels = len([price for price, size in sorted_bids if size > 0])
    ask_levels = len([price for price, size in sorted_asks if size > 0])

    context['bid_levels'] = bid_levels
    context['ask_levels'] = ask_levels


def _score_market_depth(context):
    """Score market depth."""
    bid_levels = context['bid_levels']
    ask_levels = context['ask_levels']
    min_levels = min(bid_levels, ask_levels)

    if min_levels >= 5:
        context['score'] += 15
    elif min_levels >= 3:
        context['score'] += 10
    elif min_levels >= 2:
        context['score'] += 5
    else:
        context['issues'].append(f"Insufficient depth: {min_levels} levels")


def _calculate_top_book_metrics(context):
    """Calculate top-of-book liquidity metrics."""
    best_bid_size = context['best_bid_size']
    best_ask_size = context['best_ask_size']
    tick_size = context['tick_size']
    sorted_bids = context['sorted_bids']
    sorted_asks = context['sorted_asks']
    best_bid_price = context['best_bid_price']
    best_ask_price = context['best_ask_price']

    top_book_liquidity = best_bid_size + best_ask_size

    # Calculate liquidity within 2-3 ticks of best prices
    near_bid_liquidity = sum([size for price, size in sorted_bids
                              if price >= best_bid_price - (2 * tick_size)])
    near_ask_liquidity = sum([size for price, size in sorted_asks
                              if price <= best_ask_price + (2 * tick_size)])

    context['top_book_liquidity'] = top_book_liquidity
    context['near_bid_liquidity'] = near_bid_liquidity
    context['near_ask_liquidity'] = near_ask_liquidity


def _score_top_book_liquidity(context):
    """Score top-of-book liquidity relative to trade size."""
    top_book_liquidity = context['top_book_liquidity']
    trade_size = context['trade_size']

    if top_book_liquidity >= trade_size * 3:
        context['score'] += 10
    elif top_book_liquidity >= trade_size * 2:
        context['score'] += 8
    elif top_book_liquidity >= trade_size:
        context['score'] += 5
    else:
        context['issues'].append(f"Thin top-of-book vs trade size: {top_book_liquidity:.0f} vs {trade_size}")


def _calculate_price_continuity_metrics(context):
    """Calculate price gap metrics."""
    sorted_bids = context['sorted_bids']
    sorted_asks = context['sorted_asks']

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

    context['avg_bid_gap'] = avg_bid_gap
    context['avg_ask_gap'] = avg_ask_gap


def _score_price_continuity(context):
    """Score price continuity (gaps between levels)."""
    avg_bid_gap = context['avg_bid_gap']
    avg_ask_gap = context['avg_ask_gap']
    tick_size = context['tick_size']

    max_reasonable_gap = tick_size * 3
    if avg_bid_gap <= max_reasonable_gap and avg_ask_gap <= max_reasonable_gap:
        context['score'] += 10
    elif avg_bid_gap <= max_reasonable_gap * 2 and avg_ask_gap <= max_reasonable_gap * 2:
        context['score'] += 5
    else:
        context['issues'].append(f"Large price gaps: bid={avg_bid_gap:.3f}, ask={avg_ask_gap:.3f}")


def _calculate_volatility_metrics(context):
    """Extract volatility metrics from row data."""
    row = context['row']

    volatility_1h = row['1_hour']
    volatility_24h = row['24_hour']
    volatility_7d = row['7_day']

    # Convert from string to float for comparison
    try:
        volatility_reward_ratio = float(row['volatility/reward'])
    except (ValueError, TypeError):
        volatility_reward_ratio = 0

    context['volatility_1h'] = volatility_1h
    context['volatility_24h'] = volatility_24h
    context['volatility_7d'] = volatility_7d
    context['volatility_reward_ratio'] = volatility_reward_ratio


def _score_volatility_reward_ratio(context):
    """Score volatility vs reward ratio."""
    volatility_reward_ratio = context['volatility_reward_ratio']

    # Note: volatility/reward is actually reward/volatility ratio (higher = better)
    if volatility_reward_ratio >= 2:
        context['score'] += 10
    elif volatility_reward_ratio >= 1:
        context['score'] += 8
    elif volatility_reward_ratio >= 0.5:
        context['score'] += 5
    else:
        context['issues'].append(f"Poor reward/volatility ratio: {volatility_reward_ratio:.3f}")


def _extract_reward_metrics(context):
    """Extract reward metrics from row data."""
    row = context['row']

    context['rewards_daily_rate'] = row['rewards_daily_rate']
    context['gm_reward_per_100'] = row['gm_reward_per_100']


def _finalize_score_and_recommendation(context):
    """Apply blockers and generate final recommendation."""
    # Apply blocker override - if any blocker exists, set score to 0
    if context['blocker_issues_count'] > 0:
        context['score'] = 0

    # Generate recommendation based on score
    score = context['score']
    if score >= 80:
        recommendation = "EXCELLENT"
    elif score >= 60:
        recommendation = "GOOD"
    elif score >= 40:
        recommendation = "FAIR"
    else:
        recommendation = "POOR"

    context['recommendation'] = recommendation
    context['suitable'] = score >= 40


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

    # Early exit: Missing order book data
    if not bids or not asks:
        return pd.DataFrame([{
            "market": market,
            "suitable": False,
            "score": 0,
            "recommendation": "POOR - Missing bids or asks",
            "reason": "Missing order book data"
        }])

    # Early exit: Hard-fail on excessive volatility
    volatility_threshold = params.get('volatility_threshold', 300)
    if row['3_hour'] > volatility_threshold:
        return pd.DataFrame([{
            "market": market,
            "suitable": False,
            "score": 0,
            "recommendation": "POOR - Volatility too high",
            "reason": f"3-hour volatility ({row['3_hour']}) exceeds threshold ({volatility_threshold})"
        }])

    # Initialize context dictionary - shared state for all helper functions
    tick_size = row['tick_size']
    sorted_bids = list(reversed(list(bids.items())))  # Highest first
    sorted_asks = list(asks.items())  # Lowest first
    best_bid_price, best_bid_size = sorted_bids[0]
    best_ask_price, best_ask_size = sorted_asks[0]

    context = {
        # Input data
        'market': market,
        'row': row,
        'params': params,
        'bids': bids,
        'asks': asks,
        'sorted_bids': sorted_bids,
        'sorted_asks': sorted_asks,

        # Basic price data
        'best_bid_price': best_bid_price,
        'best_bid_size': best_bid_size,
        'best_ask_price': best_ask_price,
        'best_ask_size': best_ask_size,
        'tick_size': tick_size,
        'trade_size': row['trade_size'],
        'min_size': row['min_size'],

        # Accumulator fields
        'score': 0,
        'issues': [],
        'blocker_issues_count': 0
    }

    # Execute analysis pipeline - each function adds to context
    _calculate_spread_metrics(context)
    _score_spread(context)

    _calculate_liquidity_metrics(context)
    _score_liquidity_balance(context)
    _score_total_liquidity(context)

    _calculate_depth_metrics(context)
    _score_market_depth(context)

    _calculate_top_book_metrics(context)
    _score_top_book_liquidity(context)

    _calculate_price_continuity_metrics(context)
    _score_price_continuity(context)

    _calculate_volatility_metrics(context)
    _score_volatility_reward_ratio(context)

    _extract_reward_metrics(context)

    _finalize_score_and_recommendation(context)

    # Build results DataFrame from context
    results = pd.DataFrame([{
        "market": market,
        "question": row['question'],
        "market_slug": row['market_slug'],
        "score": context['score'],
        "recommendation": context['recommendation'],
        "suitable": context['suitable'],

        # Spread metrics
        "spread": context['spread'],
        "spread_pct": context['spread_pct'],

        # Liquidity metrics
        "total_bid_liquidity": context['total_bid_liquidity'],
        "total_ask_liquidity": context['total_ask_liquidity'],
        "total_liquidity": context['total_liquidity'],
        "balance_ratio": context['balance_ratio'],
        "bid_levels": context['bid_levels'],
        "ask_levels": context['ask_levels'],

        # Best prices and sizes
        "best_bid": context['best_bid_price'],
        "best_ask": context['best_ask_price'],
        "best_bid_size": context['best_bid_size'],
        "best_ask_size": context['best_ask_size'],
        "top_book_liquidity": context['top_book_liquidity'],
        "near_bid_liquidity": context['near_bid_liquidity'],
        "near_ask_liquidity": context['near_ask_liquidity'],

        # Price continuity
        "avg_bid_gap": context['avg_bid_gap'],
        "avg_ask_gap": context['avg_ask_gap'],

        # Trading parameters
        "trade_size": context['trade_size'],
        "min_size": context['min_size'],
        "tick_size": context['tick_size'],

        # Volatility metrics
        "volatility_1h": context['volatility_1h'],
        "volatility_24h": context['volatility_24h'],
        "volatility_7d": context['volatility_7d'],
        "volatility_reward_ratio": context['volatility_reward_ratio'],

        # Reward metrics
        "rewards_daily_rate": context['rewards_daily_rate'],
        "gm_reward_per_100": context['gm_reward_per_100'],

        # Issues
        "issues_count": len(context['issues']),
        "blocker_issues_count": context['blocker_issues_count'],
        "issues": "; ".join(context['issues']) if context['issues'] else "None"
    }])

    return results