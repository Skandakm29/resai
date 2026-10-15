"""restaurant owner contact (self-serve onboarding)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-15 21:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('restaurants', sa.Column('owner_name', sa.String(length=120), nullable=True))
    op.add_column('restaurants', sa.Column('owner_email', sa.String(length=254), nullable=True))


def downgrade() -> None:
    op.drop_column('restaurants', 'owner_email')
    op.drop_column('restaurants', 'owner_name')
