import math
from poly_data.data_utils import update_positions
import poly_data.global_state as global_state


# def get_avgPrice(position, assetId):
#     curr_global = global_state.all_positions[global_state.all_positions['asset'] == str(assetId)]
#     api_position_size = 0
#     api_avgPrice = 0

#     if len(curr_global) > 0:
#         c_row = curr_global.iloc[0]
#         api_avgPrice = round(c_row['avgPrice'], 2)
#         api_position_size = c_row['size']

#     if position > 0:
#         if abs((api_position_size - position)/position * 100) > 5:
#             print("Updating global positions")
#             update_positions()

#             try:
#                 c_row = curr_global.iloc[0]
#                 api_avgPrice = round(c_row['avgPrice'], 2)
#                 api_position_size = c_row['size']
#             except:
#                 return 0
#     return api_avgPrice

def get_best_bid_ask_deets(market, name, size, deviation_threshold=0.05):
    best_bid, best_bid_size, second_best_bid, second_best_bid_size, top_bid = find_best_price_with_size(
        global_state.all_data[market]['bids'], size, reverse=True)
    best_ask, best_ask_size, second_best_ask, second_best_ask_size, top_ask = find_best_price_with_size(
        global_state.all_data[market]['asks'], size, reverse=False)

    mid_price = (best_bid + best_ask) / 2

    bid_sum_within_n_percent = sum(size for price, size in global_state.all_data[market]['bids'].items() if
                                   best_bid <= price <= mid_price * (1 + deviation_threshold))
    ask_sum_within_n_percent = sum(size for price, size in global_state.all_data[market]['asks'].items() if
                                   mid_price * (1 - deviation_threshold) <= price <= best_ask)

    if name == 'token2':
        best_bid, second_best_bid, top_bid, best_ask, second_best_ask, top_ask = 1 - best_ask, 1 - second_best_ask, 1 - top_ask, 1 - best_bid, 1 - second_best_bid, 1 - top_bid
        best_bid_size, second_best_bid_size, best_ask_size, second_best_ask_size = best_ask_size, second_best_ask_size, best_bid_size, second_best_bid_size
        bid_sum_within_n_percent, ask_sum_within_n_percent = ask_sum_within_n_percent, bid_sum_within_n_percent

    # return as dictionary
    return {
        'best_bid': best_bid,
        'best_bid_size': best_bid_size,
        'second_best_bid': second_best_bid,
        'second_best_bid_size': second_best_bid_size,
        'top_bid': top_bid,
        'best_ask': best_ask,
        'best_ask_size': best_ask_size,
        'second_best_ask': second_best_ask,
        'second_best_ask_size': second_best_ask_size,
        'top_ask': top_ask,
        'bid_sum_within_n_percent': bid_sum_within_n_percent,
        'ask_sum_within_n_percent': ask_sum_within_n_percent
    }


# TODO: Shouldn't we aggregate the order book/ Why do I serach for one individual order of my min-size?
def find_best_price_with_size(price_dict, min_size, reverse=False):
    lst = list(price_dict.items())

    if reverse:
        lst.reverse()

    best_price, best_size = None, None
    second_best_price, second_best_size = None, None
    top_price = None
    set_best = False

    for price, size in lst:
        if top_price is None:
            top_price = price

        if set_best:
            second_best_price, second_best_size = price, size
            break

        if size > min_size:
            if best_price is None:
                best_price, best_size = price, size
                set_best = True

    return best_price, best_size, second_best_price, second_best_size, top_price


def get_order_prices(best_bid, best_bid_size, top_bid, best_ask, best_ask_size, top_ask, avgPrice, row):
    # Place orders just inside the current best bid/ask spread to get priority while still making a profit on the spread.
    bid_price = best_bid + row['tick_size']
    ask_price = best_ask - row['tick_size']

    # If there's insufficient liquidity at the best price (less than 1.5x your minimum size),
    # match the best price instead of improving it.
    # This prevents you from stepping ahead of very thin liquidity that might disappear.
    if best_bid_size < row['min_size'] * 1.5:
        bid_price = best_bid

    if best_ask_size < 250 * 1.5:
        ask_price = best_ask

    # Prevent crossed markets where your bid ≥ best ask or your ask ≤ best bid.
    # This would result in immediate execution at unfavorable prices.
    if bid_price >= top_ask:
        bid_price = top_bid

    if ask_price <= top_bid:
        ask_price = top_ask

    # If your calculated prices are identical, fall back to the market's natural bid/ask
    if bid_price == ask_price:
        bid_price = top_bid
        ask_price = top_ask

    # If you have a position (avgPrice > 0), don't sell below your average cost.
    if ask_price <= avgPrice and avgPrice > 0:
        ask_price = avgPrice

    return bid_price, ask_price


def round_down(number, decimals):
    factor = 10 ** decimals
    return math.floor(number * factor) / factor


def round_up(number, decimals):
    factor = 10 ** decimals
    return math.ceil(number * factor) / factor


def get_buy_sell_amount(position, bid_price, row):
    sell_amount = position
    buy_amount = row['trade_size'] - position

    if buy_amount > 0.7 * row['min_size'] and buy_amount < row['min_size']:
        buy_amount = row['min_size']

    if bid_price < 0.1:

        if 'multiplier' in row and row['multiplier'] != '':
            print(f"Multiplying buy amount by {int(row['multiplier'])}")
            buy_amount = buy_amount * int(row['multiplier'])

    return buy_amount, sell_amount
