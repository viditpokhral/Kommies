"""add_site_members

Revision ID: 0bb740fdbf8b
Revises: 3e40ab0db1c0
Create Date: 2026-03-14 11:36:13.107614

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0bb740fdbf8b'
down_revision: Union[str, None] = '3e40ab0db1c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'site_members',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('website_id', sa.UUID(), nullable=False),
        sa.Column('super_user_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='moderator'),
        sa.Column('invited_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['website_id'], ['core.websites.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['super_user_id'], ['auth.super_users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by'], ['auth.super_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('website_id', 'super_user_id'),
        schema='auth',
    )


def downgrade() -> None:
    op.drop_table('site_members', schema='auth')
