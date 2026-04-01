#!/usr/bin/env bash
# Initialize stockscan database, user, and grants
# Run as: bash scripts/init_db.sh
# Requires superuser (zyzbot) access to PostgreSQL

set -euo pipefail

PSQL="/Applications/Postgres.app/Contents/Versions/16/bin/psql"
DB_USER="stockscan_user"
DB_PASS="stockscan_pass"
DB_NAME="stockscan"
STOCKDB="stockdb"

echo "=== Creating stockscan_user and stockscan database ==="
$PSQL -U zyzbot -d postgres <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASS}';
    RAISE NOTICE 'Created role ${DB_USER}';
  ELSE
    ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASS}';
    RAISE NOTICE 'Role ${DB_USER} already exists, password updated';
  END IF;
END
\$\$;
SQL

$PSQL -U zyzbot -d postgres -c "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
  $PSQL -U zyzbot -d postgres -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER} TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE='C' LC_CTYPE='C';"

echo "=== Granting stockscan_user access to stockscan ==="
$PSQL -U zyzbot -d ${DB_NAME} <<SQL
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
GRANT ALL PRIVILEGES ON SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DB_USER};
SQL

echo "=== Granting stockscan_user READ-ONLY access to stockdb ==="
$PSQL -U zyzbot -d ${STOCKDB} <<SQL
GRANT CONNECT ON DATABASE ${STOCKDB} TO ${DB_USER};
GRANT USAGE ON SCHEMA public TO ${DB_USER};
GRANT SELECT ON
  daily_price,
  adj_factor,
  daily_fundamental,
  money_flow,
  stock_basic,
  trade_calendar,
  top_list,
  margin_detail,
  block_trade,
  limit_list,
  index_daily,
  index_basic
TO ${DB_USER};
SQL

echo "=== Done! ==="
echo "DB: ${DB_NAME}, User: ${DB_USER}"
echo "You can connect with: psql -U ${DB_USER} -d ${DB_NAME}"
