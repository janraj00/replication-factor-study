#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for HDFS..."
until docker compose exec -T hdfs-client hdfs dfsadmin -safemode get >/dev/null 2>&1; do
  sleep 2
done

docker compose exec -T hdfs-client hdfs dfsadmin -safemode wait || true
docker compose exec -T hdfs-client hdfs dfs -mkdir -p /bench || true
docker compose exec -T hdfs-client hdfs dfsadmin -report
