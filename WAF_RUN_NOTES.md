# How to Run Your WAF (Web Application Firewall)

## 1. Activate the Python Virtual Environment
```
source venv/bin/activate
```

## 2. Extract Features from Log File
This step parses `waf_requests.log` and generates `waf_features.csv` for model training and prediction.
```
python waf_feature_extractor.py
```

## 3. Train or Retrain the WAF Model
This uses the features in `waf_features.csv` to train the ML model and save it as `waf_model.joblib`.
```
python train_waf_model.py
```

## 4. Predict/Check if Requests are Blocked
To check which requests are blocked or allowed, run:
```
python waf_feature_extractor.py --predict waf_requests.log
python train_waf_model.py --predict waf_features.csv
```

## 5. Review Results
- Blocked requests will have label `1` (malicious).
- Allowed requests will have label `0` (benign).

## 6. (Optional) Update Model
- Add new log entries to `waf_requests.log`.
- Repeat steps 2 and 3 to retrain the model with new data.

---
# WAF Run Notes

## Overview
Quick reference for running the local WAF reverse-proxy, optional GeoIP blocking, and optional ML model. Includes commands to start a simple backend and test protections (double-extension, signatures, GeoIP).

## Requirements
- Python 3.8+
- Optional packages (for GeoIP and ML):
  - geoip2 (for GeoIP blocking)
  - joblib, scikit-learn (for ML model prediction)

Install recommended packages:

```bash
pip install geoip2 joblib scikit-learn
```

If you will not use GeoIP or ML features, you can skip installing `geoip2` and/or `joblib`/`scikit-learn` and run with flags to disable them.

## GeoIP database
If you want GeoIP blocking, download the GeoLite2 Country DB from MaxMind and place the `.mmdb` file in the project root (next to `waf.py`):

- Download via MaxMind account (GeoLite2-Country): https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
- Save the file as `GeoLite2-Country.mmdb` under `/home/yonathan/Desktop/waf.`

If the DB is missing, GeoIP checks are skipped automatically (the WAF will still run).

## Files of interest
- `waf.py` - WAF reverse proxy server (entry point).
- `waf_dashboard.py` - FastAPI dashboard (metrics, charts, recent requests).
- `waf_requests.log` - JSON lines log of recent requests (used by dashboard).
- `waf_blocked.log` - Log of blocked requests and reasons.
- `waf_model.joblib` - Optional trained ML model used by the WAF.

## Running a simple backend for testing
Run a simple HTTP server to act as the backend that the WAF forwards requests to:

```bash
cd /home/yonathan/Desktop/waf.
python3 -m http.server 8000 &
```

## Running the WAF
Usage:

```bash
# Normal run (attempts to load GeoIP DB and ML model if available)
python3 waf.py <backend_port>

# Disable GeoIP checks
python3 waf.py --no-geoip <backend_port>

# Disable ML model loading/prediction
python3 waf.py --no-ml <backend_port>

# Disable both GeoIP and ML
python3 waf.py --no-geoip --no-ml <backend_port>
```

Example (run with backend on port 8000, disabling GeoIP while testing):

```bash
python3 waf.py --no-geoip 8000
```

## Quick tests
- Forwarded request (should reach backend):

```bash
curl -v http://localhost:8050/
```

- Double-extension upload test (WAF should block):

```bash
curl -v "http://localhost:8050/uploads/image.jpg.php"
```

- SQLi / XSS signature test (example):

```bash
curl -v "http://localhost:8050/?q=1%27+OR+%271%27%3D%271"
```

- Check logs:

```bash
tail -n 100 waf_blocked.log
tail -n 100 waf_requests.log
```

## Notes
- If `GeoLite2-Country.mmdb` is present and `geoip2` is installed, WAF will attempt to map client IP -> country and block or allow based on the lists `BLOCKED_COUNTRIES` and `ALLOWED_COUNTRIES` configured in `waf.py`.
- If `waf_model.joblib` is present and ML loading is enabled, the WAF will call the model to get predictions and block requests predicted as malicious. To avoid unexpected blocking during testing, run with `--no-ml`.
- The WAF logs JSON lines to `waf_requests.log` for the dashboard and feature extraction. Keep an eye on file sizes in production.

## Troubleshooting
- `ImportError` for `geoip2` or `joblib` — install the missing packages or run with `--no-geoip`/`--no-ml`.
- If GeoIP download fails: download the `.mmdb` manually from MaxMind and place in project root.
- If requests are unexpectedly blocked by ML model, run with `--no-ml`, retrain model with more labeled data, or inspect `classification_report.txt`.

## Next steps / Recommended improvements
- Add a web UI to manage `ALLOWED_COUNTRIES` / `BLOCKED_COUNTRIES` live.
- Add a systemd service or supervisor config for running WAF in production.
- Rotate and archive logs or stream them to a centralized log pipeline.

---
Generated: {now}
