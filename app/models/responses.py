from pydantic import BaseModel, Field, ConfigDict, validator, field_validator
from typing import List, Optional, Literal, Union
from decimal import Decimal
import re
from datetime import datetime


class NativeToken(BaseModel):
    """Represents the native token for a blockchain wallet."""
    symbol: str = Field(..., description="Token symbol (e.g., ETH, BNB, TRX, SOL)", min_length=1, max_length=10)
    decimals: int = Field(..., description="Number of decimal places", ge=0, le=18)
    balance: float = Field(..., description="Token balance in human-readable format", ge=0.0)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol": "ETH",
                "decimals": 18,
                "balance": 1.5
            }
        }
    )


class WalletToken(BaseModel):
    """Represents a token holding in a wallet."""
    token_address: str = Field(..., description="Contract address of the token", min_length=1)
    name: str = Field(..., description="Full name of the token", min_length=1)
    symbol: str = Field(..., description="Token symbol", min_length=1, max_length=20)
    decimals: int = Field(..., description="Number of decimal places", ge=0, le=18)
    balance: float = Field(..., description="Token balance in human-readable format", ge=0.0)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token_address": "0xA0b86a33E6441b8C4C8C0C4C0C4C0C4C0C4C0C4C",
                "name": "USD Coin",
                "symbol": "USDC",
                "decimals": 6,
                "balance": 1000.0
            }
        }
    )


class TxnTokenBalance(BaseModel):
    """Represents a token balance within the transaction list response."""
    contract_address: str = Field(..., description="Contract address of the token", min_length=1)
    name: str = Field(..., description="Full name of the token", min_length=1)
    symbol: str = Field(..., description="Token symbol", min_length=1, max_length=20)
    decimals: int = Field(..., description="Number of decimal places", ge=0, le=18)
    balance: str = Field(..., description="Raw token balance as string", min_length=1)
    balance_formatted: str = Field(..., description="Formatted token balance as string", min_length=1)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contract_address": "0xA0b86a33E6441b8C4C8C0C4C0C4C0C4C0C4C0C4C",
                "name": "USD Coin",
                "symbol": "USDC",
                "decimals": 6,
                "balance": "1000000000",
                "balance_formatted": "1000.000000"
            }
        }
    )


class Transaction(BaseModel):
    """Represents a single blockchain transaction entry."""
    hash: str = Field(..., description="Transaction hash", min_length=1)
    timestamp: str = Field(..., description="ISO 8601 timestamp", min_length=1)
    from_: str = Field(..., alias="from", description="Sender address", min_length=1)
    to: str = Field(..., description="Recipient address", min_length=1)
    amount: str = Field(..., description="Raw transaction amount as string", min_length=1)
    amount_formatted: str = Field(..., description="Formatted transaction amount as string", min_length=1)
    token_symbol: str = Field(..., description="Token symbol involved in transaction", min_length=1)
    transaction_fee: str = Field(..., description="Raw transaction fee as string", min_length=1)
    transaction_fee_formatted: str = Field(..., description="Formatted transaction fee as string", min_length=1)
    status: Literal["success", "failed", "pending"] = Field(..., description="Transaction status")
    block_number: int = Field(..., description="Block number where transaction was included", ge=0)
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "timestamp": "2024-01-15T10:30:00Z",
                "from": "0xSenderAddress1234567890abcdef1234567890abcdef",
                "to": "0xRecipientAddress1234567890abcdef1234567890ab",
                "amount": "1000000000000000000",
                "amount_formatted": "1.0",
                "token_symbol": "ETH",
                "transaction_fee": "21000000000000000",
                "transaction_fee_formatted": "0.021",
                "status": "success",
                "block_number": 12345678
            }
        }
    )


