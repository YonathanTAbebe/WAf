# waf_feature_extractor.py
# Extracts features from logged requests for ML model training
import json
import pandas as pd
import re

def extract_features(log_file="waf_requests.log", out_csv="waf_features.csv"):
    # Signature lists
    SQLI_SIGNATURES = ["select", "union", "drop", "insert", "update", "delete", "or 1=1", "'--", ";--", "' or", '" or']
    XSS_SIGNATURES = ["<script", "onerror", "onload", "<img", "<iframe", "<svg", "<a href"]
    DIR_TRAV_SIGNATURES = ["../", "..%2f", "..%5c", "..\\.", "..\\"]
    CMD_INJ_SIGNATURES = ["ls", "cat", "whoami", "pwd", "ping", "nc", "sh", "bash", "cmd.exe"]
    LFI_SIGNATURES = ["/etc/passwd", "/etc/password", "/etc/shadow", "/etc/hosts", "/proc/self/cmdline", "c:\\boot.ini", "c:\\windows\\win.ini", "file://", "php://filter"]
    HTTP_SPLIT_SIGNATURES = ["\n", "\r", "\r\n", "admin"]

    features = []
    with open(log_file) as f:
        for line in f:
            entry = json.loads(line)
            path = entry["path"]
            body = entry["body"]
            headers = entry["headers"]
            content = (path + body).lower()
            # Signature-based labeling
            is_malicious = (
                any(sig in content for sig in SQLI_SIGNATURES)
                or any(sig in content for sig in XSS_SIGNATURES)
                or any(sig in content for sig in DIR_TRAV_SIGNATURES)
                or any(sig in content for sig in CMD_INJ_SIGNATURES)
                or any(sig in content for sig in LFI_SIGNATURES)
                or any(sig in content for sig in HTTP_SPLIT_SIGNATURES)
                or headers.get("User-Agent", "").lower() == "sqlmap"
            )
            label = 1 if is_malicious else 0
            features.append({
                "length": len(path) + len(body),
                "num_special": len(re.findall(r"[\W]", path + body)),
                "num_digits": len(re.findall(r"\d", path + body)),
                "has_sql_keywords": int(any(kw in content for kw in ["select", "union", "drop", "insert", "update", "delete"])),
                "user_agent": headers.get("User-Agent", ""),
                "client_ip": entry["client_ip"],
                "method": entry["method"],
                "timestamp": entry["timestamp"],
                "label": label
            })
    df = pd.DataFrame(features)
    df.to_csv(out_csv, index=False)

if __name__ == "__main__":
    extract_features()
