import gc                       # Garbage collection
import os                       # Operating system interface
import json                     # JSON handling
import asyncio                  # Asynchronous I/O
import traceback                # Exception handling
import pandas as pd             # Data analysis library
import math                     # Mathematical functions
import poly_data.global_state as global_state
import poly_data.CONSTANTS as CONSTANTS
from poly_data.analysis_utils import analyze_market_quality
from update_markets import save_market_quality_data

# Import utility functions for trading
from poly_data.trading_utils import get_best_bid_ask_deets, get_order_prices, get_buy_sell_amount, round_down, round_up
from poly_data.data_utils import get_position, get_order, set_position

from poly_data.log_utils import log_message, log_message_deduplicated
from poly_data.log_utils import log_market_conditions_if_changed

# Create directory for storing position risk information
if not os.path.exists('positions/'):
    os.makedirs('positions/')

# Create directory for storing trading logs
if not os.path.exists('log_old/'):
    os.makedirs('log_old/')

def get_conflicting_order_sides(new_order_side, new_price, existing_orders):
    """
    Determine which order sides should be canceled to avoid conflicts.
    
    Args:
        new_order_side (str): 'BUY' or 'SELL'
        new_price (float): Price of the new order
        existing_orders (dict): Current orders {'buy': {...}, 'sell': {...}}
        
    Returns:
        list: List of sides to cancel ['BUY'] and/or ['SELL']
    """
    sides_to_cancel = []
    
    # Always cancel same-side orders (different price/size strategy)
    if new_order_side == 'BUY':
        if existing_orders.get('buy', {}).get('size', 0) > 0:
            sides_to_cancel.append('BUY')
            
        # Economic conflict check: Don't allow buy_price >= sell_price
        existing_sell_price = existing_orders.get('sell', {}).get('price', 0)
        if existing_sell_price > 0 and new_price >= existing_sell_price:
            sides_to_cancel.append('SELL')
            
    elif new_order_side == 'SELL':
        if existing_orders.get('sell', {}).get('size', 0) > 0:
            sides_to_cancel.append('SELL')
            
        # Economic conflict check: Don't allow sell_price <= buy_price  
        existing_buy_price = existing_orders.get('buy', {}).get('price', 0)
        if existing_buy_price > 0 and new_price <= existing_buy_price:
            sides_to_cancel.append('BUY')
    
    return sides_to_cancel


def cancel_specific_order_sides(token, market, sides_to_cancel):
    """
    Cancel only specific order sides for a token.
    
    Args:
        token: The token/asset_id to cancel orders for
        market: Market identifier for API call and logging context
        sides_to_cancel: List of sides to cancel ['BUY'] and/or ['SELL']
    """
    if not sides_to_cancel:
        return
        
    client = global_state.client
    
    # Get existing orders before canceling
    try:
        if market:
            # Get all orders for the market, then filter by token
            all_market_orders = client.get_market_orders(market)
            existing_orders = all_market_orders[all_market_orders['asset_id'] == str(token)]
        else:
            # Fallback: get all orders and filter by token
            all_orders = client.get_all_orders()
            existing_orders = all_orders[all_orders['asset_id'] == str(token)]
        
        # Filter to only the sides we want to cancel
        orders_to_cancel = existing_orders[existing_orders['side'].isin(sides_to_cancel)]
        
        if len(orders_to_cancel) > 0:
            # Log details about orders being canceled
            orders_info = []
            for idx, order in orders_to_cancel.iterrows():
                orders_info.append(f"{order['side']} {order['original_size']} @ {order['price']}")
            
            orders_str = ", ".join(orders_info)
            sides_str = ", ".join(sides_to_cancel)
            
            if market:
                log_message(market, f"Canceling {len(orders_to_cancel)} {sides_str} orders for token {token}: {orders_str}")
            else:
                log_message("TRADING", f"Canceling {len(orders_to_cancel)} {sides_str} orders for token {token}: {orders_str}")
        
        # Cancel each order individually (since we can't cancel by side)
        for idx, order in orders_to_cancel.iterrows():
            client.cancel_order(order['id'])
            
    except Exception as e:
        if market:
            log_message(market, f"Error checking orders before selective cancel for token {token}: {str(e)}")
        else:
            log_message("TRADING", f"Error checking orders before selective cancel for token {token}: {str(e)}")
        
        # Fallback: cancel all if selective cancellation fails
        client.cancel_all_asset(token)


