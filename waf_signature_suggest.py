# List of suspicious keywords to match for smart suggestions
SUSPICIOUS_KEYWORDS = [
    'admin', 'login', 'debug', 'config', 'root', 'secret', 'cmd', 'exec', 'eval', 'select', 'drop', 'passwd', 'password', 'shadow', 'hosts', 'boot', 'windows', 'file', 'php', 'filter', 'union', 'sleep', 'benchmark', 'information_schema', 'ping', 'nc', 'bash', 'sh', 'cmd.exe', 'document', 'cookie', 'iframe', 'svg', 'script', 'alert', 'prompt', 'confirm', 'insert', 'delete', 'update', 'cast', 'char', 'convert', 'whoami', 'id', 'cat', 'ls', 'pwd', 'onerror', 'onload', 'onmouseover', 'onfocus', 'onblur', 'onclick', 'onreadystatechange', 'onmousemove', 'src', 'img', 'body', 'a href', 'union select', 'or', 'and', '--', '#', '1=1', '1=2', 'or 1=1', 'and 1=1', 'substring', 'ascii', 'pg_sleep', 'waitfor delay', 'proc/self/cmdline'
]
# waf_signature_suggest.py
# Scans waf_blocked.log and suggests new WAF signatures

import re
from collections import Counter

import os

LOG_FILE = 'waf_blocked.log'

# Existing signatures (copy from waf.py)
EXISTING_SIGNATURES = set([
    # SQL Injection
    "' OR '1'='1", "UNION SELECT", "SELECT * FROM", "DROP TABLE", "DELETE FROM", "INSERT INTO", "UPDATE", "CAST(", "CHAR(", "CONVERT(", "INFORMATION_SCHEMA", "waitfor delay", "benchmark(", "sleep(", "pg_sleep(", "substring(", "ascii(", "1=1", "1=2", "OR 1=1", "AND 1=1", "--", "#", "'--",
    # XSS
    "<script>", "javascript:", "onerror=", "onload=", "onmouseover=", "onfocus=", "onblur=", "onclick=", "onreadystatechange=", "onmousemove=", "alert(", "prompt(", "confirm(", "document.cookie", "document.domain", "eval(", "src=", "<img", "<img>", "<body", "<iframe", "<svg", "<a href",
    # Directory Traversal
    "../", "..%2f", "..%5c", "..\\.", "..\\",
    # Command Injection
    "ls", "cat", "id", "whoami", "pwd", "ping", "nc", "sh", "bash", "cmd.exe",
    # LFI
    "/etc/passwd", "/etc/password", "/etc/shadow", "/etc/hosts", "/proc/self/cmdline", "c:\\boot.ini", "c:\\windows\\win.ini", "file://", "php://filter",
    # HTTP Splitting
    "\n", "\r", "\r\n"
])

# Helper: extract suspicious tokens from a string
TOKEN_RE = re.compile(r"[\w\-/\.\:\'\"]{5,}")

# List of common HTTP header names/values to ignore
COMMON_HEADERS = set([
    'host', 'user-agent', 'accept', 'accept-language', 'accept-encoding', 'connection',
    'upgrade-insecure-requests', 'sec-fetch-dest', 'sec-fetch-mode', 'sec-fetch-site',
    'sec-fetch-user', 'priority', 'keep-alive', 'gzip', 'deflate', 'zstd', 'document',
    'navigate', 'none', 'en-us', 'mozilla/5.0', 'linux', 'x86_64', 'rv:128.0',
    'gecko/20100101', 'firefox/128.0', 'text/html', 'application/xhtml', 'application/xml'
])

# Signature list mapping for waf.py
SIGNATURE_LISTS = {
    '1': ('SQL_INJECTION_SIGNATURE', "SQL Injection"),
    '2': ('XSS_SIGNATURES', "Cross-Site Scripting (XSS)"),
    '3': ('DIRECTORY_TRAVERSAL_SIGNATURES', "Directory Traversal"),
    '4': ('COMMAND_INJECTION_SIGNATURES', "Command Injection"),
    '5': ('LFI_SIGNATURES', "Local File Inclusion (LFI)"),
    '6': ('HTTP_SPLITTING_SIGNATURES', "HTTP Response Splitting")
}

def add_signature_to_waf(signature, list_name):
    waf_path = 'waf.py'
    with open(waf_path, 'r') as f:
        lines = f.readlines()
    # Find the list definition
    for i, line in enumerate(lines):
        if line.strip().startswith(list_name + ' = ['):
            # Find the closing bracket
            for j in range(i+1, len(lines)):
                if lines[j].strip().startswith(']'):
                    # Insert before closing bracket
                    lines.insert(j, f'    "{signature}",\n')
                    with open(waf_path, 'w') as wf:
                        wf.writelines(lines)
                    print(f"Added '{signature}' to {list_name} in waf.py.")
                    return True
    print(f"Could not find {list_name} in waf.py.")
    return False

# List of common HTTP header names/values to ignore
COMMON_HEADERS = set([
    'host', 'user-agent', 'accept', 'accept-language', 'accept-encoding', 'connection',
    'upgrade-insecure-requests', 'sec-fetch-dest', 'sec-fetch-mode', 'sec-fetch-site',
    'sec-fetch-user', 'priority', 'keep-alive', 'gzip', 'deflate', 'zstd', 'document',
    'navigate', 'none', 'en-us', 'mozilla/5.0', 'linux', 'x86_64', 'rv:128.0',
    'gecko/20100101', 'firefox/128.0', 'text/html', 'application/xhtml', 'application/xml'
])

def extract_tokens(text):
    return [t.lower() for t in TOKEN_RE.findall(text)]

def main():
    token_counter = Counter()
    with open(LOG_FILE, 'r') as f:
        for line in f:
            # Try to extract Path and Headers
            m = re.search(r"Path: ([^ ]+) Headers: (.*)", line)
            if m:
                path = m.group(1)
                headers = m.group(2)
                tokens = extract_tokens(path) + extract_tokens(headers)
                token_counter.update(tokens)
    # Filter out existing signatures and common headers, and only suggest if token contains suspicious keyword
    def is_suspicious(token):
        return any(kw in token for kw in SUSPICIOUS_KEYWORDS)
    suggestions = [token for token, count in token_counter.items()
                   if token not in EXISTING_SIGNATURES and token not in COMMON_HEADERS and count > 1 and is_suspicious(token)]
    if not suggestions:
        print("No new signature suggestions found.")
        return
    print("Suggested new signatures (appeared more than once and not already in list):")
    for token in suggestions:
        print(f"  - {token}")
        answer = input(f"Add '{token}' directly to waf.py signature lists? (y/n): ").strip().lower()
        if answer == 'y':
            print("Which attack type should this signature be added to?")
            for k, v in SIGNATURE_LISTS.items():
                print(f"  {k}: {v[1]}")
            choice = input("Enter number (1-6): ").strip()
            if choice in SIGNATURE_LISTS:
                list_name = SIGNATURE_LISTS[choice][0]
                success = add_signature_to_waf(token, list_name)
                if not success:
                    print(f"Failed to add '{token}' to waf.py.")
            else:
                print("Invalid choice. Skipped.")
        else:
            print(f"Skipped '{token}'.")

if __name__ == "__main__":
    main()
