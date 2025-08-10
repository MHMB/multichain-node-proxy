import base64
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple

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

# base58 alphabet for encoding/decoding
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class SolanaService:
    """Minimal JSON‑RPC client for Solana."""

    def __init__(self, rpc_url: Optional[str] = None) -> None:
        self.rpc_url = rpc_url or Config.QUICKNODE_API_URL or "https://api.mainnet-beta.solana.com"
        self.session = requests.Session()
        # Metadata program ID used by Metaplex for token metadata
        self.metadata_program_id = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"
        self.metadata_program_bytes = self._base58_decode(self.metadata_program_id)

    def _post(self, method: str, params: List[Any]) -> Optional[Dict[str, Any]]:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        try:
            resp = self.session.post(self.rpc_url, json=payload, timeout=20)
            if resp.ok:
                data = resp.json()
                return data.get("result")
        except Exception:
            return None
        return None

    def _base58_decode(self, s: str) -> bytes:
        num = 0
        for char in s:
            num = num * 58 + _B58_ALPHABET.index(char)
        res = b""
        if num > 0:
            res = num.to_bytes((num.bit_length() + 7) // 8, "big")
        zeros = 0
        for c in s:
            if c == "1":
                zeros += 1
            else:
                break
        return b"\x00" * zeros + res

    def _base58_encode(self, b: bytes) -> str:
        num = int.from_bytes(b, "big")
        if num == 0:
            res = ""
        else:
            res = ""
            while num > 0:
                num, mod = divmod(num, 58)
                res = _B58_ALPHABET[mod] + res
        zeros = 0
        for byte in b:
            if byte == 0:
                zeros += 1
            else:
                break
        return "1" * zeros + res

    def _find_metadata_account(self, mint: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Brute‑force the metadata PDA for a mint."""
        try:
            mint_bytes = self._base58_decode(mint)
        except Exception:
            return None
        seeds = [b"metadata", self.metadata_program_bytes, mint_bytes]
        for bump in range(255, -1, -1):
            seeds_with_bump = seeds + [bytes([bump])]
            data = b"".join(seeds_with_bump) + self.metadata_program_bytes + b"ProgramDerivedAddress"
            digest = hashlib.sha256(data).digest()
            candidate_bytes = digest[:32]
            candidate = self._base58_encode(candidate_bytes)
            acc_info = self._post("getAccountInfo", [candidate, {"encoding": "base64"}])
            if acc_info and isinstance(acc_info, dict):
                val = acc_info.get("value")
                if val and val.get("data"):
                    return candidate, acc_info
        return None

    def _decode_metadata(self, base64_data: str) -> Tuple[str, str]:
        try:
            buf = base64.b64decode(base64_data)
            # Skip key, update authority and mint (1 + 32 + 32 bytes)
            offset = 1 + 32 + 32

            def read_str() -> str:
                nonlocal offset
                length = int.from_bytes(buf[offset:offset + 4], "little")
                offset += 4
                s = buf[offset:offset + length].decode("utf-8", errors="ignore")
                offset += length
                return s

            name = read_str().replace("\0", "").strip()
            symbol = read_str().replace("\0", "").strip()
            return name, symbol
        except Exception:
            return "", ""

    def _get_token_metadata(self, mint: str) -> Tuple[str, str]:
        res = self._find_metadata_account(mint)
        if not res:
            return "", ""
        _, info = res
        value = info.get("value") or {}
        data_field = value.get("data")
        if not data_field or not isinstance(data_field, list):
            return "", ""
        base64_data = data_field[0]
        return self._decode_metadata(base64_data)

    def get_wallet_info(self, wallet_address: str) -> WalletInfoResponse:
        native_balance = 0.0
        account_info = self._post("getAccountInfo", [wallet_address, {"encoding": "jsonParsed"}])
        if account_info and isinstance(account_info, dict):
            lamports = account_info.get("value", {}).get("lamports")
            try:
                native_balance = float(lamports) / 1e9
            except Exception:
                native_balance = 0.0
        native_token = NativeToken(symbol="SOL", decimals=9, balance=native_balance)
        tokens: List[WalletToken] = []
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
                    bal = float(amount) / (10 ** int(decimals))
                except Exception:
                    bal = 0.0
                name, symbol = self._get_token_metadata(mint) if mint else ("", "")
                tokens.append(
                    WalletToken(
                        token_address=mint or "",
                        name=name,
                        symbol=symbol,
                        decimals=int(decimals),
                        balance=bal,
                    )
                )
        return WalletInfoResponse(
            wallet_address=wallet_address,
            blockchain="solana",
            native_token=native_token,
            tokens=tokens,
        )

    def get_transactions_list(self, wallet_address: str, limit: int = 20) -> TransactionsListResponse:
        transactions: List[Transaction] = []
        signatures_result = self._post("getSignaturesForAddress", [wallet_address, {"limit": limit}])
        signature_list: List[str] = []
        if signatures_result and isinstance(signatures_result, list):
            for sig in signatures_result:
                signature_list.append(sig.get("signature"))
        for sig in signature_list:
            tx_data = self._post(
                "getTransaction",
                [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
            )
            if not tx_data or not isinstance(tx_data, dict):
                continue
            meta = tx_data.get("meta", {}) or {}
            transaction = tx_data.get("transaction", {}) or {}
            block_time = tx_data.get("blockTime") or 0
            try:
                iso_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(block_time)))
            except Exception:
                iso_time = ""
            from_addr = ""
            to_addr = ""
            amount = "0"
            amount_formatted = "0.0"
            fee = meta.get("fee") or 0
            fee_formatted = 0.0
            try:
                fee_formatted = float(fee) / 1e9
            except Exception:
                fee_formatted = 0.0
            message = transaction.get("message", {}) or {}
            instructions = message.get("instructions", []) or []
            for ix in instructions:
                # system transfer
                prog = ix.get("program") or ix.get("programId") or ix.get("programIdIndex")
                parsed = ix.get("parsed", {}) if isinstance(ix.get("parsed"), dict) else None
                if parsed and isinstance(prog, str) and prog == "system" and parsed.get("type") == "transfer":
                    info = parsed.get("info", {})
                    from_addr = info.get("source", "")
                    to_addr = info.get("destination", "")
                    lamports = info.get("lamports") or 0
                    try:
                        amount = str(lamports)
                        amount_formatted = str(float(lamports) / 1e9)
                    except Exception:
                        amount = "0"
                        amount_formatted = "0.0"
                    break
                # spl‑token transfer
                if parsed and isinstance(prog, str) and prog == "spl-token" and parsed.get("type") == "transfer":
                    info = parsed.get("info", {})
                    from_addr = info.get("source", "")
                    to_addr = info.get("destination", "")
                    amount_raw = info.get("amount") or 0
                    amount = str(amount_raw)
                    amount_formatted = amount  # decimals unknown
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
                    status="success",
                    block_number=tx_data.get("slot", 0),
                )
            )
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
            blockchain="solana",
            wallet_address=wallet_address,
            native_balance=native_balance_raw,
            native_balance_formatted=native_balance_formatted,
            native_symbol=native_symbol,
            tokens=token_balances,
            transactions=transactions,
        )

    def get_contract_details(self, contract_address: str) -> ContractDetailsResponse:
        """Return basic mint info for an SPL token."""
        account_info = self._post("getAccountInfo", [contract_address, {"encoding": "jsonParsed"}])
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
            value = account_info.get("value", {}) or {}
            data = value.get("data", {}) or {}
            parsed = data.get("parsed", {}) or {}
            if parsed.get("type") == "mint":
                info = parsed.get("info", {}) or {}
                decimals = int(info.get("decimals", 0))
                supply_raw = info.get("supply", "0")
                total_supply = str(supply_raw)
                try:
                    total_supply_formatted = str(int(supply_raw) / (10 ** decimals))
                except Exception:
                    total_supply_formatted = "0.0"
                is_mintable = not bool(info.get("isInitialized") is False)
        # attempt metadata
        nm, sym = self._get_token_metadata(contract_address)
        name = nm or name
        symbol = sym or symbol
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