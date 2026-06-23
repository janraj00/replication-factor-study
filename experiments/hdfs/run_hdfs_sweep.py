#!/usr/bin/env python3
import argparse
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.common.io import ensure_dir, append_csv, write_experiment_metadata
from experiments.cockroach.crdb_common import parse_list


def dc(compose_dir: Path, *args, capture=False):
    cmd = ['docker', 'compose', '-f', str(compose_dir / 'docker-compose.yml'), *args]
    print('+', ' '.join(cmd), flush=True)
    if capture:
        return subprocess.check_output(cmd, text=True)
    subprocess.run(cmd, check=True)


def client(compose_dir: Path, shell: str, capture=False):
    return dc(compose_dir, 'exec', '-T', 'hdfs-client', 'bash', '-lc', shell, capture=capture)


def prepare_file(compose_dir: Path, file_size_mb: int):
    client(compose_dir, f'dd if=/dev/zero of=/tmp/bench_file.bin bs=1M count={file_size_mb} status=none')
    client(compose_dir, 'ls -lh /tmp/bench_file.bin')


def write_dataset(compose_dir: Path, rf: int, num_files: int, hdfs_dir: str):
    client(compose_dir, f'hdfs dfs -rm -r -f {hdfs_dir} || true')
    client(compose_dir, f'hdfs dfs -mkdir -p {hdfs_dir}')
    t0 = time.time()
    for i in range(num_files):
        client(compose_dir, f'hdfs dfs -D dfs.replication={rf} -put -f /tmp/bench_file.bin {hdfs_dir}/file_{i}.bin')
    client(compose_dir, f'hdfs dfs -setrep -w {rf} {hdfs_dir}')
    return time.time() - t0


def read_one(compose_dir: Path, hdfs_path: str):
    t0 = time.time()
    client(compose_dir, f'hdfs dfs -cat {hdfs_path} > /dev/null')
    return time.time() - t0


def read_parallel(compose_dir: Path, hdfs_dir: str, num_files: int, readers: int, file_size_mb: int):
    paths = [f'{hdfs_dir}/file_{i % num_files}.bin' for i in range(readers)]
    t0 = time.time()
    durations = []
    with ThreadPoolExecutor(max_workers=readers) as ex:
        futs = [ex.submit(read_one, compose_dir, p) for p in paths]
        for fut in as_completed(futs):
            durations.append(fut.result())
    elapsed = time.time() - t0
    total_mb = readers * file_size_mb
    return {
        'readers': readers,
        'read_elapsed_s': elapsed,
        'read_total_mb': total_mb,
        'read_throughput_mb_s': total_mb / max(elapsed, 1e-9),
        'single_read_avg_s': sum(durations) / max(len(durations), 1),
        'single_read_max_s': max(durations) if durations else 0.0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--compose-dir', default='infra/local/hdfs')
    ap.add_argument('--rfs', default='1,2,3,4,5')
    ap.add_argument('--readers', default='1,2,4,8,16')
    ap.add_argument('--file-size-mb', type=int, default=128)
    ap.add_argument('--num-files', type=int, default=8)
    ap.add_argument('--repetitions', type=int, default=1)
    ap.add_argument('--results-dir', default='results/hdfs_rf_sweep')
    ap.add_argument('--hdfs-dir', default='/bench')
    ap.add_argument('--shuffle', action='store_true', help='Randomize RF order and reader order within each repetition.')
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    compose_dir = Path(args.compose_dir).resolve()
    results_dir = ensure_dir(args.results_dir)
    write_experiment_metadata(results_dir, 'hdfs', args, repo_root)
    rows_csv = results_dir / 'runs.csv'
    rfs = parse_list(args.rfs, int)
    reader_counts = parse_list(args.readers, int)

    prepare_file(compose_dir, args.file_size_mb)

    for rep in range(1, args.repetitions + 1):
        rf_order = list(rfs)
        if args.shuffle:
            random.shuffle(rf_order)
        for rf_order_idx, rf in enumerate(rf_order, start=1):
            print(f'=== HDFS rep={rep} RF={rf} ===', flush=True)
            write_elapsed = write_dataset(compose_dir, rf, args.num_files, args.hdfs_dir)
            written_mb = args.num_files * args.file_size_mb
            write_throughput = written_mb / max(write_elapsed, 1e-9)

            reader_order = list(reader_counts)
            if args.shuffle:
                random.shuffle(reader_order)
            for reader_order_idx, readers in enumerate(reader_order, start=1):
                read_summary = read_parallel(compose_dir, args.hdfs_dir, args.num_files, readers, args.file_size_mb)
                row = {
                    'rep': rep,
                    'rf_order_idx': rf_order_idx,
                    'reader_order_idx': reader_order_idx,
                    'rf': rf,
                    'file_size_mb': args.file_size_mb,
                    'num_files': args.num_files,
                    'written_mb': written_mb,
                    'write_elapsed_s': write_elapsed,
                    'write_throughput_mb_s': write_throughput,
                    **read_summary,
                }
                append_csv(rows_csv, row)
                print(row, flush=True)

    print(f'Done. Results: {rows_csv}')


if __name__ == '__main__':
    main()
