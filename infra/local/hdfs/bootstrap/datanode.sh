#!/usr/bin/env bash
set -euo pipefail

mkdir -p /hadoop/dfs/data
exec hdfs datanode
