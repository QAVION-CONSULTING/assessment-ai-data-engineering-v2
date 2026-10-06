from datetime import date

import pytest

from data_platform.ingest import connect, ingest_incremental, ingest_range
from data_platform.smard_client import FixtureSmardSource

NETZLAST = 410
WEEK_OF_DST_END = 1760911200000  # Mon 2025-10-20 00:00 Europe/Berlin, 169 hourly points
WEEK_OF_DST_START = 1774220400000  # Mon 2026-03-23 00:00 Europe/Berlin, 167 hourly points
REGULAR_WEEK = 1774821600000  # Mon 2026-03-30 00:00 Europe/Berlin, 168 hourly points
HOUR_MS = 3_600_000


@pytest.fixture()
def con():
    connection = connect(":memory:")
    yield connection
    connection.close()


def _hours_on(con, local_day: date) -> int:
    return con.execute(
        "SELECT count(*) FROM silver_smard_hourly WHERE filter_id = ? AND local_date = ?",
        [NETZLAST, local_day],
    ).fetchone()[0]


def _rows(con) -> int:
    return con.execute(
        "SELECT count(*) FROM bronze_smard WHERE filter_id = ?", [NETZLAST]
    ).fetchone()[0]


def test_dst_end_day_has_25_hours(con):
    ingest_range(con, FixtureSmardSource(), NETZLAST, date(2025, 10, 20), date(2025, 10, 27))
    assert _hours_on(con, date(2025, 10, 26)) == 25


def test_dst_start_day_has_23_hours(con):
    ingest_range(con, FixtureSmardSource(), NETZLAST, date(2026, 3, 23), date(2026, 3, 30))
    assert _hours_on(con, date(2026, 3, 29)) == 23


def test_backfill_is_idempotent_and_keeps_other_weeks(con):
    source = FixtureSmardSource(only_chunks=[WEEK_OF_DST_START, REGULAR_WEEK])
    ingest_range(con, source, NETZLAST, date(2026, 3, 23), date(2026, 3, 30))
    ingest_range(con, source, NETZLAST, date(2026, 3, 30), date(2026, 4, 6))
    both_weeks = _rows(con)

    ingest_range(con, source, NETZLAST, date(2026, 3, 23), date(2026, 3, 30))

    assert both_weeks == 167 + 168
    assert _rows(con) == both_weeks


def test_incremental_picks_up_hours_published_later(con):
    source = FixtureSmardSource(
        only_chunks=[WEEK_OF_DST_START, REGULAR_WEEK],
        published_until_ms=REGULAR_WEEK + 127 * HOUR_MS,
    )
    ingest_incremental(con, source, NETZLAST, since=date(2026, 3, 23))
    assert _rows(con) == 167 + 128

    source.published_until_ms = None
    ingest_incremental(con, source, NETZLAST, since=date(2026, 3, 23))

    assert _rows(con) == 167 + 168
