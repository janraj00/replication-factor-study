#!/usr/bin/env python3
import argparse
import csv
import sys
from pathlib import Path


def parse_list(value, cast=str):
    if not value:
        return []
    return [cast(x.strip()) for x in value.split(',') if x.strip()]


def read_csv(path: Path):
    with path.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def require_columns(rows, columns, label, failures):
    present = set(rows[0].keys()) if rows else set()
    missing = [c for c in columns if c not in present]
    if missing:
        failures.append(f'{label}: missing columns: {", ".join(missing)}')


def number(row, key, default=0.0):
    value = row.get(key, '')
    if value in ('', None):
        return default
    return float(value)


def resolve_result_file(results_dir: Path, value: str) -> Path:
    p = Path(value)
    if p.exists():
        return p
    candidate = results_dir / p
    if candidate.exists():
        return candidate
    return p


def validate_cockroach(args):
    results_dir = Path(args.results_dir)
    failures = []
    warnings = []
    runs_path = results_dir / 'runs.csv'
    if not runs_path.exists():
        return [f'missing {runs_path}'], warnings, 0

    rows = read_csv(runs_path)
    if not rows:
        return [f'{runs_path}: no rows'], warnings, 0

    require_columns(
        rows,
        ['run_id', 'rep', 'rf', 'ratio', 'qps_actual', 'reads_err', 'writes_err', 'metrics_file', 'load_file'],
        'cockroach runs.csv',
        failures,
    )
    if failures:
        return failures, warnings, len(rows)

    if not (results_dir / 'metadata.json').exists():
        warnings.append('metadata.json is missing; older result directory or run before metadata support')

    for row in rows:
        bad_errors = number(row, 'reads_err') + number(row, 'writes_err') + number(row, 'connect_err', 0)
        if bad_errors:
            failures.append(f'{row["run_id"]}: nonzero error count ({bad_errors:g})')
        for file_key in ('metrics_file', 'load_file'):
            path = resolve_result_file(results_dir, row[file_key])
            if not path.exists():
                failures.append(f'{row["run_id"]}: missing {file_key} {row[file_key]}')
        metrics_path = resolve_result_file(results_dir, row['metrics_file'])
        if metrics_path.exists():
            metrics_rows = read_csv(metrics_path)
            if not metrics_rows:
                failures.append(f'{row["run_id"]}: metrics file is empty')
            else:
                require_columns(metrics_rows, ['timestamp', 'run_id', 'rf', 'ratio', 'node_id', 'metric', 'value', 'error'], f'{metrics_path}', failures)
                metric_errors = [m for m in metrics_rows if (m.get('error') or '').strip()]
                if metric_errors:
                    failures.append(f'{row["run_id"]}: metrics file contains {len(metric_errors)} error rows')

    expected_rfs = parse_list(args.expected_rfs, int)
    expected_ratios = parse_list(args.expected_ratios, str)
    expected_reps = args.expected_repetitions
    if expected_rfs and expected_ratios and expected_reps:
        observed = {(int(row['rep']), int(row['rf']), row['ratio']) for row in rows}
        missing = []
        for rep in range(1, expected_reps + 1):
            for rf in expected_rfs:
                for ratio in expected_ratios:
                    if (rep, rf, ratio) not in observed:
                        missing.append(f'rep={rep},rf={rf},ratio={ratio}')
        if missing:
            failures.append('missing expected runs: ' + '; '.join(missing))

    return failures, warnings, len(rows)


def validate_hdfs(args):
    results_dir = Path(args.results_dir)
    failures = []
    warnings = []
    runs_path = results_dir / 'runs.csv'
    if not runs_path.exists():
        return [f'missing {runs_path}'], warnings, 0

    rows = read_csv(runs_path)
    if not rows:
        return [f'{runs_path}: no rows'], warnings, 0

    require_columns(
        rows,
        ['rf', 'file_size_mb', 'num_files', 'written_mb', 'write_elapsed_s', 'write_throughput_mb_s', 'readers', 'read_elapsed_s', 'read_throughput_mb_s'],
        'hdfs runs.csv',
        failures,
    )
    if failures:
        return failures, warnings, len(rows)

    has_rep = 'rep' in rows[0]
    if not has_rep:
        warnings.append('rep column is missing; treating all rows as rep=1 for compatibility with older smoke results')
    if not (results_dir / 'metadata.json').exists():
        warnings.append('metadata.json is missing; older result directory or run before metadata support')

    for idx, row in enumerate(rows, start=1):
        if number(row, 'write_elapsed_s') <= 0:
            failures.append(f'row {idx}: write_elapsed_s must be positive')
        if number(row, 'read_elapsed_s') <= 0:
            failures.append(f'row {idx}: read_elapsed_s must be positive')
        if number(row, 'write_throughput_mb_s') <= 0:
            failures.append(f'row {idx}: write_throughput_mb_s must be positive')
        if number(row, 'read_throughput_mb_s') <= 0:
            failures.append(f'row {idx}: read_throughput_mb_s must be positive')

    expected_rfs = parse_list(args.expected_rfs, int)
    expected_readers = parse_list(args.expected_readers, int)
    expected_reps = args.expected_repetitions
    if expected_rfs and expected_readers and expected_reps:
        observed = {
            (int(row.get('rep') or 1), int(row['rf']), int(row['readers']))
            for row in rows
        }
        missing = []
        for rep in range(1, expected_reps + 1):
            for rf in expected_rfs:
                for readers in expected_readers:
                    if (rep, rf, readers) not in observed:
                        missing.append(f'rep={rep},rf={rf},readers={readers}')
        if missing:
            failures.append('missing expected runs: ' + '; '.join(missing))

    return failures, warnings, len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kind', choices=['cockroach', 'hdfs'], required=True)
    ap.add_argument('--results-dir', required=True)
    ap.add_argument('--expected-rfs', default='')
    ap.add_argument('--expected-ratios', default='')
    ap.add_argument('--expected-readers', default='')
    ap.add_argument('--expected-repetitions', type=int, default=0)
    args = ap.parse_args()

    if args.kind == 'cockroach':
        failures, warnings, count = validate_cockroach(args)
    else:
        failures, warnings, count = validate_hdfs(args)

    print(f'Validation kind={args.kind} results_dir={args.results_dir} rows={count}')
    for warning in warnings:
        print(f'WARN: {warning}')
    if failures:
        for failure in failures:
            print(f'FAIL: {failure}')
        print('Result: FAIL')
        return 1
    print('Result: PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
