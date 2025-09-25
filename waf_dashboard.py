from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import pandas as pd
import uvicorn
import json
import os
import base64
import asyncio
from fastapi import Request
from fastapi.responses import StreamingResponse, JSONResponse
from collections import Counter
import urllib.request as _urllib_request
import ipaddress
import re as _re


app = FastAPI()


def _embed_image_base64(path):
    try:
        with open(path, 'rb') as f:
            data = f.read()
        b64 = base64.b64encode(data).decode('ascii')
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


@app.get("/", response_class=HTMLResponse)
def dashboard():
    # Load features and stats
    try:
        df = pd.read_csv("waf_features.csv")
    except Exception:
        return "<h2>No waf_features.csv found. Run feature extraction first.</h2>"
    total = len(df)
    blocked = df['label'].sum()
    allowed = total - blocked

    # Try to read model metrics from classification_report.txt
    metrics_html = ""
    weighted_chart_html = ""
    weighted_chart_js = ""
    try:
        import re
        with open("classification_report.txt", "r") as f:
            metrics = f.read()
        lines = metrics.strip().split('\n')
        header = re.split(r'\s{2,}', lines[0].strip())
        rows = []
        for line in lines[2:]:
            if line.strip() == "" or line.startswith("accuracy"):
                continue
            row = re.split(r'\s{2,}', line.strip())
            if len(row) == len(header):
                rows.append(row)
        extra_rows = []
        weighted_avg_values = None
        for line in lines:
            if line.startswith("accuracy") or line.startswith("macro avg") or line.startswith("weighted avg"):
                row = re.split(r'\s{2,}', line.strip())
                extra_rows.append(row)
                if line.startswith("weighted avg"):
                    weighted_avg_values = row[1:5]
        table_html = "<table style='background:#fff;border-radius:8px;border:1px solid #ddd;margin-top:32px;width:100%;box-shadow:0 2px 8px #eee;font-size:1.1em;'>"
        table_html += "<thead><tr>" + "".join([f"<th style='padding:8px 12px;border-bottom:1px solid #eee;text-align:left;'>{h}</th>" for h in header]) + "</tr></thead>"
        table_html += "<tbody>"
        for row in rows:
            table_html += "<tr>" + "".join([f"<td style='padding:8px 12px;border-bottom:1px solid #f7f7f7;'>{cell}</td>" for cell in row]) + "</tr>"
        for row in extra_rows:
            table_html += "<tr style='background:#f9f9f9;'>" + "".join([f"<td style='padding:8px 12px;border-bottom:1px solid #f7f7f7;font-weight:bold;color:#000;'>{cell}</td>" for cell in row]) + "</tr>"
        table_html += "</tbody></table>"
        metrics_html = table_html
        # Extract summary KPI values for a more visible display
        accuracy_val = None
        weighted_precision = None
        weighted_recall = None
        weighted_f1 = None
        try:
            for line in lines:
                if line.lower().startswith('accuracy'):
                    parts = re.split(r'\s{2,}', line.strip())
                    if len(parts) > 1:
                        accuracy_val = parts[1]
                if line.lower().startswith('weighted avg') or line.lower().startswith('weighted average'):
                    parts = re.split(r'\s{2,}', line.strip())
                    # expected: ['weighted avg', 'precision', 'recall', 'f1-score', 'support']
                    if len(parts) >= 4:
                        weighted_precision = parts[1]
                        weighted_recall = parts[2]
                        weighted_f1 = parts[3]
        except Exception:
            pass
        metrics_summary_html = ""
        if accuracy_val or weighted_precision:
            metrics_summary_html = "<div style='display:flex;gap:12px;margin:12px 0 18px 0;'>"
            def _kpi_html(title, val, color='#06b6d4'):
                return f"<div style='flex:1;padding:12px;border-radius:10px;background:#071226;border:1px solid rgba(255,255,255,0.02);'><div style='font-size:12px;color:#98a8bf'>{title}</div><div style='font-size:18px;font-weight:700;color:#000;margin-top:6px'>{val}</div></div>"
            if accuracy_val:
                metrics_summary_html += _kpi_html('Accuracy', accuracy_val)
            if weighted_precision:
                metrics_summary_html += _kpi_html('Weighted Precision', weighted_precision)
            if weighted_recall:
                metrics_summary_html += _kpi_html('Weighted Recall', weighted_recall)
            if weighted_f1:
                metrics_summary_html += _kpi_html('Weighted F1', weighted_f1)
            metrics_summary_html += "</div>"
        else:
            metrics_summary_html = ""
        # If we parsed weighted average numeric values, render a small labeled row (Precision / Recall / F1 / Support)
        if weighted_avg_values:
            try:
                wa_vals = [ (float(x) if isinstance(x, str) and x.replace('.', '', 1).isdigit() else x) for x in weighted_avg_values ]
            except Exception:
                wa_vals = weighted_avg_values
            labels_row_html = "<div style='display:flex;gap:8px;margin-top:10px;'>"
            labels = ['Precision', 'Recall', 'F1-Score', 'Support']
            for lbl, val in zip(labels, wa_vals):
                labels_row_html += f"<div style='flex:1;padding:10px;border-radius:8px;background:#fff;color:#000;text-align:center;font-weight:700;'><div style='font-size:12px;color:#555'>{lbl}</div><div style='font-size:16px;margin-top:6px'>{val}</div></div>"
            labels_row_html += "</div>"
            # Prepend the small metrics row so it's highly visible
            metrics_summary_html = labels_row_html + metrics_summary_html
            weighted_chart_html = "<h3 style='margin-top:12px;'>Weighted Avg Metrics (Graph)</h3><div style='margin-top:12px;max-width:720px;'><canvas id='weightedChart' width='400' height='200'></canvas></div>"
            weighted_chart_js = f"""
<script>
window.addEventListener('DOMContentLoaded', function() {{
    const wctx = document.getElementById('weightedChart').getContext('2d');
    new Chart(wctx, {{
        type: 'bar',
        data: {{
            labels: ['Precision', 'Recall', 'F1-Score', 'Support'],
            datasets: [{{
                label: 'Weighted Avg',
                data: [{', '.join([str(float(x)) if x.replace('.','',1).isdigit() else '0' for x in weighted_avg_values])}],
                backgroundColor: [
                    'rgba(52, 152, 219, 0.85)',
                    'rgba(39, 174, 96, 0.85)',
                    'rgba(231, 76, 60, 0.85)',
                    'rgba(241, 196, 15, 0.85)'
                ],
                borderColor: [
                    'rgba(52, 152, 219, 1)',
                    'rgba(39, 174, 96, 1)',
                    'rgba(231, 76, 60, 1)',
                    'rgba(241, 196, 15, 1)'
                ],
                borderWidth: 2
            }}]
        }},
        options: {{
            scales: {{
                y: {{ beginAtZero: true }}
            }},
            plugins: {{ legend: {{ display:false }} }}
        }}
    }});
}});
</script>
"""
    except Exception:
        metrics_html = "<div style='color:#aaa;margin-top:32px;'>No model metrics found. Retrain your model to generate metrics.</div>"

    # Embed generated visualization images from reports/ (if available)
    reports_dir = "reports"
    images_html = ""
    if os.path.isdir(reports_dir):
        images = [
            ('confusion_matrix.png','Confusion Matrix'),
            ('roc_curve.png','ROC Curve'),
            ('precision_recall.png','Precision-Recall Curve'),
            ('feature_importances.png','Feature Importances'),
            ('class_distribution.png','Class Distribution')
        ]
        for fname, title in images:
            p = os.path.join(reports_dir, fname)
            data_uri = _embed_image_base64(p)
            if data_uri:
                images_html += f"<h3 style='margin-top:20px;'>{title}</h3><img src='{data_uri}' style='max-width:100%;border:1px solid #eee;border-radius:6px;box-shadow:0 2px 6px rgba(0,0,0,0.08);'>"
        # Link to full HTML report if present
        report_html_path = os.path.join(reports_dir, 'report.html')
        if os.path.exists(report_html_path):
            # We cannot serve the static file directly; provide an instruction/link to open locally
            images_html += f"<p style='margin-top:12px;color:#666;'>Full HTML report available at <strong>{report_html_path}</strong> (open locally).</p>"

    # Recent requests table
    try:
        with open("waf_requests.log") as f:
            lines = f.readlines()[-10:]  # Show last 10 requests
        recent_requests_html = ""
        for line in lines:
            req = json.loads(line)
            recent_requests_html += f"<tr><td>{req['timestamp']}</td><td>{req['client_ip']}</td><td>{req['method']}</td><td>{req['path']}</td></tr>"
    except Exception:
        recent_requests_html = "<tr><td colspan='4'>No recent requests found.</td></tr>"

    html = f"""
    <html>
    <head>
        <title>WAF Dashboard</title>
        <script src='https://cdn.jsdelivr.net/npm/chart.js'></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg: #0f1724;
                --card: #0b1320;
                --muted: #94a3b8;
                --accent: #4f46e5;
                --danger: #ef4444;
                --success: #10b981;
                --glass: rgba(255,255,255,0.03);
            }}
            html,body {{ height:100%; margin:0; font-family: 'Inter', Arial, sans-serif; background: linear-gradient(180deg,#071133 0%, #0b1220 100%); color:#e6eef8 }}
            .wrap {{ max-width:1100px; margin:32px auto; padding:20px; }}
            .header {{ display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:18px; }}
            .brand {{ display:flex; align-items:center; gap:12px; }}
            .logo {{ width:48px; height:48px; border-radius:10px; background:linear-gradient(135deg,var(--accent),#06b6d4); box-shadow:0 6px 18px rgba(79,70,229,0.18) }}
            h1 {{ margin:0; font-size:20px; letter-spacing:0.2px }}
            .sub {{ color:var(--muted); font-size:13px }}
            .controls {{ display:flex; gap:8px; align-items:center }}
            .btn {{ background:var(--glass); color:var(--muted); border:1px solid rgba(255,255,255,0.04); padding:8px 12px; border-radius:8px; cursor:pointer }}
            .btn.primary {{ background: linear-gradient(90deg,var(--accent),#06b6d4); color:white; border:none; box-shadow:0 8px 24px rgba(79,70,229,0.18) }}

            .grid {{ display:grid; grid-template-columns: 1fr 360px; gap:20px; align-items:start; }}
            .card {{ background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)); border-radius:12px; padding:18px; box-shadow:0 6px 18px rgba(2,6,23,0.6); border:1px solid rgba(255,255,255,0.03) }}

            .stats {{ display:flex; gap:12px; margin-bottom:12px }}
            .stat-item {{ flex:1; padding:10px; border-radius:10px; background:linear-gradient(90deg, rgba(255,255,255,0.01), rgba(255,255,255,0.005)); text-align:center }}
            .stat-item h3 {{ margin:0; font-size:14px; color:var(--muted) }}
            .stat-item p {{ margin:6px 0 0; font-size:18px; font-weight:600 }}
            .stat-item .small {{ font-size:12px; color:var(--muted); margin-top:6px }}

            #chart-container {{ height:260px }}
            canvas {{ width:100% !important; height:260px !important }}

            .metrics-table {{ width:100%; margin-top:12px; border-collapse:collapse; font-size:13px }}
            .metrics-table th, .metrics-table td {{ padding:8px 10px; text-align:left; color:var(--muted) }}

            .recent-table {{ width:100%; border-collapse:collapse; margin-top:12px }}
            .recent-table th, .recent-table td {{ padding:10px 8px; text-align:left; border-bottom:1px dashed rgba(255,255,255,0.03); color:var(--muted); font-size:13px }}
            .recent-table tr:hover td {{ background: rgba(255,255,255,0.01) }}

            .visual-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px }}
            .visual-grid img {{ width:100%; border-radius:8px; border:1px solid rgba(255,255,255,0.03) }}

            .search {{ width:100%; padding:10px 12px; border-radius:10px; border:1px solid rgba(255,255,255,0.04); background:transparent; color:var(--muted) }}

            /* Clock widget styles */
            .clock {{ display:flex; align-items:center; gap:8px; color:var(--muted); margin-right:6px }}
            .clock .dot {{ width:10px; height:10px; border-radius:50%; background:rgba(96,165,250,0.95); box-shadow:0 6px 14px rgba(96,165,250,0.12); animation: pulse 2000ms infinite; }}
            .clock .main {{ font-size:13px; font-weight:600; color:#e6eef8 }}
            .clock .sub {{ font-size:11px; color:var(--muted); line-height:1 }}
            @keyframes pulse {{ 0%{{ transform:scale(1); opacity:1 }} 50%{{ transform:scale(1.35); opacity:0.65 }} 100%{{ transform:scale(1); opacity:1 }} }}

            footer.note {{ margin-top:16px; color:var(--muted); font-size:12px; text-align:center }}

            @media (max-width:900px) {{ .grid {{ grid-template-columns: 1fr; }} .visual-grid {{ grid-template-columns:1fr 1fr }} }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <div class="header">
                <div class="brand">
                    <div class="logo"></div>
                    <div>
                        <h1>WAF Dashboard</h1>
                        <div class="sub">Realtime summary · Model visuals · Recent requests</div>
                    </div>
                </div>
                <div class="controls">
                    <div class="clock" id="clock">
                        <div class="dot" aria-hidden="true"></div>
                        <div>
                            <div class="main" id="clock-main">--:--:--</div>
                            <div class="sub" id="clock-sub">Loading…</div>
                        </div>
                    </div>
                    <button class="btn" onclick="window.location.href='/live'">Live</button>
                    <button class="btn" onclick="location.reload()">Refresh</button>
                    <button class="btn primary" onclick="toggleDarkMode()">Toggle Theme</button>
                </div>
            </div>

            <div class="grid">
                <div>
                    <div class="card">
                        <div class="stats">
                            <div class="stat-item">
                                <h3>Blocked</h3>
                                <p class="blocked">{blocked}</p>
                                <div class="small">Requests blocked by rules/model</div>
                            </div>
                            <div class="stat-item">
                                <h3>Allowed</h3>
                                <p class="allowed">{allowed}</p>
                                <div class="small">Requests forwarded to backend</div>
                            </div>
                            <div class="stat-item">
                                <h3>Total</h3>
                                <p>{total}</p>
                                <div class="small">Total requests in dataset</div>
                            </div>
                        </div>
                        <div id="chart-container">
                            <canvas id="wafChart"></canvas>
                        </div>
                    </div>

                    <div class="card" style="margin-top:18px;">
                        <h2 style="margin:0 0 10px 0;font-size:16px;color:#e6eef8;">Model Performance</h2>
                        {metrics_summary_html}
                        {metrics_html}
                        {weighted_chart_html}
                        <div class="visual-grid">
                            {images_html}
                        </div>
                    </div>

                    <div class="card" style="margin-top:18px;">
                        <h2 style="margin:0 0 10px 0;font-size:16px;color:#e6eef8;">Recent Requests</h2>
                        <input id="searchBox" class="search" placeholder="Search IP, Method, Path...">
                        <table class="recent-table" id="requestsTable">
                            <thead>
                                <tr><th>Time</th><th>IP</th><th>Method</th><th>Path</th></tr>
                            </thead>
                            <tbody>
                                {recent_requests_html}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div>
                    <div class="card">
                        <h3 style="margin-top:0;color:#e6eef8;">Training Visuals</h3>
                        <div style="font-size:13px;color:var(--muted);">Quick view of artifacts generated by training</div>
                        <div class="visual-grid" style="margin-top:12px;">
                            <!-- show up to four images in the side panel -->
                            {images_html}
                        </div>
                        <div style="margin-top:12px;">
                            <a style="color:var(--accent);font-weight:600;text-decoration:none;" href="#">Open full report (locally)</a>
                        </div>
                    </div>

                    <div class="card" style="margin-top:18px;">
                        <h3 style="margin-top:0;color:#e6eef8;">Notes</h3>
                        <div style="font-size:13px;color:var(--muted);line-height:1.4;">
                            - If visuals are missing, run <code>python3 train_waf_model.py</code> to generate reports/.
                            <br>- Open <code>reports/report.html</code> locally for the full training report.
                        </div>
                    </div>
                </div>
            </div>

            <footer class="note">Generated locally · Refresh to update stats</footer>
        </div>

        <script>
        function toggleDarkMode() {{ document.body.classList.toggle('alt-theme'); document.querySelector('.logo').classList.toggle('active'); }}

        // Enhanced clock: show time, date and timezone
        function updateClock() {{
            const main = document.getElementById('clock-main');
            const sub = document.getElementById('clock-sub');
            if (!main || !sub) return;
            const now = new Date();
            try {{
                const timeStr = now.toLocaleTimeString([], {{ hour: '2-digit', minute: '2-digit', second: '2-digit' }});
                const dateStr = now.toLocaleDateString([], {{ weekday: 'short', month: 'short', day: 'numeric' }});
                const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
                    main.textContent = timeStr;
                    sub.textContent = `${{dateStr}} · ${{tz}}`;
            }} catch (e) {{
                main.textContent = now.toTimeString().split(' ')[0];
                sub.textContent = now.toDateString();
            }}
        }}
        // start immediately and update every second
        updateClock();
        setInterval(updateClock, 1000);

        const ctx = document.getElementById('wafChart').getContext('2d');
        new Chart(ctx, {{
            type: 'doughnut',
            data: {{
                labels: ['Blocked','Allowed'],
                datasets: [{{ data: [{blocked}, {allowed}], backgroundColor: ['#ef4444', '#10b981'], hoverOffset: 8 }}]
            }},
            options: {{
                cutout: '60%',
                plugins: {{ legend: {{ display: true, labels: {{ color: '#cbd5e1' }} }} }}
            }}
        }});

        // search/filter
        document.addEventListener('DOMContentLoaded', function() {{
            // kick off clock as soon as DOM is ready
            updateClock();
             const searchBox = document.getElementById('searchBox');
             const table = document.getElementById('requestsTable');
             searchBox.addEventListener('input', function() {{
                 const filter = searchBox.value.toLowerCase();
                 for (const row of table.tBodies[0].rows) {{
                     const text = row.innerText.toLowerCase();
                     row.style.display = text.includes(filter) ? '' : 'none';
                 }}
             }});
         }});
         </script>
        {weighted_chart_js}
    </body>
    </html>
    """
    return HTMLResponse(content=html)

