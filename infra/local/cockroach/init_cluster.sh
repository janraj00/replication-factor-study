#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for CockroachDB process..."
until docker compose exec -T crdb1 /cockroach/cockroach init --insecure --host=crdb1:26257 >/tmp/crdb-init.out 2>&1; do
  if grep -qi "already initialized" /tmp/crdb-init.out; then
    break
  fi
  sleep 2
done

cat /tmp/crdb-init.out

echo "Waiting for CockroachDB SQL..."
until docker compose exec -T crdb1 /cockroach/cockroach sql --insecure --host=crdb1:26257 -e "select 1" >/dev/null 2>&1; do
  sleep 2
done

echo "Node status:"
docker compose exec -T crdb1 /cockroach/cockroach node status --insecure --host=crdb1:26257
