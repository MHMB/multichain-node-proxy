from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app.database import db_manager
from app.models.database import Wallet
from app.models.responses import WalletCreateRequest, WalletUpdateRequest, WalletResponse


class WalletService:
    """Service for wallet CRUD operations."""

    async def create_wallet(self, wallet_data: WalletCreateRequest) -> WalletResponse:
        """Create a new wallet entry."""
        session = await db_manager.get_session()
        try:
            wallet = Wallet(
                type=wallet_data.type,
                name=wallet_data.name,
                note=wallet_data.note,
                owner=wallet_data.owner,
                exchange_name=wallet_data.exchange_name,
                wallet_address=wallet_data.wallet_address,
                blockchain=wallet_data.blockchain.lower()
            )
            session.add(wallet)
            await session.commit()
            await session.refresh(wallet)
            return self._wallet_to_response(wallet)
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=400,
                detail="Wallet with this blockchain and address combination already exists"
            )
        except Exception as e:
            await session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create wallet: {str(e)}"
            )
        finally:
            await session.close()

    async def get_wallet(self, wallet_id: int) -> WalletResponse:
        """Get a wallet by ID."""
        session = await db_manager.get_session()
        try:
            query = select(Wallet).where(Wallet.id == wallet_id)
            result = await session.execute(query)
            wallet = result.scalar_one_or_none()
            if not wallet:
                raise HTTPException(status_code=404, detail="Wallet not found")
            return self._wallet_to_response(wallet)
        finally:
            await session.close()

    async def list_wallets(
        self,
        blockchain: Optional[str] = None,
        owner: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[WalletResponse]:
        """List wallets with optional filters."""
        session = await db_manager.get_session()
        try:
            query = select(Wallet)
            if blockchain:
                query = query.where(Wallet.blockchain == blockchain.lower())
            if owner:
                query = query.where(Wallet.owner == owner)
            query = query.order_by(Wallet.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(query)
            wallets = result.scalars().all()
            return [self._wallet_to_response(w) for w in wallets]
        finally:
            await session.close()

    async def update_wallet(
        self,
        wallet_id: int,
        wallet_data: WalletUpdateRequest
    ) -> WalletResponse:
        """Update a wallet by ID."""
        session = await db_manager.get_session()
        try:
            query = select(Wallet).where(Wallet.id == wallet_id)
            result = await session.execute(query)
            wallet = result.scalar_one_or_none()
            if not wallet:
                raise HTTPException(status_code=404, detail="Wallet not found")
            
            if wallet_data.type is not None:
                wallet.type = wallet_data.type
            if wallet_data.name is not None:
                wallet.name = wallet_data.name
            if wallet_data.note is not None:
                wallet.note = wallet_data.note
            if wallet_data.owner is not None:
                wallet.owner = wallet_data.owner
            if wallet_data.exchange_name is not None:
                wallet.exchange_name = wallet_data.exchange_name
            
            await session.commit()
            await session.refresh(wallet)
            return self._wallet_to_response(wallet)
        except HTTPException:
            raise
        except Exception as e:
            await session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update wallet: {str(e)}"
            )
        finally:
            await session.close()

    async def delete_wallet(self, wallet_id: int) -> None:
        """Delete a wallet by ID."""
        session = await db_manager.get_session()
        try:
            query = select(Wallet).where(Wallet.id == wallet_id)
            result = await session.execute(query)
            wallet = result.scalar_one_or_none()
            if not wallet:
                raise HTTPException(status_code=404, detail="Wallet not found")
            await session.delete(wallet)
            await session.commit()
        except HTTPException:
            raise
        except Exception as e:
            await session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete wallet: {str(e)}"
            )
        finally:
            await session.close()

    async def get_wallet_by_address(self, blockchain: str, wallet_address: str) -> Optional[WalletResponse]:
        """Get a wallet by blockchain and address."""
        session = await db_manager.get_session()
        try:
            query = select(Wallet).where(
                Wallet.blockchain == blockchain.lower(),
                Wallet.wallet_address == wallet_address
            )
            result = await session.execute(query)
            wallet = result.scalar_one_or_none()
            if wallet:
                return self._wallet_to_response(wallet)
            return None
        finally:
            await session.close()

    def _wallet_to_response(self, wallet: Wallet) -> WalletResponse:
        """Convert Wallet model to WalletResponse."""
        return WalletResponse(
            id=wallet.id,
            type=wallet.type,
            name=wallet.name,
            note=wallet.note,
            owner=wallet.owner,
            exchange_name=wallet.exchange_name,
            wallet_address=wallet.wallet_address,
            blockchain=wallet.blockchain,
            created_at=wallet.created_at.isoformat() if wallet.created_at else "",
            updated_at=wallet.updated_at.isoformat() if wallet.updated_at else ""
        )

