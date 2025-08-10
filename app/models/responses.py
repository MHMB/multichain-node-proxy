from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class NativeToken(BaseModel):
    """Represents the native token for a blockchain wallet."""
    symbol: str
    decimals: int
    balance: float


class WalletToken(BaseModel):
    """Represents a token holding in a wallet."""
    token_address: str
    name: str
    symbol: str
    decimals: int
    balance: float


class TxnTokenBalance(BaseModel):
    """Represents a token balance within the transaction list response."""
    contract_address: str
    name: str
    symbol: str
    decimals: int
    balance: str
    balance_formatted: str


class Transaction(BaseModel):
    """Represents a single blockchain transaction entry."""
    hash: str
    timestamp: str
    from_: str = Field(..., alias="from")
    to: str
    amount: str
    amount_formatted: str
    token_symbol: str
    transaction_fee: str
    transaction_fee_formatted: str
    status: str
    block_number: int
    model_config = ConfigDict(populate_by_name=True)


class WalletInfoResponse(BaseModel):
    """Response model for the wallet_info endpoint."""
    wallet_address: str
    blockchain: str
    native_token: NativeToken
    tokens: List[WalletToken]


class TransactionsListResponse(BaseModel):
    """Response model for the transactions_list endpoint."""
    blockchain: str
    wallet_address: str
    native_balance: str
    native_balance_formatted: str
    native_symbol: str
    tokens: List[TxnTokenBalance]
    transactions: List[Transaction]


class ContractDetailsResponse(BaseModel):
    """Response model for the contract_details endpoint."""
    contract_address: str
    blockchain: str
    name: str
    symbol: str
    decimals: int
    total_supply: str
    total_supply_formatted: str
    creator: str
    creation_time: str
    verified: bool
    holder_count: int
    transfer_count: int
    is_mintable: bool
    is_burnable: bool