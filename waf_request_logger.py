# waf_request_logger.py
# Logs all incoming WAF requests for ML analysis
import datetime
import json
import threading

def log_request(client_ip, method, path, headers, body):
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "client_ip": client_ip,
        "method": method,
        "path": path,
        "headers": dict(headers),
        "body": body
    }
    with threading.Lock():
        with open("waf_requests.log", "a") as f:
            f.write(json.dumps(log_entry) + "\n")
