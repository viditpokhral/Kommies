"""add_email_verification_to_super_users

Revision ID: c5f2e8b91d4a
Revises: 83f8a378cfa7
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa

revision = 'c5f2e8b91d4a'
down_revision = '83f8a378cfa7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('super_users',
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'),
        schema='auth',
    )
    op.add_column('super_users',
        sa.Column('email_verification_token', sa.String(255), nullable=True),
        schema='auth',
    )


def downgrade() -> None:
    op.drop_column('super_users', 'email_verification_token', schema='auth')
    op.drop_column('super_users', 'email_verified', schema='auth')