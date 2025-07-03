import pandas as pd




# Dictionary to store the last logged messages for each market to prevent duplicate logging
last_logged_messages = {}

# Dictionary to track the number of skipped log messages for each market
skipped_log_counts = {}

def log_market_conditions_if_changed(market, question, yes_no_outcome, orders, position, avgPrice,
                                     best_bid, best_ask, bid_price, ask_price, mid_price,
                                     trade_size, buy_amount, sell_amount):
    """
    Log market conditions and order preparation details, but only if they differ from the last logged messages.
    Tracks skipped logs and reports every 10 skipped events.

    Args:
        market: Market identifier
        question: Market question text
        yes_no_outcome: Dictionary with outcome details (answer)
        orders: Current orders for the token
        position: Current position size
        avgPrice: Average price of position
        best_bid, best_ask: Market's best bid/ask prices
        bid_price, ask_price: Our optimal bid/ask prices
        mid_price: Market mid price
        trade_size: Target trade size
        buy_amount, sell_amount: Calculated buy/sell amounts
    """
    # Format orders - only show non-zero orders
    orders_list = []
    if orders.get('buy', {}).get('size', 0) > 0 and orders.get('buy', {}).get('price', 0) > 0:
        orders_list.append(f"BUY {orders['buy']['size']} @ {orders['buy']['price']}")
    if orders.get('sell', {}).get('size', 0) > 0 and orders.get('sell', {}).get('price', 0) > 0:
        orders_list.append(f"SELL {orders['sell']['size']} @ {orders['sell']['price']}")
    
    orders_str = ", ".join(orders_list) if orders_list else "None"
    
    # Format order prepared - only show non-zero amounts
    prepared_list = []
    if buy_amount > 0:
        prepared_list.append(f"BUY {buy_amount} @ {bid_price}")
    if sell_amount > 0:
        prepared_list.append(f"SELL {sell_amount} @ {ask_price}")
    
    prepared_str = ", ".join(prepared_list) if prepared_list else "None"

    # Create the two messages
    message1 = (f"\nFor {yes_no_outcome['answer']}. Orders: {orders_str} Position: {position}, "
                f"avgPrice: {avgPrice}, Best Bid: {best_bid}, Best Ask: {best_ask}, "
                f"Our optimal bid Price: {bid_price}, Our optimal ask Price: {ask_price}, Mid Price: {mid_price}")

    message2 = (f"Position: {position}, Trade Size (constant): {trade_size}, "
                f"Order Prepared: {prepared_str}")

    # Check if these messages are the same as the last logged ones for this market + outcome
    current_messages = (message1, message2)
    
    # Create unique key for market + outcome combination
    market_outcome_key = f"{market}_{yes_no_outcome['answer']}"

    # Initialize skip counter for this market+outcome if it doesn't exist
    if market_outcome_key not in skipped_log_counts:
        skipped_log_counts[market_outcome_key] = 0

    if market_outcome_key in last_logged_messages:
        if last_logged_messages[market_outcome_key] == current_messages:
            # Increment skip counter
            skipped_log_counts[market_outcome_key] += 1

            # Check if we've skipped 10 events
            if skipped_log_counts[market_outcome_key] >= 10:
                log_message(market, f"[SKIPPED] {skipped_log_counts[market_outcome_key]} identical market condition log events were not logged to reduce spam for {yes_no_outcome['answer']}")
                skipped_log_counts[market_outcome_key] = 0  # Reset counter

            return

    # Reset skip counter when we log (since conditions changed)
    if skipped_log_counts[market_outcome_key] > 0:
        log_message(market, f"[SKIPPED] {skipped_log_counts[market_outcome_key]} identical market condition log events were not logged for {yes_no_outcome['answer']}")
        skipped_log_counts[market_outcome_key] = 0

    log_message(market, f"\n\n{pd.Timestamp.utcnow().tz_localize(None)}: {question}")
    # Log the messages since they're different or first time
    log_message(market, message1)
    log_message(market, message2)

    # Store the current messages for future comparison
    last_logged_messages[market_outcome_key] = current_messages


def log_message(market_name,  *messages):
    """
    Log a message to both console and market-specific log file.

    Args:
        market_name (str): Market name for the log file (sanitized for filename)
        message (str): Message to log
    """
    message = " ".join(str(msg) for msg in messages)

    # Print to console
    print(message)

    # Sanitize market name for filename (remove invalid characters)
    safe_filename = "".join(c for c in market_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_filename = safe_filename.replace(' ', '_')[:100]  # Limit length and replace spaces

    # Write to log file
    log_file = f'log/{safe_filename}.log'
    timestamp = pd.Timestamp.utcnow().tz_localize(None)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp}: {message}\n")