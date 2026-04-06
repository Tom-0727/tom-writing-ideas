#!/usr/bin/env python3
"""Writing Ideas web app — scores AI-Informer digests and presents topic recommendations."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from scorer import generate_ideas, find_latest_digest, score_digest

DATA_DIR = Path(__file__).resolve().parent / "data"


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_ideas() -> dict:
    """Load cached ideas or regenerate."""
    cache = DATA_DIR / "ideas.json"
    if cache.exists():
        with open(cache, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"generated_at": "", "digest_source": "", "ideas": []}


def refresh_ideas() -> dict:
    """Regenerate ideas from latest digest."""
    ideas = generate_ideas(DATA_DIR / "ideas.json")
    return load_ideas()


HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Writing Ideas — Tom-Blogs-Manager</title>
  <style>
    :root {
      --bg: #f6f3ee;
      --card: rgba(255,255,255,0.92);
      --ink: #1f2831;
      --muted: #6b7580;
      --line: rgba(31,40,49,0.12);
      --accent: #2f7a5f;
      --strong-bg: #d5f2e5; --strong-fg: #186246;
      --moderate-bg: #fef3cd; --moderate-fg: #856404;
      --weak-bg: #f0f0f0; --weak-fg: #6c757d;
    }
    * { box-sizing: border-box; margin: 0; }
    body {
      min-height: 100vh; color: var(--ink);
      font-family: "Space Grotesk","Segoe UI",sans-serif;
      background: linear-gradient(140deg, var(--bg), #eaf0ec);
    }
    .app { max-width: 900px; margin: 0 auto; padding: 28px 16px 60px; }
    header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
    h1 { font-size: 1.8rem; }
    .kicker { text-transform: uppercase; letter-spacing: .09em; color: var(--muted); font-size: 12px; font-weight: 700; margin-bottom: 2px; }
    .meta { color: var(--muted); font-size: 12px; }
    button {
      border: none; border-radius: 10px; padding: 9px 16px;
      font: inherit; font-size: 14px; font-weight: 700;
      color: #fff; background: var(--accent); cursor: pointer;
    }
    button:hover { filter: brightness(.93); }
    .idea-card {
      background: var(--card); border: 1px solid var(--line);
      border-radius: 16px; padding: 20px; margin-bottom: 14px;
      box-shadow: 0 8px 24px rgba(25,38,32,.06);
      transition: transform .12s;
    }
    .idea-card:hover { transform: translateY(-2px); }
    .idea-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 10px; }
    .idea-title { font-size: 1.05rem; font-weight: 700; line-height: 1.35; flex: 1; }
    .idea-title a { color: inherit; text-decoration: none; }
    .idea-title a:hover { color: var(--accent); }
    .badge {
      border-radius: 999px; padding: 4px 12px; font-size: 11px;
      font-weight: 700; white-space: nowrap; flex-shrink: 0;
    }
    .badge.strong { background: var(--strong-bg); color: var(--strong-fg); }
    .badge.moderate { background: var(--moderate-bg); color: var(--moderate-fg); }
    .badge.weak { background: var(--weak-bg); color: var(--weak-fg); }
    .score-total { font-size: 1.6rem; font-weight: 800; color: var(--accent); margin-right: 6px; }
    .score-max { font-size: .85rem; color: var(--muted); }
    .score-bar {
      display: flex; gap: 6px; margin: 10px 0; flex-wrap: wrap;
    }
    .dim {
      flex: 1; min-width: 100px;
      background: #f4f4f2; border-radius: 10px; padding: 8px 10px;
      text-align: center;
    }
    .dim-label { font-size: 11px; color: var(--muted); margin-bottom: 4px; }
    .dim-val { font-size: 1.1rem; font-weight: 700; }
    .idea-meta {
      display: flex; gap: 12px; flex-wrap: wrap; align-items: center;
      margin-top: 10px; font-size: 13px; color: var(--muted);
    }
    .tag {
      background: #eef0f2; border-radius: 6px; padding: 3px 8px;
      font-size: 12px; font-weight: 600;
    }
    .angle {
      margin-top: 10px; padding: 10px 14px;
      background: #f9f7f4; border-left: 3px solid var(--accent);
      border-radius: 0 8px 8px 0; font-size: 13.5px; line-height: 1.5;
      color: #3a4a42;
    }
    .empty {
      text-align: center; padding: 60px 20px;
      color: var(--muted); font-size: 15px;
    }
    @media (max-width: 600px) {
      .score-bar { flex-direction: column; }
      .dim { min-width: unset; }
    }
  </style>
</head>
<body>
  <main class="app">
    <header>
      <div>
        <p class="kicker">Writing Ideas</p>
        <h1>博客选题推荐</h1>
      </div>
      <div style="text-align:right">
        <button onclick="refresh()">刷新评估</button>
        <div id="genMeta" class="meta" style="margin-top:6px"></div>
      </div>
    </header>
    <div id="ideas"></div>
  </main>
<script>
const DIM_LABELS = {
  audience_reach: '受众覆盖',
  distribution_potential: '传播潜力',
  author_differentiation: '作者独特性',
  timeliness: '时效性',
  series_potential: '系列化',
};
const REC_LABELS = { strong: '强烈推荐', moderate: '值得考虑', weak: '优先级低' };

function renderIdea(idea) {
  const s = idea.scores;
  const rec = idea.recommendation;
  const dims = Object.entries(DIM_LABELS).map(([k, label]) => {
    const val = s[k] || 0;
    const color = val >= 4 ? '#186246' : val >= 3 ? '#856404' : '#6c757d';
    return `<div class="dim"><div class="dim-label">${label}</div><div class="dim-val" style="color:${color}">${val}</div></div>`;
  }).join('');

  return `
    <div class="idea-card">
      <div class="idea-header">
        <div class="idea-title"><a href="${idea.url}" target="_blank">${idea.title}</a></div>
        <span class="badge ${rec}">${REC_LABELS[rec] || rec}</span>
      </div>
      <div style="display:flex;align-items:baseline;gap:4px">
        <span class="score-total">${s.total}</span><span class="score-max">/ 25</span>
      </div>
      <div class="score-bar">${dims}</div>
      <div class="angle">${idea.suggested_angle}</div>
      <div class="idea-meta">
        <span class="tag">${idea.content_line}</span>
        <span>来源: ${idea.source}</span>
      </div>
    </div>`;
}

async function loadIdeas() {
  const resp = await fetch('/api/ideas');
  const data = await resp.json();
  const root = document.getElementById('ideas');
  const meta = document.getElementById('genMeta');
  if (!data.ideas || data.ideas.length === 0) {
    root.innerHTML = '<div class="empty">暂无选题推荐，点击"刷新评估"获取最新信息</div>';
    meta.textContent = '';
    return;
  }
  root.innerHTML = data.ideas.map(renderIdea).join('');
  meta.textContent = `数据来源: ${data.digest_source || ''} | 生成时间: ${data.generated_at || ''}`;
}

async function refresh() {
  document.getElementById('ideas').innerHTML = '<div class="empty">正在评估...</div>';
  await fetch('/api/refresh', { method: 'POST' });
  await loadIdeas();
}

loadIdeas();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _json(self, payload, code=200):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, body):
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._html(HTML)
        elif parsed.path == "/api/ideas":
            self._json(load_ideas())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/refresh":
            data = refresh_ideas()
            self._json(data)
        else:
            self._json({"error": "not found"}, 404)


def main():
    parser = argparse.ArgumentParser(description="Writing Ideas web app")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[{utcnow()}] Writing Ideas app at http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
