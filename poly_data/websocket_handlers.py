import asyncio                      # Asynchronous I/O
import json                        # JSON handling
import websockets                  # WebSocket client
import traceback                   # Exception handling

from poly_data.data_processing import process_data, process_user_data
import poly_data.global_state as global_state

async def connect_market_websocket(chunk):
    """
    Connect to Polymarket's market WebSocket API and process market updates.
    
    This function:
    1. Establishes a WebSocket connection to the Polymarket API
    2. Subscribes to updates for a specified list of market tokens
    3. Processes incoming order book and price updates
    4. Automatically reconnects on connection loss with exponential backoff

    Args:
        chunk (list): List of token IDs to subscribe to
        
    Notes:
        This function runs indefinitely and will automatically reconnect
        if the WebSocket connection is lost or encounters an error.
    """
    uri = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    retry_delay = 5  # Initial retry delay in seconds
    max_retry_delay = 300  # Maximum retry delay (5 minutes)

    while True:  # Retry loop - runs forever
        try:
            print(f"\n[Market WS] Connecting to {uri}...")
            async with websockets.connect(uri, ping_interval=5, ping_timeout=None) as websocket:
                # Prepare and send subscription message
                message = {"assets_ids": chunk}
                await websocket.send(json.dumps(message))

                print(f"[Market WS] Connected! Subscribed to {len(chunk)} markets")

                # Reset retry delay on successful connection
                retry_delay = 5

                # Process incoming market data indefinitely
                while True:
                    message = await websocket.recv()
                    json_data = json.loads(message)
                    # Process order book updates and trigger trading as needed
                    process_data(json_data)

        except websockets.ConnectionClosed as e:
            print(f"[Market WS] Connection closed: {e}")
            print(f"[Market WS] Reconnecting in {retry_delay} seconds...")
        except asyncio.exceptions.IncompleteReadError as e:
            print(f"[Market WS] Incomplete read error (connection dropped): {e}")
            print(f"[Market WS] Reconnecting in {retry_delay} seconds...")
        except Exception as e:
            print(f"[Market WS] Unexpected exception: {e}")
            print(traceback.format_exc())
            print(f"[Market WS] Reconnecting in {retry_delay} seconds...")

        # Wait before reconnecting
        await asyncio.sleep(retry_delay)

        # Exponential backoff: increase delay for next retry (cap at max)
        retry_delay = min(retry_delay * 1.5, max_retry_delay)

async def connect_user_websocket():
    """
    Connect to Polymarket's user WebSocket API and process order/trade updates.
    
    This function:
    1. Establishes a WebSocket connection to the Polymarket user API
    2. Authenticates using API credentials
    3. Processes incoming order and trade updates for the user
    4. Automatically reconnects on connection loss with exponential backoff

    Notes:
        This function runs indefinitely and will automatically reconnect
        if the WebSocket connection is lost or encounters an error.
    """
    uri = "wss://ws-subscriptions-clob.polymarket.com/ws/user"
    retry_delay = 5  # Initial retry delay in seconds
    max_retry_delay = 300  # Maximum retry delay (5 minutes)

    while True:  # Retry loop - runs forever
        try:
            print(f"\n[User WS] Connecting to {uri}...")
            async with websockets.connect(uri, ping_interval=5, ping_timeout=None) as websocket:
                # Prepare authentication message with API credentials
                message = {
                    "type": "user",
                    "auth": {
                        "apiKey": global_state.client.client.creds.api_key,
                        "secret": global_state.client.client.creds.api_secret,
                        "passphrase": global_state.client.client.creds.api_passphrase
                    }
                }

                # Send authentication message
                await websocket.send(json.dumps(message))

                print(f"[User WS] Connected and authenticated!")

                # Reset retry delay on successful connection
                retry_delay = 5

                # Process incoming user data indefinitely
                while True:
                    message = await websocket.recv()
                    json_data = json.loads(message)
                    # Process trade and order updates
                    process_user_data(json_data)

        except websockets.ConnectionClosed as e:
            print(f"[User WS] Connection closed: {e}")
            print(f"[User WS] Reconnecting in {retry_delay} seconds...")
        except asyncio.exceptions.IncompleteReadError as e:
            print(f"[User WS] Incomplete read error (connection dropped): {e}")
            print(f"[User WS] Reconnecting in {retry_delay} seconds...")
        except Exception as e:
            print(f"[User WS] Unexpected exception: {e}")
            print(traceback.format_exc())
            print(f"[User WS] Reconnecting in {retry_delay} seconds...")

        # Wait before reconnecting
        await asyncio.sleep(retry_delay)

        # Exponential backoff: increase delay for next retry (cap at max)
        retry_delay = min(retry_delay * 1.5, max_retry_delay)
