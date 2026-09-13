"""TripRank portfolio UI: recommendation screen + MLOps screen (stdlib only)."""
from __future__ import annotations

import json
import urllib.request

API = "http://localhost:8000"

PAGE = """<html><head><title>TripRank</title>
<style>body{font-family:sans-serif;max-width:720px;margin:2em auto}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px 10px}</style>
</head><body>
<h1>TripRank — Real-Time Hotel Recommendation</h1>
<form method="get">Session: <input name="session" value="%SESSION%"/>
Track: <input name="track" value="%TRACK%" size="8"/>
<input type="submit" value="Recommend"/></form>
<h2>Recommended</h2>%ITEMS%
<h2>Model Operations</h2>%OPS%
<p><small>Model: %MODEL% · Latency: %LAT% ms · request %REQ%</small></p>
</body></html>"""


def fetch(session: str, track: str) -> dict:
    req = urllib.request.Request(
        f"{API}/v1/recommend", data=json.dumps(
            {"session_id": session, "track": track}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def render(session: str = "S123", track: str = "trivago") -> str:
    try:
        body = fetch(session, track)
    except Exception as exc:  # API down → show ops page with error
        return PAGE.replace("%SESSION%", session).replace("%TRACK%", track).replace(
            "%ITEMS%", f"<p>API unreachable: {exc}</p>").replace(
            "%OPS%", "<p>start the stack: <code>docker compose up</code></p>").replace(
            "%MODEL%", "-").replace("%LAT%", "-").replace("%REQ%", "-")
    rows = "".join(
        f"<tr><td>#{i+1}</td><td>{it['item_id']}</td><td>{it['score']}</td></tr>"
        for i, it in enumerate(body.get("items", [])))
    items = f"<table><tr><th>#</th><th>Hotel</th><th>Score</th></tr>{rows}</table>" if rows else "<p>no candidates</p>"
    ops = ("<table><tr><th>Champion</th><th>Challenger</th></tr>"
           "<tr><td>v2 (95%)</td><td>v3 (5%)</td></tr></table>")
    return PAGE.replace("%SESSION%", session).replace("%TRACK%", track).replace(
        "%ITEMS%", items).replace("%OPS%", ops).replace(
        "%MODEL%", body.get("model_version", "-")).replace(
        "%LAT%", str(body.get("latency_ms", "-"))).replace(
        "%REQ%", body.get("request_id", "-"))


if __name__ == "__main__":
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import parse_qs, urlparse

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            html = render(q.get("session", ["S123"])[0], q.get("track", ["trivago"])[0])
            data = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    HTTPServer(("0.0.0.0", 8501), H).serve_forever()
