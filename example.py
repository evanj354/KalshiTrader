import os
import json
from dotenv import load_dotenv
from kalshi_client import KalshiTrader, KalshiMarketData, Environment

def main():
    """
    Example script to demonstrate the usage of the Kalshi client components.
    
    This script loads credentials from a .env file, instantiates the clients,
    and provides examples of how to place trades and fetch market data.
    """
    load_dotenv()

    is_production = os.environ.get("IS_PRODUCTION", "False").lower() == "true"
    
    if is_production:
        api_key_id = os.environ.get("PROD_API_KEY_ID")
        private_key_path = os.environ.get("PROD_PRIVATE_KEY_PATH")
        environment = Environment.PROD
        print("Using PRODUCTION environment")
    else:
        api_key_id = os.environ.get("DEMO_API_KEY_ID")
        private_key_path = os.environ.get("DEMO_PRIVATE_KEY_PATH")
        environment = Environment.DEMO
        print("Using DEMO environment")

    if not api_key_id or not private_key_path:
        print("Error: Ensure API_KEY_ID and PRIVATE_KEY_PATH are in your .env file.")
        return
    
    contracts_per_order = int(os.environ.get("CONTRACTS_PER_ORDER", "100"))

    # --- Market Data Initialization and Usage ---
    print("--- Initializing KalshiMarketData ---")
    try:
        market_data_client = KalshiMarketData(
            key_id=api_key_id,
            private_key_path=private_key_path,
            environment=environment
        )
        
        trader_client = KalshiTrader(
            key_id=api_key_id,
            private_key_path=private_key_path,
            environment=environment
        )

        # --- Test get_markets() API ---
        series_tickers = ['KXNHLTOTAL', 'KXNHLSPREAD']#['KXNBASPREAD', 'KXNBATOTAL']#['KXNCAAMBSPREAD', 'KXNCAAMBTOTAL']
        
        for series_ticker in series_tickers:
            print(f"\n--- Processing series: {series_ticker} ---")
            
            for markets_batch in market_data_client.get_markets_paginated(series_ticker=series_ticker, status='open'):
                print(f"\nProcessing batch of {len(markets_batch)} markets...")
                
                for market in markets_batch:
                    # print(market)
                    # Skip live markets - check if expected_expiration_time is at least 27 hours in the future
                    expected_expiration = market.get('expected_expiration_time')
                    if expected_expiration:
                        from datetime import datetime, timedelta
                        exp_dt = datetime.fromisoformat(expected_expiration.replace('Z', '+00:00'))
                        min_future_time = datetime.now(exp_dt.tzinfo) + timedelta(hours=4)
                        if exp_dt < min_future_time:
                            print(f"Skipping market (less than 4h away): {market.get('title')}")
                            continue
                    
                    ticker = market.get('ticker')
                    title = market.get('title')
                    yes_bid = market.get('yes_bid')
                    yes_ask = market.get('yes_ask')
                    no_bid = market.get('no_bid')
                    no_ask = market.get('no_ask')
                    
                    if yes_bid is not None and yes_ask is not None:
                        spread = yes_ask - yes_bid
                        print(f"\n{title} ({ticker}): yes_bid = {yes_bid}, yes_ask = {yes_ask}, spread = {spread}")
                        
                        # Calculate expiration timestamp (4 hours before event starts) in SECONDS
                        from datetime import datetime, timedelta
                        exp_dt = datetime.fromisoformat(expected_expiration.replace('Z', '+00:00'))
                        order_expiration_dt = exp_dt - timedelta(hours=4)
                        expiration_ts = int(order_expiration_dt.timestamp())
                        
                        # Set bid_price based on spread for YES side
                        if spread < 10 and spread > 0:
                            yes_bid_price = yes_bid - 1
                            print(f"  YES: Spread < 10, bidding below at {yes_bid_price}")
                        else:
                            yes_bid_price = yes_bid + 1
                            print(f"  YES: Spread >= 10, bidding above at {yes_bid_price}")
                        
                        if 1 <= yes_bid_price <= 99:
                            try:
                                print(f"  Placing YES buy order at {yes_bid_price} cents...")
                                order_response = trader_client.buy_yes(ticker, count=contracts_per_order, limit_price_cents=yes_bid_price, expiration_ts=expiration_ts)
                                print(f"  ✅ Order placed: {order_response}")
                            except Exception as e:
                                print(f"  ❌ Failed to place YES order: {e}")
                        else:
                            print(f"  ⚠️ YES bid price {yes_bid_price} out of range (1-99)")
                    
                    if no_bid is not None and no_ask is not None:
                        no_spread = no_ask - no_bid
                        print(f"  no_bid = {no_bid}, no_ask = {no_ask}, no_spread = {no_spread}")
                        
                        # Calculate expiration timestamp (4 hours before event starts) in SECONDS
                        from datetime import datetime, timedelta
                        exp_dt = datetime.fromisoformat(expected_expiration.replace('Z', '+00:00'))
                        order_expiration_dt = exp_dt - timedelta(hours=4)
                        expiration_ts = int(order_expiration_dt.timestamp())
                        
                        # Set bid_price based on spread for NO side
                        if no_spread < 10 and no_spread > 0:
                            no_bid_price = no_bid - 1
                            print(f"  NO: Spread < 10, bidding below at {no_bid_price}")
                        else:
                            no_bid_price = no_bid + 1
                            print(f"  NO: Spread >= 10, bidding above at {no_bid_price}")
                        
                        if 1 <= no_bid_price <= 99:
                            try:
                                print(f"  Placing NO buy order at {no_bid_price} cents...")
                                order_response = trader_client.buy_no(ticker, count=contracts_per_order, limit_price_cents=no_bid_price, expiration_ts=expiration_ts)
                                print(f"  ✅ Order placed: {order_response}")
                            except Exception as e:
                                print(f"  ❌ Failed to place NO order: {e}")
                        else:
                            print(f"  ⚠️ NO bid price {no_bid_price} out of range (1-99)")
                    
                    if (yes_bid is None or yes_ask is None) and (no_bid is None or no_ask is None):
                        print(f"\n{title} ({ticker}): Missing bid/ask data")
        
    except Exception as e:
        print(f"Failed to initialize or use KalshiMarketData: {e}")


if __name__ == "__main__":
    main()
