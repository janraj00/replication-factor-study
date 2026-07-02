import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from experiments.cockroach.analyze_results import summarize_metrics_file
from experiments.cockroach.crdb_common import fetch_node_metric_samples
from experiments.cockroach.load_workload import percentile


class CockroachMetricsTests(unittest.TestCase):
    def test_client_percentile_interpolates(self):
        self.assertAlmostEqual(percentile([1.0, 2.0, 3.0, 4.0], 0.90), 3.7)
        self.assertIsNone(percentile([], 0.90))

    def test_raw_histograms_use_per_run_deltas_across_nodes(self):
        rows = []
        for node_id, start_counts, end_counts in (
            (1, [100, 200, 200], [102, 205, 205]),
            (2, [300, 400, 400], [303, 405, 405]),
        ):
            for timestamp, counts in ((0.0, start_counts), (10.0, end_counts)):
                for le, value in zip(('10000000', '20000000', '+Inf'), counts):
                    rows.append({
                        'timestamp': timestamp,
                        'run_id': 'test',
                        'rf': 3,
                        'ratio': '50:50',
                        'node_id': node_id,
                        'metric': 'sql.service.latency',
                        'sample_type': 'histogram_bucket',
                        'le': le,
                        'value': value,
                        'error': '',
                    })
            for timestamp, value in ((0.0, 10 * node_id), (10.0, 10 * node_id + (4 if node_id == 1 else 6))):
                rows.append({
                    'timestamp': timestamp,
                    'run_id': 'test',
                    'rf': 3,
                    'ratio': '50:50',
                    'node_id': node_id,
                    'metric': 'sql.select.count',
                    'sample_type': 'counter',
                    'le': '',
                    'value': value,
                    'error': '',
                })

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'metrics.csv'
            pd.DataFrame(rows).to_csv(path, index=False)
            summary = summarize_metrics_file(path, duration_s=10.0)

        self.assertEqual(summary['metrics_mode'], 'raw_histogram_deltas')
        self.assertEqual(summary['metrics_node_count'], 2)
        self.assertAlmostEqual(summary['native_sql_latency_p90_ms'], 18.0)
        self.assertAlmostEqual(summary['native_sql_latency_p99_ms'], 19.8)
        self.assertAlmostEqual(summary['native_select_count_delta'], 10.0)
        self.assertAlmostEqual(summary['native_select_count_rate'], 1.0)

    def test_collector_keeps_raw_buckets_instead_of_cumulative_quantiles(self):
        prometheus = {
            'sql_service_latency_bucket': [
                {'labels': {'node_id': '2', 'le': '10000000'}, 'value': 12.0},
                {'labels': {'node_id': '2', 'le': '+Inf'}, 'value': 20.0},
            ],
            'sql_select_count': [
                {'labels': {'node_id': '2'}, 'value': 123.0},
            ],
        }
        with patch(
            'experiments.cockroach.crdb_common._fetch_prometheus_metrics',
            return_value=prometheus,
        ):
            rows = fetch_node_metric_samples(
                ['sql.service.latency', 'sql.select.count'],
                node_id=2,
            )

        bucket_rows = [row for row in rows if row['sample_type'] == 'histogram_bucket']
        self.assertEqual([row['le'] for row in bucket_rows], ['10000000', '+Inf'])
        self.assertEqual(bucket_rows[0]['name'], 'sql.service.latency')
        counter = next(row for row in rows if row['sample_type'] == 'counter')
        self.assertEqual(counter['value'], 123.0)

    def test_legacy_quantile_snapshots_are_not_reported_as_per_run_latency(self):
        rows = [{
            'timestamp': 0.0,
            'run_id': 'legacy',
            'rf': 3,
            'ratio': '100:0',
            'node_id': 1,
            'metric': 'sql.service.latency-p90',
            'value': 1000000,
            'error': '',
        }]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'metrics.csv'
            pd.DataFrame(rows).to_csv(path, index=False)
            summary = summarize_metrics_file(path, duration_s=10.0)

        self.assertEqual(summary['metrics_mode'], 'legacy_single_node_cumulative_quantiles')
        self.assertNotIn('native_sql_latency_p90_ms', summary)


if __name__ == '__main__':
    unittest.main()
