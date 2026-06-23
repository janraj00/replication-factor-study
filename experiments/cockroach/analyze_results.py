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
    runs_path = results_dir / 'runs.csv'
    if not runs_path.exists():
        raise FileNotFoundError(runs_path)

    runs = pd.read_csv(runs_path)
    metric_frames = []
    for _, run in runs.iterrows():
        p = Path(run['metrics_file'])
        if p.exists():
            m = pd.read_csv(p)
            m['run_id'] = run['run_id']
            metric_frames.append(m)

    if not metric_frames:
        print('No metrics found.')
        return

    metrics = pd.concat(metric_frames, ignore_index=True)
    metrics = metrics[metrics['error'].fillna('') == '']
    metrics['value'] = pd.to_numeric(metrics['value'], errors='coerce')

    agg = metrics.groupby(['run_id', 'rf', 'ratio', 'metric'], as_index=False).agg(value_avg=('value', 'mean'), value_max=('value', 'max'))
    merged = runs.merge(agg[agg['metric'] == 'sql.service.latency-p90'][['run_id', 'value_avg']].rename(columns={'value_avg': 'sql_p90_avg'}), on='run_id', how='left')
    merged = merged.merge(agg[agg['metric'] == 'exec.latency-p90'][['run_id', 'value_avg']].rename(columns={'value_avg': 'kv_p90_avg'}), on='run_id', how='left')

    out_csv = results_dir / 'summary_metrics.csv'
    out_xlsx = results_dir / 'summary_metrics.xlsx'
    merged.to_csv(out_csv, index=False)
    merged.to_excel(out_xlsx, index=False)
    print(f'Wrote {out_csv} and {out_xlsx}')

    grouped = merged.groupby(['rf', 'ratio', 'read_mode'], as_index=False).agg(
        runs=('run_id', 'count'),
        qps_actual_mean=('qps_actual', 'mean'),
        qps_actual_std=('qps_actual', 'std'),
        reads_err_sum=('reads_err', 'sum'),
        writes_err_sum=('writes_err', 'sum'),
        sql_p90_avg_mean=('sql_p90_avg', 'mean'),
        sql_p90_avg_std=('sql_p90_avg', 'std'),
        kv_p90_avg_mean=('kv_p90_avg', 'mean'),
        kv_p90_avg_std=('kv_p90_avg', 'std'),
    )
    if 'connect_err' in merged.columns:
        connect_errors = merged.groupby(['rf', 'ratio', 'read_mode'], as_index=False).agg(connect_err_sum=('connect_err', 'sum'))
        grouped = grouped.merge(connect_errors, on=['rf', 'ratio', 'read_mode'], how='left')
    grouped_csv = results_dir / 'summary_grouped.csv'
    grouped_xlsx = results_dir / 'summary_grouped.xlsx'
    grouped.to_csv(grouped_csv, index=False)
    grouped.to_excel(grouped_xlsx, index=False)
    print(f'Wrote {grouped_csv} and {grouped_xlsx}')

    metric_grouped = agg.groupby(['rf', 'ratio', 'metric'], as_index=False).agg(
        samples=('value_avg', 'count'),
        value_avg_mean=('value_avg', 'mean'),
        value_avg_std=('value_avg', 'std'),
        value_max_mean=('value_max', 'mean'),
        value_max_std=('value_max', 'std'),
    )
    metric_grouped_csv = results_dir / 'summary_metrics_grouped.csv'
    metric_grouped_xlsx = results_dir / 'summary_metrics_grouped.xlsx'
    metric_grouped.to_csv(metric_grouped_csv, index=False)
    metric_grouped.to_excel(metric_grouped_xlsx, index=False)
    print(f'Wrote {metric_grouped_csv} and {metric_grouped_xlsx}')

    for ratio, df in merged.groupby('ratio'):
        df = df.sort_values('rf')
        safe_ratio = str(ratio).replace(':', '-')
        plt.figure()
        plt.plot(df['rf'], df['qps_actual'], marker='o')
        plt.xlabel('Replication factor')
        plt.ylabel('Actual QPS')
        plt.title(f'CockroachDB actual QPS, ratio={ratio}')
        plt.grid(True)
        plt.savefig(results_dir / f'plot_qps_ratio_{safe_ratio}.png', bbox_inches='tight')
        plt.close()

        if df['sql_p90_avg'].notna().any():
            plt.figure()
            plt.plot(df['rf'], df['sql_p90_avg'], marker='o')
            plt.xlabel('Replication factor')
            plt.ylabel('SQL p90 metric value')
            plt.title(f'CockroachDB SQL p90, ratio={ratio}')
            plt.grid(True)
            plt.savefig(results_dir / f'plot_sql_p90_ratio_{safe_ratio}.png', bbox_inches='tight')
            plt.close()

    print(f'Plots written to {results_dir}')


if __name__ == '__main__':
    main()
