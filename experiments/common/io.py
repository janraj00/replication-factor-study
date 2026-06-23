import csv
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping


def ensure_dir(path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path, obj) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding='utf-8')


def append_csv(path, row: Mapping) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    exists = path.exists()
    with path.open('a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def _run_text(cmd, cwd: Path) -> str:
    try:
        return subprocess.check_output(cmd, cwd=str(cwd), text=True, stderr=subprocess.STDOUT).strip()
    except Exception as e:
        return f'unavailable: {type(e).__name__}: {e}'


def experiment_metadata(kind: str, args, repo_root: Path) -> dict:
    env_keys = [
        'CRDB_HOST',
        'CRDB_USER',
        'CRDB_DB',
        'CRDB_SSLMODE',
        'CRDB_TABLE',
        'HADOOP_CONF_DIR',
        'DOCKER_HOST',
        'COMPOSE_PROJECT_NAME',
    ]
    return {
        'kind': kind,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'command_line': sys.argv,
        'python': {
            'version': sys.version,
            'executable': sys.executable,
        },
        'platform': {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
        },
        'working_directory': str(Path.cwd()),
        'repo_root': str(repo_root),
        'environment': {k: os.environ.get(k, '') for k in env_keys if k in os.environ},
        'parameters': vars(args),
        'git': {
            'commit': _run_text(['git', 'rev-parse', 'HEAD'], repo_root),
            'status_short': _run_text(['git', 'status', '--short'], repo_root),
        },
    }


def write_experiment_metadata(results_dir, kind: str, args, repo_root: Path) -> Path:
    path = Path(results_dir) / 'metadata.json'
    write_json(path, experiment_metadata(kind, args, repo_root))
    return path
