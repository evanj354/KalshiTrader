# Kalshi API Trader

Automated trading bot for Kalshi prediction markets using their REST API.

## Prerequisites

- Python 3.7+
- Kalshi API credentials (Demo or Production)
- Private key file (.key format)

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/kalshi_api_trader.git
   cd kalshi_api_trader
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   
   Create a `.env` file in the project root:
   ```bash
   # Demo environment (default)
   DEMO_API_KEY_ID=your_demo_api_key_id
   DEMO_PRIVATE_KEY_PATH=./kalshi_demo_private.key

   # Production environment (optional)
   PROD_API_KEY_ID=your_prod_api_key_id
   PROD_PRIVATE_KEY_PATH=./kalshi_prod_private.key

   # Set to "true" to use production
   IS_PRODUCTION=false

   # Trading parameters
   CONTRACTS_PER_ORDER=100
   ```

5. **Add your private key file**
   
   Place your Kalshi private key file in the project directory (e.g., `kalshi_demo_private.key`)

## Running the Trader

```bash
python example.py
```

The script will:
- Connect to Kalshi API (Demo or Production based on `.env`)
- Fetch open markets for specified series
- Place buy orders based on spread analysis
- Skip markets expiring within 4 hours

## Project Structure

- `kalshi_client.py` - Core API client with authentication and trading methods
- `example.py` - Main trading script with market analysis logic
- `requirements.txt` - Python dependencies
- `.env` - Configuration (not tracked in git)
- `.gitignore` - Excludes sensitive files

## Security Notes

- Never commit `.env` files or `.key` files to version control
- Use Demo environment for testing
- Review all orders before switching to Production

## API Documentation

For more details on Kalshi's API: https://trading-api.readme.io/reference/getting-started