class WalletInfoResponse(BaseModel):
    """Response model for the wallet_info endpoint."""
    wallet_address: str = Field(..., description="Wallet address queried", min_length=1)
    blockchain: Literal["ethereum", "bnb", "tron", "solana", "base"] = Field(..., description="Blockchain network")
    native_token: NativeToken = Field(..., description="Native token information")
    tokens: List[WalletToken] = Field(default_factory=list, description="List of token holdings")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
                "blockchain": "ethereum",
                "native_token": {
                    "symbol": "ETH",
                    "decimals": 18,
                    "balance": 1.5
                },
                "tokens": [
                    {
                        "token_address": "0xA0b86a33E6441b8C4C8C0C4C0C4C0C4C0C4C0C4C",
                        "name": "USD Coin",
                        "symbol": "USDC",
                        "decimals": 6,
                        "balance": 1000.0
                    }
                ]
            }
        }
    )


class TransactionsListResponse(BaseModel):
    """Response model for the transactions_list endpoint."""
    blockchain: Literal["ethereum", "bnb", "tron", "solana", "base"] = Field(..., description="Blockchain network")
    wallet_address: str = Field(..., description="Wallet address queried", min_length=1)
    native_balance: str = Field(..., description="Raw native token balance as string", min_length=1)
    native_balance_formatted: str = Field(..., description="Formatted native token balance as string", min_length=1)
    native_symbol: str = Field(..., description="Native token symbol", min_length=1)
    tokens: List[TxnTokenBalance] = Field(default_factory=list, description="List of token balances")
    transactions: List[Transaction] = Field(default_factory=list, description="List of transactions")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "blockchain": "ethereum",
                "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
                "native_balance": "1500000000000000000",
                "native_balance_formatted": "1.500000000000000000",
                "native_symbol": "ETH",
                "tokens": [
                    {
                        "contract_address": "0xA0b86a33E6441b8C4C8C0C4C0C4C0C4C0C4C0C4C",
                        "name": "USD Coin",
                        "symbol": "USDC",
                        "decimals": 6,
                        "balance": "1000000000",
                        "balance_formatted": "1000.000000"
                    }
                ],
                "transactions": [
                    {
                        "hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "from": "0xSenderAddress1234567890abcdef1234567890abcdef",
                        "to": "0xRecipientAddress1234567890abcdef1234567890ab",
                        "amount": "1000000000000000000",
                        "amount_formatted": "1.0",
                        "token_symbol": "ETH",
                        "transaction_fee": "21000000000000000",
                        "transaction_fee_formatted": "0.021",
                        "status": "success",
                        "block_number": 12345678
                    }
                ]
            }
        }
    )


class ContractDetailsResponse(BaseModel):
    """Response model for the contract_details endpoint."""
    contract_address: str = Field(..., description="Contract address queried", min_length=1)
    blockchain: Literal["ethereum", "bnb", "tron", "solana", "base"] = Field(..., description="Blockchain network")
    name: str = Field(..., description="Contract/token name", min_length=1)
    symbol: str = Field(..., description="Token symbol", min_length=1, max_length=20)
    decimals: int = Field(..., description="Number of decimal places", ge=0, le=18)
    total_supply: str = Field(..., description="Raw total supply as string", min_length=1)
    total_supply_formatted: str = Field(..., description="Formatted total supply as string", min_length=1)
    creator: str = Field(default="", description="Contract creator address")
    creation_time: str = Field(default="", description="Contract creation timestamp")
    verified: bool = Field(default=False, description="Whether contract is verified")
    holder_count: int = Field(default=0, description="Number of token holders", ge=0)
    transfer_count: int = Field(default=0, description="Number of transfers", ge=0)
    is_mintable: bool = Field(default=False, description="Whether token is mintable")
    is_burnable: bool = Field(default=False, description="Whether token is burnable")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contract_address": "0xA0b86a33E6441b8C4C8C0C4C0C4C0C4C0C4C0C4C",
                "blockchain": "ethereum",
                "name": "USD Coin",
                "symbol": "USDC",
                "decimals": 6,
                "total_supply": "1000000000000000",
                "total_supply_formatted": "1000000000.000000",
                "creator": "0xCreatorAddress1234567890abcdef1234567890ab",
                "creation_time": "2020-01-01T00:00:00Z",
                "verified": True,
                "holder_count": 1000000,
                "transfer_count": 50000000,
                "is_mintable": True,
                "is_burnable": False
            }
        }
    )


