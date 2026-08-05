#!/usr/bin/env python3
"""
Signals from the Frontier — 수집 파이프라인

  수집 → 정규화 → 키워드 필터 → 중복 제거 → (선택) LLM 요약 → data/radar.json

사용법:
    python scripts/collect.py                 # 수집 + 요약(키 있으면)
    python scripts/collect.py --no-llm        # 요약 없이 수집만
    python scripts/collect.py --dry-run       # 파일 안 쓰고 결과만 출력

의존성:  pip install requests feedparser pyyaml
LLM 요약을 쓰려면:  pip install anthropic  +  환경변수 ANTHROPIC_API_KEY
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from xml.etree import ElementTree as ET

import requests
import yaml

try:
    import feedparser
except ImportError:
    feedparser = None

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "scripts" / "sources.yaml"
OUT = ROOT / "data" / "radar.json"
SEEN = ROOT / "data" / "seen.json"

KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "signals-bot/1.0 (portfolio radar; +https://hbp001.github.io)"}
TIMEOUT = 25


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


# ══════════════════════════════════════════════════════════════
#  데이터 모델
# ══════════════════════════════════════════════════════════════

@dataclass
class Item:
    source: str           # 표시용 소스명 (arXiv, HF, AI타임스 …)
    kind: str             # arxiv | hf | news | cfp
    title: str
    url: str              # 원본 링크 — 사이트에서 클릭 시 이동
    summary: str = ""
    published: str = ""   # ISO8601
    region: str = "global"
    trust: str = "medium"
    authors: list[str] = field(default_factory=list)
    matched: list[str] = field(default_factory=list)
    score: int = 0
    analysis: dict = field(default_factory=dict)   # LLM 결과가 들어가는 자리
    also_covered: list[dict] = field(default_factory=list)  # 같은 주제 다른 출처

    @property
    def key(self) -> str:
        return canonical_key(self.url, self.title)


# ══════════════════════════════════════════════════════════════
#  정규화 유틸
# ══════════════════════════════════════════════════════════════

TRACKING = re.compile(r"^(utm_|fbclid|gclid|mc_|ref$|source$|_hs)", re.I)


def clean_url(url: str) -> str:
    """추적 파라미터를 제거하고 URL을 표준형으로."""
    if not url:
        return ""
    try:
        p = urlparse(url.strip())
    except ValueError:
        return url.strip()
    q = [(k, v) for k, v in parse_qsl(p.query) if not TRACKING.match(k)]
    host = p.netloc.lower().removeprefix("www.")
    path = p.path.rstrip("/") or "/"
    return urlunparse(("https", host, path, "", urlencode(q), ""))


ARXIV_ID = re.compile(r"arxiv\.org/(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5})")


def canonical_key(url: str, title: str) -> str:
    """중복 판정의 1차 기준. arXiv는 버전이 달라도 같은 논문으로 묶는다."""
    m = ARXIV_ID.search(url or "")
    if m:
        return f"arxiv:{m.group(1)}"
    u = clean_url(url)
    if u:
        return f"url:{u}"
    return "title:" + hashlib.sha1(norm_title(title).encode()).hexdigest()[:16]


def norm_title(t: str) -> str:
    """제목 유사도 비교용 정규화 — 기호·공백·대소문자·전각 제거."""
    t = unicodedata.normalize("NFKC", t or "").lower()
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", t)      # [단독] (사진) 같은 머리표 제거
    t = re.sub(r"[^0-9a-z가-힣 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def to_iso(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
            try:
                d = datetime.strptime(value, fmt)
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                return d.isoformat()
            except ValueError:
                continue
        return ""
    try:  # feedparser struct_time
        return datetime(*value[:6], tzinfo=timezone.utc).isoformat()
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════
#  키워드 스코어링
# ══════════════════════════════════════════════════════════════

class Matcher:
    def __init__(self, kw: dict):
        self.core = [k.lower() for k in kw.get("core", [])]
        self.adjacent = [k.lower() for k in kw.get("adjacent", [])]
        self.korean = [k.lower() for k in kw.get("korean", [])]
        self.exclude = [k.lower() for k in kw.get("exclude", [])]

    def score(self, item: Item) -> tuple[int, list[str]]:
        blob = f"{item.title} {item.summary}".lower()
        if any(x in item.title.lower() for x in self.exclude):
            return 0, []

        hits, total = [], 0
        for k in self.core:
            if k in blob:
                hits.append(k); total += 3
        for k in self.adjacent:
            if k in blob:
                hits.append(k); total += 2
        for k in self.korean:
            if k in blob:
                hits.append(k); total += 2

        if not hits:
            return 0, []

        if item.trust == "high":
            total += 2
        if item.kind == "arxiv":
            total += 1
        return total, hits[:5]


# ══════════════════════════════════════════════════════════════
#  수집기
# ══════════════════════════════════════════════════════════════

def fetch_arxiv(cfg: dict, since: datetime) -> list[Item]:
    if not cfg.get("enabled"):
        return []
    out: list[Item] = []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for cat in cfg.get("categories", []):
        try:
            r = requests.get(
                "http://export.arxiv.org/api/query",
                params={
                    "search_query": f"cat:{cat}",
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                    "max_results": cfg.get("max_per_category", 50),
                },
                headers=UA, timeout=TIMEOUT,
            )
            r.raise_for_status()
            root = ET.fromstring(r.text)
        except Exception as e:
            log(f"✗ arXiv {cat}: {e}")
            continue

        n = 0
        for entry in root.findall("a:entry", ns):
            title = " ".join((entry.findtext("a:title", "", ns) or "").split())
            summary = " ".join((entry.findtext("a:summary", "", ns) or "").split())
            link = entry.findtext("a:id", "", ns) or ""
            pub = to_iso(entry.findtext("a:published", "", ns))
            if pub and datetime.fromisoformat(pub) < since:
                continue
            authors = [
                a.findtext("a:name", "", ns)
                for a in entry.findall("a:author", ns)
            ][:4]
            out.append(Item("arXiv", "arxiv", title, link, summary, pub,
                            "global", cfg.get("trust", "high"), authors))
            n += 1
        log(f"✓ arXiv {cat}: {n}")
    return out


def fetch_hf(cfg: dict, since: datetime) -> list[Item]:
    if not cfg.get("enabled"):
        return []
    out: list[Item] = []
    for what in cfg.get("fetch", ["models"]):
        try:
            r = requests.get(
                f"https://huggingface.co/api/{what}",
                params={"sort": "lastModified", "direction": -1,
                        "limit": cfg.get("limit", 40), "full": "true"},
                headers=UA, timeout=TIMEOUT,
            )
            r.raise_for_status()
            rows = r.json()
        except Exception as e:
            log(f"✗ HuggingFace {what}: {e}")
            continue

        n = 0
        for row in rows:
            likes = row.get("likes", 0) or 0
            if likes < cfg.get("min_likes", 0):
                continue
            rid = row.get("id") or row.get("modelId") or ""
            pub = to_iso((row.get("lastModified") or "")[:19] + "Z")
            if pub and datetime.fromisoformat(pub) < since:
                continue
            tags = [t for t in (row.get("tags") or []) if isinstance(t, str)][:12]
            label = "model" if what == "models" else "dataset"
            out.append(Item(
                "Hugging Face", "hf",
                f"{rid} · new {label} (♥ {likes})",
                f"https://huggingface.co/{'datasets/' if what=='datasets' else ''}{rid}",
                " ".join(tags), pub, "global", cfg.get("trust", "medium"),
            ))
            n += 1
        log(f"✓ HuggingFace {what}: {n}")
    return out


def fetch_rss(feeds: list[dict], since: datetime) -> list[Item]:
    if feedparser is None:
        log("✗ feedparser 미설치 — RSS 건너뜀 (pip install feedparser)")
        return []
    out: list[Item] = []
    for f in feeds:
        try:
            resp = requests.get(f["url"], headers=UA, timeout=TIMEOUT)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            if not parsed.entries:
                raise ValueError("항목 0개")
        except Exception as e:
            log(f"✗ {f['name']}: {e}")
            continue

        n = 0
        for e in parsed.entries[:40]:
            pub = to_iso(getattr(e, "published_parsed", None) or
                         getattr(e, "updated_parsed", None))
            if pub and datetime.fromisoformat(pub) < since:
                continue
            raw = getattr(e, "summary", "") or ""
            text = re.sub(r"<[^>]+>", " ", raw)
            out.append(Item(
                f["name"], "news",
                " ".join((getattr(e, "title", "") or "").split()),
                getattr(e, "link", "") or "",
                " ".join(text.split())[:600], pub,
                f.get("region", "global"), f.get("trust", "medium"),
            ))
            n += 1
        log(f"✓ {f['name']}: {n}")
    return out


def build_cfp(confs: list[dict], now: datetime) -> list[Item]:
    out: list[Item] = []
    for c in confs:
        raw = c.get("deadline")
        try:
            # YAML은 2026-11-14 형태를 date 객체로 자동 변환한다 — 둘 다 받는다
            if isinstance(raw, datetime):
                dl = raw if raw.tzinfo else raw.replace(tzinfo=KST)
            elif hasattr(raw, "year"):                      # datetime.date
                dl = datetime(raw.year, raw.month, raw.day, tzinfo=KST)
            else:
                dl = datetime.strptime(str(raw), "%Y-%m-%d").replace(tzinfo=KST)
        except Exception as e:
            log(f"✗ CFP {c.get('name','?')}: 날짜 형식 오류 ({raw}) — {e}")
            continue
        days = (dl - now).days
        if not (0 <= days <= 120):
            continue
        it = Item(
            "CFP", "cfp",
            f"{c['name']} — submission deadline",
            c.get("url", ""), f"D-{days}",
            dl.isoformat(), "global", "high",
        )
        it.score = 10 + max(0, 120 - days) // 10   # 임박할수록 위로
        it.matched = ["deadline"]
        out.append(it)
    log(f"✓ CFP: {len(out)}")
    return out


# ══════════════════════════════════════════════════════════════
#  중복 제거 — 4단계
# ══════════════════════════════════════════════════════════════

def dedupe(items: list[Item], seen: dict, ttl_days: int) -> tuple[list[Item], int, int]:
    """
    1) 이번 수집분 내부: 같은 canonical key 병합
    2) 이번 수집분 내부: 제목 유사도 0.86 이상이면 같은 사건으로 병합
       (arXiv 논문 + 그 논문을 다룬 기사 → 신뢰도 높은 쪽을 대표로, 나머지는 also_covered)
    3) 과거 발행분(seen.json)과 대조해 이미 나간 것 제거
    4) 오래된 seen 기록 정리
    """
    now = datetime.now(timezone.utc)

    # ── 1단계: 정확 키 병합
    by_key: dict[str, Item] = {}
    exact = 0
    for it in sorted(items, key=lambda x: -x.score):
        k = it.key
        if k in by_key:
            exact += 1
            merge_into(by_key[k], it)
        else:
            by_key[k] = it
    stage1 = list(by_key.values())

    # ── 2단계: 제목 유사도 병합
    kept: list[Item] = []
    fuzzy = 0
    for it in sorted(stage1, key=lambda x: (-trust_rank(x), -x.score)):
        nt = norm_title(it.title)
        if len(nt) < 12:
            kept.append(it)
            continue
        dup_of = None
        for other in kept:
            if similar(nt, norm_title(other.title)) >= 0.86:
                dup_of = other
                break
        if dup_of is not None:
            fuzzy += 1
            merge_into(dup_of, it)
        else:
            kept.append(it)

    # ── 3단계: 과거 발행분 제외
    fresh = [it for it in kept if it.key not in seen]

    # ── 4단계: seen 갱신 + 만료 정리
    cutoff = now - timedelta(days=ttl_days)
    for k, v in list(seen.items()):
        try:
            if datetime.fromisoformat(v) < cutoff:
                del seen[k]
        except Exception:
            del seen[k]
    for it in fresh:
        seen[it.key] = now.isoformat()

    return fresh, exact, fuzzy


def trust_rank(it: Item) -> int:
    base = {"arxiv": 3, "cfp": 3, "hf": 2, "news": 1}.get(it.kind, 1)
    return base + (1 if it.trust == "high" else 0)


def merge_into(keep: Item, drop: Item) -> None:
    """버리는 쪽의 출처를 '이 소식도 함께 다룸'으로 남긴다 — 정보는 잃지 않는다."""
    if drop.url and clean_url(drop.url) != clean_url(keep.url):
        entry = {"source": drop.source, "url": drop.url}
        if entry not in keep.also_covered and len(keep.also_covered) < 4:
            keep.also_covered.append(entry)
    keep.score = max(keep.score, drop.score)
    for m in drop.matched:
        if m not in keep.matched and len(keep.matched) < 6:
            keep.matched.append(m)
    if not keep.summary and drop.summary:
        keep.summary = drop.summary


# ══════════════════════════════════════════════════════════════
#  LLM 요약·분석 (선택)
# ══════════════════════════════════════════════════════════════

PROMPT = """You are the research assistant of Hyobin Park, an AI researcher working on
vision-language models, controllable generation, world models and physical AI —
especially applying them to real industrial and scientific processes.

