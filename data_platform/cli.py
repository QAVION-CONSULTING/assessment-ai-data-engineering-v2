"""``uv run python -m data_platform.cli --help``"""

import argparse
from datetime import date
from pathlib import Path

from utils import settings

from .ingest import connect, ingest_incremental, ingest_range
from .quality import incomplete_days
from .smard_client import FixtureSmardSource, HttpSmardSource


def main() -> None:
    parser = argparse.ArgumentParser(prog="data_platform")
    parser.add_argument("--fixtures", action="store_true", help="use recorded responses, no network")
    parser.add_argument("--db", default=settings.data_platform.DUCKDB_PATH)
    sub = parser.add_subparsers(dest="command", required=True)
    rng = sub.add_parser("range", help="backfill [from, to) in local time")
    rng.add_argument("--from", dest="start", type=date.fromisoformat, required=True)
    rng.add_argument("--to", dest="end", type=date.fromisoformat, required=True)
    sub.add_parser("incremental", help="load what is new since the last run")
    sub.add_parser("quality", help="list incomplete days")
    args = parser.parse_args()

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    con = connect(args.db)
    source = FixtureSmardSource() if args.fixtures else HttpSmardSource()
    filters = {name: int(fid) for name, fid in settings.data_platform.smard_filters.items()}
    region = settings.data_platform.SMARD_REGION
    resolution = settings.data_platform.SMARD_RESOLUTION

    for name, filter_id in filters.items():
        if args.command == "range":
            n = ingest_range(con, source, filter_id, args.start, args.end, region=region, resolution=resolution)
            print(f"{name}: {n} rows")
        elif args.command == "incremental":
            n = ingest_incremental(con, source, filter_id, region=region, resolution=resolution)
            print(f"{name}: {n} rows")
        else:
            for day, hours in incomplete_days(con, filter_id):
                print(f"{name}: {day} has {hours} hours")


if __name__ == "__main__":
    main()
