import os
import re
import time
import socket
import requests
import feedparser
import pandas as pd
from bs4 import BeautifulSoup
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(exist_ok=True)

STOPWORDS = {
    "the","and","for","with","from","this","that","your","you","are","was","were","will","have","has","had",
    "into","about","what","when","where","how","why","can","not","but","they","their","our","out","new","using",
    "use","used","more","than","then","also","just","like","after","before","over","under","all","one","two",
    "paper","show","shows","build","building","launch","released","release","based","first","last","best",
    "ai","llm","llms","model","models","openai","google","microsoft","meta","anthropic"
}

STRONG_WORDS = [
    "agent", "agents", "context", "memory", "runtime", "mesh", "fabric", "graph", "eval",
    "browser", "workflow", "orchestration", "synthetic", "tool", "tools", "kernel",
    "canvas", "forge", "stack", "router", "guard", "trust", "voice", "robot", "autonomy"
]

def fetch_hacker_news():
    since = int((datetime.now(timezone.utc) - timedelta(hours=48)).timestamp())
    url = f"https://hn.algolia.com/api/v1/search_by_date?tags=story&numericFilters=created_at_i>{since}&hitsPerPage=100"
    data = requests.get(url, timeout=25).json()
    texts = []
    for hit in data.get("hits", []):
        title = hit.get("title") or ""
        if any(k in title.lower() for k in ["ai", "agent", "llm", "model", "openai", "claude", "context", "robot", "gpu"]):
            texts.append(title)
    return texts

def fetch_arxiv():
    url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG&sortBy=submittedDate&sortOrder=descending&max_results=75"
    feed = feedparser.parse(url)
    texts = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=96)
    for entry in feed.entries:
        try:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except Exception:
            published = datetime.now(timezone.utc)
        if published >= cutoff:
            summary = BeautifulSoup(entry.summary, "html.parser").get_text(" ")
            texts.append(entry.title + " " + summary[:700])
    return texts

def fetch_github_trending():
    url = "https://github.com/trending?since=daily"
    html = requests.get(url, timeout=25, headers={"User-Agent": "AI Opportunity Hunter"}).text
    soup = BeautifulSoup(html, "html.parser")
    texts = []
    for article in soup.select("article.Box-row"):
        title = article.select_one("h2")
        desc = article.select_one("p")
        line = ""
        if title:
            line += title.get_text(" ", strip=True) + " "
        if desc:
            line += desc.get_text(" ", strip=True)
        if any(k in line.lower() for k in ["ai", "llm", "agent", "model", "rag", "inference", "robot"]):
            texts.append(line)
    return texts

def clean_text(text):
    return re.sub(r"[^a-zA-Z0-9\s-]", " ", text.lower())

def extract_phrases(texts):
    phrases = Counter()
    for t in texts:
        words = [w for w in clean_text(t).split() if 2 < len(w) < 18 and w not in STOPWORDS]
        for n in [2, 3]:
            for i in range(len(words)-n+1):
                gram = words[i:i+n]
                joined = "".join(gram)
                if 7 <= len(joined) <= 22 and not any(x in STOPWORDS for x in gram):
                    phrases[" ".join(gram)] += 1
    return phrases

def domainize(phrase, tld):
    return re.sub(r"[^a-z0-9]", "", phrase.lower()) + tld

def rough_domain_status(domain):
    try:
        socket.gethostbyname(domain)
        return "taken_or_active"
    except socket.gaierror:
        return "maybe_available"
    except Exception:
        return "unknown"

def brand_score(phrase, mentions):
    compact = phrase.replace(" ", "")
    score = mentions * 8
    for w in STRONG_WORDS:
        if w in phrase:
            score += 9
    if 8 <= len(compact) <= 14:
        score += 18
    elif 15 <= len(compact) <= 20:
        score += 10
    if len(phrase.split()) == 2:
        score += 8
    if any(ch.isdigit() for ch in compact):
        score -= 15
    return max(0, min(100, int(score)))

def telegram_send(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}, timeout=20)
    return True

def main():
    sources = {
        "Hacker News": fetch_hacker_news,
        "arXiv": fetch_arxiv,
        "GitHub Trending": fetch_github_trending,
    }

    all_texts = []
    source_counts = {}
    for name, fn in sources.items():
        try:
            texts = fn()
            source_counts[name] = len(texts)
            all_texts.extend(texts)
        except Exception as e:
            source_counts[name] = f"failed: {e}"

    phrases = extract_phrases(all_texts)

    rows = []
    for phrase, mentions in phrases.most_common(250):
        for tld in [".com", ".ai", ".io"]:
            domain = domainize(phrase, tld)
            if len(domain) > 32:
                continue
            status = rough_domain_status(domain)
            rows.append({
                "phrase": phrase,
                "domain": domain,
                "tld": tld,
                "rough_status": status,
                "mentions": mentions,
                "score": brand_score(phrase, mentions),
            })
            time.sleep(0.02)

    df = pd.DataFrame(rows)
    if df.empty:
        report = "# AI Opportunity Hunter\n\nBugün yeterli aday bulunamadı."
        (REPORT_DIR/"latest_report.md").write_text(report, encoding="utf-8")
        return

    df = df.sort_values(["score", "mentions"], ascending=False).drop_duplicates("domain")
    df.to_csv(REPORT_DIR/"domain_candidates.csv", index=False)

    maybe = df[df["rough_status"].isin(["maybe_available", "unknown"])].head(20)
    top = maybe if not maybe.empty else df.head(20)

    lines = []
    lines.append("# 🚀 AI Opportunity Hunter")
    lines.append("")
    lines.append(f"Rapor zamanı: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Kaynak sayıları")
    for k, v in source_counts.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Bugünün domain adayları")
    lines.append("")
    lines.append("| # | Domain | Skor | Terim | Durum |")
    lines.append("|---|--------|------|-------|-------|")
    for i, row in enumerate(top.itertuples(index=False), 1):
        lines.append(f"| {i} | {row.domain} | {row.score}/100 | {row.phrase} | {row.rough_status} |")
    lines.append("")
    lines.append("> Not: `maybe_available` kesin müsait anlamına gelmez. Satın almadan önce Namecheap, Cloudflare Registrar veya GoDaddy'den tekrar kontrol edin.")

    report = "\n".join(lines)
    (REPORT_DIR/"latest_report.md").write_text(report, encoding="utf-8")

    msg = "🚀 *AI Opportunity Hunter*\n\n"
    for i, row in enumerate(top.head(10).itertuples(index=False), 1):
        msg += f"{i}. `{row.domain}` — {row.score}/100\n"
    msg += "\nDetaylı rapor GitHub repo içinde: reports/latest_report.md"
    telegram_send(msg)

if __name__ == "__main__":
    main()
