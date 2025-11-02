from datetime import timedelta
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware

from app.models.responses import (
    WalletInfoResponse,
    TransactionsListResponse,
    ContractDetailsResponse,
    RequestLogsListResponse,
    RequestLogResponse,
)
from app.services.tron_service import TronService
from app.services.solana_service import SolanaService
from app.services.ethereum_service import EthereumService
from app.services.bnb_service import BnbService
from app.services.base_net_service import BaseNetService
from app.middlewares import (
    authenticate_user,
    create_access_token,
    get_current_user,
    User,
    Token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    IPWhitelistMiddleware,
    RequestLoggingMiddleware
)
from app.database import db_manager
from app.config import Config
from app.models.database import RequestLog
from sqlalchemy import select, func

app = FastAPI(title="Multi‑Blockchain API", version="0.1.0")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    config = Config()
    db_manager.initialize(config.DATABASE_URL)
    await db_manager.create_tables()


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up database connections on shutdown."""
    await db_manager.close()


# Add request logging middleware
config = Config()
app.add_middleware(
    RequestLoggingMiddleware,
    log_requests=config.LOG_REQUESTS,
    log_response_body=config.LOG_RESPONSE_BODY,
    log_request_headers=config.LOG_REQUEST_HEADERS
)

# Add IP whitelist middleware
# app.add_middleware(IPWhitelistMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tron_service = TronService()
solana_service = SolanaService()
ethereum_service = EthereumService()
bnb_service = BnbService()
base_net_service = BaseNetService()

# Authentication endpoint
@app.post("/auth/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login endpoint to get JWT access token.
    Default users:
    - username: admin, password: password123
    - username: user, password: userpass
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return current_user

@app.get("/wallet_info", response_model=WalletInfoResponse)
async def wallet_info(
    wallet_address: str = Query(..., description="Wallet address to query"),
    blockchain: str = Query(..., description="Blockchain: 'tron', 'solana', 'ethereum', 'bnb', or 'base'"),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve wallet balance and token holdings.  Delegates the call
    to the appropriate service based on the blockchain parameter.
    Requires authentication.
    """
    chain = blockchain.lower()
    if chain == "tron":
        return tron_service.get_wallet_info(wallet_address)
    if chain == "solana":
        return solana_service.get_wallet_info(wallet_address)
    if chain == "ethereum":
        return ethereum_service.get_wallet_info(wallet_address)
    if chain == "bnb":
        return bnb_service.get_wallet_info(wallet_address)
    if chain == "base":
        return base_net_service.get_wallet_info(wallet_address)
    raise HTTPException(status_code=400, detail="Unsupported blockchain")

@app.get("/transactions_list", response_model=TransactionsListResponse)
async def transactions_list(
    wallet_address: str = Query(..., description="Wallet address to query"),
    blockchain: str = Query(..., description="Blockchain: 'tron', 'solana', 'ethereum', 'bnb', or 'base'"),
    limit: int = Query(20, description="Number of transactions to return"),
    token: str = Query(None, description="Token contract address to filter transactions"),
    start_date: str = Query(None, description="Start date filter (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS). Supported for all chains."),
    end_date: str = Query(None, description="End date filter (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS). Supported for all chains."),
    current_user: User = Depends(get_current_user)
):
    """
    Get transaction history for a wallet. Combines native and token
    transfers into a unified list.
    Supports optional date filtering for all supported blockchains.
    Requires authentication.
    """
    chain = blockchain.lower()
    if limit < 1:
        limit = 1
    if chain == "tron":
        return tron_service.get_transactions_list(wallet_address, limit, token, start_date, end_date)
    if chain == "solana":
        return solana_service.get_transactions_list(wallet_address, limit, token, start_date, end_date)
    if chain == "ethereum":
        return ethereum_service.get_transactions_list(wallet_address, limit, token, start_date, end_date)
    if chain == "bnb":
        return bnb_service.get_transactions_list(wallet_address, limit, token, start_date, end_date)
    if chain == "base":
        return base_net_service.get_transactions_list(wallet_address, limit, token, start_date, end_date)
    raise HTTPException(status_code=400, detail="Unsupported blockchain")

@app.get("/contract_details", response_model=ContractDetailsResponse)
async def contract_details(
    contract_address: str = Query(..., description="Contract address to query"),
    blockchain: str = Query(..., description="Blockchain: 'tron', 'solana', 'ethereum', 'bnb', or 'base'"),
    current_user: User = Depends(get_current_user)
):
    """
    Get smart contract or token information.  Returns metadata for
    TRC20, SPL, ERC-20, or BEP-20 tokens.
    Requires authentication.
    """
    chain = blockchain.lower()
    if chain == "tron":
        return tron_service.get_contract_details(contract_address)
    if chain == "solana":
        return solana_service.get_contract_details(contract_address)
    if chain == "ethereum":
        return ethereum_service.get_contract_details(contract_address)
    if chain == "bnb":
        return bnb_service.get_contract_details(contract_address)
    if chain == "base":
        return base_net_service.get_contract_details(contract_address)
    raise HTTPException(status_code=400, detail="Unsupported blockchain")

@app.get("/")
async def root() -> dict:
    """Basic health check endpoint. No authentication required."""
    return {"status": "ok", "message": "Multi-Blockchain API is running"}

@app.get("/admin/request_logs", response_model=RequestLogsListResponse)
async def get_request_logs(
    user_id: str = Query(..., description="User ID to query request logs for"),
    limit: int = Query(100, description="Maximum number of logs to return", ge=1, le=1000),
    offset: int = Query(0, description="Number of logs to skip for pagination", ge=0),
    current_user: User = Depends(get_current_user)
):
    """
    Get request logs for a specific user ID.
    Returns paginated list of all API requests made by the specified user.
    Requires authentication.
    """
    try:
        # Get database session
        session = await db_manager.get_session()

        try:
            # Count total logs for this user
            count_query = select(func.count(RequestLog.id)).where(RequestLog.user_id == user_id)
            result = await session.execute(count_query)
            total_count = result.scalar()

            # Query logs for the user with pagination, ordered by timestamp descending
            query = (
                select(RequestLog)
                .where(RequestLog.user_id == user_id)
                .order_by(RequestLog.timestamp.desc())
                .limit(limit)
                .offset(offset)
            )

            result = await session.execute(query)
            logs = result.scalars().all()

            # Convert logs to response format
            log_responses = []
            for log in logs:
                log_responses.append(RequestLogResponse(
                    id=log.id,
                    timestamp=log.timestamp.isoformat() if log.timestamp else "",
                    ip_address=log.ip_address,
                    user_id=log.user_id,
                    method=log.method,
                    endpoint=log.endpoint,
                    query_params=log.query_params,
                    headers=log.headers,
                    request_body=log.request_body,
                    response_status=log.response_status,
                    response_body=log.response_body,
                    response_time_ms=log.response_time_ms,
                    blockchain=log.blockchain,
                    wallet_address=log.wallet_address,
                    error_message=log.error_message
                ))

            return RequestLogsListResponse(
                total_count=total_count or 0,
                user_id=user_id,
                logs=log_responses
            )

        finally:
            await session.close()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve request logs: {str(e)}"
        )