For the item below produce STRICT JSON, no markdown fence:
{{
  "headline_ko": "한국어 한 문장 요약 (40자 이내, 명사형 종결)",
  "what_ko":     "무엇을 했는지 2문장 이내 한국어",
  "why_ko":      "박효빈의 연구 관점에서 왜 볼 만한지 1문장 한국어",
  "relevance":   1-5 정수 (5 = 지금 하는 연구에 직접 영향),
  "topics":      ["최대 3개 영어 소문자 태그"]
}}

Title: {title}
Source: {source}
Body: {body}"""


def analyze(items: list[Item], model: str) -> int:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        log("· ANTHROPIC_API_KEY 없음 — 요약 단계 건너뜀")
        return 0
    try:
        import anthropic
    except ImportError:
        log("· anthropic 패키지 없음 — 요약 단계 건너뜀 (pip install anthropic)")
        return 0

    client = anthropic.Anthropic(api_key=key)
    done = 0
    for it in items:
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": PROMPT.format(
                        title=it.title, source=it.source, body=it.summary[:2500]),
                }],
            )
            text = msg.content[0].text.strip()
            text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
            data = json.loads(text)
            it.analysis = data
            if isinstance(data.get("relevance"), int):
                it.score += data["relevance"] * 2   # 요약 결과를 정렬에 반영
            done += 1
        except Exception as e:
            log(f"· 요약 실패 ({it.title[:40]}…): {e}")
    log(f"✓ LLM 요약: {done}/{len(items)}")
    return done


# ══════════════════════════════════════════════════════════════
#  메인
# ══════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true", help="LLM 요약 건너뛰기")
    ap.add_argument("--dry-run", action="store_true", help="파일 쓰지 않기")
    ap.add_argument("--model", default="claude-sonnet-4-6")
    args = ap.parse_args()

    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    outcfg = cfg.get("output", {})
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=outcfg.get("lookback_days", 7))

    print("\n▸ 수집")
    raw: list[Item] = []
    raw += fetch_arxiv(cfg.get("arxiv", {}), since)
    raw += fetch_hf(cfg.get("huggingface", {}), since)
    raw += fetch_rss(cfg.get("rss", []), since)
    cfps = build_cfp(cfg.get("conferences", []), now.astimezone(KST))
    print(f"  → 원본 {len(raw)}건")

    print("\n▸ 키워드 필터")
    matcher = Matcher(cfg.get("keywords", {}))
    scored: list[Item] = []
    for it in raw:
        s, hits = matcher.score(it)
        if s >= outcfg.get("min_score", 3):
            it.score, it.matched = s, hits
            scored.append(it)
    print(f"  → 통과 {len(scored)}건")

    print("\n▸ 중복 제거")
    seen = {}
    if SEEN.exists():
        try:
            seen = json.loads(SEEN.read_text(encoding="utf-8"))
        except Exception:
            seen = {}
    fresh, exact, fuzzy = dedupe(scored, seen, outcfg.get("seen_ttl_days", 90))
    print(f"  → 동일 링크 병합 {exact} · 유사 제목 병합 {fuzzy} · 기발행 제외 "
          f"{len(scored)-exact-fuzzy-len(fresh)}")
    print(f"  → 신규 {len(fresh)}건")

    final = sorted(fresh + cfps, key=lambda x: -x.score)[:outcfg.get("max_items", 40)]

    if not args.no_llm:
        print("\n▸ LLM 요약·분석")
        analyze([i for i in final if i.kind != "cfp"], args.model)
        final.sort(key=lambda x: -x.score)

    payload = {
        "generated_at": now.astimezone(KST).isoformat(),
        "count": len(final),
        "stats": {
            "raw": len(raw), "passed": len(scored),
            "merged_exact": exact, "merged_fuzzy": fuzzy, "new": len(fresh),
        },
        "items": [asdict(i) for i in final],
    }

    if args.dry_run:
        print("\n▸ DRY RUN — 파일을 쓰지 않습니다\n")
        for i in final[:12]:
            tag = f"[{i.source}]".ljust(18)
            print(f"  {tag} {i.score:>3}  {i.title[:74]}")
            print(f"  {'':18}      {i.url}")
            if i.also_covered:
                print(f"  {'':18}      ↳ 함께 다룸: "
                      f"{', '.join(a['source'] for a in i.also_covered)}")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    SEEN.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ {OUT.relative_to(ROOT)} 저장 — {len(final)}건\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
