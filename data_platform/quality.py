from datetime import date
from typing import List, Tuple

import duckdb

HOURS_PER_DAY = 24


def incomplete_days(con: duckdb.DuckDBPyConnection, filter_id: int) -> List[Tuple[date, int]]:
    """Days whose hourly series is not complete. Feeds the morning alert mail."""
    return con.execute(
        """
        SELECT local_date, count(*) AS hours
        FROM silver_smard_hourly
        WHERE filter_id = ?
        GROUP BY local_date
        HAVING count(*) <> ?
        ORDER BY local_date
        """,
        [filter_id, HOURS_PER_DAY],
    ).fetchall()
