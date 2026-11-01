"""Reference schema models.

Includes exchanges, companies, classifications, instruments, and listings.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    column,
    func,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from borsel.db.base import Base


class Exchange(Base):
    """Stock exchanges where securities are listed and traded."""

    __tablename__ = "exchanges"
    __table_args__ = (
        CheckConstraint("length(trim(code)) > 0", name="ck_exchanges_code_not_empty"),
        CheckConstraint("length(country) = 2", name="ck_exchanges_country_len"),
        {"schema": "reference"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    listings: Mapped[list["InstrumentListing"]] = relationship(
        back_populates="exchange"
    )


class Company(Base):
    """Issuing companies. Company identity is tracked via identifiers."""

    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_companies_name_not_empty"),
        CheckConstraint("length(country) = 2", name="ck_companies_country_len"),
        {"schema": "reference"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    website: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    identifiers: Mapped[list["CompanyIdentifier"]] = relationship(
        back_populates="company"
    )
    classifications: Mapped[list["CompanyClassification"]] = relationship(
        back_populates="company"
    )
    instruments: Mapped[list["Instrument"]] = relationship(
        back_populates="company"
    )


class CompanyIdentifier(Base):
    """External identifiers for companies (e.g. CIN, LEI)."""

    __tablename__ = "company_identifiers"
    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_company_identifiers_valid_range",
        ),
        ExcludeConstraint(
            ("company_id", "="),
            ("identifier_type", "="),
            (func.daterange(column("valid_from"), column("valid_to"), "[)"), "&&"),
            name="excl_company_identifiers_overlap",
        ),
        Index("ix_company_identifiers_company_id", "company_id"),
        Index("ix_company_identifiers_type_val", "identifier_type", "identifier_value"),
        {"schema": "reference"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference.companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    identifier_type: Mapped[str] = mapped_column(String(30), nullable=False)
    identifier_value: Mapped[str] = mapped_column(String(100), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    company: Mapped["Company"] = relationship(back_populates="identifiers")


class ClassificationScheme(Base):
    """Taxonomy schemes for industry and sector classifications."""

    __tablename__ = "classification_schemes"
    __table_args__ = (
        CheckConstraint(
            "length(trim(code)) > 0",
            name="ck_classification_schemes_code_not_empty",
        ),
        {"schema": "reference"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    categories: Mapped[list["ClassificationCategory"]] = relationship(
        back_populates="scheme"
    )


class ClassificationCategory(Base):
    """Hierarchical categories within a classification scheme."""

    __tablename__ = "classification_categories"
    __table_args__ = (
        UniqueConstraint(
            "scheme_id",
            "code",
            name="uq_classification_categories_scheme_id_code",
        ),
        CheckConstraint(
            "category_level IN ('SECTOR', 'INDUSTRY', 'SUB_INDUSTRY')",
            name="ck_classification_categories_level",
        ),
        Index("ix_classification_categories_scheme_id", "scheme_id"),
        Index("ix_classification_categories_parent_id", "parent_id"),
        {"schema": "reference"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scheme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference.classification_schemes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference.classification_categories.id", ondelete="RESTRICT"),
        nullable=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category_level: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    scheme: Mapped["ClassificationScheme"] = relationship(back_populates="categories")
    parent: Mapped[Optional["ClassificationCategory"]] = relationship(
        back_populates="children", remote_side="ClassificationCategory.id"
    )
    children: Mapped[list["ClassificationCategory"]] = relationship(
        back_populates="parent"
    )
    company_classifications: Mapped[list["CompanyClassification"]] = relationship(
        back_populates="category"
    )


class CompanyClassification(Base):
    """Company assignment to a classification category over time."""

    __tablename__ = "company_classifications"
    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_company_classifications_valid_range",
        ),
        Index("ix_company_classifications_company_id", "company_id"),
        Index("ix_company_classifications_category_id", "category_id"),
        {"schema": "reference"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference.companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference.classification_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    company: Mapped["Company"] = relationship(back_populates="classifications")
    category: Mapped["ClassificationCategory"] = relationship(
        back_populates="company_classifications"
    )


class Instrument(Base):
    """Securities issued by companies."""

    __tablename__ = "instruments"
    __table_args__ = (
        CheckConstraint(
            "instrument_type IN ('EQUITY', 'PREFERENCE_SHARE', 'BOND', 'DEBENTURE', 'ETF', 'OTHER')",
            name="ck_instruments_type",
        ),
        CheckConstraint(
            "face_value IS NULL OR face_value > 0",
            name="ck_instruments_face_value_positive",
        ),
        CheckConstraint("length(currency) = 3", name="ck_instruments_currency_len"),
        Index("ix_instruments_company_id", "company_id"),
        Index("ix_instruments_type", "instrument_type"),
        {"schema": "reference"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference.companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    face_value: Mapped[Optional[float]] = mapped_column(Numeric(20, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    company: Mapped["Company"] = relationship(back_populates="instruments")
    identifiers: Mapped[list["InstrumentIdentifier"]] = relationship(
        back_populates="instrument"
    )
    listings: Mapped[list["InstrumentListing"]] = relationship(
        back_populates="instrument"
    )


class InstrumentIdentifier(Base):
    """External security identifiers (e.g. ISIN)."""

    __tablename__ = "instrument_identifiers"
    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_instrument_identifiers_valid_range",
        ),
        ExcludeConstraint(
            ("instrument_id", "="),
            ("identifier_type", "="),
            (func.daterange(column("valid_from"), column("valid_to"), "[)"), "&&"),
            name="excl_instrument_identifiers_overlap",
        ),
        Index("ix_instrument_identifiers_instrument_id", "instrument_id"),
        Index(
            "ix_instrument_identifiers_type_val",
            "identifier_type",
            "identifier_value",
        ),
        {"schema": "reference"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference.instruments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    identifier_type: Mapped[str] = mapped_column(String(30), nullable=False)
    identifier_value: Mapped[str] = mapped_column(String(100), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    instrument: Mapped["Instrument"] = relationship(back_populates="identifiers")


class InstrumentListing(Base):
    """Exchange listing episode for an instrument. Supports delisting/relisting."""

    __tablename__ = "instrument_listings"
    __table_args__ = (
        CheckConstraint(
            "delisting_date IS NULL OR delisting_date > listing_date",
            name="ck_instrument_listings_dates",
        ),
        ExcludeConstraint(
            ("instrument_id", "="),
            ("exchange_id", "="),
            (func.daterange(column("listing_date"), column("delisting_date"), "[)"), "&&"),
            name="excl_instrument_listings_overlap",
        ),
        Index("ix_instrument_listings_instrument_id", "instrument_id"),
        Index("ix_instrument_listings_exchange_id", "exchange_id"),
        Index("ix_instrument_listings_listing_date", "listing_date"),
        {"schema": "reference"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference.instruments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    exchange_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference.exchanges.id", ondelete="RESTRICT"),
        nullable=False,
    )
    listing_date: Mapped[date] = mapped_column(Date, nullable=False)
    delisting_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    instrument: Mapped["Instrument"] = relationship(back_populates="listings")
    exchange: Mapped["Exchange"] = relationship(back_populates="listings")
    history: Mapped[list["ListingHistory"]] = relationship(back_populates="listing")


class ListingHistory(Base):
    """Historical trading identifiers and attributes for an exchange listing."""

    __tablename__ = "listing_history"
    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_listing_history_valid_range",
        ),
        CheckConstraint(
            "lot_size IS NULL OR lot_size > 0",
            name="ck_listing_history_lot_size_positive",
        ),
        CheckConstraint(
            "tick_size IS NULL OR tick_size > 0",
            name="ck_listing_history_tick_size_positive",
        ),
        ExcludeConstraint(
            ("listing_id", "="),
            (func.daterange(column("valid_from"), column("valid_to"), "[)"), "&&"),
            name="excl_listing_history_overlap",
        ),
        Index("ix_listing_history_listing_id", "listing_id"),
        Index("ix_listing_history_symbol", "symbol"),
        Index("ix_listing_history_security_code", "security_code"),
        Index("ix_listing_history_valid_from", "valid_from"),
        {"schema": "reference"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference.instrument_listings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    symbol: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    series: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    security_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    lot_size: Mapped[Optional[float]] = mapped_column(Numeric(20, 6), nullable=True)
    tick_size: Mapped[Optional[float]] = mapped_column(Numeric(20, 6), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    listing: Mapped["InstrumentListing"] = relationship(back_populates="history")
