import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('trends', ROOT / 'scripts/trends.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.review = json.loads((ROOT / 'data/reviews.json').read_text())['items'][0]
        self.observed = {self.review['url']: copy.deepcopy(self.review)}

    def reject(self, key, value):
        r = {**self.review, key: value}
        with self.assertRaises((ValueError, KeyError)):
            t.build([r], self.observed)

    def test_verified_reading_note_builds(self):
        result = t.build([self.review], self.observed)
        self.assertEqual(result['count'], 1)
        self.assertIn('source_checked_at', result['items'][0])

    def test_unreviewed_cannot_publish(self):
        self.reject('verification', 'unreviewed')

    def test_research_attribution_cannot_publish(self):
        self.reject('authorship', 'my-research')

    def test_missing_source_or_changed_title_date_blocks(self):
        for observed in ({}, {self.review['url']: {**self.review, 'title': 'Different'}},
                         {self.review['url']: {**self.review, 'published': '2026-10-25'}}):
            with self.assertRaises(ValueError):
                t.build([self.review], observed)

    def test_duplicate_url_and_title_block(self):
        for extra in (self.review, {**self.review, 'url': 'https://arxiv.org/abs/2610.00001'}):
            with self.assertRaises(ValueError):
                t.build([self.review, extra], self.observed)

    def test_missing_fields_and_unknown_categories_block(self):
        for key in ('summary', 'limitations', 'interview_question', 'application_idea', 'evidence_url'):
            self.reject(key, '')
        self.reject('categories', ['unknown'])
        self.reject('summary', 'x' * 601)
        self.reject('summary', '<script>bad</script>')
        self.reject('published', '2099-01-01')
        self.reject('evidence_url', 'https://example.com/a')

    def test_unsafe_urls_block(self):
        for url in ('javascript:alert(1)', 'https://arxiv.org.evil.test/abs/2610.35193',
                    'https://user@arxiv.org/abs/2610.35193', 'https://openai.com/private',
                    'https://arxiv.org/abs/2610.35193?x=1', 'https://arxiv.org:8443/abs/2610.35193'):
            with self.assertRaises(ValueError):
                t.canonical(url)

    def test_arxiv_versions_canonicalize(self):
        self.assertEqual(t.canonical('http://arxiv.org/abs/2610.35193v2'), self.review['url'])
        self.assertEqual(t.canonical('https://arxiv.org/pdf/2610.35193v1.pdf'), self.review['url'])

    def test_feed_never_stores_abstract(self):
        xml = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
        <id>http://arxiv.org/abs/2610.35193v1</id><title>Trustworthy recursive self-improvement</title>
        <published>2026-10-26T10:46:03Z</published><summary>DO NOT COPY ABSTRACT</summary>
        </entry></feed>'''
        rows = t.parse_feed(xml.encode(), 'arxiv')
        self.assertEqual(rows[0]['verification'], 'unreviewed')
        self.assertEqual(rows[0]['categories'], ['agents', 'trust'])
        self.assertNotIn('summary', rows[0])
        self.assertNotIn('DO NOT COPY', json.dumps(rows))

    def test_bad_feed_fails(self):
        for xml in (b'not xml', b'<rss><channel/></rss>'):
            with self.assertRaises(Exception):
                t.parse_feed(xml, 'official')

    def test_network_failure_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'radar.json'
            out.write_text('old feed')
            with patch('sys.argv', ['trends.py', 'build', '--output', str(out)]), patch.object(t, 'fetch', side_effect=OSError('offline')):
                self.assertEqual(t.main(), 1)
            self.assertEqual(out.read_text(), 'old feed')

    def test_metadata_cards_do_not_invent_commentary(self):
        candidate = {**self.review, 'url': 'https://arxiv.org/abs/2610.00002', 'title': 'New agent study'}
        observed = {**self.observed, candidate['url']: candidate}
        result = t.assemble([self.review], [candidate], observed)
        card = result['items'][1]
        self.assertEqual(card['verification'], 'metadata-verified')
        self.assertEqual(card['commentary_review'], 'not-reviewed')
        self.assertEqual(result['items'][0]['commentary_review'], 'reviewed')
        for field in ('summary', 'limitations', 'interview_question', 'application_idea'):
            self.assertNotIn(field, card)

    def test_metadata_mismatch_blocks_publication(self):
        candidate = {**self.review, 'url': 'https://arxiv.org/abs/2610.00002', 'title': 'New agent study'}
        with self.assertRaises(ValueError):
            t.assemble([self.review], [candidate], self.observed)

    def test_digest_ignores_timestamp_and_retains_first_collection(self):
        a = t.assemble([self.review], [], self.observed)
        b = copy.deepcopy(a)
        b['items'][0]['source_checked_at'] = '2099-01-01T00:00:00Z'
        b['items'][0]['collected_at'] = '2099-01-01T00:00:00Z'
        self.assertEqual(t.digest(a), t.digest(b))
        b['items'][0]['summary'] += ' revised'
        self.assertNotEqual(t.digest(a), t.digest(b))

    def test_refresh_dry_run_never_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'radar.json'
            with patch('sys.argv', ['trends.py', 'refresh', '--dry-run', '--output', str(out)]), patch.object(t, 'collect', return_value=[]), patch.object(t, 'verify_sources', return_value=self.observed):
                self.assertEqual(t.main(), 0)
            self.assertFalse(out.exists())

    def test_staging_excludes_private_configuration_and_requires_original_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'root'; root.mkdir()
            with self.assertRaises(ValueError):
                t.stage_site(root, Path(directory) / 'missing-image', {'items': []})
            (root / 'images').mkdir(); (root / 'images/profile-1.jpg.jpg').write_bytes(b'test fixture')
            (root / 'index.html').write_text('original portfolio')
            (root / 'styles').mkdir(); (root / 'scripts').mkdir(); (root / 'scripts/trends-ui.js').write_text('safe UI')
            (root / '.secret').write_text('never publish')
            (root / 'scripts/credentials.json').write_text('never publish')
            dest = Path(directory) / 'site'
            t.stage_site(root, dest, {'items': []})
            self.assertEqual((dest / 'index.html').read_text(), 'original portfolio')
            self.assertFalse((dest / '.secret').exists())
            self.assertFalse((dest / 'scripts/credentials.json').exists())

    def test_publisher_is_inactive_gated_and_cannot_commit(self):
        publisher = ROOT / '.github/workflows/trends-publish.yml.disabled'
        self.assertTrue(publisher.is_file())
        text = publisher.read_text()
        self.assertIn("default: true", text)
        self.assertIn("vars.AI_TRENDS_AUTOPUBLISH == 'approved'", text)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn("needs.build.outputs.changed == 'true'", text)
        self.assertIn('group: ai-trends-publish', text)
        self.assertNotIn('contents: write', text)
        self.assertNotIn('git push', text)
        self.assertNotIn('git commit', text)

    def test_workflow_cannot_deploy_or_write_repository(self):
        workflow = (ROOT / '.github/workflows/trends.yml').read_text()
        self.assertIn('contents: read', workflow)
        self.assertIn('group: ai-trends-${{ github.ref }}', workflow)
        self.assertIn('cancel-in-progress: false', workflow)
        active = '\n'.join(line for line in workflow.splitlines() if not line.lstrip().startswith('#'))
        for text in ('schedule:', 'contents: write', 'git push', 'deploy-pages', 'ANTHROPIC_API_KEY', 'git commit', 'create-pull-request'):
            self.assertNotIn(text, active)


if __name__ == '__main__':
    unittest.main()
