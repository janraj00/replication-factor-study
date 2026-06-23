#!/usr/bin/env python3
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results-dir', required=True)
    args = ap.parse_args()

    results_dir = Path(args.results_dir)
    runs = pd.read_csv(results_dir / 'runs.csv')
    runs.to_excel(results_dir / 'summary.xlsx', index=False)
    runs.to_csv(results_dir / 'summary.csv', index=False)

    if 'rep' not in runs.columns:
        runs['rep'] = 1

    grouped = runs.groupby(['rf', 'readers'], as_index=False).agg(
        runs=('rep', 'count'),
        write_throughput_mb_s_mean=('write_throughput_mb_s', 'mean'),
        write_throughput_mb_s_std=('write_throughput_mb_s', 'std'),
        read_throughput_mb_s_mean=('read_throughput_mb_s', 'mean'),
        read_throughput_mb_s_std=('read_throughput_mb_s', 'std'),
        read_elapsed_s_mean=('read_elapsed_s', 'mean'),
        read_elapsed_s_std=('read_elapsed_s', 'std'),
        single_read_avg_s_mean=('single_read_avg_s', 'mean'),
        single_read_avg_s_std=('single_read_avg_s', 'std'),
        single_read_max_s_mean=('single_read_max_s', 'mean'),
        single_read_max_s_std=('single_read_max_s', 'std'),
    )
    grouped.to_csv(results_dir / 'summary_grouped.csv', index=False)
    grouped.to_excel(results_dir / 'summary_grouped.xlsx', index=False)

    for readers, df in runs.groupby('readers'):
        df = df.sort_values('rf')
        plt.figure()
        plt.plot(df['rf'], df['read_throughput_mb_s'], marker='o')
        plt.xlabel('HDFS replication factor')
        plt.ylabel('Read throughput [MB/s]')
        plt.title(f'HDFS read throughput, readers={readers}')
        plt.grid(True)
        plt.savefig(results_dir / f'hdfs_read_throughput_readers_{readers}.png', bbox_inches='tight')
        plt.close()

    w = runs.groupby('rf', as_index=False).agg(write_throughput_mb_s=('write_throughput_mb_s', 'mean'))
    plt.figure()
    plt.plot(w['rf'], w['write_throughput_mb_s'], marker='o')
    plt.xlabel('HDFS replication factor')
    plt.ylabel('Write throughput [MB/s]')
    plt.title('HDFS write throughput vs replication factor')
    plt.grid(True)
    plt.savefig(results_dir / 'hdfs_write_throughput.png', bbox_inches='tight')
    plt.close()
    print(f'Wrote summaries and plots to {results_dir}')


if __name__ == '__main__':
    main()
