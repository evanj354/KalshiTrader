import os
import time
import math
from datetime import datetime, timedelta
from dotenv import load_dotenv
from kalshi_client import KalshiTrader, KalshiMarketData, Environment

def should_trade_market(market):
    """Check if market is eligible for trading."""
    expected_expiration = market.get('expected_expiration_time')
    if not expected_expiration:
        return False
    
    exp_dt = datetime.fromisoformat(expected_expiration.replace('Z', '+00:00'))
    now = datetime.now(exp_dt.tzinfo)
    
    # Only trade markets expiring within next 4 hours
    if exp_dt > now + timedelta(hours=4):
        return False
    
    # Skip markets expiring in less than 1 hour 30 minutes
    if 'NHL' in market.get('ticker'):
        if exp_dt < now + timedelta(hours=1):
            return False
    else:
        if exp_dt < now + timedelta(hours=1, minutes=30):
            return False
    
    
    return True

def calculate_order_expiration(order_expiry_minutes):
    """Calculate order expiration based on configurable minutes from now."""
    order_exp = datetime.now() + timedelta(minutes=order_expiry_minutes)
    return int(order_exp.timestamp())

def trade_market(trader, market, contracts_per_order, spread_threshold, low_spread_discount_pct, high_spread_discount_pct, low_spread_expiry_min, high_spread_expiry_min, dry_run=False):
    """Execute trades on a single market based on spread."""
    ticker = market.get('ticker')
    title = market.get('title')
    yes_bid = market.get('yes_bid')
    yes_ask = market.get('yes_ask')
    no_bid = market.get('no_bid')
    no_ask = market.get('no_ask')
    
    # Trade YES side
    if yes_bid and yes_ask or yes_bid > 56:
        spread = yes_ask - yes_bid
        
        if spread < spread_threshold or yes_bid > 54:
            if 'NHL' in ticker:
                price = yes_bid-3
            elif yes_bid > 59:
                price = math.floor(yes_bid * (1 - 15 / 100))
            else:
                price = math.floor(yes_bid * (1 - low_spread_discount_pct / 100))
            expiration_ts = calculate_order_expiration(low_spread_expiry_min)
            print(f"{title} - {ticker}: YES spread={spread}, bid={yes_bid} ask={yes_ask}, order_price={price} ({low_spread_discount_pct}% below ask, {low_spread_expiry_min}min expiry)")
        else:
            # High spread: discount below ask
            price = math.floor(yes_bid * (1 - high_spread_discount_pct / 100))
            expiration_ts = calculate_order_expiration(high_spread_expiry_min)
            print(f"{title} - {ticker}: YES spread={spread}, bid={yes_bid}, ask={yes_ask}, order_price={price} ({high_spread_discount_pct}% below ask, {high_spread_expiry_min}min expiry)")
        
        if 7 < price < 99 or spread > spread_threshold:
            if dry_run:
                print(f"🔍 DRY RUN: Would place YES order at {price}")
            else:
                try:
                    trader.buy_yes(ticker, contracts_per_order, price, expiration_ts)
                    print(f"✅ YES order placed at {price}")
                except Exception as e:
                    print(f"❌ YES order failed: {e}")
    
    # Trade NO side
    if no_bid and no_ask and 'NHL' not in ticker:
        spread = no_ask - no_bid
        
        if spread < spread_threshold:
        # Low spread: discount below bid
            price = math.floor(no_bid * (1 - low_spread_discount_pct / 100))
            expiration_ts = calculate_order_expiration(low_spread_expiry_min)
            print(f"{title} - {ticker}: NO bid={no_bid}, bid={no_bid}, ask={no_ask}, spread={spread}, order_price={price} ({low_spread_discount_pct}% below bid, {low_spread_expiry_min}min expiry)")
        else:
            # High spread: discount below bid
            price = math.floor(no_bid * (1 - high_spread_discount_pct / 100))
            expiration_ts = calculate_order_expiration(high_spread_expiry_min)
            print(f"{title} - {ticker}: NO bid={no_bid}, bid={no_bid}, ask={no_ask}, spread={spread}, order_price={price} ({high_spread_discount_pct}% below bid, {high_spread_expiry_min}min expiry)")
        
        if 7 <= price <= 99 or spread > spread_threshold:
            if dry_run:
                print(f"🔍 DRY RUN: Would place NO order at {price}")
            else:
                try:
                    trader.buy_no(ticker, contracts_per_order, price, expiration_ts)
                    print(f"✅ NO order placed at {price}")
                except Exception as e:
                    print(f"❌ NO order failed: {e}")