def cancel_orders_with_logging(token, market=None):
    """
    Cancel all orders for a given token with proper logging.
    
    Args:
        token: The token/asset_id to cancel orders for
        market: Market identifier for API call and logging context
    """
    client = global_state.client
    
    # Get existing orders before canceling
    try:
        if market:
            # Get all orders for the market, then filter by token
            all_market_orders = client.get_market_orders(market)
            existing_orders = all_market_orders[all_market_orders['asset_id'] == str(token)]
        else:
            # Fallback: get all orders and filter by token
            all_orders = client.get_all_orders()
            existing_orders = all_orders[all_orders['asset_id'] == str(token)]
        
        if len(existing_orders) > 0:
            # Log details about orders being canceled
            orders_info = []
            for idx, order in existing_orders.iterrows():
                orders_info.append(f"{order['side']} {order['original_size']} @ {order['price']}")
            
            orders_str = ", ".join(orders_info)
            
            if market:
                log_message(market, f"Canceling {len(existing_orders)} existing orders for token {token}: {orders_str}")
            else:
                log_message("TRADING", f"Canceling {len(existing_orders)} existing orders for token {token}: {orders_str}")
        
        # Cancel the orders
        client.cancel_all_asset(token)
        
    except Exception as e:
        if market:
            log_message(market, f"Error checking orders before cancel for token {token}: {str(e)}")
        else:
            log_message("TRADING", f"Error checking orders before cancel for token {token}: {str(e)}")
        
        # Still attempt to cancel even if we couldn't get order details
        client.cancel_all_asset(token)




def send_buy_order(order, existing_orders=None, log_message_text=None):
    """
    Create a BUY order for a specific token.
    
    This function:
    1. Checks if the new order is different from existing buy order
    2. Validates order price and conditions
    3. Only cancels and creates new order if there are differences and conditions are met
    4. Logs provided message only if order is actually created
    
    Args:
        order (dict): Order details including token, price, size, and market parameters
        existing_orders (dict, optional): Current orders for comparison. If None, uses order['orders']
        log_message_text (str, optional): Custom message to log when order is created
    
    Returns:
        bool: True if order was created, False if skipped
    """
    client = global_state.client
    market = order['market']
    
    # Use provided existing_orders or fall back to order['orders']
    current_orders = existing_orders if existing_orders is not None else order['orders']
    
    # Check if new buy order is identical to existing buy order
    existing_buy = current_orders.get('buy', {})
    existing_buy_price = existing_buy.get('price', 0)
    existing_buy_size = existing_buy.get('size', 0)
    
    new_price = float(order['price'])
    new_size = float(order['size'])
    
    # Compare with small tolerance for floating point precision
    price_same = abs(existing_buy_price - new_price) < 0.001
    size_same = abs(existing_buy_size - new_size) < 0.001
    
    if price_same and size_same and existing_buy_size > 0:
        # Skip order creation - do not log anything
        return False

    # Smart conflict checking - only cancel conflicting orders
    sides_to_cancel = get_conflicting_order_sides('BUY', new_price, current_orders)
    if sides_to_cancel:
        cancel_specific_order_sides(order['token'], market, sides_to_cancel)

    # Log the provided message or default message
    if log_message_text:
        log_message(market, log_message_text)
    else:
        log_message(market, f'BUY ORDER:: Creating new order - BUY {order["size"]} @ {order["price"]}')
    
    client.create_order(
        order['token'], 
        'BUY', 
        order['price'], 
        order['size'], 
        True if order['neg_risk'] == 'TRUE' else False
    )
    
    return True


