"""Tests for Reference schema models, constraints, and relationships."""

import uuid
from datetime import date
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from borsel.core.config import settings
from borsel.models.reference import (
    ClassificationCategory,
    ClassificationScheme,
    Company,
    CompanyClassification,
    CompanyIdentifier,
    Exchange,
    Instrument,
    InstrumentIdentifier,
    InstrumentListing,
    ListingHistory,
)

test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
async_session_factory = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.mark.asyncio
async def test_reference_tables_exist() -> None:
    """1. Verify that all 10 tables exist in the PostgreSQL reference schema."""
    expected_tables = {
        "classification_categories",
        "classification_schemes",
        "companies",
        "company_classifications",
        "company_identifiers",
        "exchanges",
        "instrument_identifiers",
        "instrument_listings",
        "instruments",
        "listing_history",
    }
    async with async_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'reference'"
            )
        )
        existing_tables = {row[0] for row in result.fetchall()}
        assert expected_tables.issubset(existing_tables)


@pytest.mark.asyncio
async def test_uuid_primary_keys_work() -> None:
    """2. Verify that UUID primary keys are generated and persisted correctly."""
    async with async_session_factory() as session:
        exchange = Exchange(
            code=f"EX_{uuid.uuid4().hex[:8].upper()}",
            name="Test Exchange for UUID",
            country="IN",
            timezone="Asia/Kolkata",
        )
        session.add(exchange)
        await session.commit()
        await session.refresh(exchange)

        assert exchange.id is not None
        assert isinstance(exchange.id, uuid.UUID)

        queried = await session.get(Exchange, exchange.id)
        assert queried is not None
        assert queried.code == exchange.code


