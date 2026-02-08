"""Initial schema: jobs table

Revision ID: 001
Revises: None
Create Date: 2026-02-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), server_default=""),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("company", sa.String(), nullable=False),
        sa.Column("location", sa.String(), server_default=""),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("url", sa.String(), server_default=""),
        sa.Column("salary_min", sa.Float(), nullable=True),
        sa.Column("salary_max", sa.Float(), nullable=True),
        sa.Column("date_posted", sa.DateTime(), nullable=True),
        sa.Column("date_collected", sa.DateTime(), nullable=True),
        sa.Column("tags", sa.Text(), server_default="[]"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("score_details", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), server_default="new"),
        sa.Column("cv_path", sa.String(), nullable=True),
        sa.Column("cover_letter_path", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("source", "source_id", name="uq_source_source_id"),
    )


def downgrade() -> None:
    op.drop_table("jobs")
