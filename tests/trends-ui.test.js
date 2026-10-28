const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.style = {}; this.events = {}; this.attrs = {}; this.textContent = ''; }
  append(...els) { this.children.push(...els); }
  replaceChildren(...els) { this.children = els; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(k, callback) { this.events[k] = callback; }
}
async function run(data, ok = true) {
  const els = Object.fromEntries(['feed', 'trendFilters', 'feedFoot'].map(id => [id, new Element('div')]));
  const context = {URL, document: {getElementById: id => els[id], createElement: tag => new Element(tag)}, fetch: async () => ({ok, json: async () => data})};
  vm.runInNewContext(fs.readFileSync('scripts/trends-ui.js', 'utf8'), context);
  await new Promise(resolve => setImmediate(resolve));
  return els;
}
(async () => {
  const data = JSON.parse(fs.readFileSync('data/radar.json', 'utf8'));
  data.items = [data.items[0]];
  const els = await run(data);
  assert.equal(els.trendFilters.children.length, 7);
  assert.equal(els.feed.children[0].tag, 'article');
  const emptyCategory = els.trendFilters.children.find(e => e.dataset.category === 'mlops');
  emptyCategory.events.click();
  assert.match(els.feed.children[0].textContent, /아직 검증/);
  assert.equal(emptyCategory.attrs['aria-pressed'], 'true');
  els.trendFilters.children[0].events.click();
  assert.equal(els.feed.children[0].tag, 'article');
  const metadata = structuredClone(data);
  metadata.items = [metadata.items.find(it => it.commentary_review === 'not-reviewed') || {...data.items[0], commentary_review:'not-reviewed', authorship:'source-metadata'}];
  for (const key of ['summary', 'limitations', 'interview_question', 'application_idea']) delete metadata.items[0][key];
  const metaUI = await run(metadata);
  assert.equal(metaUI.feed.children[0].tag, 'article');
  assert.equal(metaUI.feed.children[0].children.some(e => e.tag === 'details'), false);
  assert.match(metaUI.feed.children[0].children.at(-1).textContent, /메타데이터 카드/);
  metadata.items[0].summary = 'invented interpretation';
  assert.equal((await run(metadata)).feed.children[0].tag, 'p');
  const malicious = structuredClone(data);
  malicious.items[0].url = 'javascript:alert(1)';
  assert.equal((await run(malicious)).feed.children[0].tag, 'p');
  const unverified = structuredClone(data);
  unverified.items[0].verification = 'unreviewed';
  assert.equal((await run(unverified)).feed.children[0].tag, 'p');
  assert.equal((await run({}, false)).feed.children[0].tag, 'p');
  const escaped = structuredClone(data);
  escaped.items[0].display_title = '<img src=x onerror=alert(1)>';
  assert.equal((await run(escaped)).feed.children[0].children[0].textContent, '<img src=x onerror=alert(1)>');
  console.log('UI: categories, empty state, source guard, verification guard, failed fetch, plain-text rendering passed');
})();