@pytest.mark.asyncio
async def test_foreign_key_relationships_valid() -> None:
    """3. Verify foreign-key relationships and ORM navigation across models."""
    async with async_session_factory() as session:
        company = Company(
            name=f"Enterprise {uuid.uuid4().hex[:6]}",
            country="IN",
        )
        session.add(company)
        await session.commit()

        instrument = Instrument(
            company_id=company.id,
            name="Ordinary Equity",
            instrument_type="EQUITY",
            currency="INR",
            face_value=10.0,
        )
        exchange = Exchange(
            code=f"EX_{uuid.uuid4().hex[:8].upper()}",
            name="Relational Test Exchange",
            country="IN",
            timezone="Asia/Kolkata",
        )
        session.add_all([instrument, exchange])
        await session.commit()

        listing = InstrumentListing(
            instrument_id=instrument.id,
            exchange_id=exchange.id,
            listing_date=date(2020, 1, 1),
        )
        session.add(listing)
        await session.commit()

        history = ListingHistory(
            listing_id=listing.id,
            symbol="TESTSYM",
            series="EQ",
            valid_from=date(2020, 1, 1),
        )
        session.add(history)
        await session.commit()

        # Query back with eager loading for relationship navigation in async context
        stmt = (
            select(InstrumentListing)
            .options(
                selectinload(InstrumentListing.instrument).selectinload(Instrument.company),
                selectinload(InstrumentListing.exchange),
            )
            .where(InstrumentListing.id == listing.id)
        )
        res = await session.execute(stmt)
        retrieved_listing = res.scalar_one()

        assert retrieved_listing.instrument.id == instrument.id
        assert retrieved_listing.instrument.company.id == company.id
        assert retrieved_listing.exchange.id == exchange.id

        # Invalid foreign key rejection
        invalid_instrument = Instrument(
            company_id=uuid.uuid4(),  # Non-existent company
            name="Orphan Instrument",
            instrument_type="EQUITY",
            currency="INR",
        )
        session.add(invalid_instrument)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_duplicate_exchange_codes_rejected() -> None:
    """4. Verify that duplicate exchange codes are rejected."""
    code = f"DUP_{uuid.uuid4().hex[:6].upper()}"
    async with async_session_factory() as session:
        ex1 = Exchange(
            code=code,
            name="Exchange 1",
            country="IN",
            timezone="Asia/Kolkata",
        )
        session.add(ex1)
        await session.commit()

        ex2 = Exchange(
            code=code,
            name="Exchange 2 (Duplicate)",
            country="IN",
            timezone="Asia/Kolkata",
        )
        session.add(ex2)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_duplicate_category_codes_within_scheme_rejected() -> None:
    """5. Verify that duplicate category codes within the same scheme are rejected."""
    async with async_session_factory() as session:
        scheme1 = ClassificationScheme(
            code=f"SCHEME_{uuid.uuid4().hex[:6]}",
            name="Scheme 1",
        )
        scheme2 = ClassificationScheme(
            code=f"SCHEME_{uuid.uuid4().hex[:6]}",
            name="Scheme 2",
        )
        session.add_all([scheme1, scheme2])
        await session.commit()

        cat1 = ClassificationCategory(
            scheme_id=scheme1.id,
            code="TECH",
            name="Technology",
            category_level="SECTOR",
        )
        session.add(cat1)
        await session.commit()

        # Same code within DIFFERENT scheme must succeed
        cat_other_scheme = ClassificationCategory(
            scheme_id=scheme2.id,
            code="TECH",
            name="Technology in Scheme 2",
            category_level="SECTOR",
        )
        session.add(cat_other_scheme)
        await session.commit()

        # Duplicate code within SAME scheme must fail
        cat_duplicate = ClassificationCategory(
            scheme_id=scheme1.id,
            code="TECH",
            name="Duplicate Tech",
            category_level="SECTOR",
        )
        session.add(cat_duplicate)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_invalid_date_ranges_rejected() -> None:
    """6. Verify that valid_to <= valid_from or invalid delisting dates are rejected."""
    async with async_session_factory() as session:
        company = Company(name=f"Date Co {uuid.uuid4().hex[:6]}", country="IN")
        session.add(company)
        await session.commit()
        company_id = company.id

        # valid_to < valid_from on CompanyIdentifier
        invalid_identifier = CompanyIdentifier(
            company_id=company_id,
            identifier_type="CIN",
            identifier_value="L12345MH2000PLC123456",
            valid_from=date(2023, 1, 1),
            valid_to=date(2022, 1, 1),
        )
        session.add(invalid_identifier)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        # Listing with delisting_date < listing_date
        instrument = Instrument(
            company_id=company_id,
            name="Equity",
            instrument_type="EQUITY",
            currency="INR",
        )
        exchange = Exchange(
            code=f"EX_{uuid.uuid4().hex[:6]}",
            name="Ex Date Test",
            country="IN",
            timezone="Asia/Kolkata",
        )
        session.add_all([instrument, exchange])
        await session.commit()
        instrument_id = instrument.id
        exchange_id = exchange.id

        invalid_listing = InstrumentListing(
            instrument_id=instrument_id,
            exchange_id=exchange_id,
            listing_date=date(2023, 1, 1),
            delisting_date=date(2022, 1, 1),
        )
        session.add(invalid_listing)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_overlapping_temporal_assignments_rejected() -> None:
    """7. Verify that overlapping intervals are rejected for exclusive entities."""
    async with async_session_factory() as session:
        company = Company(name=f"Temporal Co {uuid.uuid4().hex[:6]}", country="IN")
        session.add(company)
        await session.commit()
        company_id = company.id

        # A. CompanyIdentifier overlap
        ci1 = CompanyIdentifier(
            company_id=company_id,
            identifier_type="CIN",
            identifier_value="CIN001",
            valid_from=date(2020, 1, 1),
            valid_to=date(2022, 1, 1),
        )
        session.add(ci1)
        await session.commit()

        # Adjacent non-overlapping interval [2022-01-01, None) succeeds
        ci2 = CompanyIdentifier(
            company_id=company_id,
            identifier_type="CIN",
            identifier_value="CIN002",
            valid_from=date(2022, 1, 1),
            valid_to=None,
        )
        session.add(ci2)
        await session.commit()

        # Overlapping interval [2021-01-01, 2023-01-01) must fail
        ci_overlap = CompanyIdentifier(
            company_id=company_id,
            identifier_type="CIN",
            identifier_value="CIN003",
            valid_from=date(2021, 1, 1),
            valid_to=date(2023, 1, 1),
        )
        session.add(ci_overlap)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        # B. CompanyClassification overlap within the same scheme
        scheme = ClassificationScheme(code=f"SCH_{uuid.uuid4().hex[:6]}", name="Industry Scheme")
        session.add(scheme)
        await session.commit()
        scheme_id = scheme.id

        cat1 = ClassificationCategory(scheme_id=scheme_id, code="C1", name="Cat 1", category_level="SECTOR")
        cat2 = ClassificationCategory(scheme_id=scheme_id, code="C2", name="Cat 2", category_level="SECTOR")
        session.add_all([cat1, cat2])
        await session.commit()
        cat1_id = cat1.id
        cat2_id = cat2.id

        cc1 = CompanyClassification(
            company_id=company_id,
            category_id=cat1_id,
            valid_from=date(2020, 1, 1),
            valid_to=date(2022, 1, 1),
        )
        session.add(cc1)
        await session.commit()

        # Overlapping classification under same scheme must fail
        cc_overlap = CompanyClassification(
            company_id=company_id,
            category_id=cat2_id,
            valid_from=date(2021, 1, 1),
            valid_to=date(2023, 1, 1),
        )
        session.add(cc_overlap)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        # Different scheme classification can overlap
        scheme_alt = ClassificationScheme(code=f"SCH_ALT_{uuid.uuid4().hex[:6]}", name="Alternate Scheme")
        session.add(scheme_alt)
        await session.commit()
        scheme_alt_id = scheme_alt.id

        cat_alt = ClassificationCategory(scheme_id=scheme_alt_id, code="ALT1", name="Alt Cat 1", category_level="SECTOR")
        session.add(cat_alt)
        await session.commit()
        cat_alt_id = cat_alt.id

        cc_diff_scheme = CompanyClassification(
            company_id=company_id,
            category_id=cat_alt_id,
            valid_from=date(2021, 1, 1),
            valid_to=date(2023, 1, 1),
        )
        session.add(cc_diff_scheme)
        await session.commit()


