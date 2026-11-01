"""Create reference schema tables, constraints, and indexes

Revision ID: 0002_create_reference_schema
Revises: 0001_create_database_schemas
Create Date: 2026-11-02 01:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0002_create_reference_schema"
down_revision: Union[str, None] = "0001_create_database_schemas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TRIGGER_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION reference.check_company_classification_overlap()
RETURNS TRIGGER AS $$
DECLARE
    v_scheme_id UUID;
    v_conflict_count INT;
BEGIN
    SELECT scheme_id INTO v_scheme_id
    FROM reference.classification_categories
    WHERE id = NEW.category_id;

    SELECT COUNT(*) INTO v_conflict_count
    FROM reference.company_classifications cc
    JOIN reference.classification_categories cat ON cc.category_id = cat.id
    WHERE cc.company_id = NEW.company_id
      AND cat.scheme_id = v_scheme_id
      AND cc.id != NEW.id
      AND daterange(cc.valid_from, cc.valid_to, '[)') && daterange(NEW.valid_from, NEW.valid_to, '[)');

    IF v_conflict_count > 0 THEN
        RAISE EXCEPTION 'Conflicting company classification: overlapping validity period for company in classification scheme'
            USING ERRCODE = 'exclusion_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

CREATE_TRIGGER_SQL = """
CREATE TRIGGER trg_check_company_classification_overlap
BEFORE INSERT OR UPDATE ON reference.company_classifications
FOR EACH ROW EXECUTE FUNCTION reference.check_company_classification_overlap();
"""


def upgrade() -> None:
    # 0. Ensure btree_gist extension is available for exclusion constraints
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # 1. exchanges
    op.create_table(
        "exchanges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("timezone", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(code)) > 0", name="ck_exchanges_code_not_empty"),
        sa.CheckConstraint("length(country) = 2", name="ck_exchanges_country_len"),
        sa.UniqueConstraint("code", name="uq_exchanges_code"),
        schema="reference",
    )

    # 2. companies
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_companies_name_not_empty"),
        sa.CheckConstraint("length(country) = 2", name="ck_companies_country_len"),
        schema="reference",
    )

    # 3. company_identifiers
    op.create_table(
        "company_identifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reference.companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("identifier_type", sa.String(length=30), nullable=False),
        sa.Column("identifier_value", sa.String(length=100), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_company_identifiers_valid_range"),
        schema="reference",
    )
    op.create_index(
        "ix_company_identifiers_company_id",
        "company_identifiers",
        ["company_id"],
        schema="reference",
    )
    op.create_index(
        "ix_company_identifiers_type_val",
        "company_identifiers",
        ["identifier_type", "identifier_value"],
        schema="reference",
    )
    op.execute(
        "ALTER TABLE reference.company_identifiers ADD CONSTRAINT excl_company_identifiers_overlap "
        "EXCLUDE USING gist (company_id WITH =, identifier_type WITH =, daterange(valid_from, valid_to, '[)') WITH &&)"
    )

    # 4. classification_schemes
    op.create_table(
        "classification_schemes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(code)) > 0", name="ck_classification_schemes_code_not_empty"),
        sa.UniqueConstraint("code", name="uq_classification_schemes_code"),
        schema="reference",
    )

    # 5. classification_categories
    op.create_table(
        "classification_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scheme_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reference.classification_schemes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reference.classification_categories.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("category_level", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "category_level IN ('SECTOR', 'INDUSTRY', 'SUB_INDUSTRY')",
            name="ck_classification_categories_level",
        ),
        sa.UniqueConstraint("scheme_id", "code", name="uq_classification_categories_scheme_id_code"),
        schema="reference",
    )
    op.create_index(
        "ix_classification_categories_scheme_id",
        "classification_categories",
        ["scheme_id"],
        schema="reference",
    )
    op.create_index(
        "ix_classification_categories_parent_id",
        "classification_categories",
        ["parent_id"],
        schema="reference",
    )

    # 6. company_classifications
    op.create_table(
        "company_classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reference.companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reference.classification_categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source_name", sa.String(length=150), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_company_classifications_valid_range"),
        schema="reference",
    )
    op.create_index(
        "ix_company_classifications_company_id",
        "company_classifications",
        ["company_id"],
        schema="reference",
    )
    op.create_index(
        "ix_company_classifications_category_id",
        "company_classifications",
        ["category_id"],
        schema="reference",
    )
    op.execute(TRIGGER_FUNCTION_SQL)
    op.execute(CREATE_TRIGGER_SQL)

    # 7. instruments
    op.create_table(
        "instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reference.companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("instrument_type", sa.String(length=50), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("face_value", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "instrument_type IN ('EQUITY', 'PREFERENCE_SHARE', 'BOND', 'DEBENTURE', 'ETF', 'OTHER')",
            name="ck_instruments_type",
        ),
        sa.CheckConstraint("face_value IS NULL OR face_value > 0", name="ck_instruments_face_value_positive"),
        sa.CheckConstraint("length(currency) = 3", name="ck_instruments_currency_len"),
        schema="reference",
    )
    op.create_index(
        "ix_instruments_company_id",
        "instruments",
        ["company_id"],
        schema="reference",
    )
    op.create_index(
        "ix_instruments_type",
        "instruments",
        ["instrument_type"],
        schema="reference",
    )

    # 8. instrument_identifiers
    op.create_table(
        "instrument_identifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "instrument_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reference.instruments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("identifier_type", sa.String(length=30), nullable=False),
        sa.Column("identifier_value", sa.String(length=100), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_instrument_identifiers_valid_range"),
        schema="reference",
    )
    op.create_index(
        "ix_instrument_identifiers_instrument_id",
        "instrument_identifiers",
        ["instrument_id"],
        schema="reference",
    )
    op.create_index(
        "ix_instrument_identifiers_type_val",
        "instrument_identifiers",
        ["identifier_type", "identifier_value"],
        schema="reference",
    )
    op.execute(
        "ALTER TABLE reference.instrument_identifiers ADD CONSTRAINT excl_instrument_identifiers_overlap "
        "EXCLUDE USING gist (instrument_id WITH =, identifier_type WITH =, daterange(valid_from, valid_to, '[)') WITH &&)"
    )

    # 9. instrument_listings
    op.create_table(
        "instrument_listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "instrument_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reference.instruments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "exchange_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reference.exchanges.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("listing_date", sa.Date(), nullable=False),
        sa.Column("delisting_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("delisting_date IS NULL OR delisting_date > listing_date", name="ck_instrument_listings_dates"),
        schema="reference",
    )
    op.create_index(
        "ix_instrument_listings_instrument_id",
        "instrument_listings",
        ["instrument_id"],
        schema="reference",
    )
    op.create_index(
        "ix_instrument_listings_exchange_id",
        "instrument_listings",
        ["exchange_id"],
        schema="reference",
    )
    op.create_index(
        "ix_instrument_listings_listing_date",
        "instrument_listings",
        ["listing_date"],
        schema="reference",
    )
    op.execute(
        "ALTER TABLE reference.instrument_listings ADD CONSTRAINT excl_instrument_listings_overlap "
        "EXCLUDE USING gist (instrument_id WITH =, exchange_id WITH =, daterange(listing_date, delisting_date, '[)') WITH &&)"
    )

    # 10. listing_history
    op.create_table(
        "listing_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reference.instrument_listings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=100), nullable=True),
        sa.Column("series", sa.String(length=20), nullable=True),
        sa.Column("security_code", sa.String(length=50), nullable=True),
        sa.Column("lot_size", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("tick_size", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_listing_history_valid_range"),
        sa.CheckConstraint("lot_size IS NULL OR lot_size > 0", name="ck_listing_history_lot_size_positive"),
        sa.CheckConstraint("tick_size IS NULL OR tick_size > 0", name="ck_listing_history_tick_size_positive"),
        schema="reference",
    )
    op.create_index(
        "ix_listing_history_listing_id",
        "listing_history",
        ["listing_id"],
        schema="reference",
    )
    op.create_index(
        "ix_listing_history_symbol",
        "listing_history",
        ["symbol"],
        schema="reference",
    )
    op.create_index(
        "ix_listing_history_security_code",
        "listing_history",
        ["security_code"],
        schema="reference",
    )
    op.create_index(
        "ix_listing_history_valid_from",
        "listing_history",
        ["valid_from"],
        schema="reference",
    )
    op.execute(
        "ALTER TABLE reference.listing_history ADD CONSTRAINT excl_listing_history_overlap "
        "EXCLUDE USING gist (listing_id WITH =, daterange(valid_from, valid_to, '[)') WITH &&)"
    )


def downgrade() -> None:
    # Drop trigger and trigger function
    op.execute("DROP TRIGGER IF EXISTS trg_check_company_classification_overlap ON reference.company_classifications")
    op.execute("DROP FUNCTION IF EXISTS reference.check_company_classification_overlap()")

    # Drop tables in reverse dependency order
    op.drop_table("listing_history", schema="reference")
    op.drop_table("instrument_listings", schema="reference")
    op.drop_table("instrument_identifiers", schema="reference")
    op.drop_table("instruments", schema="reference")
    op.drop_table("company_classifications", schema="reference")
    op.drop_table("classification_categories", schema="reference")
    op.drop_table("classification_schemes", schema="reference")
    op.drop_table("company_identifiers", schema="reference")
    op.drop_table("companies", schema="reference")
    op.drop_table("exchanges", schema="reference")

    # Note: btree_gist extension is intentionally NOT dropped as it is a shared database extension
