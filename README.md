# multichain-node-proxy
This is a **quick proof‑of‑concept** FastAPI service that aggregates wallet info, recent transfers and basic token metadata for Ethereum, BNB Smart Chain, Tron and Solana.  It wraps the public APIs from these blockchains and presents the results in a unified JSON format.  The code intentionally avoids over‑engineering – there's no fancy caching or indexing, just straightforward HTTP requests and some simple parsing.

## Running the service

```bash
uvicorn app.main:app –reload –host 0.0.0.0 –port 8000
```



## Quick Docker run

```bash
docker build -t blockchain-api:latest .
docker run --rm -p 8000:8000 \
  -e ETHERSCAN_API_KEY=your_etherscan_key \
  -e TRONSCAN_API_KEY=your_tronscan_key \
  -e QUICKNODE_API_URL=https://your-solana-rpc \
  blockchain-api:latest
```

or use local .env file

```bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  blockchain-api:latest
```
Environment variables are optional but recommended:

- `ETHERSCAN_API_KEY` – API key for the Etherscan V2 API endpoints. Used for both Ethereum and BNB Smart Chain data. Without it you'll be rate‑limited.
- `TRONSCAN_API_KEY` – API key for the TronScan REST endpoints (passed as `TRON‑PRO‑API‑KEY` header).  Without it you'll be rate‑limited.
- `QUICKNODE_API_URL` – Solana RPC URL from QuickNode (or any other Solana RPC provider).  The default falls back to `api.mainnet‑beta.solana.com` but you'll get better reliability with a real endpoint.

## API endpoints

### `GET /wallet_info`

Query parameters:

- `wallet_address` – the public address of the wallet.
- `blockchain` – one of `ethereum`, `bnb`, `tron`, or `solana`.

Returns native token balance and a list of held tokens.  For example, on Ethereum you'll see ETH balance plus any ERC‑20 tokens; on BNB Smart Chain you'll see BNB balance plus BEP‑20 tokens; on Tron you'll see TRX balance plus any TRC‑20 tokens; on Solana you'll see SOL balance plus SPL tokens.  Behind the scenes:

- **Ethereum** and **BNB Smart Chain** use Etherscan V2 API with chainid=1 and chainid=56 respectively to get native balance and token transactions.
- **Tron** calls `/api/account` to get the TRX balance and `/api/account/tokens` to list TRC‑20 tokens.
- **Solana** uses JSON‑RPC `getAccountInfo` (for lamports) and `getTokenAccountsByOwner` (for SPL token balances).  Names and symbols are fetched by deriving the Metaplex metadata account and reading its fields.

### `GET /transactions_list`

Query parameters:

- `wallet_address` – the address to inspect.
- `blockchain` – one of `ethereum`, `bnb`, `tron`, or `solana`.
- `limit` (optional) – number of records to return (default `20`).

Returns a slice of recent transfers with unified fields (`hash`, `timestamp`, `from`, `to`, `amount`, `token_symbol`, `transaction_fee`, etc.).  Notes on how this is assembled:

- **Ethereum** and **BNB Smart Chain** use Etherscan V2 API:
  - `/api` with `module=account&action=txlist` for native ETH/BNB transfers.
  - `/api` with `module=account&action=tokentx` for ERC‑20/BEP‑20 token transfers.
  
- **Tron** queries the Wallet API endpoints:
  - `/api/transfer/trx` for TRX (native) transfers with `direction=0` so both incoming and outgoing transfers are returned.
  - `/api/transfer/trc20` for TRC‑20 token transfers; it returns similar fields plus `decimals` for proper formatting.

- **Solana** uses JSON‑RPC calls:
  - `getSignaturesForAddress` to fetch recent transaction signatures.
  - `getTransaction` for each signature to decode instructions and extract sender/receiver addresses, amounts and fees.

### `GET /contract_details`

Query parameters:

- `contract_address` – the token contract or mint address.
- `blockchain` – one of `ethereum`, `bnb`, `tron`, or `solana`.

Returns basic token metadata (name, symbol, decimals, total supply, creation time, mintability, burnability, etc.).  Implementation details:

- **Ethereum** and **BNB Smart Chain** use Etherscan V2 API endpoints for contract source code, token supply, and creation information.
- **Tron** looks up `/api/contract` and `/api/token_trc20` for the contract.  `total_supply` and decimals are formatted, and flags like `mintable`/`burnable` are exposed.
- **Solana** calls `getAccountInfo` for the mint account to read the `Mint` struct (supply and decimals).  It then tries to fetch the Metaplex metadata account to get the name and symbol.

## Output formats

All endpoints return JSON objects conforming to the models defined in `app/models/responses.py`.  For instance, `/transactions_list` includes a `native_balance` (raw wei, lamports or sun), a `native_balance_formatted` (decimal), a list of token balances and the list of transactions.  Empty strings or zero values are used when data isn't available.

This service is a **minimal demonstration**, not a production indexer.  It depends on external APIs; if those endpoints change or rate‑limit you, you may see missing fields or empty lists.  Feel free to extend it with error handling, caching or support for other blockchains.

