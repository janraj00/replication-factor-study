#!/usr/bin/env python3
import argparse
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.cockroach.crdb_common import TABLE, connect, fetch_ranges

DDL_DROP_CREATE = f'''
DROP TABLE IF EXISTS {TABLE} CASCADE;
CREATE TABLE {TABLE} (
  id INT PRIMARY KEY,
  name STRING NOT NULL,
  email STRING NOT NULL,
  placeholder STRING
);
'''

INSERT_ROWS = f'''
INSERT INTO {TABLE} (id, name, email, placeholder)
SELECT i,
       'user_' || i,
       'user_' || i || '@example.com',
       repeat('x', 32)
FROM generate_series(%s, %s) AS g(i);
'''


def make_zone_cfg(rf: int, min_bytes: int, max_bytes: int) -> str:
    return f'''
ALTER TABLE {TABLE} CONFIGURE ZONE USING
  range_min_bytes = {min_bytes},
  range_max_bytes = {max_bytes},
  num_replicas = {rf};
'''


def split_table(conn, rows: int, start_id: int, num_ranges: int) -> None:
    if num_ranges <= 1:
        return
    step = rows // num_ranges
    split_points = [start_id + step * i for i in range(1, num_ranges)]
    if not split_points:
        return
    vals = ','.join(f'({sp})' for sp in split_points)
    print(f'Splitting into {num_ranges} ranges at {split_points}')
    with conn.cursor() as cur:
        cur.execute(f'ALTER TABLE {TABLE} SPLIT AT VALUES {vals};')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--node', type=int, default=1)
    ap.add_argument('--rows', type=int, default=90000)
    ap.add_argument('--mb', type=float, default=0.0)
    ap.add_argument('--start-id', type=int, default=1)
    ap.add_argument('--batch-rows', type=int, default=10000)
    ap.add_argument('--rf', type=int, default=3)
    ap.add_argument('--ranges', type=int, default=1)
    ap.add_argument('--range-min-bytes', type=int, default=1073741824)
    ap.add_argument('--range-max-bytes', type=int, default=2147483648)
    ap.add_argument('--disable-load-split', action='store_true', default=True)
    args = ap.parse_args()

    rows = args.rows
    if rows <= 0 and args.mb > 0:
        approx_row_bytes = 96
        rows = math.ceil((args.mb * 1024 * 1024) / approx_row_bytes)

    conn = connect(args.node, 'setup_users')
    try:
        with conn.cursor() as cur:
            print(f'Dropping/recreating {TABLE}')
            cur.execute(DDL_DROP_CREATE)

            if args.disable_load_split:
                print('Disabling load-based splitting; enabling merge queue')
                cur.execute('SET CLUSTER SETTING kv.range_split.by_load_enabled = false')
                cur.execute('SET CLUSTER SETTING kv.range_merge.queue_enabled = true')

            print(f'Configuring RF={args.rf}')
            cur.execute(make_zone_cfg(args.rf, args.range_min_bytes, args.range_max_bytes))

        inserted = 0
        next_id = args.start_id
        while inserted < rows:
            take = min(args.batch_rows, rows - inserted)
            end_id = next_id + take - 1
            with conn.cursor() as cur:
                cur.execute(INSERT_ROWS, (next_id, end_id))
            inserted += take
            next_id += take
            print(f'Inserted {inserted}/{rows}', flush=True)

        split_table(conn, rows, args.start_id, args.ranges)

        with conn.cursor() as cur:
            cur.execute(f'SELECT count(*), min(id), max(id) FROM {TABLE}')
            count, min_id, max_id = cur.fetchone()
            print(f'Done. count={count}, min={min_id}, max={max_id}, rf={args.rf}, ranges={args.ranges}')

        print('Ranges:')
        for r in fetch_ranges(args.node):
            print(r)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
