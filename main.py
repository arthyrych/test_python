import secrets
import requests
import time
from datetime import datetime, timedelta, timezone
import hmac
import hashlib


# Binance API base URL
BASE_URL = "https://fapi.binance.com"


# Generate a signature for the API request
def generate_signature(query_string, secret_key):
    return hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()


# Send a request to the Binance API
def send_signed_request(http_method, url_path, payload=None):
    if payload is None:
        payload = {}

    global time_offset
    # Add timestamp and signature
    payload['timestamp'] = int(time.time() * 1000) + time_offset
    query_string = '&'.join([f"{key}={value}" for key, value in payload.items()])
    signature = generate_signature(query_string, secrets.SECRET_KEY)
    payload['signature'] = signature

    headers = {
        'X-MBX-APIKEY': secrets.API_KEY
    }

    url = BASE_URL + url_path
    if http_method == "GET":
        response = requests.get(url, headers=headers, params=payload)
    elif http_method == "POST":
        response = requests.post(url, headers=headers, params=payload)
    elif http_method == "DELETE":
        response = requests.delete(url, headers=headers, params=payload)
    
    return response.json()


# Global variable to store the time difference (in milliseconds)
time_offset = 0


# Function to fetch server time difference (optional but good practice)
def get_server_time():
    response = requests.get(BASE_URL + "/fapi/v1/time").json()
    return response['serverTime']


# Calculate time difference with Binance server time
def calculate_time_offset():
    global time_offset
    server_time = get_server_time()
    local_time = int(time.time() * 1000)
    time_offset = server_time - local_time
    print(f"- Time offset with Binance server: {time_offset} ms")


# Fetch the current time in UTC (timezone-aware)
def get_current_time():
    return datetime.now(timezone.utc)


# DEBUG
# def calculate_next_position_time():
#     now = get_current_time()
#     next_position_time = now + timedelta(seconds=30)  # Adjust for faster testing
#     return next_position_time

# Calculate the next 16:00:05 UTC time
def calculate_next_position_time():
    now = get_current_time()
    next_position_time = now.replace(hour=16, minute=0, second=2, microsecond=0)

    if now >= next_position_time:
        next_position_time += timedelta(days=1)  # Move to next day if current time has passed 16:00:05 today
    
    return next_position_time


# Function to fetch balance from Binance Futures account
def get_balance():
    return send_signed_request("GET", "/fapi/v2/balance")


# Adjust price based on the tick size for BTCUSDT (0.10 for this pair)
def round_to_tick_size(price, tick_size=0.10):
    return round(price / tick_size) * tick_size


# Check the account position mode (One-Way or Hedge Mode)
def get_position_mode():
    response = send_signed_request("GET", "/fapi/v1/positionSide/dual")
    if response.get('dualSidePosition', None):
        return "HEDGE"
    return "ONE-WAY"


