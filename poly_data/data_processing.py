
import json
from sortedcontainers import SortedDict
import poly_data.global_state as global_state
import poly_data.CONSTANTS as CONSTANTS

from poly_data.log_utils import log_message
from trading import perform_trade
import time
import asyncio
from poly_data.data_utils import set_position, set_order, update_positions
import json

def process_book_data(asset, json_data):
    global_state.all_data[asset] = {
        'asset_id': json_data['asset_id'],  # token_id for the Yes token
        'bids': SortedDict(),
        'asks': SortedDict()
    }

    global_state.all_data[asset]['bids'].update({float(entry['price']): float(entry['size']) for entry in json_data['bids']})
    global_state.all_data[asset]['asks'].update({float(entry['price']): float(entry['size']) for entry in json_data['asks']})

def process_price_change(asset, asset_id, side, price_level, new_size):
    if asset_id != global_state.all_data[asset]['asset_id']:
        return  # skip updates for the No token to prevent duplicated updates
    if side == 'bids':
        book = global_state.all_data[asset]['bids']
    else:
        book = global_state.all_data[asset]['asks']

    if new_size == 0:
        if price_level in book:
            del book[price_level]
    else:
        book[price_level] = new_size

def process_data(json_datas, trade=True):
    # Convert single dict to list if needed
    if isinstance(json_datas, dict):
        json_datas = [json_datas]

    for json_data in json_datas:
        event_type = json_data['event_type']
        asset = json_data['market']

        if event_type == 'book':
            process_book_data(asset, json_data)

            if trade:
                asyncio.create_task(perform_trade(asset))
                
        elif event_type == 'price_change':
            asset_id = json_data.get('asset_id')  # Get asset_id from the event data
            for data in json_data['price_changes']:
                side = 'bids' if data['side'] == 'BUY' else 'asks'
                price_level = float(data['price'])
                new_size = float(data['size'])
                # Use asset_id from data if available, otherwise from json_data
                data_asset_id = data.get('asset_id', asset_id)
                process_price_change(asset, data_asset_id, side, price_level, new_size)

                if trade:
                    asyncio.create_task(perform_trade(asset))
        

        # pretty_log_message(market,f'Received book update for {asset}:', global_state.all_data[asset])

def add_to_performing(col, id):
    if col not in global_state.performing:
        global_state.performing[col] = set()
    
    if col not in global_state.performing_timestamps:
        global_state.performing_timestamps[col] = {}

    # Add the trade ID and track its timestamp
    global_state.performing[col].add(id)
    global_state.performing_timestamps[col][id] = time.time()

def remove_from_performing(col, id):
    if col in global_state.performing:
        global_state.performing[col].discard(id)

    if col in global_state.performing_timestamps:
        global_state.performing_timestamps[col].pop(id, None)

def process_user_data(rows):
    if isinstance(rows, dict):
        rows = [rows]

    for row in rows:
        market = row['market']
        log_message(market, "PROCESS USER DATA: " +json.dumps(row))
        side = row['side'].lower()
        token = row['asset_id']
            
        if token in global_state.REVERSE_TOKENS:     
            col = token + "_" + side

            if row['event_type'] == 'trade':
                size = 0
                price = 0
                maker_outcome = ""
                taker_outcome = row['outcome']

                is_user_maker = False
                for maker_order in row['maker_orders']:
                    if maker_order['maker_address'].lower() == global_state.client.browser_wallet.lower():
                        log_message(market,"User is maker")
                        size = float(maker_order['matched_amount'])
                        price = float(maker_order['price'])
                        
                        is_user_maker = True
                        maker_outcome = maker_order['outcome'] #this is curious

                        if maker_outcome == taker_outcome:
                            side = 'buy' if side == 'sell' else 'sell' #need to reverse as we reverse token too
                        else:
                            token = global_state.REVERSE_TOKENS[token]
                
                if not is_user_maker:
                    size = float(row['size'])
                    price = float(row['price'])
                    log_message(market,"User is taker")

                # Format trade event in a pretty table format
                log_message(market,
                    f"\n{'='*80}\n"
                    f"TRADE EVENT: {row['market'][:50]}\n"
                    f"{'-'*80}\n"
                    f"{'ID':<20} {row['id']}\n"
                    f"{'STATUS':<20} {row['status']}\n"
                    f"{'SIDE (raw)':<20} {row['side']}\n"
                    f"{'SIDE (processed)':<20} {side.upper()}\n"
                    f"{'MAKER OUTCOME':<20} {maker_outcome if maker_outcome else 'N/A'}\n"
                    f"{'TAKER OUTCOME':<20} {taker_outcome}\n"
                    f"{'SIZE':<20} {size:.2f}\n"
                    f"{'PRICE':<20} ${float(row['price']):.3f}\n"
                    f"{'TOKEN':<20} {token[:16]}...\n"
                    f"{'='*80}"
                )


                if row['status'] == 'CONFIRMED' or row['status'] == 'FAILED' :
                    if row['status'] == 'FAILED':
                        log_message(market, f"Trade failed for {token}, decreasing")
                        asyncio.create_task(asyncio.sleep(2))
                        update_positions()
                    else:
                        remove_from_performing(col, row['id'])
                        log_message(market, "Confirmed. Performing is ", len(global_state.performing[col]))
                        log_message(market, "Last trade update is ", global_state.last_trade_update)
                        log_message(market, "Performing is ", global_state.performing)
                        log_message(market, "Performing timestamps is ", global_state.performing_timestamps)
                        
                        asyncio.create_task(perform_trade(market))

                elif row['status'] == 'MATCHED':
                    add_to_performing(col, row['id'])

                    log_message(market, "Matched. Performing is ", len(global_state.performing[col]))
                    set_position(token, side, size, price)
                    log_message(market, "Position after matching is ", global_state.positions[str(token)])
                    log_message(market, "Last trade update is ", global_state.last_trade_update)
                    log_message(market, "Performing is ", global_state.performing)
                    log_message(market, "Performing timestamps is ", global_state.performing_timestamps)
                    asyncio.create_task(perform_trade(market))
                elif row['status'] == 'MINED':
                    remove_from_performing(col, row['id'])

            elif row['event_type'] == 'order':
                # Format order event in a pretty table format
                remaining_size = float(row['original_size']) - float(row['size_matched'])
                log_message(market,
                    f"\n{'='*80}\n"
                    f"ORDER EVENT: {row['market'][:50]}\n"
                    f"{'-'*80}\n"
                    f"{'STATUS':<20} {row['status']}\n"
                    f"{'TYPE':<20} {row['type']}\n"
                    f"{'SIDE':<20} {side.upper()}\n"
                    f"{'ORIGINAL SIZE':<20} {float(row['original_size']):.2f}\n"
                    f"{'SIZE MATCHED':<20} {float(row['size_matched']):.2f}\n"
                    f"{'REMAINING SIZE':<20} {remaining_size:.2f}\n"
                    f"{'PRICE':<20} ${float(row['price']):.3f}\n"
                    f"{'TOKEN':<20} {token[:16]}...\n"
                    f"{'='*80}"
                )

                set_order(token, side, remaining_size, row['price'])
                asyncio.create_task(perform_trade(market))

        else:
            log_message(market, f"User date received for {market} but its not in global_state.REVERSE_TOKENS")