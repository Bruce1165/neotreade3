# NeoTrade3 Tests

This directory will hold unit, integration, and smoke tests for NeoTrade3.

Current CI baseline is intentionally conservative:

- supported Python: `3.10.x`
- backend: `./.venv/bin/python -m pytest tests -q`
- frontend: `cd neotrade3-dashboard && npm run lint && npm run test && npm run build`

Not yet part of the required baseline:

- broader backend integration/e2e coverage beyond the current `tests/integration/test_http_smoke.py` coverage of `healthz`, stored `bootstrap-summary`, and the `orchestration` POST/detail/download round trip, because the repository still only has a small automated backend integration surface
- broader frontend component/page coverage beyond the current `src/services/api.test.js`, `src/components/DateSelector.test.jsx`, `src/pages/StockCheck.test.jsx`, `src/pages/Overview.test.jsx`, `src/pages/Screeners.test.jsx`, and `src/pages/Lowfreq.test.jsx`, because the repository still only has a minimal frontend automated test surface
