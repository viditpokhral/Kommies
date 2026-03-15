"""add_is_admin_to_super_users

Revision ID: 83f8a378cfa7
Revises: a10197564ab6
Create Date: 2026-03-14 18:13:15.843862

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '83f8a378cfa7'
down_revision: Union[str, None] = 'a10197564ab6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('super_users',
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'),
        schema='auth',
    )


def downgrade() -> None:
    op.drop_column('super_users', 'is_admin', schema='auth')
