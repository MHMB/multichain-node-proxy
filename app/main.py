from fastapi import FastAPI, HTTPException, Query

from app.models.responses import (
    WalletInfoResponse,
    TransactionsListResponse,
    ContractDetailsResponse,
)
from app.services.tron_service import TronService
from app.services.solana_service import SolanaService


app = FastAPI(title="Multi‑Blockchain API", version="0.1.0")

tron_service = TronService()
solana_service = SolanaService()


@app.get("/wallet_info", response_model=WalletInfoResponse)
async def wallet_info(
    wallet_address: str = Query(..., description="Wallet address to query"),
    blockchain: str = Query(..., description="Blockchain: 'tron' or 'solana'"),
):
    """
    Retrieve wallet balance and token holdings.  Delegates the call
    to the appropriate service based on the blockchain parameter.
    """
    chain = blockchain.lower()
    if chain == "tron":
        return tron_service.get_wallet_info(wallet_address)
    if chain == "solana":
        return solana_service.get_wallet_info(wallet_address)
    raise HTTPException(status_code=400, detail="Unsupported blockchain")


@app.get("/transactions_list", response_model=TransactionsListResponse)
async def transactions_list(
    wallet_address: str = Query(..., description="Wallet address to query"),
    blockchain: str = Query(..., description="Blockchain: 'tron' or 'solana'"),
    limit: int = Query(20, description="Number of transactions to return"),
):
    """
    Get transaction history for a wallet.  Combines native and token
    transfers into a unified list.
    """
    chain = blockchain.lower()
    if limit < 1:
        limit = 1
    if chain == "tron":
        return tron_service.get_transactions_list(wallet_address, limit)
    if chain == "solana":
        return solana_service.get_transactions_list(wallet_address, limit)
    raise HTTPException(status_code=400, detail="Unsupported blockchain")


@app.get("/contract_details", response_model=ContractDetailsResponse)
async def contract_details(
    contract_address: str = Query(..., description="Contract address to query"),
    blockchain: str = Query(..., description="Blockchain: 'tron' or 'solana'"),
):
    """
    Get smart contract or token information.  Returns metadata for
    TRC20 or SPL tokens.
    """
    chain = blockchain.lower()
    if chain == "tron":
        return tron_service.get_contract_details(contract_address)
    if chain == "solana":
        return solana_service.get_contract_details(contract_address)
    raise HTTPException(status_code=400, detail="Unsupported blockchain")


@app.get("/")
async def root() -> dict:
    """Basic health check endpoint."""
    return {"status": "ok"}