def send_sell_order(order, existing_orders=None, log_message_text=None):
    """
    Create a SELL order for a specific token.
    
    This function:
    1. Checks if the new order is different from existing sell order
    2. Only cancels and creates new order if there are differences
    3. Creates a new sell order with the specified parameters
    4. Logs provided message only if order is actually created
    
    Args:
        order (dict): Order details including token, price, size, and market parameters
        existing_orders (dict, optional): Current orders for comparison. If None, uses order['orders']
        log_message_text (str, optional): Custom message to log when order is created
    
    Returns:
        bool: True if order was created, False if skipped
    """
    client = global_state.client
    market = order['market']
    
    # Use provided existing_orders or fall back to order['orders']
    current_orders = existing_orders if existing_orders is not None else order['orders']
    
    # Check if new sell order is identical to existing sell order
    existing_sell = current_orders.get('sell', {})
    existing_sell_price = existing_sell.get('price', 0)
    existing_sell_size = existing_sell.get('size', 0)
    
    new_price = float(order['price'])
    new_size = float(order['size'])
    
    # Compare with small tolerance for floating point precision
    price_same = abs(existing_sell_price - new_price) < 0.001
    size_same = abs(existing_sell_size - new_size) < 0.001
    
    if price_same and size_same and existing_sell_size > 0:
        # Skip order creation - do not log anything
        return False
    
    # Smart conflict checking - only cancel conflicting orders
    sides_to_cancel = get_conflicting_order_sides('SELL', new_price, current_orders)
    if sides_to_cancel:
        cancel_specific_order_sides(order['token'], market, sides_to_cancel)

    # Log the provided message or default message
    if log_message_text:
        log_message(market, log_message_text)
    log_message(market, f'SELL ORDER:: Creating new order - SELL {order["size"]} @ {order["price"]}')
    
    client.create_order(
        order['token'], 
        'SELL', 
        order['price'], 
        order['size'], 
        True if order['neg_risk'] == 'TRUE' else False
    )
    
    return True

# Dictionary to store locks for each market to prevent concurrent trading on the same market
market_locks = {}

