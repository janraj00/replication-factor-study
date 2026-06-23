#!/usr/bin/env python3
import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.cockroach.crdb_common import fetch_node_metrics

DEFAULT_METRICS = [
    'sql.service.latency-p90',
    'sql.service.latency-p99',
    'exec.latency-p90',
    'exec.latency-p99',
    'sql.select.count',
    'sql.insert.count',
    'sql.update.count',
    'sql.delete.count',
    'sys.rss',
]


def sample_once(metric_names, run_id='', rf='', ratio='', node_id=1):
    ts = time.time()
    rows = []
    try:
        metrics = fetch_node_metrics(metric_names, node_id=node_id)
    except Exception as e:
        return [{'timestamp': ts, 'run_id': run_id, 'rf': rf, 'ratio': ratio, 'node_id': '', 'metric': '__error__', 'value': '', 'error': str(e)}]

    for m in metrics:
        rows.append({'timestamp': ts, 'run_id': run_id, 'rf': rf, 'ratio': ratio, 'node_id': m.get('node_id', ''), 'metric': m.get('name', ''), 'value': m.get('value', ''), 'error': ''})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--metrics', default=','.join(DEFAULT_METRICS))
    ap.add_argument('--interval', type=float, default=15.0)
    ap.add_argument('--duration', type=float, default=180.0)
    ap.add_argument('--out', required=True)
    ap.add_argument('--run-id', default='')
    ap.add_argument('--rf', default='')
    ap.add_argument('--ratio', default='')
    ap.add_argument('--node', type=int, default=1)
    args = ap.parse_args()

    metric_names = [m.strip() for m in args.metrics.split(',') if m.strip()]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    end = time.time() + args.duration

    with out.open('w', newline='', encoding='utf-8') as f:
        fieldnames = ['timestamp', 'run_id', 'rf', 'ratio', 'node_id', 'metric', 'value', 'error']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        while time.time() < end:
            for row in sample_once(metric_names, args.run_id, args.rf, args.ratio, args.node):
                writer.writerow(row)
            f.flush()
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
