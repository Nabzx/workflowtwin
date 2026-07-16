"""PostgreSQL integration tests for referral audit persistence."""

import os
from collections.abc import AsyncIterator
from datetime import UTC
from itertools import pairwise
from typing import Any

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload

from workflowtwin.domain.referrals.enums import EventType, ReferralStatus
from workflowtwin.domain.referrals.fixtures import (
    referral_with_delayed_out_of_order_ingestion,
    referral_with_duplicate_source_event,
    straight_through_successful_referral,
)
from workflowtwin.infrastructure.persistence.models import (
    ImmutableEventError,
    ReferralCaseRecord,
    ReferralEventRecord,
)

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]


@pytest.fixture
async def postgres_engine() -> AsyncIterator[AsyncEngine]:
    """Connect only when the caller explicitly provides an isolated test database."""
    database_url = os.getenv("WORKFLOWTWIN_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("set WORKFLOWTWIN_TEST_DATABASE_URL to run PostgreSQL integration tests")

    engine = create_async_engine(database_url)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def database_session(postgres_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Rollback every test so fixed fixture identifiers remain reusable."""
    async with postgres_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()


def _schema_details(connection: Connection) -> dict[str, Any]:
    inspector = inspect(connection)
    return {
        "tables": set(inspector.get_table_names()),
        "case_indexes": {index["name"] for index in inspector.get_indexes("referral_cases")},
        "event_indexes": {index["name"] for index in inspector.get_indexes("referral_events")},
        "event_checks": {
            constraint["name"] for constraint in inspector.get_check_constraints("referral_events")
        },
        "event_foreign_keys": inspector.get_foreign_keys("referral_events"),
    }


async def test_migration_created_expected_schema(postgres_engine: AsyncEngine) -> None:
    async with postgres_engine.connect() as connection:
        details = await connection.run_sync(_schema_details)

    assert {
        "alembic_version",
        "referral_cases",
        "referral_events",
        "synthetic_generation_runs",
    } <= details["tables"]
    assert {"ix_referral_cases_status", "ix_referral_cases_received_at"} <= details["case_indexes"]
    assert {"ix_referral_events_case_event_at", "ix_referral_events_event_type"} <= details[
        "event_indexes"
    ]
    assert "ck_referral_events_reason_required_for_exception_event" in details["event_checks"]
    assert details["event_foreign_keys"][0]["options"]["ondelete"] == "RESTRICT"


async def test_referral_relationship_and_event_ordering(database_session: AsyncSession) -> None:
    scenario = straight_through_successful_referral()
    database_session.add(ReferralCaseRecord.from_domain(scenario.case))
    database_session.add_all(ReferralEventRecord.from_domain(event) for event in scenario.events)
    await database_session.flush()
    database_session.expire_all()

    statement = (
        select(ReferralCaseRecord)
        .where(ReferralCaseRecord.id == scenario.case.id)
        .options(selectinload(ReferralCaseRecord.events))
    )
    stored_case = (await database_session.scalars(statement)).one()

    assert len(stored_case.events) == len(scenario.events)
    assert [event.event_at for event in stored_case.events] == sorted(
        event.event_at for event in scenario.events
    )
    assert all(event.referral_case_id == stored_case.id for event in stored_case.events)


async def test_duplicate_source_event_is_rejected(database_session: AsyncSession) -> None:
    scenario = referral_with_duplicate_source_event()
    database_session.add(ReferralCaseRecord.from_domain(scenario.case))
    database_session.add_all(ReferralEventRecord.from_domain(event) for event in scenario.events)

    with pytest.raises(IntegrityError, match="uq_referral_events_source_external_event"):
        await database_session.flush()


async def test_terminal_status_constraint_is_enforced(database_session: AsyncSession) -> None:
    scenario = straight_through_successful_referral()
    record = ReferralCaseRecord.from_domain(scenario.case)
    record.closed_at = None
    database_session.add(record)

    with pytest.raises(IntegrityError, match="terminal_status_matches_closed_at"):
        await database_session.flush()


async def test_timezone_and_out_of_order_events_round_trip(database_session: AsyncSession) -> None:
    scenario = referral_with_delayed_out_of_order_ingestion()
    database_session.add(ReferralCaseRecord.from_domain(scenario.case))
    database_session.add_all(ReferralEventRecord.from_domain(event) for event in scenario.events)
    await database_session.flush()

    statement = (
        select(ReferralEventRecord)
        .where(ReferralEventRecord.referral_case_id == scenario.case.id)
        .order_by(ReferralEventRecord.ingested_at)
    )
    events = list(await database_session.scalars(statement))

    assert all(event.event_at.tzinfo is not None for event in events)
    assert all(event.event_at.utcoffset() == UTC.utcoffset(None) for event in events)
    assert any(event.event_at < previous.event_at for previous, event in pairwise(events))


async def test_orm_prevents_event_update(database_session: AsyncSession) -> None:
    scenario = straight_through_successful_referral()
    event_record = ReferralEventRecord.from_domain(scenario.events[0])
    database_session.add(ReferralCaseRecord.from_domain(scenario.case))
    database_session.add(event_record)
    await database_session.flush()

    event_record.event_type = EventType.REFERRAL_COMPLETED
    with pytest.raises(ImmutableEventError, match="append-only"):
        await database_session.flush()


@pytest.mark.parametrize("statement_kind", ["update", "delete"])
async def test_database_trigger_prevents_direct_event_mutation(
    database_session: AsyncSession, statement_kind: str
) -> None:
    scenario = straight_through_successful_referral()
    event = scenario.events[0]
    database_session.add(ReferralCaseRecord.from_domain(scenario.case))
    database_session.add(ReferralEventRecord.from_domain(event))
    await database_session.flush()

    if statement_kind == "update":
        statement = text("UPDATE referral_events SET event_type = :value WHERE id = :event_id")
        parameters = {"value": EventType.REFERRAL_RECEIVED.value, "event_id": event.id}
    else:
        statement = text("DELETE FROM referral_events WHERE id = :event_id")
        parameters = {"event_id": event.id}

    with pytest.raises(DBAPIError, match="append-only"):
        await database_session.execute(statement, parameters)


async def test_case_deletion_cannot_erase_event_history(database_session: AsyncSession) -> None:
    scenario = straight_through_successful_referral()
    case_record = ReferralCaseRecord.from_domain(scenario.case)
    database_session.add(case_record)
    database_session.add(ReferralEventRecord.from_domain(scenario.events[0]))
    await database_session.flush()

    await database_session.delete(case_record)
    with pytest.raises(IntegrityError):
        await database_session.flush()


async def test_events_can_be_queried_by_type(database_session: AsyncSession) -> None:
    scenario = straight_through_successful_referral()
    database_session.add(ReferralCaseRecord.from_domain(scenario.case))
    database_session.add_all(ReferralEventRecord.from_domain(event) for event in scenario.events)
    await database_session.flush()

    statement = select(ReferralEventRecord).where(
        ReferralEventRecord.event_type == EventType.COMPLETENESS_CHECK_COMPLETED
    )
    stored_event = (await database_session.scalars(statement)).one()

    assert stored_event.referral_case_id == scenario.case.id
    assert stored_event.event_metadata == {
        "fixture_scenario": "straight_through_successful_referral"
    }
    assert scenario.case.status is ReferralStatus.COMPLETED
