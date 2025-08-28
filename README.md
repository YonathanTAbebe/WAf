 WAF Project README

## Overview
This project implements a Web Application Firewall (WAF) system with machine learning, logging, and a FastAPI dashboard for monitoring and analysis.

## Main Components
- **waf.py**: Core WAF logic for request filtering and blocking.
- **waf_feature_extractor.py**: Extracts features from requests for ML model training.
- **train_waf_model.py**: Trains the ML model and generates `waf_model.joblib` and `classification_report.txt`.
- **waf_dashboard.py**: FastAPI dashboard to visualize request stats and model metrics.
- **waf_request_logger.py**: Logs all incoming requests and their WAF status to `waf_requests.log`.
- **waf_signature_suggest.py**: Suggests new WAF signatures based on request patterns.

## Data & Model Files
- **waf_features.csv**: Extracted features and labels for ML training/testing.
- **waf_model.joblib**: Trained ML model for WAF decisions.
- **classification_report.txt**: Model performance metrics (precision, recall, F1-score, support).
- **waf_requests.log**: Log of all processed requests and their WAF status.
- **waf_blocked.log**: Log of blocked requests for auditing.

## Usage
1. **Extract Features**: Run `waf_feature_extractor.py` to generate `waf_features.csv`.
2. **Train Model**: Run `train_waf_model.py` to train the ML model and generate metrics.
3. **Run WAF**: Use `waf.py` to start the WAF and process requests.
4. **View Dashboard**: Run `waf_dashboard.py` and open [http://localhost:8051](http://localhost:8051) in your browser.
5. **Review Logs**: Check `waf_requests.log` and `waf_blocked.log` for request history and blocked events.

## Customization
- Update feature extraction, model training, or dashboard code to fit your application.
- Retrain the model as needed and update `classification_report.txt` for new metrics.

## Requirements
- Python 3.7+
- FastAPI, pandas, scikit-learn, uvicorn, joblib

## Security Note
- Regularly review blocked requests and update WAF signatures for best protection.

---
For more details, see comments in each file or contact the project maintainer.