BLOCKED_IPS_FILE = "blocked_ips.json"


def load_blocked_ips():
    try:
        with open(BLOCKED_IPS_FILE, 'r') as f:
            data = json.load(f)
        return set(data)
    except Exception:
        return set()


def save_blocked_ips(ips):
    try:
        with open(BLOCKED_IPS_FILE, 'w') as f:
            json.dump(list(ips), f)
    except Exception:
        pass


@app.get('/blocked_ips')
def get_blocked_ips():
    return JSONResponse(content={"blocked": list(load_blocked_ips())})


@app.post('/block')
async def block_ip(request: Request):
    payload = await request.json()
    ip = payload.get('ip')
    if not ip:
        return JSONResponse({"error": "missing ip"}, status_code=400)
    ips = load_blocked_ips()
    ips.add(ip)
    save_blocked_ips(ips)
    return JSONResponse({"blocked": list(ips)})


@app.post('/unblock')
async def unblock_ip(request: Request):
    payload = await request.json()
    ip = payload.get('ip')
    if not ip:
        return JSONResponse({"error": "missing ip"}, status_code=400)
    ips = load_blocked_ips()
    if ip in ips:
        ips.remove(ip)
        save_blocked_ips(ips)
    return JSONResponse({"blocked": list(ips)})


@app.get('/sse')
async def sse_stream():
    async def event_generator():
        while True:
            try:
                if os.path.exists('waf_requests.log'):
                    with open('waf_requests.log') as f:
                        lines = f.readlines()[-50:]
                    requests = []
                    for l in lines:
                        l = l.strip()
                        if not l:
                            continue
                        try:
                            requests.append(json.loads(l))
                        except Exception:
                            continue
                else:
                    requests = []
                payload = {"requests": requests, "blocked": list(load_blocked_ips())}
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception:
                yield f"data: {json.dumps({'requests': [], 'blocked': list(load_blocked_ips())})}\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(event_generator(), media_type='text/event-stream')


