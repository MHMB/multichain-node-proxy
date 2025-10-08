import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests

from app.config import Config
from app.models.responses import (
    NativeToken,
    WalletToken,
    WalletInfoResponse,
    TxnTokenBalance,
    Transaction,
    TransactionsListResponse,
    ContractDetailsResponse,
)


class BnbService:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or Config.ETHERSCAN_API_KEY  # Using Etherscan API key now
        self.base_url = "https://api.etherscan.io/v2/api"
        self.chain_id = 56  # BNB Smart Chain Mainnet
        self.session = requests.Session()
        if not self.api_key:
            raise ValueError("Etherscan API key is required")

    def _get(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            # Add chainid and API key to all requests
            params["chainid"] = self.chain_id
            params["apikey"] = self.api_key
            resp = self.session.get(self.base_url, params=params, timeout=15)
            if resp.ok:
                data = resp.json()
                if data.get("status") == "1":  # Etherscan success status
                    return data.get("result")
                else:
                    # Log error message from Etherscan
                    error_msg = data.get("message", "Unknown error")
                    print(f"Etherscan API error: {error_msg}")
                    return None
        except Exception as e:
            print(f"Request error: {e}")
            return None
        return None

    def get_wallet_info(self, wallet_address: str) -> WalletInfoResponse:
        # Get BNB balance
        balance_params = {
            "module": "account",
            "action": "balance",
            "address": wallet_address,
            "tag": "latest"
        }
        balance_data = self._get(balance_params)
        
        native_balance = 0.0
        if balance_data:
            try:
                # BscScan returns balance in Wei (1 BNB = 10^18 Wei)
                balance_wei = int(balance_data)
                native_balance = float(balance_wei) / 1e18
            except Exception:
                native_balance = 0.0

        # Get BEP-20 token balances
        tokens_params = {
            "module": "account",
            "action": "tokentx",
            "address": wallet_address,
            "startblock": 0,
            "endblock": 99999999,
            "sort": "desc"
        }
        tokens_data = self._get(tokens_params)
        
        wallet_tokens: List[WalletToken] = []
        token_contracts = set()
        
        if tokens_data and isinstance(tokens_data, list):
            for tx in tokens_data:
                contract_address = tx.get("contractAddress", "")
                if contract_address and contract_address not in token_contracts:
                    token_contracts.add(contract_address)
                    
                    # Get token info from contract
                    token_info = self._get_token_info(contract_address)
                    if token_info:
                        # Calculate current balance by summing all incoming and outgoing transactions
                        balance = self._calculate_token_balance(wallet_address, contract_address, tokens_data)
                        
                        wallet_tokens.append(
                            WalletToken(
                                token_address=contract_address,
                                name=token_info.get("name", ""),
                                symbol=token_info.get("symbol", ""),
                                decimals=int(token_info.get("decimals", 0)),
                                balance=balance,
                            )
                        )

        native_token = NativeToken(symbol="BNB", decimals=18, balance=native_balance)
        
        return WalletInfoResponse(
            wallet_address=wallet_address,
            blockchain="bnb",
            native_token=native_token,
            tokens=wallet_tokens,
        )

    def _get_token_info(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Get token information from contract using BscScan's contract API"""
        # Try to get verified contract source code first
        source_params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": contract_address
        }
        source_data = self._get(source_params)
        
        if source_data and isinstance(source_data, list) and len(source_data) > 0:
            contract_info = source_data[0]
            if contract_info.get("SourceCode"):
                # For verified contracts, we can parse the source code
                # This is a simplified approach - in production you might want to use a proper parser
                source_code = contract_info.get("SourceCode", "")
                name = contract_info.get("ContractName", "")
                symbol = ""
                decimals = 18
                
                # Try to extract symbol and decimals from source code or use defaults
                # This is a basic implementation - you might want to enhance this
                if "symbol" in source_code.lower():
                    symbol = "TKN"  # Default symbol
                if "decimals" in source_code.lower():
                    decimals = 18  # Default decimals
                
                return {
                    "name": name or "Unknown Token",
                    "symbol": symbol or "TKN",
                    "decimals": decimals
                }
        
        # Fallback: try to get token info from a few known token contracts
        # This is a simplified approach - in production you might want to use a more robust method
        return {
            "name": "Unknown Token",
            "symbol": "TKN",
            "decimals": 18
        }

    def _calculate_token_balance(self, wallet_address: str, contract_address: str, transactions: List[Dict[str, Any]]) -> float:
        """Calculate current token balance by summing all transactions"""
        balance = 0.0

        for tx in transactions:
            if tx.get("contractAddress") == contract_address:
                if tx.get("to", "").lower() == wallet_address.lower():
                    # Incoming transaction
                    amount = float(tx.get("value", "0"))
                    decimals = int(tx.get("tokenDecimal", 18))
                    balance += amount / (10 ** decimals)
                elif tx.get("from", "").lower() == wallet_address.lower():
                    # Outgoing transaction
                    amount = float(tx.get("value", "0"))
                    decimals = int(tx.get("tokenDecimal", 18))
                    balance -= amount / (10 ** decimals)

        return max(0.0, balance)  # Balance can't be negative

    def _get_block_number_by_timestamp(self, timestamp: int, closest: str = "before") -> Optional[int]:
        """
        Convert Unix timestamp to block number using Etherscan API.

        Args:
            timestamp: Unix timestamp in seconds
            closest: "before" or "after" - get closest block to timestamp

        Returns:
            Block number or None if request fails
        """
        params = {
            "module": "block",
            "action": "getblocknobytime",
            "timestamp": timestamp,
            "closest": closest
        }
        result = self._get(params)

        if result:
            try:
                return int(result)
            except (ValueError, TypeError):
                return None
        return None

    def _convert_dates_to_blocks(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> tuple:
        """
        Convert date strings to block numbers.

        Args:
            start_date: Start date in ISO format (YYYY-MM-DD) or datetime string
            end_date: End date in ISO format (YYYY-MM-DD) or datetime string

        Returns:
            Tuple of (start_block, end_block)
        """
        start_block = 0
        end_block = 99999999

        if start_date:
            try:
                # Parse date string to datetime
                dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                start_timestamp = int(dt.timestamp())

                # Get block number for start date
                block = self._get_block_number_by_timestamp(start_timestamp, "after")
                if block:
                    start_block = block
            except Exception as e:
                print(f"Error parsing start_date: {e}")

        if end_date:
            try:
                # Parse date string to datetime
                dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                end_timestamp = int(dt.timestamp())

                # Get block number for end date
                block = self._get_block_number_by_timestamp(end_timestamp, "before")
                if block:
                    end_block = block
            except Exception as e:
                print(f"Error parsing end_date: {e}")

        return start_block, end_block

    def get_transactions_list(self, wallet_address: str, limit: int = 20, token: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> TransactionsListResponse:
        txs: List[Transaction] = []

        # Convert dates to block numbers if provided
        start_block, end_block = self._convert_dates_to_blocks(start_date, end_date)

        if token:
            # If token is specified, only get transactions for that specific token
            token_params = {
                "module": "account",
                "action": "tokentx",
                "contractaddress": token,  # This is the key fix - filtering by contract address
                "address": wallet_address,
                "startblock": start_block,
                "endblock": end_block,
                "page": 1,
                "offset": limit,
                "sort": "desc"
            }
            token_data = self._get(token_params)
            
            # Process token transactions only
            if token_data and isinstance(token_data, list):
                for tx in token_data:
                    timestamp = tx.get("timeStamp", "")
                    iso_time = ""
                    if timestamp:
                        try:
                            iso_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(timestamp)))
                        except Exception:
                            iso_time = str(timestamp)
                    
                    amount_raw = tx.get("value", "0")
                    decimals = int(tx.get("tokenDecimal", 18))
                    try:
                        amount_formatted = float(amount_raw) / (10 ** decimals)
                    except Exception:
                        amount_formatted = 0.0
                    
                    gas_price = tx.get("gasPrice", "0")
                    gas_used = tx.get("gasUsed", "0")
                    try:
                        fee_wei = int(gas_price) * int(gas_used)
                        fee_bnb = fee_wei / 1e18
                    except Exception:
                        fee_bnb = 0.0
                    
                    symbol = tx.get("tokenSymbol", "TKN")
                    
                    transaction_data = {
                        "hash": tx.get("hash", "") or "",
                        "timestamp": iso_time or "",
                        "from": tx.get("from", "") or "",
                        "to": tx.get("to", "") or "",
                        "amount": str(amount_raw),
                        "amount_formatted": str(amount_formatted),
                        "token_symbol": str(symbol),
                        "transaction_fee": str(fee_wei),
                        "transaction_fee_formatted": str(fee_bnb),
                        "status": "success",
                        "block_number": int(tx.get("blockNumber", 0)) or 0,
                    }
                    txs.append(Transaction(**transaction_data))
        else:
            # Original logic when no token filter is applied
            # Get BNB transactions
            bnb_params = {
                "module": "account",
                "action": "txlist",
                "address": wallet_address,
                "startblock": start_block,
                "endblock": end_block,
                "page": 1,
                "offset": limit,
                "sort": "desc"
            }
            bnb_data = self._get(bnb_params)

            # Get BEP-20 token transactions
            token_params = {
                "module": "account",
                "action": "tokentx",
                "address": wallet_address,
                "startblock": start_block,
                "endblock": end_block,
                "page": 1,
                "offset": limit,
                "sort": "desc"
            }
            token_data = self._get(token_params)
            
            # Process BNB transactions
            if bnb_data and isinstance(bnb_data, list):
                for tx in bnb_data:
                    timestamp = tx.get("timeStamp", "")
                    iso_time = ""
                    if timestamp:
                        try:
                            iso_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(timestamp)))
                        except Exception:
                            iso_time = str(timestamp)
                    
                    amount_wei = tx.get("value", "0")
                    try:
                        amount_bnb = float(amount_wei) / 1e18
                    except Exception:
                        amount_bnb = 0.0
                    
                    gas_price = tx.get("gasPrice", "0")
                    gas_used = tx.get("gasUsed", "0")
                    try:
                        fee_wei = int(gas_price) * int(gas_used)
                        fee_bnb = fee_wei / 1e18
                    except Exception:
                        fee_bnb = 0.0
                    
                    transaction_data = {
                        "hash": tx.get("hash", "") or "",
                        "timestamp": iso_time or "",
                        "from": tx.get("from", "") or "",
                        "to": tx.get("to", "") or "",
                        "amount": str(amount_wei),
                        "amount_formatted": str(amount_bnb),
                        "token_symbol": "BNB",
                        "transaction_fee": str(fee_wei),
                        "transaction_fee_formatted": str(fee_bnb),
                        "status": "success" if tx.get("isError") == "0" else "failed",
                        "block_number": int(tx.get("blockNumber", 0)) or 0,
                    }
                    txs.append(Transaction(**transaction_data))
            
            # Process BEP-20 token transactions
            if token_data and isinstance(token_data, list):
                for tx in token_data:
                    timestamp = tx.get("timeStamp", "")
                    iso_time = ""
                    if timestamp:
                        try:
                            iso_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(timestamp)))
                        except Exception:
                            iso_time = str(timestamp)
                    
                    amount_raw = tx.get("value", "0")
                    decimals = int(tx.get("tokenDecimal", 18))
                    try:
                        amount_formatted = float(amount_raw) / (10 ** decimals)
                    except Exception:
                        amount_formatted = 0.0
                    
                    gas_price = tx.get("gasPrice", "0")
                    gas_used = tx.get("gasUsed", "0")
                    try:
                        fee_wei = int(gas_price) * int(gas_used)
                        fee_bnb = fee_wei / 1e18
                    except Exception:
                        fee_bnb = 0.0
                    
                    symbol = tx.get("tokenSymbol", "TKN")
                    
                    transaction_data = {
                        "hash": tx.get("hash", "") or "",
                        "timestamp": iso_time or "",
                        "from": tx.get("from", "") or "",
                        "to": tx.get("to", "") or "",
                        "amount": str(amount_raw),
                        "amount_formatted": str(amount_formatted),
                        "token_symbol": str(symbol),
                        "transaction_fee": str(fee_wei),
                        "transaction_fee_formatted": str(fee_bnb),
                        "status": "success",
                        "block_number": int(tx.get("blockNumber", 0)) or 0,
                    }
                    txs.append(Transaction(**transaction_data))
            
            # Sort by timestamp and limit results
            txs.sort(key=lambda t: t.timestamp, reverse=True)
            txs = txs[:limit]
        
        # Get wallet info for balances
        wallet_info = self.get_wallet_info(wallet_address)
        native_symbol = wallet_info.native_token.symbol
        native_balance_formatted = format(wallet_info.native_token.balance, "f")
        native_balance_raw = str(
            int(wallet_info.native_token.balance * (10 ** wallet_info.native_token.decimals))
        )
        
        token_balances: List[TxnTokenBalance] = []
        for t in wallet_info.tokens:
            raw_balance = int(t.balance * (10 ** t.decimals))
            formatted_balance = format(t.balance, "f")
            token_balances.append(
                TxnTokenBalance(
                    contract_address=t.token_address,
                    name=t.name,
                    symbol=t.symbol,
                    decimals=t.decimals,
                    balance=str(raw_balance),
                    balance_formatted=formatted_balance,
                )
            )
        
        return TransactionsListResponse(
            blockchain="bnb",
            wallet_address=wallet_address,
            native_balance=native_balance_raw,
            native_balance_formatted=native_balance_formatted,
            native_symbol=native_symbol,
            tokens=token_balances,
            transactions=txs,
        )

    def get_contract_details(self, contract_address: str) -> ContractDetailsResponse:
        # Get contract source code and basic info
        source_params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": contract_address
        }
        source_data = self._get(source_params)
        
        # Get token info if it's a token contract
        token_params = {
            "module": "stats",
            "action": "tokensupply",
            "contractaddress": contract_address
        }
        token_supply_data = self._get(token_params)
        
        # Get contract creation info
        creation_params = {
            "module": "contract",
            "action": "getcontractcreation",
            "contractaddresses": contract_address
        }
        creation_data = self._get(creation_params)
        
        # Initialize default values
        name = ""
        symbol = ""
        decimals = 18
        total_supply = "0"
        total_supply_formatted = "0.0"
        creator = ""
        creation_time = ""
        verified = False
        holder_count = 0
        transfer_count = 0
        is_mintable = False
        is_burnable = False
        
        # Extract contract information
        if source_data and isinstance(source_data, list) and len(source_data) > 0:
            contract_info = source_data[0]
            name = contract_info.get("ContractName", "") or "Unknown Contract"
            verified = bool(contract_info.get("SourceCode"))
            
            # Try to extract more info from source code if available
            source_code = contract_info.get("SourceCode", "")
            if source_code:
                # This is a simplified approach - in production you might want to use a proper parser
                if "mint" in source_code.lower():
                    is_mintable = True
                if "burn" in source_code.lower():
                    is_burnable = True
        
        # Extract token supply information
        if token_supply_data:
            try:
                total_supply = str(token_supply_data)
                total_supply_value = int(token_supply_data) / (10 ** decimals)
                total_supply_formatted = str(total_supply_value)
            except Exception:
                total_supply = "0"
                total_supply_formatted = "0.0"
        
        # Extract creation information
        if creation_data and isinstance(creation_data, list) and len(creation_data) > 0:
            creation_info = creation_data[0]
            creator = creation_info.get("contractCreator", "")
            creation_tx_hash = creation_info.get("txHash", "")
            
            # Get transaction details to get timestamp
            if creation_tx_hash:
                tx_params = {
                    "module": "proxy",
                    "action": "eth_getTransactionByHash",
                    "txhash": creation_tx_hash
                }
                tx_data = self._get(tx_params)
                if tx_data:
                    block_number = tx_data.get("blockNumber", "0")
                    if block_number != "0":
                        # Get block timestamp
                        block_params = {
                            "module": "proxy",
                            "action": "eth_getBlockByNumber",
                            "tag": block_number,
                            "boolean": "false"
                        }
                        block_data = self._get(block_params)
                        if block_data:
                            timestamp_hex = block_data.get("timestamp", "0")
                            try:
                                timestamp = int(timestamp_hex, 16)
                                creation_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp))
                            except Exception:
                                creation_time = str(timestamp_hex)
        
        # Try to get token symbol and decimals from contract
        # This is a simplified approach - in production you might want to use a more robust method
        if not symbol:
            symbol = "TKN"
        
        return ContractDetailsResponse(
            contract_address=contract_address,
            blockchain="bnb",
            name=name,
            symbol=symbol,
            decimals=decimals,
            total_supply=total_supply,
            total_supply_formatted=total_supply_formatted,
            creator=creator,
            creation_time=creation_time,
            verified=verified,
            holder_count=holder_count,
            transfer_count=transfer_count,
            is_mintable=is_mintable,
            is_burnable=is_burnable,
        )
