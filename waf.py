# waf.py
# This script contains a reverse proxy (WAF) that protects a backend server.

import http.server
import socketserver
import urllib.request
import urllib.parse
import threading
import datetime
import sys
import time
import re

# --- CONFIGURATION ---
WAF_PORT = 8050
BACKEND_PORT = None  # Will be set from argv

RATE_LIMIT = 60  # max requests per minute per IP
rate_limit_window = 60  # seconds
request_counts = {}
lock = threading.Lock()

BLOCKED_USER_AGENTS = [
    'sqlmap', 'curl', 'wget', 'nikto', 'fuzz', 'scanner', 'bot', 'python-requests'
]

LOG_FILE = 'waf_blocked.log'
def log_blocked(client_ip, reason, path, headers):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.datetime.now()}] BLOCKED {client_ip} Reason: {reason} Path: {path} Headers: {dict(headers)}\n")

SQL_INJECTION_SIGNATURE = [
    "' OR '1'='1",
    "UNION SELECT",
    "SELECT * FROM",
    "DROP TABLE",
    "DELETE FROM",
    "INSERT INTO",
    "UPDATE",
    "CAST(",
    "CHAR(",
    "CONVERT(",
    "INFORMATION_SCHEMA",
    "waitfor delay",
    "benchmark(",
    "sleep(",
    "pg_sleep(",
    "substring(",
    "ascii(",
    "1=1",
    "1=2",
    "OR 1=1",
    "AND 1=1",
    "--",
    "#",
    "'--",
    "'"
]
XSS_SIGNATURES = [
    "<script>",
    "javascript:",
    "onerror=",
    "onload=",
    "onmouseover=",
    "onfocus=",
    "onblur=",
    "onclick=",
    "onreadystatechange=",
    "onmousemove=",
    "alert(",
    "prompt(",
    "confirm(",
    "document.cookie",
    "document.domain",
    "eval(",
    "src=",
    "<img",
    "<img>",
    "<body",
    "<iframe",
    "<svg",
    "<a href"
]
DIRECTORY_TRAVERSAL_SIGNATURES = [
    "../",
    "..%2f",
    "..%5c",
    "..\\.",
    "..\\"
]
COMMAND_INJECTION_SIGNATURES = [
    "ls",
    "cat",
    "whoami",
    "pwd",
    "ping",
    "nc",
    "sh",
    "bash",
    "cmd.exe"
]
LFI_SIGNATURES = [
    "/etc/passwd",
    "/etc/password",
    "/etc/shadow",
    "/etc/hosts",
    "/proc/self/cmdline",
    "c:\\boot.ini",
    "c:\\windows\\win.ini",
    "file://",
    "php://filter"
]
HTTP_SPLITTING_SIGNATURES = [
    "\n",
    "\r",
    "\r\n",
    "admin"
]

class WAFProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.handle_request()
    def do_POST(self):
        self.handle_request()
    def handle_request(self):
        client_ip = self.client_address[0]
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        now = int(time.time())
        window_start = now - rate_limit_window
        # --- LOG REQUEST FOR ML ---
        try:
            from waf_request_logger import log_request
            body_preview = ''
            if self.command == 'POST':
                content_length = int(self.headers.get('Content-Length', 0))
                body_bytes = self.rfile.read(content_length)
                body_preview = body_bytes.decode(errors='ignore')
                self.rfile = http.server.BytesIO(body_bytes)
            log_request(
                client_ip=client_ip,
                method=self.command,
                path=self.path,
                headers=self.headers,
                body=body_preview
            )
        except Exception as e:
            print(f"[WAF LOGGING ERROR] {e}")
        # --- ML MODEL PREDICTION ---
        try:
            if hasattr(self.server, 'ml_model'):
                # Feature extraction (simple demo, match your CSV columns)
                path_len = len(self.path)
                num_special = sum(1 for c in self.path if not c.isalnum())
                num_digits = sum(1 for c in self.path if c.isdigit())
                has_sql_keywords = int(any(kw in self.path.lower() for kw in ['select', 'union', 'insert', 'drop', 'update', 'delete', 'or 1=1', 'and 1=1']))
                user_agent = self.headers.get('User-Agent', '')
                features = [[path_len, num_special, num_digits, has_sql_keywords]]
                pred = self.server.ml_model.predict(features)[0]
                if pred == 1:
                    print(f"[*] ML BLOCKED: Predicted malicious request from {client_ip}")
                    log_blocked(client_ip, "ML Model: Malicious", self.path, self.headers)
                    self.send_response(403)
                    self.send_header("Content-type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"Request blocked by WAF ML model prediction.")
                    return
        except Exception as e:
            print(f"[WAF ML ERROR] {e}")
        with lock:
            for ip in list(request_counts.keys()):
                request_counts[ip] = [t for t in request_counts[ip] if t > window_start]
                if not request_counts[ip]:
                    del request_counts[ip]
            if client_ip not in request_counts:
                request_counts[client_ip] = []
            request_counts[client_ip].append(now)
            if len(request_counts[client_ip]) > RATE_LIMIT:
                print(f"[*] Rate limit exceeded for {client_ip}")
                log_blocked(client_ip, "Rate limit exceeded", self.path, self.headers)
                self.send_response(429)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Rate limit exceeded. Try again later.")
                return
        user_agent = self.headers.get('User-Agent', '').lower()
        for bad_ua in BLOCKED_USER_AGENTS:
            if bad_ua in user_agent:
                print(f"[*] Blocked User-Agent for {client_ip}: {user_agent}")
                log_blocked(client_ip, f"Blocked User-Agent: {user_agent}", self.path, self.headers)
                self.send_response(403)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Request blocked by WAF: Suspicious User-Agent detected.")
                return
        print(f"[{timestamp}] Incoming request from {client_ip}: {self.path}")
        malicious_type = None
        # Combine path and query string for full inspection
        parsed_url = urllib.parse.urlparse(self.path)
        full_path = urllib.parse.unquote(parsed_url.path).lower()
        query_str = urllib.parse.unquote(parsed_url.query).lower()
        combined_path_query = full_path + '?' + query_str if query_str else full_path
        print(f"[DEBUG] combined_path_query: {combined_path_query}")
        header_str = ' '.join([str(v).lower() for v in self.headers.values()])
        body_str = ''
        if self.command == 'POST':
            content_length = int(self.headers.get('Content-Length', 0))
            body_bytes = self.rfile.read(content_length)
            body_str = body_bytes.decode(errors='ignore').lower()
            self.rfile = http.server.BytesIO(body_bytes)
        def check_signatures(signatures, label):
            for signature in signatures:
                pattern = re.escape(signature.lower())
                if (re.search(pattern, combined_path_query) or
                    re.search(pattern, header_str) or
                    re.search(pattern, body_str)):
                    return label, signature
            return None, None
        block_reason = None
        for sigs, label in [
            (SQL_INJECTION_SIGNATURE, "SQL Injection"),
            (XSS_SIGNATURES, "Cross-Site Scripting (XSS)"),
            (DIRECTORY_TRAVERSAL_SIGNATURES, "Directory Traversal"),
            (COMMAND_INJECTION_SIGNATURES, "Command Injection"),
            (LFI_SIGNATURES, "Local File Inclusion (LFI)"),
            (HTTP_SPLITTING_SIGNATURES, "HTTP Response Splitting")
        ]:
            for signature in sigs:
                # Use substring matching for '--', ''--', '1=1', '1=2', 'OR 1=1', 'AND 1=1' SQLi signatures
                if label == "SQL Injection" and signature in ["--", "'--", "1=1", "1=2", "OR 1=1", "AND 1=1", "'"]:
                    sig_lower = signature.lower()
                    print(f"[DEBUG] Checking signature: {sig_lower}")
                    if (sig_lower in combined_path_query or
                        sig_lower in header_str or
                        sig_lower in body_str):
                        block_reason = f"{label} ({signature})"
                        print(f"[*] BLOCKED: {block_reason} in request from {client_ip}")
                        log_blocked(client_ip, block_reason, self.path, self.headers)
                        break
                elif label == "Local File Inclusion (LFI)" or label == "HTTP Response Splitting":
                    # Use substring matching for LFI and HTTP splitting signatures
                    if (signature.lower() in combined_path_query or
                        signature.lower() in header_str or
                        signature.lower() in body_str):
                        block_reason = f"{label} ({signature})"
                        print(f"[*] BLOCKED: {block_reason} in request from {client_ip}")
                        log_blocked(client_ip, block_reason, self.path, self.headers)
                        break
                else:
                    # Only match whole words or exact phrases to reduce false positives
                    pattern = r'\b' + re.escape(signature.lower()) + r'\b'
                    if (re.search(pattern, combined_path_query) or
                        re.search(pattern, header_str) or
                        re.search(pattern, body_str)):
                        block_reason = f"{label} ({signature})"
                        print(f"[*] BLOCKED: {block_reason} in request from {client_ip}")
                        log_blocked(client_ip, block_reason, self.path, self.headers)
                        break
            if block_reason:
                break
        if block_reason:
            self.send_response(403)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Request blocked by WAF: {block_reason} detected.".encode('utf-8'))
            print(f"[*] Request from {client_ip} has been BLOCKED. Reason: {block_reason}")
            return
        try:
            global BACKEND_PORT
            target_url = f"http://localhost:{BACKEND_PORT}{self.path}"
            req = urllib.request.Request(target_url, headers=self.headers, method=self.command)
            if self.command == 'POST':
                content_length = int(self.headers.get('Content-Length', 0))
                req.data = self.rfile.read(content_length)
            with urllib.request.urlopen(req) as response:
                self.send_response(response.status)
                for header, value in response.info().items():
                    self.send_header(header, value)
                self.end_headers()
                self.copyfile(response, self.wfile)
                print(f"[*] Request from {client_ip} has been FORWARDED successfully.")
        except urllib.error.URLError as e:
            print(f"[-] Error forwarding request: {e.reason}")
            self.send_response(500)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"WAF Error: Could not connect to backend.")

def run_waf_proxy():
    global BACKEND_PORT
    try:
        with socketserver.TCPServer(("", WAF_PORT), WAFProxyHandler) as httpd:
            # Load ML model
            try:
                import joblib
                httpd.ml_model = joblib.load("waf_model.joblib")
                print("[*] ML model loaded for WAF.")
            except Exception as e:
                print(f"[WAF ML LOAD ERROR] {e}")
            print(f"\n[*] WAF reverse proxy started on port {WAF_PORT}")
            print(f"[*] WAF is protecting backend at http://localhost:{BACKEND_PORT}")
            print("--------------------------------------------------")
            print(f"[*] Visit http://localhost:{WAF_PORT} to test it.")
            print("--------------------------------------------------")
            httpd.serve_forever()
    except Exception as e:
        print(f"[-] Failed to start WAF proxy: {e}")
        sys.exit(1)

def main(argv):
    print("Starting WAF demo...")
    print("--------------------------------------------------")
    print(argv)
    global BACKEND_PORT
    BACKEND_PORT = int(argv[1])
    import time
    time.sleep(1)
    run_waf_proxy()

if __name__ == "__main__":
    main(argv=sys.argv)