async def perform_trade(market):
    """
    Main trading function that handles market making for a specific market.
    
    This function:
    1. Merges positions when possible to free up capital
    2. Analyzes the market to determine optimal bid/ask prices
    3. Manages buy and sell orders based on position size and market conditions
    4. Implements risk management with stop-loss and take-profit logic
    
    Args:
        market (str): The market ID to trade on
    """
    # Create a lock for this market if it doesn't exist
    if market not in market_locks:
        market_locks[market] = asyncio.Lock()

    row = global_state.df[global_state.df['condition_id'] == market].iloc[0]
    market_making = row['market_making']



    # Use lock to prevent concurrent trading on the same market
    async with market_locks[market]:
        try:
            if row['trade_size'] == "":
                row['trade_size'] = row['min_size']

            # Get trading parameters for this market type
            params = global_state.params[row['param_type']]

            market_quality_df = analyze_market_quality(market, row, params)
            save_market_quality_data(market_quality_df)

            if market_making == "STOP" or market_making == "":
                #log_message(market, "Market Making option is set to STOP. No trading.")
                return


            client = global_state.client
            # Get market details from the configuration

            # Determine decimal precision from tick size
            round_length = len(str(row['tick_size']).split(".")[1])

            
            # Create a list with both outcomes for the market
            yes_no_outcomes = [
                {'name': 'token1', 'token': row['token1'], 'answer': row['answer1']}, 
                {'name': 'token2', 'token': row['token2'], 'answer': row['answer2']}
            ]

            # Log structured trading state summary
            log_trading_state_summary(market, row, yes_no_outcomes, params, market_quality_df)

            apply_merge_positions_logic(client, market, row)

            # ------- TRADING LOGIC FOR EACH OUTCOME -------
            # Loop through both outcomes in the market (YES and NO)
            for yes_no_outcome in yes_no_outcomes:
                token = int(yes_no_outcome['token'])

                # Get current orders for this token
                orders = get_order(token)

                # Get our current position and average price
                pos = get_position(token)
                position = round_down(pos['size'], 2)
                avgPrice = pos['avgPrice']


                # TODO: target_size was 100 in the initial code. We updated it to the exact needed target. We risk to be taker here
                target_size = row['trade_size'] - position
                # Get market depth and price information
                processed_market_data = get_best_bid_ask_deets(market, yes_no_outcome['name'], target_size, 0.1)

                # Extract all order book details
                best_bid = round(processed_market_data['best_bid'], round_length)
                best_bid_size = processed_market_data['best_bid_size']
                top_bid = round(processed_market_data['top_bid'], round_length)

                best_ask = round(processed_market_data['best_ask'], round_length)
                best_ask_size = processed_market_data['best_ask_size']
                top_ask = round (processed_market_data['top_ask'], round_length)

                # Calculate optimal bid and ask prices based on market conditions
                bid_price, ask_price = get_order_prices(
                    best_bid, best_bid_size, top_bid, best_ask, 
                    best_ask_size, top_ask, avgPrice, row
                )

                bid_price = round(bid_price, round_length)
                ask_price = round(ask_price, round_length)

                # Calculate mid price for reference
                mid_price = (top_bid + top_ask) / 2

                # Calculate how much to buy or sell based on our position
                buy_amount, sell_amount = get_buy_sell_amount(position, bid_price, row)

                # Prepare order object with all necessary information
                order = {
                    "token": token,
                    "mid_price": mid_price,
                    "neg_risk": row['neg_risk'],
                    "max_spread": row['max_spread'],
                    'orders': orders,
                    'token_name': yes_no_outcome['name'],
                    'row': row,
                    'market': market
                }


                # ------- SELL ORDER LOGIC -------
                if sell_amount > 0 and check_and_execute_stop_loss(market, row, yes_no_outcome, order, sell_amount, avgPrice, ask_price, round_length, params, client):
                    continue

                # ------- TAKE PROFIT / SELL ORDER MANAGEMENT -------
                if sell_amount > 0:
                    if handle_take_profit_orders(market, token, order, sell_amount, avgPrice, ask_price, orders, position, params, round_length, yes_no_outcome, best_bid, best_ask):
                        continue

                if send_buy_order_if_needed(market, row, processed_market_data, yes_no_outcome, order, buy_amount, bid_price, round_length, market_quality_df, market_making):
                    continue
                        


        except Exception as ex:
            log_message(market, f"Error performing trade for {market}: {str(ex)}\n{traceback.format_exc()}")
            traceback.print_exc()

        # Clean up memory and introduce a small delay
        gc.collect()
        await asyncio.sleep(2)


