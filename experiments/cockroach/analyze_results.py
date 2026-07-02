#!/usr/bin/env python3
import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


NATIVE_LATENCY_METRICS = {
    'sql.service.latency': 'native_sql_latency',
    'exec.latency': 'native_exec_latency',
}

COUNTER_METRICS = {
    'sql.select.count': 'native_select_count',
    'sql.insert.count': 'native_insert_count',
    'sql.update.count': 'native_update_count',
    'sql.delete.count': 'native_delete_count',
}


def resolve_result_file(results_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.exists():
        return path
    candidate = results_dir / path
    if candidate.exists():
        return candidate
    return path


def bucket_upper_bound(value) -> float:
    text = str(value)
    if text in ('+Inf', 'inf', 'Infinity'):
        return math.inf
    return float(text)


def histogram_quantile(cumulative_buckets, quantile):
    """Prometheus-style interpolation over cumulative classic buckets."""
    if not cumulative_buckets:
        return math.nan
    buckets = sorted(cumulative_buckets, key=lambda item: item[0])
    monotonic = []
    previous = 0.0
    for upper, count in buckets:
        count = max(float(count), previous)
        monotonic.append((upper, count))
        previous = count

    total = monotonic[-1][1]
    if total <= 0:
        return math.nan
    rank = quantile * total
    previous_upper = 0.0
    previous_count = 0.0
    for upper, count in monotonic:
        if count < rank:
            previous_upper = upper
            previous_count = count
            continue
        if math.isinf(upper):
            return previous_upper
        bucket_count = count - previous_count
        if bucket_count <= 0:
            return upper
        fraction = (rank - previous_count) / bucket_count
        return previous_upper + (upper - previous_upper) * fraction
    return monotonic[-1][0]


def series_delta(frame):
    ordered = frame.sort_values('timestamp')
    values = pd.to_numeric(ordered['value'], errors='coerce').dropna()
    if len(values) < 2:
        return math.nan
    delta = float(values.iloc[-1] - values.iloc[0])
    return delta if delta >= 0 else math.nan


def histogram_delta_quantiles(metrics, metric_name):
    subset = metrics[
        (metrics['metric'] == metric_name)
        & (metrics['sample_type'] == 'histogram_bucket')
    ].copy()
    if subset.empty:
        return math.nan, math.nan

    combined = {}
    for (_, le), group in subset.groupby(['node_id', 'le'], dropna=False):
        delta = series_delta(group)
        if math.isnan(delta):
            continue
        upper = bucket_upper_bound(le)
        combined[upper] = combined.get(upper, 0.0) + delta
    buckets = list(combined.items())
    return histogram_quantile(buckets, 0.90), histogram_quantile(buckets, 0.99)


def counter_delta(metrics, metric_name):
    subset = metrics[
        (metrics['metric'] == metric_name)
        & (metrics['sample_type'] == 'counter')
    ]
    if subset.empty:
        return math.nan
    deltas = []
    for _, group in subset.groupby('node_id'):
        delta = series_delta(group)
        if not math.isnan(delta):
            deltas.append(delta)
    return sum(deltas) if deltas else math.nan


def summarize_metrics_file(path: Path, duration_s: float):
    summary = {
        'metrics_mode': 'missing',
        'metrics_node_count': 0,
        'metrics_error_rows': 0,
    }
    if not path.exists():
        return summary

    metrics = pd.read_csv(path)
    summary['metrics_error_rows'] = int(metrics.get('error', pd.Series(dtype=str)).fillna('').ne('').sum())
    if 'node_id' in metrics:
        summary['metrics_node_count'] = int(pd.to_numeric(metrics['node_id'], errors='coerce').dropna().nunique())

    if not {'sample_type', 'le'}.issubset(metrics.columns):
        summary['metrics_mode'] = 'legacy_single_node_cumulative_quantiles'
        return summary

    metrics = metrics[metrics['error'].fillna('') == ''].copy()
    metrics['timestamp'] = pd.to_numeric(metrics['timestamp'], errors='coerce')
    metrics['value'] = pd.to_numeric(metrics['value'], errors='coerce')
    summary['metrics_mode'] = 'raw_histogram_deltas'

    for metric_name, prefix in NATIVE_LATENCY_METRICS.items():
        p90_ns, p99_ns = histogram_delta_quantiles(metrics, metric_name)
        summary[f'{prefix}_p90_ms'] = p90_ns / 1_000_000.0
        summary[f'{prefix}_p99_ms'] = p99_ns / 1_000_000.0

    for metric_name, prefix in COUNTER_METRICS.items():
        delta = counter_delta(metrics, metric_name)
        summary[f'{prefix}_delta'] = delta
        summary[f'{prefix}_rate'] = delta / duration_s if duration_s > 0 and not math.isnan(delta) else math.nan

    rss = metrics[
        (metrics['metric'] == 'sys.rss')
        & (metrics['sample_type'] == 'gauge')
    ]['value'].dropna()
    summary['native_rss_mean_mb'] = rss.mean() / (1024.0 * 1024.0) if not rss.empty else math.nan
    summary['native_rss_max_mb'] = rss.max() / (1024.0 * 1024.0) if not rss.empty else math.nan
    return summary


def add_mean_std_aggregations(aggregations, columns):
    for column in columns:
        aggregations[f'{column}_mean'] = (column, 'mean')
        aggregations[f'{column}_std'] = (column, 'std')


def plot_grouped(grouped, out_path, mean_column, std_column, ylabel, title):
    if mean_column not in grouped or grouped[mean_column].notna().sum() == 0:
        return
    plt.figure(figsize=(7.2, 4.2))
    for ratio, frame in grouped.groupby('ratio'):
        frame = frame.sort_values('rf')
        plt.errorbar(
            frame['rf'],
            frame[mean_column],
            yerr=frame[std_column].fillna(0),
            marker='o',
            capsize=4,
            linewidth=1.8,
            label=f'ratio {ratio}',
        )
    plt.xticks(sorted(grouped['rf'].unique()))
    plt.xlabel('Replication factor')
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--results-dir', required=True)
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    runs_path = results_dir / 'runs.csv'
    if not runs_path.exists():
        raise FileNotFoundError(runs_path)

    runs = pd.read_csv(runs_path)
    metric_summaries = []
    for _, run in runs.iterrows():
        metrics_path = resolve_result_file(results_dir, run['metrics_file'])
        summary = {'run_id': run['run_id']}
        summary.update(summarize_metrics_file(metrics_path, float(run.get('duration', 0) or 0)))
        metric_summaries.append(summary)

    merged = runs.merge(pd.DataFrame(metric_summaries), on='run_id', how='left')
    out_csv = results_dir / 'summary_metrics.csv'
    out_xlsx = results_dir / 'summary_metrics.xlsx'
    merged.to_csv(out_csv, index=False)
    merged.to_excel(out_xlsx, index=False)
    print(f'Wrote {out_csv} and {out_xlsx}')

    aggregations = {
        'runs': ('run_id', 'count'),
        'qps_actual_mean': ('qps_actual', 'mean'),
        'qps_actual_std': ('qps_actual', 'std'),
        'reads_err_sum': ('reads_err', 'sum'),
        'writes_err_sum': ('writes_err', 'sum'),
        'native_metrics_runs': ('metrics_mode', lambda values: int((values == 'raw_histogram_deltas').sum())),
        'legacy_metrics_runs': ('metrics_mode', lambda values: int((values == 'legacy_single_node_cumulative_quantiles').sum())),
        'metrics_error_rows_sum': ('metrics_error_rows', 'sum'),
    }
    if 'connect_err' in merged:
        aggregations['connect_err_sum'] = ('connect_err', 'sum')

    result_columns = [
        'read_latency_ms_p90',
        'read_latency_ms_p99',
        'write_latency_ms_p90',
        'write_latency_ms_p99',
        'native_sql_latency_p90_ms',
        'native_sql_latency_p99_ms',
        'native_exec_latency_p90_ms',
        'native_exec_latency_p99_ms',
        'native_select_count_rate',
        'native_insert_count_rate',
        'native_rss_mean_mb',
    ]
    add_mean_std_aggregations(aggregations, [column for column in result_columns if column in merged])

    grouped = merged.groupby(['rf', 'ratio', 'read_mode'], as_index=False).agg(**aggregations)
    grouped_csv = results_dir / 'summary_grouped.csv'
    grouped_xlsx = results_dir / 'summary_grouped.xlsx'
    grouped.to_csv(grouped_csv, index=False)
    grouped.to_excel(grouped_xlsx, index=False)
    print(f'Wrote {grouped_csv} and {grouped_xlsx}')

    metric_columns = [column for column in result_columns if column in merged]
    if metric_columns:
        long_metrics = merged.melt(
            id_vars=['run_id', 'rf', 'ratio'],
            value_vars=metric_columns,
            var_name='metric',
            value_name='value',
        ).dropna(subset=['value'])
        metric_grouped = long_metrics.groupby(['rf', 'ratio', 'metric'], as_index=False).agg(
            samples=('value', 'count'),
            value_mean=('value', 'mean'),
            value_std=('value', 'std'),
        )
    else:
        metric_grouped = pd.DataFrame(columns=['rf', 'ratio', 'metric', 'samples', 'value_mean', 'value_std'])

    metric_grouped_csv = results_dir / 'summary_metrics_grouped.csv'
    metric_grouped_xlsx = results_dir / 'summary_metrics_grouped.xlsx'
    metric_grouped.to_csv(metric_grouped_csv, index=False)
    metric_grouped.to_excel(metric_grouped_xlsx, index=False)
    print(f'Wrote {metric_grouped_csv} and {metric_grouped_xlsx}')

    plot_grouped(
        grouped,
        results_dir / 'plot_qps.png',
        'qps_actual_mean',
        'qps_actual_std',
        'Actual throughput [QPS]',
        'CockroachDB target attainment',
    )
    plot_grouped(
        grouped,
        results_dir / 'plot_client_read_p90.png',
        'read_latency_ms_p90_mean',
        'read_latency_ms_p90_std',
        'Client read latency p90 [ms]',
        'CockroachDB client-observed read latency',
    )
    plot_grouped(
        grouped,
        results_dir / 'plot_native_sql_p90.png',
        'native_sql_latency_p90_ms_mean',
        'native_sql_latency_p90_ms_std',
        'Native SQL service latency p90 [ms]',
        'CockroachDB native SQL service latency',
    )
    print(f'Plots written to {results_dir}')


if __name__ == '__main__':
    main()
