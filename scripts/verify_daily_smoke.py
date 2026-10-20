"""Check that a bounded daily run produced a real, readable paper before publishing."""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
spec = importlib.util.spec_from_file_location('daily_docs', ROOT / 'src/6.generate_docs.py')
docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs)

date = datetime.now(timezone.utc).strftime('%Y%m%d')
payload = json.loads((ROOT / f'archive/{date}/recommend/arxiv_papers_{date}.standard.json').read_text())
papers = payload.get('deep_dive', []) + payload.get('quick_skim', [])
if len(papers) != 1:
    raise SystemExit('Smoke verification requires exactly one qualified paper; no empty success.')
for paper in papers:
    md, txt, route = docs.prepare_paper_paths(str(ROOT / 'docs'), date, paper['title'], paper['id'])
    content = Path(md).read_text()
    meta = docs._parse_front_matter(content)
    required = ('title_zh', 'tldr', 'motivation', 'method', 'result', 'conclusion')
    if any(not meta.get(key) for key in required):
        raise SystemExit('Smoke page missing translated title or overview metadata.')
    fulltext = Path(txt).read_text()
    if len(fulltext) < 2000 or 'reference' not in fulltext.lower():
        raise SystemExit('Smoke full text missing body or references.')
    if route not in (ROOT / 'docs/_sidebar.md').read_text():
        raise SystemExit('Smoke page missing sidebar route.')
    print(json.dumps({'paper_id': paper['id'], 'score': paper['llm_score'],
                      'route': route, 'fulltext_chars': len(fulltext),
                      'metadata_complete': True}, ensure_ascii=False))
