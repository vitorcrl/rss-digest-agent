"""create fii tables

Revision ID: c1a3f8e92b47
Revises: b5c29e314434
Create Date: 2026-06-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "c1a3f8e92b47"
down_revision = "b5c29e314434"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("market", sa.String(5), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("dy_12m", sa.Float, nullable=False),
        sa.Column("pvp", sa.Float, nullable=False),
        sa.Column("vacancia", sa.Float, nullable=True),
        sa.Column("ltv", sa.Float, nullable=True),
        sa.Column("liquidez", sa.Float, nullable=False),
        sa.Column("ffo_per_share", sa.Float, nullable=True),
        sa.Column("price_ffo", sa.Float, nullable=True),
        sa.Column("debt_ebitda", sa.Float, nullable=True),
        sa.Column("occupancy", sa.Float, nullable=True),
        sa.Column("eps", sa.Float, nullable=True),
        sa.Column("book_value_per_share", sa.Float, nullable=True),
        sa.Column("roe", sa.Float, nullable=True),
        sa.Column("ev_ebitda", sa.Float, nullable=True),
        sa.Column("revenue_growth", sa.Float, nullable=True),
        sa.Column("net_margin", sa.Float, nullable=True),
        sa.Column("debt_equity", sa.Float, nullable=True),
        sa.Column("beta", sa.Float, nullable=True),
        sa.Column("payout_ratio", sa.Float, nullable=True),
        sa.Column("provento_anunciado", sa.Numeric(10, 4), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_asset_snapshots_ticker_date", "asset_snapshots", ["ticker", "date"], unique=True)

    op.create_table(
        "fii_portfolio",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(20), unique=True, nullable=False),
        sa.Column("shares", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_price", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("total_invested", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "fii_trades",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("shares", sa.Integer, nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_fii_trades_ticker_date", "fii_trades", ["ticker", "date"])

    op.create_table(
        "fii_proventos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("amount_per_share", sa.Numeric(10, 4), nullable=False),
        sa.Column("total_received", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_fii_proventos_ticker_date", "fii_proventos", ["ticker", "date"])

    op.create_table(
        "fii_budget",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("week_start", sa.Date, unique=True, nullable=False),
        sa.Column("base_budget", sa.Numeric(14, 2), nullable=False),
        sa.Column("reinvested_income", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("carried_over", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("fii_budget")
    op.drop_index("ix_fii_proventos_ticker_date", table_name="fii_proventos")
    op.drop_table("fii_proventos")
    op.drop_index("ix_fii_trades_ticker_date", table_name="fii_trades")
    op.drop_table("fii_trades")
    op.drop_table("fii_portfolio")
    op.drop_index("ix_asset_snapshots_ticker_date", table_name="asset_snapshots")
    op.drop_table("asset_snapshots")