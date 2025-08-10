import time
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
    """
    Service responsible for interacting with TronScan APIs to fetch
    wallet balances, token holdings, transaction history and
    contract details.  It hides the raw TronScan API details and
    exposes high level methods that return data in unified formats.

    For simplicity and robustness this implementation performs minimal
    error handling.  When the external API fails or returns an
    unexpected structure the service returns sensible defaults rather
    than raising exceptions.  The goal is to keep the proof of
    concept working even in degraded network conditions.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or Config.TRONSCAN_API_KEY
        # Base endpoint for TronScan.  The free API resides under
        # apilist.tronscanapi.com.  See https://tronscan.org for details.
        self.base_url = "https://apilist.tronscanapi.com"
        self.session = requests.Session()
        if self.api_key:
            # TronScan uses the header TRON-PRO-API-KEY for pro keys.  If
            # provided this improves rate limits.
            self.session.headers.update({"TRON-PRO-API-KEY": self.api_key})

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Internal helper to perform GET requests against TronScan.
        Returns the parsed JSON response on success or None on failure.
        """
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.ok:
                return resp.json()
        except Exception:
            # ignore network errors and return None
            return None
        return None

    def get_wallet_info(self, wallet_address: str) -> WalletInfoResponse:
        """
        Fetch wallet information from TronScan.  Combines account and
        token holdings into a unified response.  If the API is
        unreachable default values are returned.
        """
        # query account endpoint for native balance
        account_data = self._get("/api/account", {"address": wallet_address})
        # query token holdings
        tokens_data = self._get("/api/account/tokens", {"address": wallet_address, "limit": 50})

        # parse native balance; Tron uses sun units (1 TRX = 10^6 sun)
        native_balance = 0.0
        if account_data and isinstance(account_data, dict):
            balance_sun = account_data.get("balance", 0)
            try:
                native_balance = float(balance_sun) / (10 ** 6)
            except Exception:
                native_balance = 0.0

        native_token = NativeToken(symbol="TRX", decimals=6, balance=native_balance)

        # parse token list
        wallet_tokens: List[WalletToken] = []
        if tokens_data and isinstance(tokens_data, dict):
            # TronScan returns an array of token info objects under
            # "tokens" or "trc20_tokens" depending on the endpoint version.
            raw_tokens = tokens_data.get("tokens") or tokens_data.get("trc20_tokens") or []
            for token in raw_tokens:
                # Each token object may contain tokenId or tokenAddress
                contract = token.get("tokenId") or token.get("tokenAddress") or token.get("contractAddress")
                name = token.get("tokenName") or token.get("name") or ""
                symbol = token.get("tokenAbbr") or token.get("symbol") or ""
                decimals = token.get("tokenDecimal") or token.get("decimals") or 0
                balance_raw = token.get("balance") or token.get("quantity") or token.get("amount") or 0
                # convert to float using decimals
                try:
                    balance = float(balance_raw) / (10 ** int(decimals))
                except Exception:
                    balance = 0.0
                if contract:
                    wallet_tokens.append(
                        WalletToken(
                            token_address=str(contract),
                            name=str(name),
                            symbol=str(symbol),
                            decimals=int(decimals),
                            balance=balance,
                        )
                    )

        return WalletInfoResponse(
            wallet_address=wallet_address,
            blockchain="tron",
            native_token=native_token,
            tokens=wallet_tokens,
        )

    def get_transactions_list(self, wallet_address: str, limit: int = 20) -> TransactionsListResponse:
        """
        Fetch transaction history for a Tron wallet.  Merges TRX and
        TRC20 transfers into a single list, sorted by timestamp
        descending.  If the API fails a response with empty lists is
        returned.
        """
        # fetch TRX transfers
        trx_data = self._get(
            "/api/transfer/trx",
            {
                "address": wallet_address,
                "limit": limit,
                "start": 0,
                "direction": "out",
                "reverse": True,
            },
        )
        # fetch TRC20 transfers
        trc20_data = self._get(
            "/api/transfer/trc20",
            {
                "address": wallet_address,
                "limit": limit,
                "start": 0,
                "direction": "out",
                "reverse": True,
            },
        )

        transactions: List[Transaction] = []

        # parse TRX transfers
        if trx_data and isinstance(trx_data, dict):
            for tx in trx_data.get("data", []):
                # convert timestamp from milliseconds to ISO format
                ts = tx.get("timestamp")
                try:
                    iso_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ts) / 1000))
                except Exception:
                    iso_time = ""
                amount_sun = tx.get("amount", 0)
                amount_formatted = 0.0
                try:
                    amount_formatted = float(amount_sun) / (10 ** 6)
                except Exception:
                    amount_formatted = 0.0
                fee = tx.get("energy_fee", 0)
                fee_formatted = 0.0
                try:
                    fee_formatted = float(fee) / (10 ** 6)
                except Exception:
                    fee_formatted = 0.0
                transactions.append(
                    Transaction(
                        hash=tx.get("hash", ""),
                        timestamp=iso_time,
                        from_=tx.get("ownerAddress", ""),
                        to=tx.get("toAddress", ""),
                        amount=str(amount_sun),
                        amount_formatted=str(amount_formatted),
                        token_symbol="TRX",
                        transaction_fee=str(fee),
                        transaction_fee_formatted=str(fee_formatted),
                        status="success" if tx.get("confirmed", True) else "failed",
                        block_number=int(tx.get("block", 0)),
                    )
                )

        # parse TRC20 transfers
        if trc20_data and isinstance(trc20_data, dict):
            for tx in trc20_data.get("data", []):
                ts = tx.get("timestamp")
                try:
                    iso_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ts) / 1000))
                except Exception:
                    iso_time = ""
                amount_raw = tx.get("amount", 0)
                # decimals come from tokenInfo
                decimals = 0
                token_info = tx.get("tokenInfo") or {}
                decimals = token_info.get("tokenDecimal") or token_info.get("decimals") or 0
                try:
                    amount_formatted = float(amount_raw) / (10 ** int(decimals))
                except Exception:
                    amount_formatted = 0.0
                fee = tx.get("energy_fee", 0) or tx.get("fee", 0)
                try:
                    fee_formatted = float(fee) / (10 ** 6)
                except Exception:
                    fee_formatted = 0.0
                transactions.append(
                    Transaction(
                        hash=tx.get("hash", ""),
                        timestamp=iso_time,
                        from_=tx.get("from", "") or tx.get("ownerAddress", ""),
                        to=tx.get("to", "") or tx.get("toAddress", ""),
                        amount=str(amount_raw),
                        amount_formatted=str(amount_formatted),
                        token_symbol=(token_info.get("tokenAbbr") or token_info.get("symbol") or "TKN"),
                        transaction_fee=str(fee),
                        transaction_fee_formatted=str(fee_formatted),
                        status="success" if tx.get("confirmed", True) else "failed",
                        block_number=int(tx.get("block", 0)),
                    )
                )

        # sort all transactions by timestamp descending
        transactions.sort(key=lambda t: t.timestamp, reverse=True)
        # limit number of transactions
        transactions = transactions[:limit]

        # compute native balance again for this wallet
        wallet_info = self.get_wallet_info(wallet_address)
        native_symbol = wallet_info.native_token.symbol
        native_balance_formatted = str(wallet_info.native_token.balance)
        native_balance_raw = str(int(wallet_info.native_token.balance * (10 ** wallet_info.native_token.decimals)))

        # tokens summary for transactions response; using wallet_info tokens list and convert to TxnTokenBalance
        token_balances: List[TxnTokenBalance] = []
        for t in wallet_info.tokens:
            raw_balance = int(t.balance * (10 ** t.decimals))
            token_balances.append(
                TxnTokenBalance(
                    contract_address=t.token_address,
                    name=t.name,
                    symbol=t.symbol,
                    decimals=t.decimals,
                    balance=str(raw_balance),
                    balance_formatted=str(t.balance),
                )
            )

        return TransactionsListResponse(
            blockchain="tron",
            wallet_address=wallet_address,
            native_balance=native_balance_raw,
            native_balance_formatted=native_balance_formatted,
            native_symbol=native_symbol,
            tokens=token_balances,
            transactions=transactions,
        )

    def get_contract_details(self, contract_address: str) -> ContractDetailsResponse:
        """
        Retrieve TRC20 contract/token details.  Combines information
        from the contract and token endpoints.  If no information is
        available default values are returned.
        """
        contract_data = self._get("/api/contract", {"contract": contract_address})
        token_data = self._get("/api/token_trc20", {"contract": contract_address})

        # default values
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
            # supply may be numeric or string; convert to string raw and formatted
            supply_raw = token_data.get("total_supply") or token_data.get("totalSupply") or token_data.get("totalSupplyWithDecimals") or 0
            try:
                total_supply = str(supply_raw)
                # convert supply_raw to formatted using decimals; cast to float may overflow for very large numbers; we use int
                total_supply_value = int(supply_raw) / (10 ** decimals)
                total_supply_formatted = str(total_supply_value)
            except Exception:
                total_supply = str(supply_raw)
                total_supply_formatted = "0.0"
            creator = token_data.get("owner_address") or token_data.get("ownerAddress") or creator
            # TronScan returns creation time under issue_time
            issue_time = token_data.get("issue_time") or token_data.get("createTime")
            if issue_time:
                try:
                    # issue_time may be timestamp in ms
                    creation_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(issue_time) / 1000))
                except Exception:
                    creation_time = str(issue_time)
            verified = bool(token_data.get("verified"))
            holder_count = int(token_data.get("holders_count") or token_data.get("holders") or holder_count)
            transfer_count = int(token_data.get("transfer_count") or token_data.get("transfers") or transfer_count)
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