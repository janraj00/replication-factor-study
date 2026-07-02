#!/usr/bin/env python3
import argparse
import concurrent.futures
import csv
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.cockroach.crdb_common import NODE_PORTS, fetch_node_metric_samples, parse_list

DEFAULT_METRICS = [
    'sql.service.latency',
    'exec.latency',
    'sql.select.count',
    'sql.insert.count',
    'sql.update.count',
    'sql.delete.count',
    'sys.rss',
]


def sample_once(metric_names, run_id='', rf='', ratio='', node_ids=None):
    ts = time.time()
    rows = []
    node_ids = list(NODE_PORTS) if node_ids is None else node_ids
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(node_ids)) as pool:
        futures = {
            pool.submit(fetch_node_metric_samples, metric_names, node_id): node_id
            for node_id in node_ids
        }
        for future, node_id in futures.items():
            try:
                metrics = future.result()
            except Exception as e:
                rows.append({
                    'timestamp': ts,
                    'run_id': run_id,
                    'rf': rf,
                    'ratio': ratio,
                    'node_id': node_id,
                    'metric': '__error__',
                    'sample_type': 'error',
                    'le': '',
                    'value': '',
                    'error': str(e),
                })
                continue
            for metric in metrics:
                rows.append({
                    'timestamp': ts,
                    'run_id': run_id,
                    'rf': rf,
                    'ratio': ratio,
                    'node_id': metric.get('node_id', node_id),
                    'metric': metric.get('name', ''),
                    'sample_type': metric.get('sample_type', ''),
                    'le': metric.get('le', ''),
                    'value': metric.get('value', ''),
                    'error': '',
                })
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
    ap.add_argument('--nodes', default='all')
    ap.add_argument('--stop-file', default='')
    ap.add_argument('--ready-file', default='')
    args = ap.parse_args()

    metric_names = [m.strip() for m in args.metrics.split(',') if m.strip()]
    node_ids = list(NODE_PORTS) if args.nodes == 'all' else parse_list(args.nodes, int)
    if not node_ids:
        raise ValueError('At least one CockroachDB node must be selected')
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    stop_file = Path(args.stop_file) if args.stop_file else None
    ready_file = Path(args.ready_file) if args.ready_file else None
    end = time.monotonic() + args.duration

    with out.open('w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'timestamp', 'run_id', 'rf', 'ratio', 'node_id', 'metric',
            'sample_type', 'le', 'value', 'error',
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        def write_sample():
            for row in sample_once(metric_names, args.run_id, args.rf, args.ratio, node_ids):
                writer.writerow(row)
            f.flush()

        write_sample()
        if ready_file:
            ready_file.parent.mkdir(parents=True, exist_ok=True)
            ready_file.touch()
        next_sample = time.monotonic() + args.interval
        while True:
            now = time.monotonic()
            if stop_file and stop_file.exists():
                write_sample()
                break
            if now >= end:
                write_sample()
                break
            if now >= next_sample:
                write_sample()
                next_sample += args.interval
                continue
            time.sleep(min(0.25, next_sample - now, end - now))


if __name__ == '__main__':
    main()
