"""Flask dashboard for Agent Guard detection log.

Run: `agent-guard-dashboard` (after pip install agent-guard-plugins[dashboard])
Or:  `python -m agent_guard_plugins.dashboard.app`

Reads ~/.agent-guard/detections.sqlite (written by guard()).
"""
from __future__ import annotations
import pathlib
import sqlite3
import time
from collections import Counter

DB = pathlib.Path.home() / ".agent-guard" / "detections.sqlite"


HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Agent Guard</title>
<style>
body { font: 14px/1.4 -apple-system, system-ui, sans-serif; margin: 24px; max-width: 1200px; color: #222; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 16px; margin-top: 28px; }
.row { display:grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin: 16px 0; }
.card { background:#f7f7f9; border-radius:8px; padding:14px 18px; }
.card .v { font-size: 28px; font-weight: 600; }
.card.flag .v { color: #c0392b; }
table { width:100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #eee; vertical-align: top; }
th { background: #fafafa; }
.flagged { background: #fff5f5; }
.txt { max-width: 600px; overflow-x: auto; white-space: pre-wrap; font-family: -apple-system, system-ui; }
.tag { display:inline-block; padding: 1px 6px; border-radius: 4px; background: #ececef; font-size: 11px; margin-right: 3px; }
.bar { display:flex; gap:8px; align-items:baseline; }
.bar .label { width: 140px; }
.bar .fill { background:#ddd; height:14px; border-radius:3px; }
</style></head>
<body>
<h1>Agent Guard — detections</h1>
<div class="row">
  <div class="card"><div>Total inputs</div><div class="v">{{ stats.total }}</div></div>
  <div class="card flag"><div>Flagged as injection</div><div class="v">{{ stats.flagged }}</div></div>
  <div class="card"><div>Distinct sources</div><div class="v">{{ stats.sources|length }}</div></div>
</div>

<h2>OWASP LLM categories detected</h2>
{% for k, v in owasp.most_common() %}
<div class="bar"><div class="label">{{ k }}</div><div class="fill" style="width:{{ v*3 }}px"></div><div>{{ v }}</div></div>
{% endfor %}

<h2>MITRE ATLAS techniques detected</h2>
{% for k, v in atlas.most_common() %}
<div class="bar"><div class="label">{{ k }}</div><div class="fill" style="width:{{ v*3 }}px"></div><div>{{ v }}</div></div>
{% endfor %}

<h2>Last 200 inputs</h2>
<table>
<tr><th>Time</th><th>Source</th><th>P(inj)</th><th>Labels</th><th>Input</th></tr>
{% for r in rows %}
<tr class="{% if r.flagged %}flagged{% endif %}">
  <td>{{ fmt(r.ts) }}</td>
  <td>{{ r.source }}</td>
  <td>{{ "%.2f"|format(r.prob) }}</td>
  <td>
    {% for o in (r.owasp or '').split(',') if o %}<span class="tag">{{ o }}</span>{% endfor %}
    {% for a in (r.atlas or '').split(',') if a %}<span class="tag">{{ a }}</span>{% endfor %}
  </td>
  <td><div class="txt">{{ r.text }}</div></td>
</tr>
{% endfor %}
</table>
</body></html>"""


def _build_app():
    from flask import Flask, jsonify, render_template_string
    app = Flask(__name__)

    def fmt(ts):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

    def db():
        c = sqlite3.connect(str(DB))
        c.row_factory = sqlite3.Row
        return c

    @app.route("/")
    def index():
        if not DB.exists():
            return "<h1>No detections yet</h1><p>Run something through agent_guard_plugins.guard() first.</p>"
        c = db()
        rows = c.execute("SELECT * FROM detections ORDER BY ts DESC LIMIT 200").fetchall()
        stats = {
            "total": c.execute("SELECT COUNT(*) FROM detections").fetchone()[0],
            "flagged": c.execute("SELECT COUNT(*) FROM detections WHERE flagged=1").fetchone()[0],
            "sources": Counter(r["source"] for r in c.execute("SELECT source FROM detections").fetchall()),
        }
        owasp, atlas = Counter(), Counter()
        for r in c.execute("SELECT owasp, atlas FROM detections WHERE flagged=1").fetchall():
            if r["owasp"]:
                owasp.update(r["owasp"].split(","))
            if r["atlas"]:
                atlas.update(r["atlas"].split(","))
        c.close()
        return render_template_string(HTML, rows=rows, stats=stats, owasp=owasp, atlas=atlas, fmt=fmt)

    @app.route("/api/stats")
    def api_stats():
        if not DB.exists():
            return jsonify({"total": 0, "flagged": 0})
        c = db()
        total = c.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
        flagged = c.execute("SELECT COUNT(*) FROM detections WHERE flagged=1").fetchone()[0]
        c.close()
        return jsonify({"total": total, "flagged": flagged})

    return app


def main():
    """Console script entry point: `agent-guard-dashboard`."""
    import argparse
    parser = argparse.ArgumentParser(description="Agent Guard detection dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=5174, type=int)
    args = parser.parse_args()
    app = _build_app()
    print(f"agent-guard dashboard at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
