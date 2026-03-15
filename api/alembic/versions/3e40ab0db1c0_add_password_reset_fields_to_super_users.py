"""add password reset fields to super_users

Revision ID: 3e40ab0db1c0
Revises: 
Create Date: 2026-03-06 23:56:51.185880

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3e40ab0db1c0'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('super_users',
        sa.Column('password_reset_token', sa.String(100), nullable=True),
        schema='auth'
    )
    op.add_column('super_users',
        sa.Column('password_reset_expires_at', sa.DateTime(), nullable=True),
        schema='auth'
    )


def upgrade() -> None:
    op.add_column('super_users',
        sa.Column('password_reset_token', sa.String(100), nullable=True),
        schema='auth'
    )
    op.add_column('super_users',
        sa.Column('password_reset_expires_at', sa.DateTime(), nullable=True),
        schema='auth'
    )