def log_trading_state_summary(market, row, yes_no_outcomes, params, market_quality_df):
    """
    Log a structured summary of the current trading state for this market.
    
    Args:
        market: Market identifier
        row: Market data row
        yes_no_outcomes: List of outcome details
        params: Trading parameters
        market_quality_df: Market quality analysis data
    """
    try:
        # Extract market quality score
        quality_score = "N/A"
        if market_quality_df is not None and not market_quality_df.empty:
            quality_score = market_quality_df.get('score', pd.Series([None])).iloc[0]
            if pd.isna(quality_score):
                quality_score = "N/A"
            else:
                quality_score = f"{quality_score:.1f}"
        
        # Build header
        summary_lines = []
        summary_lines.append("==================== TRADING STATE ====================")
        summary_lines.append(f"Market: {row['question']}")
        summary_lines.append("")
        summary_lines.append("TOKEN    POSITION   AVG_PRICE   ORDERS         MARKET           PREPARED")
        
        # Process each outcome
        for yes_no_outcome in yes_no_outcomes:
            token = int(yes_no_outcome['token'])
            
            # Get position data
            pos = get_position(token)
            position = round_down(pos['size'], 2)
            avg_price = pos['avgPrice']
            avg_price_str = f"${avg_price:.3f}" if avg_price > 0 else "$0.000"
            
            # Get current orders
            orders = get_order(token)
            orders_list = []
            if orders.get('buy', {}).get('size', 0) > 0:
                orders_list.append(f"BUY {orders['buy']['size']:.0f}@{orders['buy']['price']:.2f}")
            if orders.get('sell', {}).get('size', 0) > 0:
                orders_list.append(f"SELL {orders['sell']['size']:.0f}@{orders['sell']['price']:.2f}")
            orders_str = ", ".join(orders_list) if orders_list else "None"
            
            # Get market data
            try:
                target_size = row['trade_size'] - position
                market_data = get_best_bid_ask_deets(market, yes_no_outcome['name'], target_size, 0.1)
                best_bid = market_data['best_bid']
                best_ask = market_data['best_ask']
                top_bid = market_data['top_bid'] 
                top_ask = market_data['top_ask']
                mid_price = (top_bid + top_ask) / 2
                market_str = f"Bid:{best_bid:.2f} Ask:{best_ask:.2f}"
                
                # Calculate optimal prices for prepared orders
                optimal_bid, optimal_ask = get_order_prices(
                    best_bid, market_data['best_bid_size'], top_bid, best_ask,
                    market_data['best_ask_size'], top_ask, avg_price, row
                )
                round_length = len(str(row['tick_size']).split(".")[1])
                optimal_bid = round(optimal_bid, round_length)
                optimal_ask = round(optimal_ask, round_length)
                
                # Calculate what orders would be prepared
                buy_amount, sell_amount = get_buy_sell_amount(position, optimal_bid, row)
                prepared_list = []
                if buy_amount > 0:
                    prepared_list.append(f"BUY {buy_amount:.0f}@{optimal_bid:.2f}")
                if sell_amount > 0:
                    prepared_list.append(f"SELL {sell_amount:.0f}@{optimal_ask:.2f}")
                prepared_str = ", ".join(prepared_list) if prepared_list else "None"
                
            except Exception:
                market_str = "Bid:N/A Ask:N/A"
                prepared_str = "N/A"
            
            # Format the line with enhanced columns
            outcome_name = yes_no_outcome['answer'][:8]  # Truncate long names
            summary_lines.append(f"{outcome_name:<8} {position:<10.1f} {avg_price_str:<11} {orders_str:<14} {market_str:<16} {prepared_str}")
        
        # Add footer with key metrics
        summary_lines.append("")
        summary_lines.append(f"Target: {row['trade_size']} per side | Quality: {quality_score} | Volatility: {row['3_hour']:.1f}%")
        summary_lines.append("=======================================================")
        
        # Join all lines into single message
        summary_message = "\n".join(summary_lines)
        
        # Log with deduplication
        log_message_deduplicated(market, "trading_state_summary", summary_message)
        
    except Exception as e:
        log_message(market, f"Error creating trading state summary: {str(e)}")


def check_and_execute_stop_loss(market, row, yes_no_outcome, order, sell_amount, avgPrice, ask_price, round_length, params, client):
    """
    Check if stop-loss conditions are met and execute stop-loss if needed.
    
    Args:
        market: Market identifier
        row: Market data row
        yes_no_outcome: Outcome details
        order: Order object to modify
        sell_amount: Amount to sell
        avgPrice: Average price of position
        ask_price: Current ask price
        round_length: Decimal precision
        params: Trading parameters
        client: Trading client
        
    Returns:
        bool: True if stop-loss was triggered and executed, False otherwise
    """
    # Skip if we have no average price (no real position)
    if avgPrice == 0:
        log_message(market, "Avg Price is 0. Skipping")
        return True  # Return True to continue to next iteration
    
    order['size'] = sell_amount
    order['price'] = ask_price

    # Get fresh market data for risk assessment
    n_deets = get_best_bid_ask_deets(market, yes_no_outcome['name'], 100, 0.1)
    
    # Calculate current market price and spread
    mid_price = round_up((n_deets['best_bid'] + n_deets['best_ask']) / 2, round_length)
    spread = round(n_deets['best_ask'] - n_deets['best_bid'], 2)

    # Calculate current profit/loss on position
    pnl = (mid_price - avgPrice) / avgPrice * 100
    
    # Prepare risk details for tracking
    risk_details = {
        'time': str(pd.Timestamp.utcnow().tz_localize(None)),
        'question': row['question']
    }

    try:
        ratio = (n_deets['bid_sum_within_n_percent']) / (n_deets['ask_sum_within_n_percent'])
    except:
        ratio = 0

    pos_to_sell = sell_amount  # Amount to sell in risk-off scenario

    # ------- STOP-LOSS LOGIC -------
    # Trigger stop-loss if either:
    # 1. PnL is below threshold and spread is tight enough to exit
    # 2. Volatility is too high
    if (pnl < params['stop_loss_threshold'] and spread <= params['spread_threshold']) or row['3_hour'] > params['volatility_threshold']:
        risk_details['msg'] = (f"STOP LOSS ORDER:: Selling {pos_to_sell} because spread is {spread} and pnl is {pnl} "
                              f"and ratio is {ratio} and 3 hour volatility is {row['3_hour']}")
        log_message(market, "Stop loss Triggered: " + risk_details['msg'])

        # Sell at market best bid to ensure execution
        order['size'] = pos_to_sell
        order['price'] = n_deets['best_bid']

        # Set period to avoid trading after stop-loss
        risk_details['sleep_till'] = str(pd.Timestamp.utcnow().tz_localize(None) + 
                                        pd.Timedelta(hours=params['sleep_period']))

        send_sell_order(order, None, f"STOP LOSS ORDER:: Risking off - SELL {order['size']} @ {order['price']}")
        client.cancel_all_market(market)

        # Save risk details to file
        open(risk_management_filename(market), 'w').write(json.dumps(risk_details))
        return True  # Stop-loss triggered, skip to next iteration
    
    return False  # No stop-loss triggered, continue with normal logic


