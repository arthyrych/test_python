# Config variables
BASE_URL = "https://fapi.binance.com" # Futures

# Requests
recvWindow = 10000 # Increase recvWindow for buffer
retries = 3 # Amount of request retries
delay = 2 # Amount of seconds between request retries

# Trading
symbol = 'BTCUSDT'
leverage = 20
position_size = 140  # USDT
min_quantity = 0.002 # Minimum quantity for BTCUSDT
round_tick_size = 1 # Tick size requirements
stop_loss_percentage = 0.005  # 0.5%
take_profit_percentage = 0.05  # 5%