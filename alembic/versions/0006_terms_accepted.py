"""add terms_accepted to users

Revision ID: 0006_terms_accepted
Revises: 0005_feedback_messages
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_terms_accepted"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("terms_accepted", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "terms_accepted")
