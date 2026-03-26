"""add subscription_until to users

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-26

"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("subscription_until", sa.DateTime(timezone=True), nullable=True),
    )
    # Выдаём доступ yakushentsiya на 6 месяцев при первом /start (через код)
    # Здесь только схема


def downgrade() -> None:
    op.drop_column("users", "subscription_until")
