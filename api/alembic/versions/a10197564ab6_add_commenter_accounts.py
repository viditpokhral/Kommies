"""add_commenter_accounts

Revision ID: a10197564ab6
Revises: 0bb740fdbf8b
Create Date: 2026-03-14 17:46:49.710302

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a10197564ab6'
down_revision: Union[str, None] = '0bb740fdbf8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'commenter_accounts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True, server_default='active'),
        sa.Column('email_verified', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('email_verification_token', sa.String(255), nullable=True),
        sa.Column('password_reset_token', sa.String(255), nullable=True),
        sa.Column('password_reset_expires', sa.DateTime(), nullable=True),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
        schema='core',
    )
    op.add_column('comments',
        sa.Column('commenter_id', sa.UUID(), nullable=True),
        schema='core',
    )
    op.create_foreign_key(
        'fk_comments_commenter_id',
        'comments', 'commenter_accounts',
        ['commenter_id'], ['id'],
        source_schema='core', referent_schema='core',
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_comments_commenter_id', 'comments', schema='core', type_='foreignkey')
    op.drop_column('comments', 'commenter_id', schema='core')
    op.drop_table('commenter_accounts', schema='core')
