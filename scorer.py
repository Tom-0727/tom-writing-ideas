#!/usr/bin/env python3
"""Score AI-Informer digest items against the blog topic recommendation framework."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

# Tom's expertise domains — used for author differentiation scoring
AUTHOR_STRENGTHS = {
    "agent", "agents", "ai agent", "agent engineering", "agent architecture",
    "claude code", "anthropic", "claude", "memory", "context", "learning",
    "human in the loop", "human-ai", "ai employee", "ai workers",
    "openclaw", "researcher", "skill", "skills", "workflow", "automation",
    "solo founder", "one man", "indie", "solopreneur",
    "llm application", "ai startup", "ai business",
}

WEAK_DOMAINS = {
    "edge ai", "on device", "mobile ai", "image generation", "video generation",
    "diffusion", "stable diffusion", "midjourney", "text to image", "text to video",
    "model training", "pretraining", "fine-tuning", "rlhf",
    "robotics", "self-driving", "autonomous vehicle",
    "gaming", "game ai",
}

# High-value signal keywords
HIGH_VALUE_SIGNALS = {
    "agent platform", "agent infrastructure", "ai pricing", "ai business model",
    "solo founder", "one person", "ai workforce", "digital worker",
    "claude code", "anthropic", "openclaw",
    "agent framework", "agent tool", "open source agent",
    "context engineering", "agent memory", "agent learning",
}


def score_item(item: dict) -> dict:
    """Score a single digest item on 5 dimensions (1-5 each, max 25)."""
    title = (item.get("title") or "").lower()
    summary = (item.get("raw_item", {}).get("summary") or "").lower()
    readme = (item.get("raw_item", {}).get("readme_excerpt") or "").lower()
    text = f"{title} {summary} {readme}"
    signals = item.get("matched_signals", [])
    source = item.get("source", "")
    raw = item.get("raw_item", {})

    # 1. Audience Reach (1-5)
    audience_score = 2
    # Broad appeal topics
    if any(kw in text for kw in ["solo founder", "one person", "startup", "business model", "pricing"]):
        audience_score = 5
    elif any(kw in text for kw in ["agent platform", "ai workforce", "ai employee", "openclaw", "anthropic"]):
        audience_score = 4
    elif any(kw in text for kw in ["agent", "framework", "architecture", "engineering"]):
        audience_score = 3

    # 2. Distribution Potential (1-5)
    dist_score = 2
    hn_score = raw.get("score", 0) if source == "hacker-news" else 0
    if hn_score > 400 or any(kw in text for kw in ["pricing", "pay up", "solo founder", "billion"]):
        dist_score = 5
    elif hn_score > 200 or source == "rundown-ai":
        dist_score = 4
    elif hn_score > 50 or source == "product-hunt":
        dist_score = 3

    # 3. Author Differentiation (1-5)
    author_score = 2
    strength_matches = sum(1 for kw in AUTHOR_STRENGTHS if kw in text)
    weak_matches = sum(1 for kw in WEAK_DOMAINS if kw in text)
    if weak_matches > 0:
        author_score = max(1, 2 - weak_matches)
    elif strength_matches >= 3:
        author_score = 5
    elif strength_matches >= 2:
        author_score = 4
    elif strength_matches >= 1:
        author_score = 3

    # Special boost: OpenClaw or Claude Code — Tom is a direct user
    if "openclaw" in text or "claude code" in text:
        author_score = 5

    # 4. Timeliness (1-5)
    time_score = 3  # default: medium window
    if any(kw in text for kw in ["pay up", "pricing change", "announces", "launches", "released"]):
        time_score = 5
    elif any(kw in text for kw in ["trend", "future", "prediction"]):
        time_score = 4
    elif any(kw in text for kw in ["tutorial", "guide", "how to", "demystify"]):
        time_score = 1  # evergreen

    # 5. Series Potential (1-5)
    series_score = 2
    if any(kw in text for kw in ["solo founder", "ai workforce", "ai employee", "one man"]):
        series_score = 4  # can be serialized with personal practice updates
    elif any(kw in text for kw in ["framework", "architecture", "platform"]):
        series_score = 3
    elif any(kw in text for kw in ["pricing", "pay up"]):
        series_score = 3  # can follow up with alternatives, impact analysis

    total = audience_score + dist_score + author_score + time_score + series_score

    # Generate suggested angle
    angle = _suggest_angle(text, author_score)

    # Determine content line
    content_line = _classify_content_line(text)

    return {
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "source": source,
        "scores": {
            "audience_reach": audience_score,
            "distribution_potential": dist_score,
            "author_differentiation": author_score,
            "timeliness": time_score,
            "series_potential": series_score,
            "total": total,
        },
        "content_line": content_line,
        "suggested_angle": angle,
        "recommendation": "strong" if total >= 20 else "moderate" if total >= 15 else "weak",
    }


def _suggest_angle(text: str, author_score: int) -> str:
    if "openclaw" in text and "pay" in text:
        return "作为OpenClaw的真实用户，从亲历者视角分析这次定价变化对独立开发者意味着什么，延伸到AI基础设施的商业模式演变"
    if "solo founder" in text or "one person" in text or "billion" in text:
        return "从'One Man, Many Agents'的实践出发，用自己构建AI员工体系的经验，讨论AI如何改变个人的能力边界"
    if author_score >= 4 and ("agent" in text or "claude" in text):
        return "从工程实践角度分享一手体验和判断，突出独特洞察"
    if "framework" in text or "open source" in text:
        return "代码级拆解 + 对自建系统的参考价值分析"
    return "结合行业趋势和个人视角，提供独特分析"


def _classify_content_line(text: str) -> str:
    if any(kw in text for kw in ["pricing", "business", "founder", "startup", "trend", "market",
                                  "pay up", "billion", "solo", "industry", "funding", "valuation",
                                  "acquisition", "ipo", "revenue", "superapp"]):
        return "行业洞察"
    if any(kw in text for kw in ["tool", "workflow", "automation", "how to", "tutorial"]):
        return "实用工具"
    return "技术深度"


def score_digest(digest_path: str | Path) -> list[dict]:
    """Score all items in a filtered.json digest file."""
    path = Path(digest_path)
    if path.is_dir():
        path = path / "filtered.json"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    shortlist = data.get("shortlist", [])
    scored = [score_item(item) for item in shortlist]
    scored.sort(key=lambda x: x["scores"]["total"], reverse=True)
    return scored


def find_latest_digest() -> Path | None:
    """Find the latest AI-Informer digest directory."""
    base = Path("/home/ubuntu/agents/ai-informer/Runtime/digests")
    latest_file = base / "LATEST_DAILY_READY"
    if latest_file.exists():
        target = latest_file.read_text().strip()
        p = Path(target)
        if p.exists():
            return p
    # Fallback: find most recent directory
    dirs = sorted([d for d in base.iterdir() if d.is_dir() and d.name.startswith("2")], reverse=True)
    return dirs[0] if dirs else None


def generate_ideas(output_path: str | Path | None = None) -> list[dict]:
    """Main entry: find latest digest, score, and optionally save."""
    digest_dir = find_latest_digest()
    if not digest_dir:
        return []

    scored = score_digest(digest_dir)

    result = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "digest_source": str(digest_dir),
        "ideas": scored,
    }

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    return scored


if __name__ == "__main__":
    ideas = generate_ideas("data/ideas.json")
    for idea in ideas:
        s = idea["scores"]
        print(f"[{s['total']}/25] [{idea['recommendation']}] {idea['title']}")
        print(f"  内容线: {idea['content_line']} | 角度: {idea['suggested_angle'][:50]}...")
        print()
