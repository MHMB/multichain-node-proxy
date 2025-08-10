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
    """Minimal client for interacting with TronScan.

    This service wraps the TronScan REST endpoints and converts raw
    responses into the unified formats defined in the spec.  It does
    very little validation and always attempts to return sensible
    defaults when external requests fail.
    """

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

    def get_wallet_info(self, wallet_address: str) -> WalletInfoResponse:
        account_data = self._get("/api/account", {"address": wallet_address})
        tokens_data = self._get("/api/account/tokens", {"address": wallet_address, "limit": 50})
        native_balance = 0.0
        if account_data and isinstance(account_data, dict):
            balance_sun = account_data.get("balance") or 0
            try:
                native_balance = float(balance_sun) / 1e6
            except Exception:
                native_balance = 0.0
        native_token = NativeToken(symbol="TRX", decimals=6, balance=native_balance)
        wallet_tokens: List[WalletToken] = []
        if tokens_data and isinstance(tokens_data, dict):
            raw_tokens = tokens_data.get("tokens") or tokens_data.get("trc20_tokens") or []
            for token in raw_tokens:
                contract = token.get("tokenId") or token.get("tokenAddress") or token.get("contractAddress")
                name = token.get("tokenName") or token.get("name") or ""
                symbol = token.get("tokenAbbr") or token.get("symbol") or ""
                decimals = token.get("tokenDecimal") or token.get("decimals") or 0
                balance_raw = token.get("balance") or token.get("quantity") or token.get("amount") or 0
                try:
                    bal = float(balance_raw) / (10 ** int(decimals))
                except Exception:
                    bal = 0.0
                if contract:
                    wallet_tokens.append(
                        WalletToken(
                            token_address=str(contract),
                            name=str(name),
                            symbol=str(symbol),
                            decimals=int(decimals),
                            balance=bal,
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
        Return a unified list of recent transfers for a Tron address.

        This method queries the TRX and TRC20 transfer endpoints documented under
        the Wallet API.  The TRX transfer endpoint returns transfers of the
        native token (TRX/trc10) with `from` and `to` fields, while the TRC20
        transfer endpoint returns transfers of any TRC20 token.  Both endpoints
        support filtering by address and return amounts as strings along with
        decimals.  We request both inbound and outbound transfers (direction=0)
        and sort by timestamp descending.
        """
        # Fetch native TRX transfers (trc10). direction=0 returns both incoming
        # and outgoing transfers.  db_version=1 filters out invalid addresses.
        trx_params = {
            "address": wallet_address,
            "limit": limit,
            "start": 0,
            "direction": 0,
            "reverse": True,
            "db_version": 1,
        }
        trx_data = self._get("/api/transfer/trx", trx_params)

        # Fetch TRC20 transfers.  No trc20Id is specified so all tokens are
        # returned.  direction=0 for both incoming and outgoing transfers.
        trc20_params = {
            "address": wallet_address,
            "limit": limit,
            "start": 0,
            "direction": 0,
            "reverse": True,
            "db_version": 1,
        }
        trc20_data = self._get("/api/transfer/trc20", trc20_params)

        txs: List[Transaction] = []

        # Process TRX (native) transfers
        if isinstance(trx_data, dict):
            for tx in trx_data.get("data", []):
                # Use block_timestamp or timestamp (ms) to compute ISO time
                ts = tx.get("timestamp") or tx.get("block_timestamp")
                try:
                    iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ts) / 1000)) if ts else ""
                except Exception:
                    iso = ""
                # Amount is in sun (1e6 = 1 TRX)
                amount_raw = tx.get("amount") or 0
                try:
                    amount_fmt = float(amount_raw) / 1e6
                except Exception:
                    amount_fmt = 0.0
                # Fee information may not be present for simple transfers
                fee = tx.get("energy_fee") or tx.get("fee") or 0
                try:
                    fee_fmt = float(fee) / 1e6
                except Exception:
                    fee_fmt = 0.0
                # From/to fields are provided directly
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

        # Process TRC20 transfers
        if isinstance(trc20_data, dict):
            for tx in trc20_data.get("data", []):
                ts = tx.get("timestamp") or tx.get("block_timestamp")
                try:
                    iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ts) / 1000)) if ts else ""
                except Exception:
                    iso = ""
                amount_raw = tx.get("amount") or 0
                # decimals may be present either in top-level `decimals` or nested tokenInfo
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
                # from/to fields
                from_addr = tx.get("from") or tx.get("ownerAddress") or ""
                to_addr = tx.get("to") or tx.get("toAddress") or ""
                # token symbol
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

        # Sort transactions by time descending and limit results
        txs.sort(key=lambda t: t.timestamp, reverse=True)
        txs = txs[:limit]

        # Gather wallet info for balances
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