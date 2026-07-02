#!/usr/bin/env python3
import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.cockroach.crdb_common import parse_list
from experiments.common.io import ensure_dir, append_csv, write_experiment_metadata, write_json


def run(cmd):
    print('+', ' '.join(str(x) for x in cmd), flush=True)
    return subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rfs', default='3,4,5,6,7,8,9,10')
    ap.add_argument('--ratios', default='0:100,10:90,20:80,30:70,40:60,50:50,60:40,70:30,80:20,90:10,100:0')
    ap.add_argument('--repetitions', type=int, default=1)
    ap.add_argument('--rows', type=int, default=90000)
    ap.add_argument('--ranges', type=int, default=1)
    ap.add_argument('--duration', type=int, default=180)
    ap.add_argument('--cooldown', type=int, default=60)
    ap.add_argument('--qps-total', type=float, default=1200)
    ap.add_argument('--workers-per-node', type=int, default=2)
    ap.add_argument('--read-mode', choices=['strong', 'follower'], default='strong')
    ap.add_argument('--metric-interval', type=float, default=15.0)
    ap.add_argument('--results-dir', default='results/cockroach_rf_sweep')
    ap.add_argument('--shuffle', action='store_true', help='Randomize RF/ratio run order within each repetition.')
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    results_dir = ensure_dir(args.results_dir)
    write_experiment_metadata(results_dir, 'cockroach', args, repo_root)
    runs_csv = results_dir / 'runs.csv'
    rfs = parse_list(args.rfs, int)
    ratios = parse_list(args.ratios, str)

    for rep in range(1, args.repetitions + 1):
        planned_runs = [(ratio, rf) for ratio in ratios for rf in rfs]
        if args.shuffle:
            random.shuffle(planned_runs)
        for order_idx, (ratio, rf) in enumerate(planned_runs, start=1):
            run_id = f'rep{rep}_ratio{ratio.replace(":", "-")}_rf{rf}_{args.read_mode}'
            run_dir = ensure_dir(results_dir / run_id)
            run_meta = {
                'run_id': run_id,
                'rep': rep,
                'order_idx': order_idx,
                'rf': rf,
                'ratio': ratio,
                'rows': args.rows,
                'ranges': args.ranges,
                'duration': args.duration,
                'cooldown': args.cooldown,
                'qps_total': args.qps_total,
                'workers_per_node': args.workers_per_node,
                'read_mode': args.read_mode,
                'metric_interval': args.metric_interval,
            }
            write_json(run_dir / 'run_metadata.json', run_meta)

            run([sys.executable, str(repo_root / 'experiments/cockroach/setup_users.py'), '--rows', str(args.rows), '--rf', str(rf), '--ranges', str(args.ranges)])
            print(f'Cooldown before load: {args.cooldown}s', flush=True)
            time.sleep(args.cooldown)

            metrics_out = run_dir / 'metrics.csv'
            load_out = run_dir / 'load.json'
            metrics_stop = run_dir / 'load_complete.signal'
            metrics_ready = run_dir / 'metrics_ready.signal'
            for signal_file in (metrics_stop, metrics_ready):
                if signal_file.exists():
                    signal_file.unlink()
            metrics_cmd = [
                sys.executable,
                str(repo_root / 'experiments/cockroach/collect_metrics.py'),
                '--duration',
                str(args.duration + 120),
                '--interval',
                str(args.metric_interval),
                '--out',
                str(metrics_out),
                '--run-id',
                run_id,
                '--rf',
                str(rf),
                '--ratio',
                ratio,
                '--nodes',
                'all',
                '--stop-file',
                str(metrics_stop),
                '--ready-file',
                str(metrics_ready),
            ]
            load_cmd = [sys.executable, str(repo_root / 'experiments/cockroach/load_workload.py'), '--duration', str(args.duration), '--qps-total', str(args.qps_total), '--workers-per-node', str(args.workers_per_node), '--ratio', ratio, '--read-mode', args.read_mode, '--json-out', str(load_out)]

            metrics_proc = subprocess.Popen(metrics_cmd)
            try:
                ready_deadline = time.time() + 30.0
                while not metrics_ready.exists():
                    if metrics_proc.poll() is not None:
                        raise RuntimeError('Metrics collector exited before its baseline snapshot')
                    if time.time() >= ready_deadline:
                        raise TimeoutError('Metrics collector did not produce a baseline snapshot within 30s')
                    time.sleep(0.1)
                run(load_cmd)
            finally:
                metrics_stop.touch()
                metrics_proc.wait(timeout=90)

            print(f'Cooldown after load: {args.cooldown}s', flush=True)
            time.sleep(args.cooldown)

            load_summary = json.loads(load_out.read_text(encoding='utf-8'))
            append_csv(runs_csv, {
                'run_id': run_id,
                'rep': rep,
                'order_idx': order_idx,
                'rf': rf,
                'ratio': ratio,
                'rows': args.rows,
                'ranges': args.ranges,
                'duration': args.duration,
                'cooldown': args.cooldown,
                'qps_target': load_summary.get('qps_target'),
                'qps_actual': load_summary.get('qps_actual'),
                'connect_err': load_summary.get('connect_err', 0),
                'reads_ok': load_summary.get('reads_ok'),
                'reads_err': load_summary.get('reads_err'),
                'writes_ok': load_summary.get('writes_ok'),
                'writes_err': load_summary.get('writes_err'),
                'read_mode': args.read_mode,
                'read_latency_ms_mean': load_summary.get('read_latency_ms_mean'),
                'read_latency_ms_p50': load_summary.get('read_latency_ms_p50'),
                'read_latency_ms_p90': load_summary.get('read_latency_ms_p90'),
                'read_latency_ms_p99': load_summary.get('read_latency_ms_p99'),
                'write_latency_ms_mean': load_summary.get('write_latency_ms_mean'),
                'write_latency_ms_p50': load_summary.get('write_latency_ms_p50'),
                'write_latency_ms_p90': load_summary.get('write_latency_ms_p90'),
                'write_latency_ms_p99': load_summary.get('write_latency_ms_p99'),
                'metrics_file': str(metrics_out),
                'load_file': str(load_out),
            })

    print(f'Done. Results: {results_dir}')


if __name__ == '__main__':
    main()