def handle_take_profit_orders(market, token, order, sell_amount, avgPrice, ask_price, orders, position, params, round_length, yes_no_outcome, best_bid, best_ask):
    """
    Handle take profit sell order management.
    
    Args:
        market: Market identifier
        token: Token identifier
        order: Order object to modify
        sell_amount: Amount to sell
        avgPrice: Average price of position
        ask_price: Current ask price
        orders: Current orders for the token
        position: Current position size
        params: Trading parameters
        round_length: Decimal precision
        yes_no_outcome: Outcome details for token name
        best_bid: Current best bid price
        best_ask: Current best ask price
    """
    order['size'] = sell_amount
    
    # Calculate take-profit price based on average cost
    tp_price = round_up(avgPrice + (avgPrice * params['take_profit_threshold']/100), round_length)
    order['price'] = round_up(tp_price if ask_price < tp_price else ask_price, round_length)
    
    # Calculate market metrics for logging
    mid_price = (best_bid + best_ask) / 2
    spread = round(best_ask - best_bid, 4)
    pnl = (mid_price - avgPrice) / avgPrice * 100 if avgPrice > 0 else 0
    
    tp_price = float(tp_price)
    order_price = float(orders['sell']['price'])
    
    # Calculate % difference between current order and ideal price
    diff = abs(order_price - tp_price)/tp_price * 100

    # Log comprehensive take profit information
    would_be_order = f"SELL {order['size']} @ {order['price']}"
    log_message_deduplicated(
        market, 
        f"{yes_no_outcome['answer']}_take_profit_analysis",
        f"TAKE PROFIT ANALYSIS for {yes_no_outcome['answer']} - Would be: {would_be_order}. "
        f"Mid Price: {mid_price:.4f}, Spread: {spread:.4f}, PnL: {pnl:.2f}%, "
        f"Position: {position}, Sell Amount: {sell_amount}, Avg Price: {avgPrice:.4f}, "
        f"TP Price: {tp_price:.4f}, Current Order Price: {order_price:.4f}, "
        f"Price Diff: {diff:.2f}%, Take Profit Threshold: {params['take_profit_threshold']}%, "
        f"Order Size Coverage: {orders['sell']['size']}/{position * 0.97:.1f}"
    )

    # Update sell order if:
    # 1. Current order price is significantly different from target
    if diff > 2:
        send_sell_order(order, orders, f"TAKE PROFIT ORDER:: Sending Sell Order for {token} because price deviant - NEW: SELL {order['size']} @ {order['price']}, OLD: SELL {orders['sell']['size']} @ {order_price} (diff: {diff}%)")
        return True
    # 2. Current order size is too small for our position
    elif orders['sell']['size'] < position * 0.97:
        send_sell_order(order, orders, f"TAKE PROFIT ORDER:: Sending Sell Order for {token} because not enough sell size - NEW: SELL {order['size']} @ {order['price']}, OLD: SELL {orders['sell']['size']} @ {orders['sell']['price']} (Position: {position})")
        return True

    return False

