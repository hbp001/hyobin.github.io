"""Public metadata collection and fail-closed reviewed-feed builder. Standard library only."""
import argparse
import shutil
import hashlib
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {
    'agents': ('AI 에이전트·자기개선', ('agent', 'self-improv', 'recursive', 'memory')),
    'trust': ('신뢰성·평가·안전', ('trust', 'evaluat', 'safety', 'benchmark', 'alignment')),
    'multimodal': ('멀티모달·VLM', ('multimodal', 'vision-language', 'vlm', 'embodied')),
    'generation': ('생성 모델', ('diffusion', 'generative', 'generation', 'world model')),
    'training': ('학습·최적화', ('optimization', 'training', 'reinforcement', 'fine-tun')),
    'mlops': ('MLOps·배포', ('inference', 'deployment', 'serving', 'compression', 'mlops')),
}
ARXIV = 'https://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.CV+OR+cat:cs.LG&sortBy=submittedDate&sortOrder=descending&max_results=60'
FEEDS = [(ARXIV, 'arxiv'), ('https://openai.com/news/rss.xml', 'official')]
NS = {'a': 'http://www.w3.org/2005/Atom'}


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(url):
    p = urlsplit(url)
    if p.username or p.password or p.port or p.query or p.fragment:
        raise ValueError('URL must be canonical')
    if p.scheme not in ('http', 'https'):
        raise ValueError('Unsafe scheme')
    if p.hostname in ('arxiv.org', 'export.arxiv.org'):
        m = re.fullmatch(r'/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?', p.path)
        if m:
            return 'https://arxiv.org/abs/' + m[1]
    if p.scheme == 'https' and p.hostname == 'openai.com' and re.fullmatch(r'/index/[a-z0-9-]+/?', p.path):
        return 'https://openai.com' + p.path.rstrip('/') + '/'
    raise ValueError('Source is not allowlisted')


def day(value):
    from email.utils import parsedate_to_datetime
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        raise ValueError('Date must include timezone')
    if dt > datetime.now(timezone.utc):
        raise ValueError('Future publication date')
    return dt.date().isoformat()


def clean(value):
    return ' '.join(value.split())


def fingerprint(record):
    return hashlib.sha256(json.dumps({k: record[k] for k in ('url', 'title', 'published')}, sort_keys=True).encode()).hexdigest()