@app.get('/live', response_class=HTMLResponse)
def live_page():
    # A minimal live requests page that connects to /sse and allows blocking/unblocking IPs
    html = """
    <html>
    <head>
      <title>Live Requests</title>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
      <style>
        body { font-family: 'Inter', Arial, sans-serif; background: #071133; color:#e6eef8; margin:0; padding:20px }
        .wrap { max-width:1000px; margin:0 auto }
        .card { background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)); padding:16px; border-radius:10px }
        table { width:100%; border-collapse:collapse; margin-top:12px }
        th,td { padding:10px; text-align:left; border-bottom:1px solid rgba(255,255,255,0.03); font-size:13px }
        .btn { padding:6px 8px; border-radius:6px; background:#0b1320; color:#cbd5e1; border:1px solid rgba(255,255,255,0.03); cursor:pointer }
        .btn.block { background:#ef4444; color:#fff }
        .btn.unblock { background:#10b981; color:#fff }
        .search { padding:8px 10px; border-radius:8px; width:100%; margin-bottom:10px; border:1px solid rgba(255,255,255,0.03); background:transparent; color:#e6eef8 }
      </style>
    </head>
    <body>
      <div class="wrap">
        <h2>Live Requests</h2>
        <div style="margin-top:8px;">
          <button class="btn" onclick="window.location.href='/'">Back to Dashboard</button>
        </div>
        <div class="card">
          <input id="filter" class="search" placeholder="Filter by IP, method, path...">
          <table id="liveTable">
            <thead><tr><th>Time</th><th>IP</th><th>Method</th><th>Path</th><th>Blocked</th><th>Action</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
        <p style="margin-top:12px;color:#94a3b8">Connected via Server-Sent Events (updates every ~2s). Use the action buttons to mark an IP as blocked/unblocked locally.</p>
        <p style="margin-top:6px;color:#94a3b8"><a href="/" style="color:#60a5fa">Back to Dashboard</a></p>
      </div>

      <script>
        const evtSource = new EventSource('/sse');
        let current = { requests: [], blocked: [] };

        evtSource.onmessage = function(e) {
          try {
            current = JSON.parse(e.data);
            renderTable(current.requests, current.blocked);
          } catch(err) {
            console.error('Failed to parse SSE data', err);
          }
        };

        function renderTable(requests, blocked) {
          const tbody = document.querySelector('#liveTable tbody');
          const filter = document.getElementById('filter').value.toLowerCase();
          tbody.innerHTML = '';
          for (const r of requests.slice().reverse()) {
            const rowText = `${r.timestamp} ${r.client_ip} ${r.method} ${r.path}`.toLowerCase();
            if (filter && !rowText.includes(filter)) continue;
            const isBlocked = blocked.includes(r.client_ip);
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${r.timestamp}</td><td>${r.client_ip}</td><td>${r.method}</td><td>${r.path}</td><td>${isBlocked ? 'Yes' : 'No'}</td><td></td>`;
            const actionTd = tr.querySelector('td:last-child');
            const btn = document.createElement('button');
            btn.className = 'btn ' + (isBlocked ? 'unblock' : 'block');
            btn.textContent = isBlocked ? 'Unblock' : 'Block';
            btn.onclick = () => toggleBlock(r.client_ip, isBlocked);
            actionTd.appendChild(btn);
            tbody.appendChild(tr);
          }
        }

        document.getElementById('filter').addEventListener('input', function(){
          renderTable(current.requests, current.blocked);
        });

        async function toggleBlock(ip, currentlyBlocked) {
          try {
            const res = await fetch(currentlyBlocked ? '/unblock' : '/block', {
              method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ ip })
            });
            const data = await res.json();
            current.blocked = data.blocked;
            renderTable(current.requests, current.blocked);
          } catch(err) {
            console.error('Toggle failed', err);
            alert('Action failed');
          }
        }
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

GEOIP_DB_PATH = "GeoLite2-Country.mmdb"
_geoip_reader = None


def _get_geoip_reader():
    global _geoip_reader
    if _geoip_reader is not None:
        return _geoip_reader
    try:
        import geoip2.database
        if os.path.exists(GEOIP_DB_PATH):
            _geoip_reader = geoip2.database.Reader(GEOIP_DB_PATH)
            return _geoip_reader
    except Exception:
        _geoip_reader = None
    return None


def _resolve_country(ip):
    r = _get_geoip_reader()
    if not r:
        return None
    try:
        resp = r.country(ip)
        return resp.country.iso_code
    except Exception:
        return None


@app.get('/api/countries')
def api_countries():
    # Aggregate last N requests by country (uses GeoIP DB if available)
    try:
        with open('waf_requests.log') as f:
            lines = f.readlines()[-2000:]
    except Exception:
        return JSONResponse(content={"countries": {}, "total": 0})
    counts = Counter()
    for l in lines:
        l = l.strip()
        if not l:
            continue
        try:
            req = json.loads(l)
            ip = req.get('client_ip')
            code = _resolve_country(ip) or 'Unknown'
            counts[code] += 1
        except Exception:
            continue
    return JSONResponse(content={"countries": dict(counts), "total": sum(counts.values())})


@app.get('/countries', response_class=HTMLResponse)
def countries_page():
    # Read last 50 requests
    recent = []
    try:
        if os.path.exists('waf_requests.log'):
            with open('waf_requests.log', 'r') as f:
                lines = f.readlines()[-50:]
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    recent.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        recent = []

    # GeoIP resolution with fallback to public API and local cache
    GEOIP_CACHE_FILE = 'geoip_cache.json'
    # Load cache
    try:
        if os.path.exists(GEOIP_CACHE_FILE):
            with open(GEOIP_CACHE_FILE, 'r') as f:
                geo_cache = json.load(f)
        else:
            geo_cache = {}
    except Exception:
        geo_cache = {}

    country_counts = Counter()
    resolved = []
    geo_available = False
    geo_reader = None
    # Prefer local GeoLite2 DB if present
    try:
        import geoip2.database
        if os.path.exists('GeoLite2-Country.mmdb'):
            geo_reader = geoip2.database.Reader('GeoLite2-Country.mmdb')
            geo_available = True
    except Exception:
        geo_available = False
        geo_reader = None

    # Determine which IPs we need to resolve via API
    ips_to_query = set()
    for r in recent:
        ip_raw = r.get('client_ip')
        if not ip_raw:
            continue
        ip = _normalize_ip(ip_raw)
        # Treat localhost/private addresses as Local (do not query external API)
        if _is_local_ip(ip):
            geo_cache[ip] = 'Local'
            r['_client_ip_clean'] = ip
            continue
        if ip in geo_cache:
            r['_client_ip_clean'] = ip
            continue
        if not geo_available:
            ips_to_query.add(ip)
        r['_client_ip_clean'] = ip

    # Query external API for missing IPs (ip-api.com, no key required) - be gentle with timeouts
    if ips_to_query:
        for ip in list(ips_to_query)[:50]:  # limit just in case
            try:
                url = f'http://ip-api.com/json/{ip}?fields=status,countryCode'
                with _urllib_request.urlopen(url, timeout=3) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                if data.get('status') == 'success' and data.get('countryCode'):
                    geo_cache[ip] = data.get('countryCode')
                else:
                    geo_cache[ip] = 'Unknown'
            except Exception:
                geo_cache[ip] = 'Unknown'
        # Save cache back to disk
        try:
            with open(GEOIP_CACHE_FILE, 'w') as f:
                json.dump(geo_cache, f)
        except Exception:
            pass

    # Resolve countries for the recent requests (use GeoLite2 DB if available, else cache)
    for r in recent:
        ip_raw = r.get('client_ip')
        ip = r.get('_client_ip_clean') or _normalize_ip(ip_raw)
        country = 'Unknown'
        if ip:
            if geo_reader:
                try:
                    resp = geo_reader.country(ip)
                    if resp and resp.country and resp.country.iso_code:
                        country = resp.country.iso_code
                except Exception:
                    country = geo_cache.get(ip, 'Unknown')
            else:
                country = geo_cache.get(ip, 'Unknown')
        r['_country'] = country
        resolved.append(r)
        country_counts[country] += 1

    # Prepare top countries data
    top = country_counts.most_common(10)
    labels = [c for c, _ in top]
    values = [v for _, v in top]

    # Build a simple table of the last 50 requests
    rows_html = ''
    if resolved:
        for r in resolved[::-1]:
            # show original IP (with port if present) in the table for clarity
            rows_html += f"<tr><td>{r.get('timestamp','-')}</td><td>{r.get('client_ip','-')}</td><td>{r.get('method','-')}</td><td>{r.get('path','-')}</td><td>{r.get('_country','Unknown')}</td></tr>"
    else:
        rows_html = '<tr><td colspan="5">No recent requests found.</td></tr>'

    # Render HTML with Chart.js and chartjs-chart-geo for world map bubbles
    import string as _string
    labels_json = json.dumps(labels)
    values_json = json.dumps(values)
    resolved_json = json.dumps(resolved)
    # compute flags for display
    local_geo_text = 'yes' if geo_available else 'no'
    api_used_text = 'yes' if (not geo_available and bool(geo_cache)) else 'no'
    resolved_count = sum(1 for r in resolved if r.get('_country') and r.get('_country') != 'Unknown')
    geo_available_text = 'true' if geo_available else 'false'

    template = _string.Template("""
    <html>
    <head>
      <title>Top Countries - WAF</title>
      <script src='https://cdn.jsdelivr.net/npm/chart.js'></script>
      <script src='https://unpkg.com/topojson-client@3.1.0/dist/topojson-client.min.js'></script>
      <script src='https://unpkg.com/chartjs-chart-geo@3.7.0/dist/chartjs-chart-geo.min.js'></script>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
      <style>
        body { font-family: 'Inter', Arial, sans-serif; background:#071133; color:#e6eef8; margin:0; padding:20px }
        .wrap { max-width:1100px; margin:0 auto }
        .card { background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)); padding:16px; border-radius:10px }
        .row { display:flex; gap:16px }
        .col-2 { flex:1 }
        canvas { width:100%; height:360px }
        table { width:100%; border-collapse:collapse; margin-top:12px }
        th,td { padding:8px; text-align:left; border-bottom:1px solid rgba(255,255,255,0.03); color:#cbd5e1 }
        .small { color:#94a3b8; font-size:13px }
        a.back { color:#60a5fa; text-decoration:none }
        .tooltip-lines { white-space: pre-line; }
      </style>
    </head>
    <body>
      <div class="wrap">
        <h2>Top Countries (last 50 requests)</h2>
        <div class="card">
          <div class="small">Local GeoIP DB: $local_geo · API fallback: $api_used · Resolved: $resolved_count</div>
          <div class="row" style="margin-top:12px;align-items:stretch;">
            <div class="col-2">
              <h4 style="margin:6px 0 8px 0">World Map (bubbles)</h4>
              <canvas id="mapChart"></canvas>
            </div>
            <div style="width:360px">
              <h4 style="margin:6px 0 8px 0">Top Countries</h4>
              <canvas id="barChart" height="360"></canvas>
            </div>
          </div>
          <h4 style="margin-top:16px">Last ${count} Requests (most recent first)</h4>
          <table>
            <thead><tr><th>Time</th><th>IP</th><th>Method</th><th>Path</th><th>Country</th></tr></thead>
            <tbody>
              $rows_html
            </tbody>
          </table>
          <p style="margin-top:12px"><a class="back" href="/">Back to Dashboard</a></p>
        </div>
      </div>

      <script>
      // Data from server
      const topLabels = $labels;
      const topValues = $values;
      const recentRequests = $resolved;

      // Bar chart
      const bctx = document.getElementById('barChart').getContext('2d');
      new Chart(bctx, {
        type: 'bar',
        data: {
          labels: topLabels,
          datasets: [{ label: 'Requests', data: topValues, backgroundColor: 'rgba(96,165,250,0.9)' }]
        },
        options: {
          plugins: {
            legend: { display:false },
            tooltip: {
              callbacks: {
                label: function(context) {
                  return `${context.label}: ${context.parsed.y || context.raw}`;
                }
              }
            }
          },
          scales: { y: { beginAtZero:true } }
        }
      });

      // If no data, show friendly placeholder and skip map rendering
      if (!topLabels || topLabels.length === 0) {
        const mapCanvas = document.getElementById('mapChart');
        const parent = mapCanvas.parentNode;
        mapCanvas.remove();
        const note = document.createElement('div');
        note.style.color = '#94a3b8';
        note.style.padding = '40px 12px';
        note.innerText = 'No country data to display.';
        parent.appendChild(note);
      } else {
        // World map bubbles using chartjs-chart-geo + topojson-client
        (async function(){
          try {
            const world = await fetch('https://unpkg.com/world-atlas@2/countries-110m.json').then(r=>r.json());
            const countries = topojson.feature(world, world.objects.countries).features;

            // Build bubble data: match our topLabels (ISO A2 codes)
            const points = [];
            for (const [i, c] of topLabels.entries()) {
              const coordMap = {
                'US':[37.0902,-95.7129],'CN':[35.8617,104.1954],'RU':[61.5240,105.3188],'IN':[20.5937,78.9629],'BR':[-14.2350,-51.9253],'DE':[51.1657,10.4515],'FR':[46.2276,2.2137],'GB':[55.3781,-3.4360],'CA':[56.1304,-106.3468],'AU':[-25.2744,133.7751]
              };
              let latlon = coordMap[c];
              if (!latlon) {
                latlon = [ (Math.random()*140)-70, (Math.random()*360)-180 ];
              }
              points.push({
                type: 'Feature',
                properties: { label: c, value: topValues[i] },
                geometry: { type:'Point', coordinates: [latlon[1], latlon[0]] }
              });
            }

            const mctx = document.getElementById('mapChart').getContext('2d');
            new Chart(mctx, {
              type: 'bubbleMap',
              data: {
                labels: topLabels,
                datasets: [{
                  label: 'Top countries',
                  data: points,
                  pointRadius: function(ctx){
                    const v = ctx.raw.properties.value || 1;
                    return 4 + Math.sqrt(v) * 3;
                  },
                  backgroundColor: 'rgba(96,165,250,0.85)'
                }]
              },
              options: {
                showOutline: false,
                plugins: {
                  legend: { display:false },
                  tooltip: {
                    callbacks: {
                      label: function(context) {
                        const label = (context.raw && context.raw.properties && context.raw.properties.label) || context.label;
                        const val = context.raw && context.raw.properties && context.raw.properties.value ? context.raw.properties.value : '';
                        return `${label}: ${val}`;
                      }
                    }
                  }
                }
              }
            });
          } catch(err) {
            console.warn('Map rendering failed', err);
            const mapCanvas = document.getElementById('mapChart');
            if (mapCanvas) mapCanvas.remove();
          }
        })();
      }
      </script>
    </body>
    </html>
    """
    )

    html = template.safe_substitute(labels=labels_json, values=values_json, resolved=resolved_json, local_geo=local_geo_text, api_used=api_used_text, rows_html=rows_html, count=str(len(resolved)), resolved_count=str(resolved_count))
    return HTMLResponse(content=html)

def _is_local_ip(ip_str):
    """Return True if ip_str is loopback/private/reserved (e.g., 127.0.0.1, RFC1918)."""
    try:
        addr = ipaddress.ip_address(ip_str)
        # treat loopback, private, link-local and reserved as local
        return addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_reserved
    except Exception:
        return False


def _normalize_ip(ip_str):
    """Strip common port suffixes from IPv4 and bracketed IPv6 addresses for lookups.
    Examples: '1.2.3.4:1234' -> '1.2.3.4', '[::1]:8080' -> '::1'."""
    if not ip_str:
        return ip_str
    try:
        # IPv4 with optional port
        m = _re.match(r'^(\d{1,3}(?:\.\d{1,3}){3})(?::\d+)?$', ip_str)
        if m:
            return m.group(1)
        # [ipv6]:port or [ipv6]
        m2 = _re.match(r'^\[(.+)\](?::\d+)?$', ip_str)
        if m2:
            return m2.group(1)
        # plain IPv6 or other formats - leave as-is
        return ip_str
    except Exception:
        return ip_str


if __name__ == "__main__":
    uvicorn.run("waf_dashboard:app", host="0.0.0.0", port=8051, reload=True)