def apply_merge_positions_logic(client, market, row):
    # ------- POSITION MERGING LOGIC -------
    # Get current positions for both outcomes
    pos_1 = get_position(row['token1'])['size']
    pos_2 = get_position(row['token2'])['size']

    # Calculate if we have opposing positions that can be merged
    amount_to_merge = min(pos_1, pos_2)
    # Only merge if positions are above minimum threshold
    if float(amount_to_merge) > CONSTANTS.MIN_MERGE_SIZE:
        # Get exact position sizes from blockchain for merging
        pos_1 = client.get_position(row['token1'])[0]
        pos_2 = client.get_position(row['token2'])[0]
        amount_to_merge = min(pos_1, pos_2)
        scaled_amt = amount_to_merge / 10 ** 6

        if scaled_amt > CONSTANTS.MIN_MERGE_SIZE:
            log_message(market, f"Position 1 is of size {pos_1} and Position 2 is of size {pos_2}. Merging positions")
            # Execute the merge operation
            client.merge_positions(amount_to_merge, market, row['neg_risk'] == 'TRUE')
            # Update our local position tracking
            set_position(row['token1'], 'SELL', scaled_amt, 0, 'merge')
            set_position(row['token2'], 'SELL', scaled_amt, 0, 'merge')


def base_buy_conditions_met(market, position, buy_amount, row, market_quality_row=None, token=None, orders=None, processed_market_data=None, params=None, order_price=None, mid_price=None, max_spread=None):
    """
    Check if buy conditions are met and return list of failed conditions.
    
    Returns:
        list: Empty list if all conditions met, otherwise list of failure messages
    """
    failed_conditions = []
    
    # Check market quality score first
    if market_quality_row is not None:
        market_quality_score = market_quality_row.get('score', None) if isinstance(market_quality_row, dict) else market_quality_row.iloc[0].get('score', None) if hasattr(market_quality_row, 'iloc') else None
        
        if market_quality_score is None or market_quality_score <= params['min_market_quality']:
            failed_conditions.append(f"Market quality score too low: score={market_quality_score}")
    else:
        failed_conditions.append("Market quality data not available")
    
    if position >= 0.9 * row['trade_size']:
        failed_conditions.append(f"Position exceeds 90% of trade size: position={position}, trade_size={row['trade_size']}")

    if position >= 250:
        failed_conditions.append(f"Position exceeds 250: position={position}")

    if buy_amount <= 0:
        failed_conditions.append(f"Buy amount is not positive: buy_amount={buy_amount}")

    if buy_amount < row['min_size'] and params['buy_under_reward_min_size'] != "YES":
        failed_conditions.append(f"Buy amount below min_size: buy_amount={buy_amount}, min_size={row['min_size']}")

    # Condition 1: Volatility check
    if params is not None and row['3_hour'] > params['volatility_threshold']:
        failed_conditions.append(f"3 Hour Volatility of {row['3_hour']} is greater than max volatility of {params['volatility_threshold']}")

    # Condition 2: Reverse position check
    if token is not None:
        rev_token = global_state.REVERSE_TOKENS[str(token)]
        rev_pos = get_position(rev_token)
        
        if rev_pos['size'] > row['trade_size']:
            failed_conditions.append(f"Reverse position too large: size={rev_pos['size']}, trade_size={row['trade_size']}")

    # Condition 3: Overall ratio check
    if processed_market_data is not None:
        try:
            overall_ratio = (processed_market_data['bid_sum_within_n_percent']) / (processed_market_data['ask_sum_within_n_percent'])
        except:
            overall_ratio = 0
        
        if overall_ratio < 0:
            failed_conditions.append(f"Overall ratio is negative: ratio={overall_ratio}")

    # Condition 4: Price validation checks
    if order_price is not None and mid_price is not None and max_spread is not None:
        # Check incentive start price threshold
        incentive_start = mid_price - max_spread/100
        if order_price < incentive_start:
            failed_conditions.append(f"Order price below incentive threshold: price={order_price} < {incentive_start}, mid_price={mid_price}")
        
        # Check price range (0.1 to 0.9)
        if not (order_price >= 0.1 and order_price < 0.9):
            failed_conditions.append(f"Order price outside acceptable range (0.1-0.9): price={order_price}")

    return failed_conditions

