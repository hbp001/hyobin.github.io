/* Plain text only. Candidates and unverified records never enter the public feed. */
(() => {
  'use strict';
  const categories = {
    all: '전체', agents: 'AI 에이전트·자기개선', trust: '신뢰성·평가·안전',
    multimodal: '멀티모달·VLM', generation: '생성 모델', training: '학습·최적화', mlops: 'MLOps·배포'
  };
  const feed = document.getElementById('feed');
  const filters = document.getElementById('trendFilters');
  const foot = document.getElementById('feedFoot');
  const node = (tag, text, cls) => {
    const el = document.createElement(tag);
    if (text) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  };
  function allowed(url) {
    try {
      const u = new URL(url);
      return u.protocol === 'https:' && !u.username && !u.password && !u.port && !u.search && !u.hash &&
        ((u.hostname === 'arxiv.org' && /^\/abs\/\d{4}\.\d{4,5}$/.test(u.pathname)) ||
         (u.hostname === 'openai.com' && /^\/index\/[a-z0-9-]+\/$/.test(u.pathname)));
    } catch { return false; }
  }
  function valid(it) {
    const metadata = it && it.verification === 'metadata-verified' && allowed(it.url) &&
      ['title', 'published', 'collected_at', 'source_checked_at'].every(k => typeof it[k] === 'string' && it[k].trim()) &&
      Array.isArray(it.categories) && it.categories.length && it.categories.every(c => c !== 'all' && categories[c]);
    if (!metadata) return false;
    if (it.commentary_review === 'not-reviewed') return it.authorship === 'source-metadata' &&
      ['summary', 'limitations', 'interview_question', 'application_idea'].every(k => !(k in it));
    return it.commentary_review === 'reviewed' && it.authorship === 'reading-note' &&
      ['summary', 'limitations', 'interview_question', 'application_idea'].every(k => typeof it[k] === 'string' && it[k].trim());
  }
  function render(items, selected) {
    feed.replaceChildren();
    const visible = items.filter(it => selected === 'all' || it.categories.includes(selected));
    if (!visible.length) feed.append(node('p', '이 카테고리에는 아직 검증된 읽기 노트가 없습니다.', 'item'));
    for (const it of visible) {
      const article = node('article', '', 'item');
      article.style.display = 'block';
      const link = node('a', it.display_title || it.title, 'ttl');
      link.href = it.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      article.append(link);
      article.append(node('p', it.categories.map(c => categories[c]).join(' · '), 'tags'));
      article.append(node('p', `출처: ${it.source === 'arxiv' ? 'arXiv · 프리프린트' : '공식 기술 자료'} · 발행 ${it.published} · 수집 ${it.collected_at.slice(0, 10)} · 서지 대조 ${it.source_checked_at.slice(0, 10)} · 서지 메타데이터 대조됨 · 해설 ${it.commentary_review === 'reviewed' ? '원문 검토됨' : '미검토'}`, 'trend-meta'));
      if (it.commentary_review === 'not-reviewed') {
        article.append(node('p', '자동 수집 메타데이터 카드 · 제목 기반 분류 제안입니다. 요약·내용·성능·안전성은 검토하지 않았습니다. 원문 링크에서 직접 확인하세요.'));
        feed.append(article);
        continue;
      }
      article.append(node('p', it.summary));
      const details = node('details');
      details.append(node('summary', '한계 · 면접 질문 · 프로젝트 제안'));
      for (const [key, label] of [['limitations', '한계'], ['interview_question', '면접 질문'], ['application_idea', '적용 아이디어 · 실적 아님']]) {
        details.append(node('p', `${label}: ${it[key]}`));
      }
      article.append(details);
      feed.append(article);
    }
    for (const button of filters.children) button.setAttribute('aria-pressed', String(button.dataset.category === selected));
    foot.textContent = `서지 대조 자료 ${items.length}건 · 표시 ${visible.length}건 · 서지 대조는 내용·성능 검증이 아닙니다. 해설의 원문 검토 여부를 카드별로 표시합니다.`;
  }
  fetch('data/radar.json', {cache: 'no-store'})
    .then(r => { if (!r.ok) throw new Error('Feed unavailable'); return r.json(); })
    .then(data => {
      if (data.schema_version !== 1 || !Array.isArray(data.items) || !data.items.every(valid)) throw new Error('Invalid feed');
      for (const [key, label] of Object.entries(categories)) {
        const button = node('button', label, 'tag');
        button.type = 'button'; button.dataset.category = key;
        button.addEventListener('click', () => render(data.items, key));
        filters.append(button);
      }
      render(data.items, 'all');
    })
    .catch(() => {
      filters.replaceChildren();
      feed.replaceChildren(node('p', '현재 표시할 수 있는 서지 대조 자료가 없습니다.', 'item'));
      foot.textContent = '피드를 불러오지 못했거나 검증 형식이 맞지 않습니다. 미검증 후보와 예시 데이터는 게시하지 않습니다.';
    });
})();
