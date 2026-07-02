import os
import re
import time
from typing import Dict, List
from urllib.request import urlopen

import psycopg2
import psycopg2.extras

NODE_PORTS: Dict[int, int] = {
    1: 26257,
    2: 26261,
    3: 26264,
    4: 26265,
    5: 26259,
    6: 26262,
    7: 26258,
    8: 26263,
    9: 26260,
}

HTTP_PORTS: Dict[int, int] = {
    1: 8080,
    2: 8081,
    3: 8082,
    4: 8083,
    5: 8084,
    6: 8085,
    7: 8086,
    8: 8087,
    9: 8088,
}

DB_HOST = os.environ.get('CRDB_HOST', '127.0.0.1')
DB_USER = os.environ.get('CRDB_USER', 'root')
DB_NAME = os.environ.get('CRDB_DB', 'defaultdb')
SSL_MODE = os.environ.get('CRDB_SSLMODE', 'disable')
TABLE = os.environ.get('CRDB_TABLE', 'public.users')

DIRECT_METRICS = {
    'sql.select.count': ('sql_select_count', 'counter'),
    'sql.insert.count': ('sql_insert_count', 'counter'),
    'sql.update.count': ('sql_update_count', 'counter'),
    'sql.delete.count': ('sql_delete_count', 'counter'),
    'sys.rss': ('sys_rss', 'gauge'),
}

HISTOGRAM_METRICS = {
    'sql.service.latency': 'sql_service_latency',
    'exec.latency': 'exec_latency',
}

LEGACY_HISTOGRAM_ALIASES = {
    'sql.service.latency-p90': 'sql.service.latency',
    'sql.service.latency-p99': 'sql.service.latency',
    'exec.latency-p90': 'exec.latency',
    'exec.latency-p99': 'exec.latency',
}


def dsn(node_id: int = 1, app: str = 'rf_study') -> str:
    return (
        f'postgresql://{DB_USER}@{DB_HOST}:{NODE_PORTS[node_id]}/{DB_NAME}'
        f'?sslmode={SSL_MODE}&application_name={app}'
    )


def connect(node_id: int = 1, app: str = 'rf_study', follower: bool = False):
    conn = psycopg2.connect(dsn(node_id, app=app))
    conn.set_session(autocommit=True)
    if follower:
        with conn.cursor() as cur:
            try:
                cur.execute('SET default_transaction_use_follower_reads = true')
            except Exception:
                pass
    return conn


def parse_list(s: str, cast=str):
    if not s:
        return []
    return [cast(x.strip()) for x in s.split(',') if x.strip()]


def wait_for_sql(node_id: int = 1, timeout_s: int = 120) -> None:
    t0 = time.time()
    while True:
        try:
            conn = connect(node_id, 'wait')
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
            conn.close()
            return
        except Exception as e:
            if time.time() - t0 > timeout_s:
                raise TimeoutError(f'CockroachDB not ready after {timeout_s}s: {e}') from e
            time.sleep(2)


def _parse_prometheus_metrics(text: str) -> Dict[str, List[dict]]:
    metrics: Dict[str, List[dict]] = {}
    line_re = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+([-+0-9.eE]+)$')
    label_re = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"')
    for line in text.splitlines():
        match = line_re.match(line)
        if not match:
            continue
        name, labels_text, value = match.groups()
        labels = dict(label_re.findall(labels_text or ''))
        metrics.setdefault(name, []).append({'labels': labels, 'value': float(value)})
    return metrics


def _first_metric_value(metrics: Dict[str, List[dict]], prometheus_name: str, node_id: int) -> float:
    samples = metrics.get(prometheus_name, [])
    for sample in samples:
        labels = sample['labels']
        if labels.get('node_id') in ('', str(node_id)):
            return sample['value']
    if samples:
        return samples[0]['value']
    raise KeyError(prometheus_name)


def _sample_node_id(sample: dict, endpoint_id: int):
    value = sample.get('labels', {}).get('node_id')
    if value in ('', None):
        return endpoint_id
    try:
        return int(value)
    except ValueError:
        return value