def send_buy_order_if_needed(market, row, processed_market_data, yes_no_outcome, order, buy_amount, bid_price, round_length, market_quality_row, market_making):
    if market_making == 'EXIT':
        log_message_deduplicated(market, "market_making_exit", 'Market making EXIT mode. Will not send buy orders.')
        return

    risk_file_name = risk_management_filename(market)
    client = global_state.client
    params = global_state.params[row['param_type']]
    token = int(yes_no_outcome['token'])
    best_bid = processed_market_data['best_bid']
    # Get current orders for this token
    orders = get_order(token)
    order['size'] = buy_amount
    order['price'] = bid_price

    position = round_down(get_position(token)['size'], 2)

    failed_conditions = base_buy_conditions_met(market, position, buy_amount, row, market_quality_row, token, orders, processed_market_data, params, order['price'], order['mid_price'], order['max_spread'])
    if failed_conditions:
        # Log all failed conditions in a single message with duplicate detection
        conditions_text = "; ".join(failed_conditions)
        would_be_order = f"BUY {order['size']} @ {order['price']}"
        log_message_deduplicated(market, f"buy_failed_conditions_{yes_no_outcome['answer']}", f"Buy order conditions for {yes_no_outcome['answer']} not met - Would be: {would_be_order}. Reasons: {conditions_text}")
        return False



    # ------- RISK-OFF PERIOD CHECK -------
    # If we're in a risk-off period (after stop-loss), don't buy
    if os.path.isfile(risk_file_name):
        risk_details = json.load(open(risk_file_name))

        start_trading_at = pd.to_datetime(risk_details['sleep_till'])
        current_time = pd.Timestamp.utcnow().tz_localize(None)

        if current_time < start_trading_at:
            # Log with deduplication - only stable parts of the message
            would_be_order = f"BUY {order['size']} @ {order['price']}"
            log_message_deduplicated(
                market, 
                f"buy_risk_off_check_{yes_no_outcome['answer']}", 
                f"Not sending a buy order for {yes_no_outcome['answer']} because recently risked off - Would be: {would_be_order}. Sleep until {risk_details['sleep_till']}"
            )
            return False



    # Place new buy order if any of these conditions are met:
    # 1. We can get a better price than current order
    if best_bid > orders['buy']['price']:
        send_buy_order(order, orders, f"Sending Buy Order for {yes_no_outcome['answer']} [{token}] - NEW: BUY {order['size']} @ {best_bid}, OLD: BUY {orders['buy']['size']} @ {orders['buy']['price']}")
    # 2. Current position + orders is not enough to reach target
    elif position + orders['buy']['size'] < 0.95 * row['trade_size']:
        send_buy_order(order, orders, f"Sending Buy Order for {yes_no_outcome['answer']} [{token}] because not enough position + size - NEW: BUY {order['size']} @ {bid_price}, OLD: BUY {orders['buy']['size']} @ {orders['buy']['price']}")
    # 3. Our current order is too large and needs to be resized
    elif orders['buy']['size'] > order['size'] * 1.01:
        send_buy_order(order, orders, f"Resending buy orders for {yes_no_outcome['answer']} [{token}] because open orders are too large - NEW: BUY {order['size']} @ {bid_price}, OLD: BUY {orders['buy']['size']} @ {orders['buy']['price']}")

    return True
    # Commented out logic for cancelling orders when market conditions change
    # elif best_bid_size < orders['buy']['size'] * 0.98 and abs(best_bid - second_best_bid) > 0.03:
    #     print(f"Cancelling buy orders because best size is less than 90% of open orders and spread is too large")
    #     global_state.client.cancel_all_asset(order['token'])


def risk_management_filename(market):
    return 'positions/' + str(market) + '.json'