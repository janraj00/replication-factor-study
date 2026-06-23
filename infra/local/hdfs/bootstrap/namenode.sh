#!/usr/bin/env bash
set -euo pipefail

mkdir -p /hadoop/dfs/name
if [ ! -d /hadoop/dfs/name/current ]; then
  echo "Formatting NameNode..."
  hdfs namenode -format -force -nonInteractive
fi

exec hdfs namenode
