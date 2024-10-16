import secrets
import ccxt

# Initialize Binance API connection
binance = ccxt.binance({
    'apiKey': 'your_api_key',  # Replace with your actual Binance API key
    'secret': 'your_api_secret',  # Replace with your actual Binance API secret
    'options': {
        'defaultType': 'future',  # Ensure you're using the Binance Futures market
    }
})

# Test
print(secrets.API_KEY)

# Test connection by fetching balance
# balance = binance.fetch_balance()
# print(balance)