def main():
    load_dotenv()
    
    # CONFIGURATION
    DRY_RUN = False  # Set to True to simulate orders without placing them
    SPREAD_THRESHOLD = 30  # Spread value that determines which strategy to use
    LOW_SPREAD_DISCOUNT_PCT = 35  # Percentage below ask when spread < threshold
    HIGH_SPREAD_DISCOUNT_PCT = -6  # Percentage below ask when spread >= threshold (0 = at ask)
    LOW_SPREAD_EXPIRY_MIN = 2  # Minutes until order expires for low spread
    HIGH_SPREAD_EXPIRY_MIN = 1  # Minutes until order expires for high spread
    THROTTLE_DELAY = 0.5  # Seconds to wait between each trade to avoid rate limiting
    
    is_production = os.environ.get("IS_PRODUCTION", "False").lower() == "true"
    environment = Environment.PROD if is_production else Environment.DEMO
    
    api_key_id = os.environ.get("PROD_API_KEY_ID" if is_production else "DEMO_API_KEY_ID")
    private_key_path = os.environ.get("PROD_PRIVATE_KEY_PATH" if is_production else "DEMO_PRIVATE_KEY_PATH")
    contracts_per_order = int(os.environ.get("CONTRACTS_PER_ORDER", "100"))
    
    if not api_key_id or not private_key_path:
        print("Error: API credentials not found in .env")
        return
    
    print(f"🚀 Starting live sports trader ({environment.name} mode)")
    if DRY_RUN:
        print("⚠️  DRY RUN MODE - Orders will NOT be placed")
    
    market_data = KalshiMarketData(api_key_id, private_key_path, environment)
    trader = KalshiTrader(api_key_id, private_key_path, environment)
    
    # Sports series to monitor
    sports_series = ['KXNCAAMBSPREAD', 'KXNCAAMBTOTAL', 'KXNBASPREAD', 'KXNBATOTAL', 'KXNHLTOTAL', 'KXNFLTOTAL', 'KXNFLSPREAD']
    
    traded_markets = set()
    
    while True:
        print(f"\n{'='*60}")
        print(f"🔄 Scanning markets at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        for series in sports_series:
            print(f"\n📊 Checking {series}...")
            
            try:
                for markets_batch in market_data.get_markets_paginated(series_ticker=series, limit=12, status='open'):
                    for market in markets_batch:
                        ticker = market.get('ticker')

                        if not should_trade_market(market) or 'Tulane' in market.get('title'):
                            continue
                        
                        print(f"\n🎯 Trading: {market.get('title')}")
                        trade_market(trader, market, contracts_per_order, SPREAD_THRESHOLD, 
                                   LOW_SPREAD_DISCOUNT_PCT, HIGH_SPREAD_DISCOUNT_PCT,
                                   LOW_SPREAD_EXPIRY_MIN, HIGH_SPREAD_EXPIRY_MIN, DRY_RUN)
                        traded_markets.add(ticker)
                    time.sleep(THROTTLE_DELAY)  # Prevent rate limiting
                        
            except Exception as e:
                print(f"❌ Error processing {series}: {e}")
        
        print(f"\n💤 Sleeping 60 seconds... (Traded {len(traded_markets)} markets)")
        time.sleep(100)

if __name__ == "__main__":
    main()
