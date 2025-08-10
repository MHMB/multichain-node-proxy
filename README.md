# multichain-node-proxy
This is a **quick proof‑of‑concept** FastAPI service that aggregates wallet info, recent transfers and basic token metadata for Tron and Solana.  It wraps the public APIs from both blockchains and presents the results in a unified JSON format.  The code intentionally avoids over‑engineering – there’s no fancy caching or indexing, just straightforward HTTP requests and some simple parsing.

## Running the service

```bash
uvicorn app.main:app –reload –host 0.0.0.0 –port 8000
```



## Quick Docker run

```bash
docker build -t blockchain-api:latest .
docker run --rm -p 8000:8000 \
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

- `TRONSCAN_API_KEY` – API key for the TronScan REST endpoints (passed as `TRON‑PRO‑API‑KEY` header).  Without it you’ll be rate‑limited.
- `QUICKNODE_API_URL` – Solana RPC URL from QuickNode (or any other Solana RPC provider).  The default falls back to `api.mainnet‑beta.solana.com` but you’ll get better reliability with a real endpoint.
- `ALCHEMY_API_KEY` – Currently unused; reserved for future Ethereum support.

## API endpoints

### `GET /wallet_info`

Query parameters:

- `wallet_address` – the public address of the wallet.
- `blockchain` – either `tron` or `solana`.

Returns native token balance and a list of held tokens.  For example, on Tron you’ll see TRX balance plus any TRC‑20 tokens; on Solana you’ll see SOL balance plus SPL tokens.  Behind the scenes:

- **Tron** calls `/api/account` to get the TRX balance and `/api/account/tokens` to list TRC‑20 tokens.
- **Solana** uses JSON‑RPC `getAccountInfo` (for lamports) and `getTokenAccountsByOwner` (for SPL token balances).  Names and symbols are fetched by deriving the Metaplex metadata account and reading its fields [oai_citation:0‡quicknode.com](https://www.quicknode.com/docs/functions/functions-library/solana-token-fetcher#:~:text=async%20function%20fetchTokenMetadata%28connection%2C%20mintAddress%29%20,METADATA_PROGRAM_ID).

### `GET /transactions_list`

Query parameters:

- `wallet_address` – the address to inspect.
- `blockchain` – `tron` or `solana`.
- `limit` (optional) – number of records to return (default `20`).

Returns a slice of recent transfers with unified fields (`hash`, `timestamp`, `from`, `to`, `amount`, `token_symbol`, `transaction_fee`, etc.).  Notes on how this is assembled:

- **Tron** queries the Wallet API endpoints:
  - `/api/transfer/trx` for TRX (native) transfers with `direction=0` so both incoming and outgoing transfers are returned.  This endpoint returns `from` and `to` addresses and amounts in sun (1e6 sun = 1 TRX) [oai_citation:1‡docs.tronscan.org](https://docs.tronscan.org/api-endpoints/wallet#:~:text=,1).
  - `/api/transfer/trc20` for TRC‑20 token transfers; it returns similar fields plus `decimals` for proper formatting.  The service does not specify a particular `trc20Id` so all token transfers for the wallet are returned.

- **Solana** uses JSON‑RPC calls:
  - `getSignaturesForAddress` to fetch recent transaction signatures.
  - `getTransaction` for each signature to decode instructions and extract sender/receiver addresses, amounts and fees.

### `GET /contract_details`

Query parameters:

- `contract_address` – the token contract or mint address.
- `blockchain` – `tron` or `solana`.

Returns basic token metadata (name, symbol, decimals, total supply, creation time, mintability, burnability, etc.).  Implementation details:

- **Tron** looks up `/api/contract` and `/api/token_trc20` for the contract.  `total_supply` and decimals are formatted, and flags like `mintable`/`burnable` are exposed.
- **Solana** calls `getAccountInfo` for the mint account to read the `Mint` struct (supply and decimals).  It then tries to fetch the Metaplex metadata account to get the name and symbol.

## Output formats

All endpoints return JSON objects conforming to the models defined in `app/models/responses.py`.  For instance, `/transactions_list` includes a `native_balance` (raw lamports or sun), a `native_balance_formatted` (decimal), a list of token balances and the list of transactions.  Empty strings or zero values are used when data isn’t available.

This service is a **minimal demonstration**, not a production indexer.  It depends on external APIs; if those endpoints change or rate‑limit you, you may see missing fields or empty lists.  Feel free to extend it with error handling, caching or support for other blockchains.

