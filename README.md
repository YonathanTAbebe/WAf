# WAF Project

A compact local Web Application Firewall (WAF) demo with ML-assisted blocking, request logging, and a FastAPI dashboard.

## Overview
This repository contains a simple reverse-proxy WAF, tooling to extract features and train a classifier, and a dashboard to monitor requests and model performance.

## Quickstart (local development)
1. Create and activate a virtual environment (recommended):

   python3 -m venv venv
   source venv/bin/activate

2. Upgrade pip and install required packages:

   python -m pip install --upgrade pip setuptools wheel
   python -m pip install -r requirements.txt

   If you don't have `requirements.txt`, install the common packages used here:

   python -m pip install fastapi uvicorn pandas scikit-learn joblib geoip2 matplotlib seaborn chartjs-chart-geo

3. Run a demo backend (optional) to test the proxy, for example:

   python backend_demo.py

4. Start the WAF reverse proxy (point it to your backend port):

   python waf.py <backend_port>

   Flags:
   - `--no-geoip`  : skip GeoIP lookups
   - `--no-ml`     : disable ML model prediction

5. Start the dashboard (in the same venv):

   python -m uvicorn waf_dashboard:app --reload --port 8051

   Open: http://localhost:8051/

## Main files and purpose
- `waf.py` — reverse proxy WAF that inspects requests (signatures, rate-limit, optional ML blocking).
- `waf_request_logger.py` — helper to append JSON-lines to `waf_requests.log` used by the dashboard.
- `waf_feature_extractor.py` — create `waf_features.csv` from logged requests (for training).
- `train_waf_model.py` — train model and save `waf_model.joblib` and `classification_report.txt`.
- `waf_dashboard.py` — FastAPI dashboard with pages: `/` (overview), `/live` (SSE live view), `/countries` (Top Countries), and block/unblock APIs.
- `waf_requests.log` — JSON-lines of observed requests.
- `waf_blocked.log` — human-readable record of blocked events.
- `waf_model.joblib`, `classification_report.txt`, `reports/` — model and training artifacts.

## Dashboard endpoints (useful)
- `/` — main dashboard (KPIs, model metrics, recent requests).
- `/live` — live requests table (Server-Sent Events). Actions: Block/Unblock update `blocked_ips.json`.
- `/sse` — SSE stream used by `/live`.
- `/countries` — top-countries map (last 50 requests) with GeoIP fallback.
- `/blocked_ips` — GET current blocked IPs (JSON).
- `/block` — POST {"ip":"1.2.3.4"} to add to the persisted block list.
- `/unblock` — POST {"ip":"1.2.3.4"} to remove.

Note: The WAF can be configured to enforce `blocked_ips.json` (UI-driven blocks). See `waf.py` — this behavior may be enabled or disabled depending on the code version.

## GeoIP
To enable local GeoIP country lookups, download a GeoLite2 Country MMDB from MaxMind and place `GeoLite2-Country.mmdb` in the project root. The dashboard will fall back to a public geo API (cached) if the DB is missing.

Download example (requires MaxMind license key):

  mkdir -p ./geoip && \
  curl -L -o GeoLite2-Country.tar.gz "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-Country&license_key=YOUR_KEY&suffix=tar.gz" && \
  tar -xzf GeoLite2-Country.tar.gz --wildcards --strip-components=1 "*GeoLite2-Country.mmdb" -C . && \
  rm GeoLite2-Country.tar.gz

## Runtime files
- `blocked_ips.json` — persisted IPs from dashboard block actions (may be empty).
- `geoip_cache.json` — cache of IP -> country lookups when no MMDB is present.
- `waf_requests.log` / `waf_blocked.log` — runtime logs.

## Troubleshooting
- If the ML model fails to load with an sklearn version warning, either install the matching scikit-learn version used during training or retrain the model locally.
- If `pip` is restricted by system packaging (PEP 668), create a fresh virtualenv and use `venv/bin/python -m pip install ...`.
- If the dashboard shows `GeoIP available: false`, either provide the local MMDB (recommended) or allow the dashboard to use the API fallback.

## Security
- The block/unblock endpoints are not protected by default. Add authentication if exposing the dashboard on an untrusted network.
- Review `waf_blocked.log` and tune signature lists for your environment.

---
Contributions, improvements, and feature requests are welcome. Open an issue or submit a PR on the upstream repository.