@pytest.mark.asyncio
async def test_instrument_dual_listings_nse_and_bse() -> None:
    """8. Verify that an instrument can have concurrent listings on NSE and BSE."""
    async with async_session_factory() as session:
        nse = Exchange(code=f"NSE_{uuid.uuid4().hex[:4]}", name="National Stock Exchange", country="IN", timezone="Asia/Kolkata")
        bse = Exchange(code=f"BSE_{uuid.uuid4().hex[:4]}", name="Bombay Stock Exchange", country="IN", timezone="Asia/Kolkata")
        company = Company(name=f"Dual Listed Corp {uuid.uuid4().hex[:6]}", country="IN")
        session.add_all([nse, bse, company])
        await session.commit()

        equity = Instrument(
            company_id=company.id,
            name="Dual Listed Equity",
            instrument_type="EQUITY",
            currency="INR",
            face_value=10.0,
        )
        session.add(equity)
        await session.commit()

        nse_listing = InstrumentListing(
            instrument_id=equity.id,
            exchange_id=nse.id,
            listing_date=date(2010, 1, 1),
            delisting_date=None,
            is_active=True,
        )
        bse_listing = InstrumentListing(
            instrument_id=equity.id,
            exchange_id=bse.id,
            listing_date=date(2010, 1, 1),
            delisting_date=None,
            is_active=True,
        )
        session.add_all([nse_listing, bse_listing])
        await session.commit()

        listings = (
            await session.execute(
                select(InstrumentListing).where(InstrumentListing.instrument_id == equity.id)
            )
        ).scalars().all()

        assert len(listings) == 2
        exchange_ids = {l.exchange_id for l in listings}
        assert exchange_ids == {nse.id, bse.id}


@pytest.mark.asyncio
async def test_delisting_and_relisting_preserves_history() -> None:
    """9. Verify delisting and subsequent relisting with historical preservation."""
    async with async_session_factory() as session:
        exchange = Exchange(
            code=f"EX_{uuid.uuid4().hex[:6]}",
            name="Relisting Exchange",
            country="IN",
            timezone="Asia/Kolkata",
        )
        company = Company(name=f"Relisted Corp {uuid.uuid4().hex[:6]}", country="IN")
        session.add_all([exchange, company])
        await session.commit()

        instrument = Instrument(
            company_id=company.id,
            name="Relisted Share",
            instrument_type="EQUITY",
            currency="INR",
        )
        session.add(instrument)
        await session.commit()

        # Episode 1: Listed 2010 to 2018, then delisted
        episode_1 = InstrumentListing(
            instrument_id=instrument.id,
            exchange_id=exchange.id,
            listing_date=date(2010, 1, 1),
            delisting_date=date(2018, 1, 1),
            is_active=False,
        )
        session.add(episode_1)
        await session.commit()

        hist_1 = ListingHistory(
            listing_id=episode_1.id,
            symbol="OLD_SYM",
            series="EQ",
            valid_from=date(2010, 1, 1),
            valid_to=date(2018, 1, 1),
        )
        session.add(hist_1)
        await session.commit()

        # Episode 2: Relisted 2021 onwards
        episode_2 = InstrumentListing(
            instrument_id=instrument.id,
            exchange_id=exchange.id,
            listing_date=date(2021, 1, 1),
            delisting_date=None,
            is_active=True,
        )
        session.add(episode_2)
        await session.commit()

        hist_2 = ListingHistory(
            listing_id=episode_2.id,
            symbol="NEW_SYM",
            series="EQ",
            valid_from=date(2021, 1, 1),
            valid_to=None,
        )
        session.add(hist_2)
        await session.commit()

        # Query all episodes with history eagerly loaded
        all_episodes = (
            await session.execute(
                select(InstrumentListing)
                .options(selectinload(InstrumentListing.history))
                .where(
                    InstrumentListing.instrument_id == instrument.id,
                    InstrumentListing.exchange_id == exchange.id,
                )
                .order_by(InstrumentListing.listing_date)
            )
        ).scalars().all()

        assert len(all_episodes) == 2
        assert all_episodes[0].delisting_date == date(2018, 1, 1)
        assert all_episodes[0].is_active is False
        assert all_episodes[1].delisting_date is None
        assert all_episodes[1].is_active is True

        assert len(all_episodes[0].history) == 1
        assert all_episodes[0].history[0].symbol == "OLD_SYM"
        assert len(all_episodes[1].history) == 1
        assert all_episodes[1].history[0].symbol == "NEW_SYM"
