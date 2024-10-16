import secrets
import ccxt
import time

# Initialize Binance API connection
binance = ccxt.binance({
    'apiKey': secrets.API_KEY,  # API key
    'secret': secrets.SECRET_KEY,  # API secret
    'options': {
        'defaultType': 'future',  # Ensure you're using the Binance Futures market
    }
})

# Synchronize system time with Binance server time
binance.load_time_difference()

# Test connection by fetching balance
try:
    balance = binance.fetch_balance()
    print(balance)
except Exception as e:
    print(f"Error fetching balance: {e}")
