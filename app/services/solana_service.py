import base64
import time
from typing import Any, Dict, List, Optional

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


class SolanaService:
    """
    Service integrating with Solana JSON‑RPC API to gather wallet
    balances, token holdings, transactions and contract metadata.

    The implementation uses the public mainnet RPC endpoint when
    QUICKNODE_API_URL is not supplied.  If environment variables are
    undefined the service gracefully falls back to static dummy
    responses.  This approach keeps the proof of concept operational
    without requiring actual blockchain connectivity.
    """

    def __init__(self, rpc_url: Optional[str] = None) -> None:
        self.rpc_url = rpc_url or Config.QUICKNODE_API_URL or "https://api.mainnet-beta.solana.com"
        self.session = requests.Session()

    def _post(self, method: str, params: List[Any]) -> Optional[Dict[str, Any]]:
        """
        Internal helper to perform JSON‑RPC POST requests.  Returns
        parsed JSON on success or None on failure.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        try:
            resp = self.session.post(self.rpc_url, json=payload, timeout=20)
            if resp.ok:
                data = resp.json()
                return data.get("result")
        except Exception:
            return None
        return None

    def get_wallet_info(self, wallet_address: str) -> WalletInfoResponse:
        """
        Retrieve the native SOL balance and SPL token holdings for a
        given wallet.  Uses `getAccountInfo` to obtain lamports and
        `getTokenAccountsByOwner` for token accounts.  On failure
        returns zero balances.
        """
        native_balance = 0.0
        # fetch account info for SOL balance
        account_info = self._post(
            "getAccountInfo",
            [wallet_address, {"encoding": "jsonParsed"}],
        )
        if account_info and isinstance(account_info, dict):
            lamports = account_info.get("value", {}).get("lamports")
            try:
                native_balance = float(lamports) / (10 ** 9)
            except Exception:
                native_balance = 0.0

        native_token = NativeToken(symbol="SOL", decimals=9, balance=native_balance)

        tokens: List[WalletToken] = []
        # fetch SPL token accounts
        token_accounts = self._post(
            "getTokenAccountsByOwner",
            [
                wallet_address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"},
            ],
        )
        if token_accounts and isinstance(token_accounts, dict):
            for item in token_accounts.get("value", []):
                account_data = item.get("account", {}).get("data", {})
                parsed = account_data.get("parsed", {})
                if parsed.get("type") != "account":
                    continue
                info = parsed.get("info", {})
                token_amount = info.get("tokenAmount", {})
                mint = info.get("mint")
                decimals = token_amount.get("decimals", 0)
                amount = token_amount.get("amount", "0")
                try:
                    balance = float(amount) / (10 ** int(decimals))
                except Exception:
                    balance = 0.0
                tokens.append(
                    WalletToken(
                        token_address=mint or "",
                        name="",  # Solana RPC does not expose name directly
                        symbol="",  # symbol unknown via RPC
                        decimals=int(decimals),
                        balance=balance,
                    )
                )

        return WalletInfoResponse(
            wallet_address=wallet_address,
            blockchain="solana",
            native_token=native_token,
            tokens=tokens,
        )

    def get_transactions_list(self, wallet_address: str, limit: int = 20) -> TransactionsListResponse:
        """
        Get recent transactions for a wallet.  Uses
        `getSignaturesForAddress` to obtain signatures then calls
        `getTransaction` to decode each transaction.  Due to the
        complexity of Solana transactions this implementation only
        extracts high level fields such as signatures, block time,
        sender, receiver and lamport amounts.  Token transfers are not
        deeply parsed.  When the RPC endpoint fails the response
        contains empty lists.
        """
        transactions: List[Transaction] = []

        # fetch signatures
        signatures_result = self._post(
            "getSignaturesForAddress",
            [wallet_address, {"limit": limit}],
        )
        signature_list = []
        if signatures_result and isinstance(signatures_result, list):
            for sig in signatures_result:
                signature_list.append(sig.get("signature"))

        # iterate signatures and fetch transaction details
        for sig in signature_list:
            tx_data = self._post(
                "getTransaction",
                [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
            )
            if not tx_data or not isinstance(tx_data, dict):
                continue
            meta = tx_data.get("meta", {})
            transaction = tx_data.get("transaction", {})
            block_time = tx_data.get("blockTime") or 0
            try:
                iso_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(block_time)))
            except Exception:
                iso_time = ""
            # default values
            from_addr = ""
            to_addr = ""
            amount = "0"
            amount_formatted = "0.0"
            fee = meta.get("fee", 0)
            fee_formatted = 0.0
            try:
                fee_formatted = float(fee) / (10 ** 9)
            except Exception:
                fee_formatted = 0.0
            # parse instructions for simple SOL transfer
            message = transaction.get("message", {})
            account_keys = message.get("accountKeys", [])
            instructions = message.get("instructions", [])
            # iterate instructions to find transfer
            for ix in instructions:
                # system program (11111111111111111111111111111111) instruction for lamport transfer
                program_id = ix.get("programId") or ix.get("programIdIndex")
                # when encoded, programIdIndex is int referencing account_keys
                if isinstance(program_id, int) and account_keys:
                    try:
                        program_id = account_keys[program_id].get("pubkey") if isinstance(account_keys[program_id], dict) else account_keys[program_id]
                    except Exception:
                        program_id = None
                if program_id == "11111111111111111111111111111111":
                    # decode transfer amount from data base64
                    data = ix.get("data")
                    try:
                        # data for SystemProgram::Transfer is 8 byte little endian amount
                        decoded = base64.b64decode(data)
                        lamports = int.from_bytes(decoded, "little")
                        amount = str(lamports)
                        amount_formatted = str(lamports / (10 ** 9))
                    except Exception:
                        amount = "0"
                        amount_formatted = "0.0"
                    # find source and destination
                    ix_accounts = ix.get("accounts", [])
                    if ix_accounts and account_keys:
                        try:
                            from_index, to_index = ix_accounts[0], ix_accounts[1]
                            from_addr = account_keys[from_index] if isinstance(account_keys[from_index], str) else account_keys[from_index].get("pubkey", "")
                            to_addr = account_keys[to_index] if isinstance(account_keys[to_index], str) else account_keys[to_index].get("pubkey", "")
                        except Exception:
                            pass
                    break
            transactions.append(
                Transaction(
                    hash=sig,
                    timestamp=iso_time,
                    from_=from_addr,
                    to=to_addr,
                    amount=amount,
                    amount_formatted=amount_formatted,
                    token_symbol="SOL",
                    transaction_fee=str(fee),
                    transaction_fee_formatted=str(fee_formatted),
                    status="success",  # Solana RPC does not expose failed flag easily
                    block_number=tx_data.get("slot", 0),
                )
            )

        # compute native balance for summary
        wallet_info = self.get_wallet_info(wallet_address)
        native_symbol = wallet_info.native_token.symbol
        native_balance_formatted = str(wallet_info.native_token.balance)
        native_balance_raw = str(int(wallet_info.native_token.balance * (10 ** wallet_info.native_token.decimals)))

        # convert tokens to TxnTokenBalance list
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
            blockchain="solana",
            wallet_address=wallet_address,
            native_balance=native_balance_raw,
            native_balance_formatted=native_balance_formatted,
            native_symbol=native_symbol,
            tokens=token_balances,
            transactions=transactions,
        )

    def get_contract_details(self, contract_address: str) -> ContractDetailsResponse:
        """
        Retrieve mint information for an SPL token.  Uses the
        `getAccountInfo` method on the mint address.  Because Solana
        metadata (name, symbol, etc.) is stored off-chain via the
        Metaplex metadata program, this implementation cannot fetch
        those fields via the basic RPC call and returns empty strings.
        """
        account_info = self._post(
            "getAccountInfo",
            [contract_address, {"encoding": "jsonParsed"}],
        )
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
        if account_info and isinstance(account_info, dict):
            value = account_info.get("value", {})
            data = value.get("data", {})
            parsed = data.get("parsed", {})
            if parsed.get("type") == "mint":
                info = parsed.get("info", {})
                decimals = int(info.get("decimals", 0))
                supply_raw = info.get("supply", "0")
                total_supply = str(supply_raw)
                try:
                    total_supply_formatted = str(int(supply_raw) / (10 ** decimals))
                except Exception:
                    total_supply_formatted = "0.0"
                is_mintable = not bool(info.get("isInitialized") is False)
                # creator and creation time cannot be reliably extracted from RPC
        return ContractDetailsResponse(
            contract_address=contract_address,
            blockchain="solana",
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