def _histogram_quantile(metrics: Dict[str, List[dict]], prometheus_name: str, node_id: int, quantile: float) -> float:
    bucket_name = f'{prometheus_name}_bucket'
    buckets = []
    for sample in metrics.get(bucket_name, []):
        labels = sample['labels']
        if labels.get('node_id') != str(node_id):
            continue
        le = labels.get('le')
        if le is None:
            continue
        upper = float('inf') if le == '+Inf' else float(le)
        buckets.append((upper, sample['value']))
    if not buckets:
        raise KeyError(bucket_name)
    buckets.sort(key=lambda item: item[0])
    total = buckets[-1][1]
    if total <= 0:
        return 0.0
    target = total * quantile
    for upper, cumulative_count in buckets:
        if cumulative_count >= target:
            return upper
    return buckets[-1][0]


def _fetch_prometheus_metrics(node_id: int) -> Dict[str, List[dict]]:
    url = f'http://{DB_HOST}:{HTTP_PORTS[node_id]}/_status/vars'
    text = urlopen(url, timeout=10).read().decode('utf-8')
    return _parse_prometheus_metrics(text)


def fetch_node_metric_samples(metric_names: List[str], node_id: int = 1) -> List[dict]:
    """Return raw counter/gauge values and cumulative histogram buckets.

    Histogram buckets must be differenced between the beginning and end of a
    benchmark run before quantiles are calculated.
    """
    metrics = _fetch_prometheus_metrics(node_id)
    rows = []
    seen_histograms = set()
    for requested_name in metric_names:
        metric_name = LEGACY_HISTOGRAM_ALIASES.get(requested_name, requested_name)
        if metric_name in DIRECT_METRICS:
            prometheus_name, sample_type = DIRECT_METRICS[metric_name]
            samples = metrics.get(prometheus_name, [])
            if not samples:
                continue
            sample = next(
                (
                    item
                    for item in samples
                    if item['labels'].get('node_id') in ('', str(node_id))
                ),
                samples[0],
            )
            rows.append({
                'node_id': _sample_node_id(sample, node_id),
                'name': metric_name,
                'sample_type': sample_type,
                'le': '',
                'value': sample['value'],
            })
            continue

        if metric_name in HISTOGRAM_METRICS and metric_name not in seen_histograms:
            seen_histograms.add(metric_name)
            bucket_name = f'{HISTOGRAM_METRICS[metric_name]}_bucket'
            for sample in metrics.get(bucket_name, []):
                labels = sample['labels']
                le = labels.get('le')
                if le is None:
                    continue
                rows.append({
                    'node_id': _sample_node_id(sample, node_id),
                    'name': metric_name,
                    'sample_type': 'histogram_bucket',
                    'le': le,
                    'value': sample['value'],
                })
    return rows


def fetch_node_metrics(metric_names: List[str], node_id: int = 1) -> List[dict]:
    """Legacy helper returning instantaneous values or cumulative quantiles."""
    metrics = _fetch_prometheus_metrics(node_id)
    rows = []
    histogram_names = {
        'sql.service.latency-p90': ('sql_service_latency', 0.90),
        'sql.service.latency-p99': ('sql_service_latency', 0.99),
        'exec.latency-p90': ('exec_latency', 0.90),
        'exec.latency-p99': ('exec_latency', 0.99),
    }
    for metric_name in metric_names:
        try:
            if metric_name in DIRECT_METRICS:
                value = _first_metric_value(metrics, DIRECT_METRICS[metric_name][0], node_id)
            elif metric_name in histogram_names:
                prometheus_name, quantile = histogram_names[metric_name]
                value = _histogram_quantile(metrics, prometheus_name, node_id, quantile)
            else:
                prometheus_name = metric_name.replace('.', '_').replace('-', '_')
                value = _first_metric_value(metrics, prometheus_name, node_id)
            rows.append({'node_id': node_id, 'name': metric_name, 'value': value})
        except KeyError:
            continue
    return rows


def fetch_ranges(node_id: int = 1) -> List[dict]:
    conn = connect(node_id, 'show_ranges')
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f'SHOW RANGES FROM TABLE {TABLE} WITH DETAILS')
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
