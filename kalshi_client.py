import base64
import datetime
import json
import time
import uuid
from enum import Enum

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


class Environment(Enum):
    """Enumeration for Kalshi API environments."""
    DEMO = "demo"
    PROD = "prod"


class KalshiBaseClient:
    """Base client for authenticating and interacting with the Kalshi API."""

    def __init__(
        self,
        key_id: str,
        private_key_path: str,
        environment: Environment = Environment.DEMO,
    ):
        """
        Initializes the client.

        Args:
            key_id (str): Your Kalshi API key ID.
            private_key_pem (str): Your RSA private key in PEM format.
            environment (Environment): The API environment to use.
        """
        self.key_id = key_id
        try:
            with open(private_key_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(), password=None, backend=default_backend()
                )
        except (ValueError, TypeError) as e:
            raise ValueError("Failed to load private key. Ensure it is a valid PEM string.") from e
            
        self.environment = environment

        if self.environment == Environment.DEMO:
            self.api_base = "https://demo-api.kalshi.co"
        elif self.environment == Environment.PROD:
            self.api_base = "https://api.elections.kalshi.com/"
        else:
            raise ValueError("Invalid environment specified.")
            
        self.session = requests.Session()
        print(f"KalshiBaseClient initialized for {self.environment.name} environment.")

    def _create_signature(self, private_key, timestamp, method, path):
        """Create the request signature."""
        # Strip query parameters before signing
        path_without_query = path.split('?')[0]
        message = f"{timestamp}{method}{path_without_query}".encode('utf-8')
        signature = private_key.sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')

    def _get_request_headers(self, method: str, path_with_query: str) -> dict:
        """Generates the required authentication headers for an API request."""
        timestamp_str = str(int(datetime.datetime.now().timestamp() * 1000))
        
        path_without_query = path_with_query.split('?')[0]
        
        signature = self._create_signature(self.private_key, timestamp_str, method, path_without_query)
        
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_str,
        }

    def _send_request(self, method: str, path: str, params: dict = None, payload: dict = None):
        """Sends a signed request to the Kalshi API."""
        
        # Construct the full path with query string to pass to the signing function
        full_path = path
        if params:
            query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
            full_path += '?' + query_string
        
        headers = self._get_request_headers(method, full_path)
        url = f"{self.api_base}{path}"

        try:
            print(f"Sending {method.upper()} request to {url}")
            print(f"Headers: {headers}")
            print(f"URL: {url}")
            response = self.session.request(method.upper(), url, headers=headers, params=params, json=payload)
            response.raise_for_status()
            # For Kalshi, 204 No Content is a valid success response for some endpoints
            if response.status_code == 204:
                return None
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = e.response.json()
                except (ValueError, AttributeError):
                    error_details = e.response.text if hasattr(e.response, 'text') else 'No details available'
                raise Exception(f"API request failed: {e.response.status_code} - {error_details}")
            else:
                raise Exception(f"API request failed: {str(e)}")


class KalshiTrader(KalshiBaseClient):
    """
    A client for placing trades on the Kalshi platform. Inherits authentication
    and request handling from KalshiBaseClient.
    """

    def _place_order(self, ticker, action, side, count, price_cents, expiration_ts=None):
        """A private method to place a limit order."""
        if not 1 <= price_cents <= 99:
            raise ValueError("Price must be in cents, between 1 and 99.")

        path = "/trade-api/v2/portfolio/orders"
        order_payload = {
            "client_order_id": str(uuid.uuid4()),
            "ticker": ticker,
            "action": action,
            "side": side,
            "count": count,
            "type": "limit",
            "yes_price": price_cents if side == 'yes' else None,
            "no_price": price_cents if side == 'no' else None,
            "expiration_ts": expiration_ts,
        }
        
        order_payload = {k: v for k, v in order_payload.items() if v is not None}
        print(f"Placing order: {order_payload} - {path}")
        return self._send_request('POST', path, payload=order_payload)

    def buy_yes(self, ticker: str, count: int, limit_price_cents: int, expiration_ts: int = None) -> dict:
        """Places a limit order to BUY 'yes' contracts."""
        return self._place_order(ticker, 'buy', 'yes', count, limit_price_cents, expiration_ts)

    def sell_yes(self, ticker: str, count: int, limit_price_cents: int, expiration_ts: int = None) -> dict:
        """Places a limit order to SELL 'yes' contracts."""
        return self._place_order(ticker, 'sell', 'yes', count, limit_price_cents, expiration_ts)
        
    def buy_no(self, ticker: str, count: int, limit_price_cents: int, expiration_ts: int = None) -> dict:
        """Places a limit order to BUY 'no' contracts."""
        return self._place_order(ticker, 'buy', 'no', count, limit_price_cents, expiration_ts)

    def sell_no(self, ticker: str, count: int, limit_price_cents: int, expiration_ts: int = None) -> dict:
        """Places a limit order to SELL 'no' contracts."""
        return self._place_order(ticker, 'sell', 'no', count, limit_price_cents, expiration_ts)

class KalshiMarketData(KalshiBaseClient):
    """
    A client for retrieving market data from the Kalshi platform.
    """

    def get_events(self, **params) -> dict:
        """
        Retrieves a list of events, filtered by optional parameters.
        
        For example: get_events(series_ticker='KXNCAAMBSPREAD', limit=20)
        """
        return self._send_request('GET', '/trade-api/v2/events', params=params)

    def get_markets_paginated(self, **params):
        """
        Generator that yields markets one page at a time.
        Handles pagination automatically.
        
        For example: 
        for markets_batch in get_markets_paginated(series_ticker='SPORT', status='open'):
            for market in markets_batch:
                # process market
        """
        cursor = None
        
        while True:
            if cursor:
                params['cursor'] = cursor
            
            response = self._send_request('GET', '/trade-api/v2/markets', params=params)
            markets = response.get('markets', [])
            
            if markets:
                yield markets
            
            cursor = response.get('cursor')
            if not cursor:
                break

    def get_market(self, ticker: str) -> dict:
        """Retrieves detailed information and orderbook for a single market."""
        return self._send_request('GET', f'/trade-api/v2/markets/{ticker}')

    def get_sports_market_prices(self) -> dict:
        """
        Fetches all open sports markets and returns their orderbooks.

        Returns:
            dict: A dictionary where keys are market titles and values are their
                  orderbooks.
        """
        print("Fetching open sports markets...")
        try:
            response = self.get_markets(series_ticker='SPORT', status='open')
        except Exception as e:
            print(f"Could not fetch sports markets. The 'SPORT' series may not be active. Error: {e}")
            return {}

        markets = response.get('markets', [])
        if not markets:
            print("No open sports markets found.")
            return {}

        print(f"Found {len(markets)} sports markets. Fetching orderbooks...")
        market_prices = {}
        for market in markets:
            ticker = market.get('ticker')
            title = market.get('title')
            if not ticker or not title:
                continue
            
            print(f"  - Getting orderbook for {title} ({ticker})")
            try:
                market_details = self.get_market(ticker)
                if 'orderbook' in market_details:
                    market_prices[title] = market_details['orderbook']
            except Exception as e:
                print(f"    Could not retrieve orderbook for {ticker}: {e}")
        
        return market_prices
