#!/usr/bin/env python3
import argparse
import json
import random
import string
import sys
import threading
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.cockroach.crdb_common import NODE_PORTS, TABLE, connect, parse_list


def rand_str(n=8):
    return ''.join(random.choices(string.ascii_lowercase, k=n))


class RateLimiter:
    def __init__(self, qps: float):
        self.interval = 1.0 / max(qps, 1e-9)
        self.next_ts = time.perf_counter()

    def wait(self):
        now = time.perf_counter()
        if self.next_ts > now:
            time.sleep(self.next_ts - now)
        self.next_ts += self.interval


def parse_ratio(s: str):
    for sep in (':', '/', ','):
        if sep in s:
            a, b = s.split(sep, 1)
            return float(a), float(b)
    return float(s), 0.0


def percentile(values, quantile):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def latency_summary(values, prefix):
    if not values:
        return {
            f'{prefix}_latency_ms_mean': None,
            f'{prefix}_latency_ms_p50': None,
            f'{prefix}_latency_ms_p90': None,
            f'{prefix}_latency_ms_p99': None,
        }
    return {
        f'{prefix}_latency_ms_mean': sum(values) / len(values),
        f'{prefix}_latency_ms_p50': percentile(values, 0.50),
        f'{prefix}_latency_ms_p90': percentile(values, 0.90),
        f'{prefix}_latency_ms_p99': percentile(values, 0.99),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--qps-total', type=float, default=1200)
    ap.add_argument('--qps-per-node', type=float, default=0.0)
    ap.add_argument('--ratio', type=str, default='80:20')
    ap.add_argument('--duration', type=int, default=180)
    ap.add_argument('--workers-per-node', type=int, default=2)
    ap.add_argument('--nodes', type=str, default='all')
    ap.add_argument('--id-min', type=int, default=1)
    ap.add_argument('--id-max', type=int, default=90000)
    ap.add_argument('--read-mode', choices=['strong', 'follower'], default='strong')
    ap.add_argument('--json-out', default='')
    ap.add_argument('--max-error-prints', type=int, default=20)
    args = ap.parse_args()

    nodes = list(NODE_PORTS.keys()) if args.nodes == 'all' else parse_list(args.nodes, int)
    r, w = parse_ratio(args.ratio)
    read_share = r / max(r + w, 1e-9)
    total_workers = len(nodes) * args.workers_per_node
    total_qps = args.qps_per_node * len(nodes) if args.qps_per_node > 0 else args.qps_total
    per_worker_qps = total_qps / max(total_workers, 1)

    lock = threading.Lock()
    stop_evt = threading.Event()
    counts = {'reads_ok': 0, 'reads_err': 0, 'writes_ok': 0, 'writes_err': 0, 'connect_err': 0, 'printed_errors': 0}
    latencies = {'read_ms': [], 'write_ms': []}

    def worker(node: int, worker_id: int):
        deadline = time.time() + 30
        while True:
            try:
                strong = connect(node, f'load_strong_w{worker_id}', follower=False)
                follower = connect(node, f'load_follower_w{worker_id}', follower=True)
                break
            except Exception as e:
                if time.time() >= deadline:
                    with lock:
                        counts['connect_err'] += 1
                        if counts['printed_errors'] < args.max_error_prints:
                            counts['printed_errors'] += 1
                            print(f'[node={node} worker={worker_id}] connect error: {type(e).__name__}: {e}', flush=True)
                    return
                time.sleep(1)
        limiter = RateLimiter(per_worker_qps)
        try:
            while not stop_evt.is_set():
                idv = random.randint(args.id_min, args.id_max)
                is_read = random.random() < read_share
                op_started = time.perf_counter()
                try:
                    if is_read:
                        conn = follower if args.read_mode == 'follower' else strong
                        with conn.cursor() as cur:
                            cur.execute(f'SELECT id FROM {TABLE} WHERE id=%s', (idv,))
                            cur.fetchone()
                        with lock:
                            counts['reads_ok'] += 1
                            latencies['read_ms'].append((time.perf_counter() - op_started) * 1000.0)
                    else:
                        with strong.cursor() as cur:
                            cur.execute(
                                f'UPSERT INTO {TABLE}(id, name, email, placeholder) VALUES (%s, %s, %s, %s)',
                                (idv, f'name_{rand_str(6)}', f'{rand_str(6)}@x.com', 'x' * 32),
                            )
                        with lock:
                            counts['writes_ok'] += 1
                            latencies['write_ms'].append((time.perf_counter() - op_started) * 1000.0)
                except Exception as e:
                    with lock:
                        counts['reads_err' if is_read else 'writes_err'] += 1
                        if counts['printed_errors'] < args.max_error_prints:
                            counts['printed_errors'] += 1
                            print(f'[node={node} worker={worker_id}] error: {type(e).__name__}: {e}', flush=True)
                limiter.wait()
        finally:
            for conn in (strong, follower):
                try:
                    conn.close()
                except Exception:
                    pass

    threads = []
    wid = 0
    for node in nodes:
        for _ in range(args.workers_per_node):
            t = threading.Thread(target=worker, args=(node, wid), daemon=True)
            t.start()
            threads.append(t)
            wid += 1

    t0 = time.time()
    try:
        time.sleep(args.duration)
    finally:
        stop_evt.set()
        for t in threads:
            t.join(timeout=2.0)

    elapsed = max(time.time() - t0, 0.001)
    with lock:
        summary = dict(counts)
        read_latencies = list(latencies['read_ms'])
        write_latencies = list(latencies['write_ms'])
    summary.update({
        'ratio': args.ratio,
        'duration': args.duration,
        'elapsed': elapsed,
        'nodes': nodes,
        'workers_per_node': args.workers_per_node,
        'total_workers': total_workers,
        'qps_target': total_qps,
        'qps_actual': (summary['reads_ok'] + summary['writes_ok']) / elapsed,
        'read_mode': args.read_mode,
        'id_min': args.id_min,
        'id_max': args.id_max,
    })
    summary.update(latency_summary(read_latencies, 'read'))
    summary.update(latency_summary(write_latencies, 'write'))

    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding='utf-8')


if __name__ == '__main__':
    main()