# Function to open a position based on the last 4H candle (12:00-16:00 UTC)
def open_position():
    symbol = 'BTCUSDT'
    leverage = 20  # Leverage
    position_size = 140  # USDT
    stop_loss_percentage = 0.005  # 0.5%
    take_profit_percentage = 0.05  # 5%

    try:
        # Fetch balance
        balance = get_balance()
        if isinstance(balance, list):
            usdt_balance = float(next(b['availableBalance'] for b in balance if b['asset'] == 'USDT'))
        else:
            raise Exception(f"Unexpected balance response format: {balance}")
        
        print(f"- Available USDT: {usdt_balance}")

        # Set leverage
        leverage_payload = {'symbol': symbol, 'leverage': leverage}
        leverage_response = send_signed_request("POST", "/fapi/v1/leverage", leverage_payload)
        print(f"- Leverage set: {leverage_response}")

        # Fetch last 4H candle data
        params = {'symbol': symbol, 'interval': '4h', 'limit': 2}
        ohlcv_response = requests.get(BASE_URL + "/fapi/v1/klines", params=params)

        if ohlcv_response.status_code != 200:
            raise Exception(f"Failed to fetch OHLCV data: {ohlcv_response.text}")

        ohlcv = ohlcv_response.json()

        if isinstance(ohlcv, list) and len(ohlcv) >= 2:
            last_candle = ohlcv[-2]
            open_price, close_price = float(last_candle[1]), float(last_candle[4])
        else:
            raise Exception(f"Unexpected OHLCV response format: {ohlcv}")

        print(f"- Fetched OHLCV data: {ohlcv}")

        # Determine long or short position
        direction = 'short' if close_price > open_price else 'long'
        print(f"- Opening {direction} position")

        # Stop-loss and take-profit levels
        entry_price = close_price
        stop_loss = entry_price * (1 - stop_loss_percentage) if direction == 'long' else entry_price * (1 + stop_loss_percentage)
        take_profit = entry_price * (1 + take_profit_percentage) if direction == 'long' else entry_price * (1 - take_profit_percentage)

        # Adjust prices to meet tick size requirements
        stop_loss = round_to_tick_size(stop_loss)
        take_profit = round_to_tick_size(take_profit)

        print(f"- Entry Price: {entry_price}, Stop-Loss: {stop_loss}, Take-Profit: {take_profit}")

        # Ensure enough balance to open position
        margin_required = position_size / leverage
        if usdt_balance >= margin_required:
            side = 'BUY' if direction == 'long' else 'SELL'
            quantity = round(position_size / close_price, 3)  # Round quantity to 3 decimals for BTCUSDT

            print(f"- Quantity to trade: {quantity} BTC")

            # Get the position mode
            position_mode = get_position_mode()

            # Place market order
            order_payload = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': quantity
            }

            # Only specify positionSide if in HEDGE mode
            if position_mode == "HEDGE":
                order_payload['positionSide'] = 'LONG' if direction == 'long' else 'SHORT'

            order_response = send_signed_request("POST", "/fapi/v1/order", order_payload)
            print(f"- Position opened: {order_response}")

            # Place a stop-loss and take-profit order separately
            if order_response.get('orderId'):
                # Place stop-loss order (STOP_MARKET)
                stop_loss_payload = {
                    'symbol': symbol,
                    'side': 'SELL' if direction == 'long' else 'BUY',
                    'quantity': quantity,
                    'type': 'STOP_MARKET',
                    'stopPrice': str(stop_loss),
                    'timeInForce': 'GTC'
                }

                # Only specify positionSide if in HEDGE mode
                if position_mode == "HEDGE":
                    stop_loss_payload['positionSide'] = 'LONG' if direction == 'long' else 'SHORT'

                stop_loss_response = send_signed_request("POST", "/fapi/v1/order", stop_loss_payload)
                print(f"- Stop-Loss order placed: {stop_loss_response}")

                # Place take-profit order (LIMIT)
                take_profit_payload = {
                    'symbol': symbol,
                    'side': 'SELL' if direction == 'long' else 'BUY',
                    'quantity': quantity,
                    'type': 'LIMIT',
                    'price': str(take_profit),
                    'timeInForce': 'GTC',
                }

                # Only specify positionSide if in HEDGE mode
                if position_mode == "HEDGE":
                    take_profit_payload['positionSide'] = 'LONG' if direction == 'long' else 'SHORT'

                take_profit_response = send_signed_request("POST", "/fapi/v1/order", take_profit_payload)
                print(f"- Take-Profit order placed: {take_profit_response}")

        else:
            print(f"- Insufficient USDT balance to open a {direction} position. Required margin: {margin_required} USDT.")
    
    except Exception as e:
        print(f"- Error fetching candles or opening position: {e}")


# Main script logic
def main():
    calculate_time_offset()  # Adjust the time offset at the start of the script
    while True:
        next_position_time = calculate_next_position_time()
        print(f"\n- Next position opening time: {next_position_time}")
        
        while get_current_time() < next_position_time:
            if int(get_current_time().strftime("%S")) % 1 == 0: # Frequency about waiting and current time
                print(f"- Waiting for: {next_position_time}. Current time: {get_current_time()}\n")
            time.sleep(1)  # Amount of seconds before running again

        print("- Opening position...")
        open_position()

if __name__ == "__main__":
    main()
