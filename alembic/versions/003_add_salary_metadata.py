"""Add salary_currency and salary_interval to jobs

Revision ID: 003
Revises: 002
Create Date: 2026-07-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("salary_currency", sa.String(), nullable=True))
    op.add_column("jobs", sa.Column("salary_interval", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "salary_interval")
    op.drop_column("jobs", "salary_currency")
