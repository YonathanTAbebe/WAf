# backend_demo.py
# Simple backend server to be protected by WAF

import http.server
import socketserver

BACKEND_PORT = 9000

class SimpleBackendHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Hello from the backend!')

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Received POST data: ' + post_data)

if __name__ == "__main__":
    with socketserver.TCPServer(("", BACKEND_PORT), SimpleBackendHandler) as httpd:
        print(f"[*] Backend server started on port {BACKEND_PORT}")
        httpd.serve_forever()
