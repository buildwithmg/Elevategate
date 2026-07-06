#!/bin/sh
set -e

# Single-instance MVP assumption: running this on every container start is safe for a single
# backend replica, but a multi-replica deployment behind a load balancer should run migrations
# as one dedicated release step instead of letting every replica race to run them concurrently.
# See docs/BACKEND_THREAT_MODEL.md and backend/README.md.
echo "Running database migrations..."
alembic upgrade head

exec "$@"
