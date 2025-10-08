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


class TronService:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or Config.TRONSCAN_API_KEY
        self.base_url = "https://apilist.tronscanapi.com"
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"TRON-PRO-API-KEY": self.api_key})

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        try:
            resp = self.session.get(f"{self.base_url}{path}", params=params, timeout=15)
            if resp.ok:
                return resp.json()
        except Exception:
            return None
        return None

    def _date_to_milliseconds(self, date_str: str) -> Optional[int]:
        """
        Convert ISO date string to millisecond timestamp.

        Args:
            date_str: Date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)

        Returns:
            Timestamp in milliseconds, or None if parsing fails

        Example:
            "2024-01-01" -> 1704067200000
            "2024-01-01T12:30:00" -> 1704112200000
        """
        try:
            # Handle ISO format with or without timezone
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except Exception as e:
            print(f"Error parsing date: {e}")
            return None

    def get_wallet_info(self, wallet_address: str) -> WalletInfoResponse:
        account_data = self._get("/api/accountv2", {"address": wallet_address})
        
        native_balance = 0.0
        wallet_tokens: List[WalletToken] = []
        
        if account_data and isinstance(account_data, dict):
            balance_sun = account_data.get("balance") or 0
            try:
                native_balance = float(balance_sun) / 1e6
            except Exception:
                native_balance = 0.0
            
            with_price_tokens = account_data.get("withPriceTokens", [])
            for token in with_price_tokens:
                if not isinstance(token, dict):
                    continue
                
                token_id = token.get("tokenId", "")
                if token_id == "_":
                    continue
                
                token_name = token.get("tokenName", "")
                token_symbol = token.get("tokenAbbr", "")
                token_decimals = token.get("tokenDecimal", 0)
                token_balance_raw = token.get("balance", "0")
                
                try:
                    decimals_int = int(token_decimals)
                    balance_float = float(token_balance_raw) / (10 ** decimals_int) if decimals_int > 0 else float(token_balance_raw)
                except Exception:
                    balance_float = 0.0
                
                if token_id and token_id.strip():
                    wallet_tokens.append(
                        WalletToken(
                            token_address=token_id,
                            name=token_name,
                            symbol=token_symbol,
                            decimals=decimals_int,
                            balance=balance_float,
                        )
                    )
        
        native_token = NativeToken(symbol="TRX", decimals=6, balance=native_balance)
        
        return WalletInfoResponse(
            wallet_address=wallet_address,
            blockchain="tron",
            native_token=native_token,
            tokens=wallet_tokens,
        )

    def get_transactions_list(self, wallet_address: str, limit: int = 20, token: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> TransactionsListResponse:
        """
        Get transaction history for a wallet. If token is specified, only returns transactions
        for that specific TRC20 token contract. Otherwise, returns both TRX and TRC20 transactions.

        Args:
            wallet_address: The wallet address to query
            limit: Maximum number of transactions to return
            token: Optional TRC20 token contract address to filter transactions
            start_date: Start date filter in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
            end_date: End date filter in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)

        Returns:
            TransactionsListResponse with transaction history and wallet balances

        Note:
            TronScan API supports timestamp filtering natively using millisecond timestamps.
        """
        txs: List[Transaction] = []

        # Validate parameters
        if limit < 1:
            limit = 1
        elif limit > 100:  # Reasonable upper limit
            limit = 100

        # Convert dates to millisecond timestamps
        min_timestamp = None
        max_timestamp = None
        if start_date:
            min_timestamp = self._date_to_milliseconds(start_date)
        if end_date:
            max_timestamp = self._date_to_milliseconds(end_date)
            
        if token:
            # If token is specified, only get transactions for that specific TRC20 token
            # Use the corrected TRC20 transfers endpoint with proper parameters
            trc20_token_params = {
                "limit": limit,
                "start": 0,
                "contract_address": token,  # This filters by specific token contract
                "relatedAddress": wallet_address,  # This filters by wallet address
                "confirm": "true",  # Only confirmed transactions
                "filterTokenValue": "1"  # Filter out zero-value transfers
            }

            # Add timestamp filters if provided
            if min_timestamp:
                trc20_token_params["min_timestamp"] = min_timestamp
            if max_timestamp:
                trc20_token_params["max_timestamp"] = max_timestamp
            
            # Try the TRC20 transfers endpoint
            trc20_token_data = self._get("/api/token_trc20/transfers", trc20_token_params)
            
            # Process token transactions
            if isinstance(trc20_token_data, dict):
                # Check if we have token_transfers in the response
                token_transfers = trc20_token_data.get("token_transfers", [])
                
                # If token_transfers is empty, try the data field (alternative response format)
                if not token_transfers:
                    token_transfers = trc20_token_data.get("data", [])
                
                for tx in token_transfers:
                    if not isinstance(tx, dict):
                        continue
                    
                    # Extract timestamp
                    ts = tx.get("timestamp") or tx.get("block_timestamp")
                    iso = ""
                    if ts:
                        try:
                            # Handle both timestamp formats (seconds and milliseconds)
                            timestamp_val = int(ts)
                            if timestamp_val > 1e12:  # Milliseconds
                                timestamp_val = timestamp_val / 1000
                            iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp_val))
                        except Exception:
                            iso = ""
                    
                    # Extract amount and decimals
                    amount_raw = tx.get("amount") or tx.get("value") or 0
                    decimals = 0
                    
                    # Get decimals from multiple possible sources
                    if "decimals" in tx and tx.get("decimals") is not None:
                        decimals = int(tx.get("decimals"))
                    
                    token_info = tx.get("tokenInfo") or {}
                    if not decimals and token_info:
                        decimals = int(token_info.get("tokenDecimal") or token_info.get("decimals") or 0)
                    
                    # If still no decimals found, try to get from token name (USDT typically has 6 decimals)
                    if not decimals:
                        symbol = (token_info.get("tokenAbbr") or token_info.get("symbol") or 
                                tx.get("symbol") or "").upper()
                        if symbol in ["USDT", "JUSDT"]:
                            decimals = 6
                        else:
                            decimals = 6  # Default for most TRC20 tokens on TRON
                    
                    # Format amount
                    try:
                        amount_fmt = float(amount_raw) / (10 ** decimals) if decimals > 0 else float(amount_raw)
                    except Exception:
                        amount_fmt = 0.0
                    
                    # Extract fee information
                    fee = tx.get("energy_fee") or tx.get("fee") or tx.get("cost") or 0
                    try:
                        fee_fmt = float(fee) / 1e6  # TRX fees are in SUN (1 TRX = 1e6 SUN)
                    except Exception:
                        fee_fmt = 0.0
                    
                    # Extract addresses
                    from_addr = tx.get("from") or tx.get("from_address") or tx.get("ownerAddress") or ""
                    to_addr = tx.get("to") or tx.get("to_address") or tx.get("toAddress") or ""
                    
                    # Extract symbol
                    symbol = (
                        token_info.get("tokenAbbr") or
                        token_info.get("symbol") or
                        tx.get("symbol") or
                        token_info.get("tokenName") or
                        tx.get("token_name") or
                        "TRC20"
                    )
                    
                    # Determine transaction status
                    status = "success"
                    if "confirmed" in tx:
                        status = "success" if bool(tx.get("confirmed", 1)) else "failed"
                    elif "status" in tx:
                        status = "success" if tx.get("status") in [1, "1", "SUCCESS", True] else "failed"
                    
                    txs.append(
                        Transaction(
                            hash=tx.get("hash", "") or tx.get("transaction_id", ""),
                            timestamp=iso,
                            from_=from_addr,
                            to=to_addr,
                            amount=str(amount_raw),
                            amount_formatted=str(amount_fmt),
                            token_symbol=str(symbol),
                            transaction_fee=str(fee),
                            transaction_fee_formatted=str(fee_fmt),
                            status=status,
                            block_number=int(tx.get("block") or tx.get("blockNumber") or 0),
                        )
                    )
            
            # If no transactions found with the above method, try alternative endpoint
            if not txs:
                # Try the alternative endpoint used in your curl command
                alt_params = {
                    "trc20Id": token,
                    "address": wallet_address,
                    "limit": limit,
                    "start": 0,
                    "direction": 0,  # 0: all, 1: out, 2: in
                    "db_version": 1,
                    "reverse": "true"
                }

                # Add timestamp filters if provided
                if min_timestamp:
                    alt_params["min_timestamp"] = min_timestamp
                if max_timestamp:
                    alt_params["max_timestamp"] = max_timestamp

                alt_data = self._get("/api/token_trc20/transfers-with-status", alt_params)
                
                if isinstance(alt_data, dict):
                    token_transfers = alt_data.get("data", [])
                    
                    for tx in token_transfers:
                        if not isinstance(tx, dict):
                            continue
                        
                        ts = tx.get("timestamp") or tx.get("block_timestamp")
                        iso = ""
                        if ts:
                            try:
                                timestamp_val = int(ts)
                                if timestamp_val > 1e12:
                                    timestamp_val = timestamp_val / 1000
                                iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp_val))
                            except Exception:
                                iso = ""
                        
                        amount_raw = tx.get("amount") or tx.get("value") or 0
                        decimals = int(tx.get("decimals") or 6)  # Default to 6 for TRON
                        
                        try:
                            amount_fmt = float(amount_raw) / (10 ** decimals)
                        except Exception:
                            amount_fmt = 0.0
                        
                        fee = tx.get("energy_fee") or tx.get("fee") or 0
                        try:
                            fee_fmt = float(fee) / 1e6
                        except Exception:
                            fee_fmt = 0.0
                        
                        from_addr = tx.get("from") or tx.get("ownerAddress") or ""
                        to_addr = tx.get("to") or tx.get("toAddress") or ""
                        symbol = tx.get("symbol") or tx.get("tokenAbbr") or "TRC20"
                        
                        txs.append(
                            Transaction(
                                hash=tx.get("hash", "") or tx.get("transaction_id", ""),
                                timestamp=iso,
                                from_=from_addr,
                                to=to_addr,
                                amount=str(amount_raw),
                                amount_formatted=str(amount_fmt),
                                token_symbol=str(symbol),
                                transaction_fee=str(fee),
                                transaction_fee_formatted=str(fee_fmt),
                                status="success" if bool(tx.get("confirmed", 1)) else "failed",
                                block_number=int(tx.get("block") or 0),
                            )
                        )
            
        else:
            # Original logic when no token filter is applied
            trx_params = {
                "address": wallet_address,
                "limit": limit,
                "start": 0,
                "direction": 0,
                "reverse": True,
                "db_version": 1,
            }

            # Add timestamp filters if provided
            if min_timestamp:
                trx_params["min_timestamp"] = min_timestamp
            if max_timestamp:
                trx_params["max_timestamp"] = max_timestamp

            trx_data = self._get("/api/transfer/trx", trx_params)

            trc20_params = {
                "address": wallet_address,
                "limit": limit,
                "start": 0,
                "direction": 0,
                "reverse": True,
                "db_version": 1,
            }

            # Add timestamp filters if provided
            if min_timestamp:
                trc20_params["min_timestamp"] = min_timestamp
            if max_timestamp:
                trc20_params["max_timestamp"] = max_timestamp

            trc20_data = self._get("/api/transfer/trc20", trc20_params)

            if isinstance(trx_data, dict):
                for tx in trx_data.get("data", []):
                    ts = tx.get("timestamp") or tx.get("block_timestamp")
                    try:
                        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ts) / 1000)) if ts else ""
                    except Exception:
                        iso = ""
                    amount_raw = tx.get("amount") or 0
                    try:
                        amount_fmt = float(amount_raw) / 1e6
                    except Exception:
                        amount_fmt = 0.0
                    fee = tx.get("energy_fee") or tx.get("fee") or 0
                    try:
                        fee_fmt = float(fee) / 1e6
                    except Exception:
                        fee_fmt = 0.0
                    from_addr = tx.get("from") or tx.get("ownerAddress") or ""
                    to_addr = tx.get("to") or tx.get("toAddress") or ""
                    txs.append(
                        Transaction(
                            hash=tx.get("hash", ""),
                            timestamp=iso,
                            from_=from_addr,
                            to=to_addr,
                            amount=str(amount_raw),
                            amount_formatted=str(amount_fmt),
                            token_symbol="TRX",
                            transaction_fee=str(fee),
                            transaction_fee_formatted=str(fee_fmt),
                            status="success" if bool(tx.get("confirmed", 1)) else "failed",
                            block_number=int(tx.get("block") or 0),
                        )
                    )

            if isinstance(trc20_data, dict):
                for tx in trc20_data.get("data", []):
                    ts = tx.get("timestamp") or tx.get("block_timestamp")
                    try:
                        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ts) / 1000)) if ts else ""
                    except Exception:
                        iso = ""
                    amount_raw = tx.get("amount") or 0
                    decimals = 0
                    if "decimals" in tx and tx.get("decimals") is not None:
                        decimals = int(tx.get("decimals"))
                    token_info = tx.get("tokenInfo") or {}
                    decimals = int(token_info.get("tokenDecimal") or token_info.get("decimals") or decimals)
                    try:
                        amount_fmt = float(amount_raw) / (10 ** decimals) if decimals else float(amount_raw)
                    except Exception:
                        amount_fmt = 0.0
                    fee = tx.get("energy_fee") or tx.get("fee") or 0
                    try:
                        fee_fmt = float(fee) / 1e6
                    except Exception:
                        fee_fmt = 0.0
                    from_addr = tx.get("from") or tx.get("ownerAddress") or ""
                    to_addr = tx.get("to") or tx.get("toAddress") or ""
                    symbol = (
                        token_info.get("tokenAbbr")
                        or token_info.get("symbol")
                        or tx.get("symbol")
                        or token_info.get("tokenName")
                        or tx.get("token_name")
                        or "TKN"
                    )
                    txs.append(
                        Transaction(
                            hash=tx.get("hash", ""),
                            timestamp=iso,
                            from_=from_addr,
                            to=to_addr,
                            amount=str(amount_raw),
                            amount_formatted=str(amount_fmt),
                            token_symbol=str(symbol),
                            transaction_fee=str(fee),
                            transaction_fee_formatted=str(fee_fmt),
                            status="success" if bool(tx.get("confirmed", 1)) else "failed",
                            block_number=int(tx.get("block") or 0),
                        )
                    )

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
            blockchain="tron",
            wallet_address=wallet_address,
            native_balance=native_balance_raw,
            native_balance_formatted=native_balance_formatted,
            native_symbol=native_symbol,
            tokens=token_balances,
            transactions=txs,
        )

    def get_contract_details(self, contract_address: str) -> ContractDetailsResponse:
        contract_data = self._get("/api/contract", {"contract": contract_address})
        token_data = self._get("/api/token_trc20", {"contract": contract_address})
        name = ""
        symbol = ""
        decimals = 0
        total_supply = "0"
        total_supply_formatted = "0.0"
        creator = ""
        creation_time = ""
        verified = False
        holder_count = 0
        transfer_count = 0
        is_mintable = False
        is_burnable = False
        if token_data and isinstance(token_data, dict):
            name = token_data.get("name") or token_data.get("tokenName") or name
            symbol = token_data.get("symbol") or token_data.get("tokenAbbr") or symbol
            decimals = int(token_data.get("decimals") or token_data.get("tokenDecimal") or decimals)
            supply_raw = (
                token_data.get("total_supply")
                or token_data.get("totalSupply")
                or token_data.get("totalSupplyWithDecimals")
                or 0
            )
            try:
                total_supply = str(supply_raw)
                total_supply_value = int(supply_raw) / (10 ** decimals) if decimals else int(supply_raw)
                total_supply_formatted = str(total_supply_value)
            except Exception:
                total_supply = str(supply_raw)
                total_supply_formatted = "0.0"
            creator = token_data.get("owner_address") or token_data.get("ownerAddress") or creator
            issue_time = token_data.get("issue_time") or token_data.get("createTime")
            if issue_time:
                try:
                    creation_time = time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(issue_time) / 1000)
                    )
                except Exception:
                    creation_time = str(issue_time)
            verified = bool(token_data.get("verified"))
            holder_count = int(
                token_data.get("holders_count") or token_data.get("holders") or holder_count
            )
            transfer_count = int(
                token_data.get("transfer_count") or token_data.get("transfers") or transfer_count
            )
            is_mintable = bool(token_data.get("mintable") or token_data.get("is_mintable"))
            is_burnable = bool(token_data.get("burnable") or token_data.get("is_burnable"))
        return ContractDetailsResponse(
            contract_address=contract_address,
            blockchain="tron",
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