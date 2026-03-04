#!/usr/bin/env bash
set -euo pipefail

AUTO_BUILD_VALUE="${AUTO_BUILD_WAREHOUSE:-true}"
AUTO_BUILD_VALUE="$(printf '%s' "${AUTO_BUILD_VALUE}" | tr '[:upper:]' '[:lower:]')"

if [[ "${AUTO_BUILD_VALUE}" == "1" || "${AUTO_BUILD_VALUE}" == "true" || "${AUTO_BUILD_VALUE}" == "yes" ]]; then
  echo "[startup] Building warehouse before starting Streamlit..."
  python -m src.warehouse --build --drop-invalid-purchases-rows
else
  echo "[startup] AUTO_BUILD_WAREHOUSE disabled, skipping warehouse build."
fi

PORT_VALUE="${PORT:-8501}"
echo "[startup] Launching Streamlit on 0.0.0.0:${PORT_VALUE}"

exec streamlit run app/streamlit_app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT_VALUE}" \
  --server.headless=true
