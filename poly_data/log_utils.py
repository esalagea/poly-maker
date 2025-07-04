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

    # Create combined message with header
    combined_message = (f"\n\n{pd.Timestamp.utcnow().tz_localize(None)}: {question}\n"
                       f"For {yes_no_outcome['answer']}. Orders: {orders_str} Position: {position}, "
                       f"avgPrice: {avgPrice}, Best Bid: {best_bid}, Best Ask: {best_ask}, "
                       f"Our optimal bid Price: {bid_price}, Our optimal ask Price: {ask_price}, Mid Price: {mid_price}\n"
                       f"Position: {position}, Trade Size (constant): {trade_size}, "
                       f"Order Prepared: {prepared_str}")

    # Use generic log_message with single message_id for duplicate detection
    message_id = f"{yes_no_outcome['answer']}_market_conditions_and_positions"
    log_message(market, message_id, combined_message)


def log_message(market_name, message_id=None, *messages):
    """
    Log a message to both console and market-specific log file.
    If message_id is provided, applies duplicate detection logic.

    Args:
        market_name (str): Market name for the log file (sanitized for filename)
        message_id (str, optional): Unique identifier for this message type for duplicate detection
        *messages: Message parts to join and log
        
    Returns:
        bool: True if message was logged, False if skipped due to duplication
    """
    message = " ".join(str(msg) for msg in messages)
    
    # If no message_id provided, log directly (backward compatibility)
    if message_id is None:
        _write_log_message(market_name, message)
        return True
    
    # Apply duplicate detection logic
    message_key = f"{market_name}_{message_id}"
    
    # Initialize skip counter if it doesn't exist
    if message_key not in skipped_log_counts:
        skipped_log_counts[message_key] = 0
    
    # Check if message has changed
    message_changed = True
    if message_key in last_logged_messages:
        if last_logged_messages[message_key] == message:
            message_changed = False
            skipped_log_counts[message_key] += 1
    
    # If message hasn't changed, check skip counter
    if not message_changed:
        # Report skipped events every 100 iterations
        if skipped_log_counts[message_key] >= 100:
            _write_log_message(market_name, f"[SKIPPED] {skipped_log_counts[message_key]} identical '{message_id}' log events were not logged to reduce spam")
            skipped_log_counts[message_key] = 0  # Reset counter
        return False
    
    # Message has changed - report any pending skipped messages
    if skipped_log_counts[message_key] > 0:
        _write_log_message(market_name, f"[SKIPPED] {skipped_log_counts[message_key]} identical '{message_id}' log events were not logged")
        skipped_log_counts[message_key] = 0
    
    # Log the new message and store it
    _write_log_message(market_name, message)
    last_logged_messages[message_key] = message
    return True



def _write_log_message(market_name, message):
    """
    Internal function to write message to console and log file.
    
    Args:
        market_name (str): Market name for the log file (sanitized for filename)
        message (str): Message to log
    """
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