def parse_feed(body, kind):
    root = ET.fromstring(body)
    rows = []
    entries = root.findall('a:entry', NS) if kind == 'arxiv' else root.findall('./channel/item')
    for entry in entries:
        try:
            if kind == 'arxiv':
                url = entry.findtext('a:id', '', NS)
                title = entry.findtext('a:title', '', NS)
                published = entry.findtext('a:published', '', NS)
            else:
                url = entry.findtext('link', '')
                title = entry.findtext('title', '')
                published = entry.findtext('pubDate', '')
            record = dict(url=canonical(url), title=clean(title), published=day(published), source=kind)
            if not record['title'] or len(record['title']) > 500:
                continue
            record['fingerprint'] = fingerprint(record)
            record['categories'] = [key for key, (_, words) in CATEGORIES.items() if any(w in title.lower() for w in words)]
            record['collected_at'] = now()
            record['verification'] = 'unreviewed'
            rows.append(record)
        except (ValueError, TypeError):
            continue
    if not entries:
        raise ValueError('Empty or unsupported feed')
    return rows


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never follow a feed redirect outside the exact public source hosts.
        if urlsplit(newurl).scheme != 'https' or urlsplit(newurl).hostname not in ('export.arxiv.org', 'openai.com'):
            raise ValueError('Unapproved redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'HyobinPortfolio-Trends/1.0 (public metadata only)'})
    with urllib.request.build_opener(SafeRedirect).open(req, timeout=30) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError('Source exceeds metadata size limit')
    return data


def collect():
    rows = {}
    for url, kind in FEEDS:
        for record in parse_feed(fetch(url), kind):
            if record['categories']:
                rows.setdefault(record['url'], record)
        time.sleep(3)  # Respect arXiv API pacing.
    if not rows:
        raise ValueError('No candidates; nothing written')
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat()
    return sorted((r for r in rows.values() if r['published'] >= cutoff), key=lambda r: (r['published'], r['url']), reverse=True)[:60]


def verify_sources(reviews):
    """Fetch independently at build time; collection does not grant publication."""
    found = {}
    ids = [canonical(r['url']).rsplit('/', 1)[-1] for r in reviews if r.get('source') == 'arxiv']
    if ids:
        if len(ids) > 100:
            raise ValueError('Review batch exceeds 100')
        for r in parse_feed(fetch('https://export.arxiv.org/api/query?max_results=100&id_list=' + ','.join(ids)), 'arxiv'):
            found[r['url']] = r
        time.sleep(3)
    if any(r.get('source') == 'official' for r in reviews):
        for r in parse_feed(fetch(FEEDS[1][0]), 'official'):
            found[r['url']] = r
    return found


def build(reviews, observed):
    output, seen = [], set()
    for r in reviews:
        url = canonical(r['url'])
        titlekey = re.sub(r'\W+', '', r['title']).casefold()
        if url in seen or titlekey in seen:
            raise ValueError('Duplicate URL or title')
        seen.update((url, titlekey))
        if r.get('verification') != 'verified' or r.get('authorship') != 'reading-note':
            raise ValueError('Unverified or invalid attribution')
        for field in ('title', 'summary', 'limitations', 'interview_question', 'application_idea', 'reviewed_at', 'evidence_url', 'collected_at'):
            if not isinstance(r.get(field), str) or not r[field].strip():
                raise ValueError('Missing field: ' + field)
        day(r['collected_at']); day(r['reviewed_at'])
        day(r['published'] + 'T00:00:00Z')
        if not r.get('categories') or any(c not in CATEGORIES for c in r['categories']):
            raise ValueError('Invalid category')
        for f in ('summary', 'limitations', 'interview_question', 'application_idea'):
            if len(r[f]) > 600 or '<' in r[f] or '>' in r[f]:
                raise ValueError('Use short plain-text original notes')
        if r.get('source') not in ('arxiv', 'official'):
            raise ValueError('Invalid source')
        evidence = urlsplit(r['evidence_url'])
        if evidence.scheme != 'https' or evidence.hostname != urlsplit(url).hostname or evidence.username or evidence.password or evidence.port:
            raise ValueError('Evidence must be on the original source')
        source = observed.get(url)
        if not source or fingerprint(r) != fingerprint(source):
            raise ValueError('Original missing or title/date mismatch: ' + url)
        if source['source'] != r['source']:
            raise ValueError('Source type mismatch')
        output.append({**r, 'url': url, 'source_checked_at': now()})
    return {'schema_version': 1, 'generated_at': now(), 'count': len(output), 'items': output}


def digest(payload):
    # Verification/collection timestamps do not trigger repeated publication.
    stable = [{k: v for k, v in r.items() if k not in ('collected_at', 'source_checked_at', 'fingerprint')}
              for r in payload['items']]
    return hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def assemble(reviews, candidates, observed, previous=None):
    payload = build(reviews, observed)
    for record in payload['items']:
        record['commentary_review'] = 'reviewed'
        record['verification'] = 'metadata-verified'
    seen_urls = {r['url'] for r in payload['items']}
    seen_titles = {re.sub(r'\W+', '', r['title']).casefold() for r in payload['items']}
    previous_by_url = {r['url']: r for r in (previous or {}).get('items', [])}
    for candidate in candidates:
        url = canonical(candidate['url'])
        titlekey = re.sub(r'\W+', '', candidate['title']).casefold()
        if url in seen_urls or titlekey in seen_titles:
            continue
        source = observed.get(url)
        if not source or fingerprint(candidate) != fingerprint(source) or candidate['source'] != source['source']:
            raise ValueError('Candidate metadata mismatch: ' + url)
        if not candidate.get('categories') or any(c not in CATEGORIES for c in candidate['categories']):
            raise ValueError('Invalid candidate category')
        # No generated abstract, interpretation, interview answer, or achievement.
        record = {k: candidate[k] for k in ('url', 'title', 'source', 'published', 'categories', 'collected_at')}
        old = previous_by_url.get(url)
        if old and fingerprint(old) == fingerprint(record):
            day(old['collected_at'])
            record['collected_at'] = old['collected_at']
        record.update(verification='metadata-verified', commentary_review='not-reviewed',
                      authorship='source-metadata', source_checked_at=now())
        payload['items'].append(record)
        seen_urls.add(url); seen_titles.add(titlekey)
    payload['count'] = len(payload['items'])
    payload['content_digest'] = digest(payload)
    return payload


def stage_site(root, destination, payload):
    # A complete static checkout is required; never deploy a partial local fixture.
    if not (root / 'images/profile-1.jpg.jpg').is_file():
        raise ValueError('Original profile image missing; refuse partial-site deployment')
    if destination.resolve().is_relative_to(root.resolve()):
        raise ValueError('Site staging must be outside source tree')
    destination.mkdir(parents=True, exist_ok=False)
    # Explicit public site assets only; never ship scripts, config, candidates, .git or reviews.
    for name in ('index.html', 'images', 'styles'):
        source = root / name
        if source.is_symlink():
            raise ValueError('Symlinks forbidden in public site')
        if source.is_dir():
            if any(p.is_symlink() for p in source.rglob('*')):
                raise ValueError('Symlinks forbidden in public site')
            shutil.copytree(source, destination / name)
        else:
            shutil.copy2(source, destination / name)
    (destination / 'scripts').mkdir()
    shutil.copy2(root / 'scripts/trends-ui.js', destination / 'scripts/trends-ui.js')
    write(destination / 'data/radar.json', payload)


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=('collect', 'build', 'refresh', 'stage'))
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--previous', type=Path)
    ap.add_argument('--input', type=Path)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    try:
        if args.command == 'collect':
            payload = {'generated_at': now(), 'items': collect()}
        elif args.command == 'stage':
            payload = json.loads(args.input.read_text())
            if args.dry_run:
                print('DRY RUN: would stage static site; no files written')
                return 0
            stage_site(ROOT, args.output, payload)
            print(f'Staged static site → {args.output}')
            return 0
        else:
            reviews = json.loads((ROOT / 'data/reviews.json').read_text())['items']
            if args.command == 'refresh':
                candidates = collect()
                previous = json.loads(args.previous.read_text()) if args.previous else {}
                observed = verify_sources(reviews + candidates)
                payload = assemble(reviews, candidates, observed, previous)
                if previous.get('content_digest') == payload['content_digest'] and digest(previous) == payload['content_digest']:
                    payload = previous  # Byte-stable when no substantive content changed.
                print('changed=' + str(previous.get('content_digest') != payload['content_digest']).lower())
            else:
                payload = assemble(reviews, [], verify_sources(reviews))
        if args.dry_run:
            print(f'DRY RUN: {len(payload["items"])} validated records; no files written')
            return 0
        write(args.output, payload)
        print(f'{args.command}: {len(payload["items"])} records → {args.output}')
    except Exception as exc:
        print(f'Blocked; existing output preserved: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
