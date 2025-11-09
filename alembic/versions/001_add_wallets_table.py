"""add wallets table

Revision ID: 001
Revises: 
Create Date: 2025-11-10 00:52:45.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'wallets' not in tables:
        op.create_table(
            'wallets',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('type', sa.String(length=50), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('owner', sa.String(length=200), nullable=False),
            sa.Column('exchange_name', sa.String(length=200), nullable=True),
            sa.Column('wallet_address', sa.String(length=200), nullable=False),
            sa.Column('blockchain', sa.String(length=50), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('blockchain', 'wallet_address', name='uq_wallet_blockchain_address')
        )
        op.create_index(op.f('ix_wallets_id'), 'wallets', ['id'], unique=False)
    else:
        indexes = [idx['name'] for idx in inspector.get_indexes('wallets')]
        if 'ix_wallets_id' not in indexes:
            op.create_index(op.f('ix_wallets_id'), 'wallets', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_wallets_id'), table_name='wallets')
    op.drop_table('wallets')