# Additional utility models for enhanced type safety
class BlockchainType(BaseModel):
    """Enum-like model for supported blockchains."""
    blockchain: Literal["ethereum", "bnb", "tron", "solana", "base"]


class TransactionStatus(BaseModel):
    """Enum-like model for transaction statuses."""
    status: Literal["success", "failed", "pending"]


# Version compatibility models
class ApiVersion(BaseModel):
    """API version information for compatibility checking."""
    version: str = Field(..., description="API version", pattern=r"^\d+\.\d+\.\d+$")
    supported_blockchains: List[Literal["ethereum", "bnb", "tron", "solana", "base"]] = Field(
        ..., description="List of supported blockchains"
    )
    deprecated_features: List[str] = Field(default_factory=list, description="List of deprecated features")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "1.0.0",
                "supported_blockchains": ["ethereum", "bnb", "tron", "solana", "base"],
                "deprecated_features": []
            }
        }
    )


# Error response models
class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")
    details: Optional[str] = Field(None, description="Additional error details")
    timestamp: str = Field(..., description="Error timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "Invalid wallet address",
                "error_code": "INVALID_ADDRESS",
                "details": "The provided wallet address is not valid for the specified blockchain",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
    )


# Request log models
class RequestLogResponse(BaseModel):
    """Response model for a single request log entry."""
    id: int = Field(..., description="Log entry ID")
    timestamp: str = Field(..., description="Request timestamp")
    ip_address: str = Field(..., description="Client IP address")
    user_id: Optional[str] = Field(None, description="User ID from JWT token")
    method: str = Field(..., description="HTTP method")
    endpoint: str = Field(..., description="Request endpoint")
    query_params: Optional[dict] = Field(None, description="Query parameters")
    headers: Optional[dict] = Field(None, description="Request headers")
    request_body: Optional[dict] = Field(None, description="Request body")
    response_status: int = Field(..., description="HTTP response status code")
    response_body: Optional[dict] = Field(None, description="Response body")
    response_time_ms: float = Field(..., description="Response time in milliseconds")
    blockchain: Optional[str] = Field(None, description="Target blockchain")
    wallet_address: Optional[str] = Field(None, description="Target wallet address")
    error_message: Optional[str] = Field(None, description="Error message if any")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "timestamp": "2024-01-15T10:30:00Z",
                "ip_address": "192.168.1.1",
                "user_id": "admin",
                "method": "GET",
                "endpoint": "/wallet_info",
                "query_params": {"blockchain": "ethereum", "wallet_address": "0x123..."},
                "headers": None,
                "request_body": None,
                "response_status": 200,
                "response_body": {"status": "success"},
                "response_time_ms": 125.5,
                "blockchain": "ethereum",
                "wallet_address": "0x123...",
                "error_message": None
            }
        }
    )


class RequestLogsListResponse(BaseModel):
    """Response model for list of request logs."""
    total_count: int = Field(..., description="Total number of logs for this user")
    user_id: str = Field(..., description="User ID being queried")
    logs: List[RequestLogResponse] = Field(..., description="List of request logs")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_count": 100,
                "user_id": "admin",
                "logs": [
                    {
                        "id": 1,
                        "timestamp": "2024-01-15T10:30:00Z",
                        "ip_address": "192.168.1.1",
                        "user_id": "admin",
                        "method": "GET",
                        "endpoint": "/wallet_info",
                        "query_params": {"blockchain": "ethereum"},
                        "headers": None,
                        "request_body": None,
                        "response_status": 200,
                        "response_body": {"status": "success"},
                        "response_time_ms": 125.5,
                        "blockchain": "ethereum",
                        "wallet_address": "0x123...",
                        "error_message": None
                    }
                ]
            }
        }
    )