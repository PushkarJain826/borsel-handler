"""Create demo market and ingestion tables for Phase 1 MVP pipeline

Revision ID: 0003_create_market_ingestion_demo_tables
Revises: 0002_create_reference_schema
Create Date: 2026-11-02 02:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0003_create_demo_tables"
down_revision: Union[str, None] = "0002_create_reference_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. market.demo_daily_prices
    op.create_table(
        "demo_daily_prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("high", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("low", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("close", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("data_source", sa.String(length=50), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("high >= low", name="ck_demo_daily_prices_high_low"),
        sa.CheckConstraint("volume >= 0", name="ck_demo_daily_prices_volume_nonneg"),
        sa.UniqueConstraint(
            "symbol",
            "trading_date",
            "data_source",
            name="uq_demo_daily_prices_sym_date_src",
        ),
        schema="market",
    )
    op.create_index(
        "ix_demo_daily_prices_symbol_date",
        "demo_daily_prices",
        ["symbol", "trading_date"],
        schema="market",
    )
    op.create_index(
        "ix_demo_daily_prices_trading_date",
        "demo_daily_prices",
        ["trading_date"],
        schema="market",
    )

    # 2. ingestion.demo_import_runs
    op.create_table(
        "demo_import_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column(
            "records_processed",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "records_failed",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        schema="ingestion",
    )
    op.create_index(
        "ix_demo_import_runs_started_at",
        "demo_import_runs",
        ["started_at"],
        schema="ingestion",
    )
    op.create_index(
        "ix_demo_import_runs_status",
        "demo_import_runs",
        ["status"],
        schema="ingestion",
    )


def downgrade() -> None:
    op.drop_table("demo_import_runs", schema="ingestion")
    op.drop_table("demo_daily_prices", schema="market")
