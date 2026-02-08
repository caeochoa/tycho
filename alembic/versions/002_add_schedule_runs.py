"""Add schedule_runs table

Revision ID: 002
Revises: 001
Create Date: 2026-02-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schedule_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("raw_count", sa.Integer(), server_default="0"),
        sa.Column("deduped_count", sa.Integer(), server_default="0"),
        sa.Column("new_count", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(), server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("schedule_runs")
