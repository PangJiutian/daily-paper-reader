import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
spec = importlib.util.spec_from_file_location('daily_selection', ROOT / 'src/5.select_papers.py')
selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selection)

POLICY = dict(max_papers=5, min_score=8, deep_papers=2,
              discovery_tag='ai-discovery', discovery_max=1)


def paper(pid, score, tag='video-world-models'):
    return dict(id=pid, llm_score=score, llm_tags=['query:' + tag],
                tags=['keyword:video-world-models'])


def test_high_scores_cannot_bypass_daily_cap_and_discovery_quota():
    candidates = [paper('d1', 10, 'ai-discovery'), paper('d2', 9.9, 'ai-discovery')]
    candidates += [paper(str(i), 9.8 - i / 100) for i in range(10)]
    result = selection.apply_daily_selection(candidates, {'stats': {}}, POLICY)
    picked = result['deep_dive'] + result['quick_skim']
    assert len(picked) == 5
    assert len(result['deep_dive']) == 2
    assert sum(p['id'].startswith('d') for p in picked) == 1


def test_no_padding_and_canonical_deduplication():
    candidates = [paper('2601.00001v2', 9), paper('2601.00001v1', 8.5), paper('low', 7.9)]
    result = selection.apply_daily_selection(candidates, {'stats': {}}, POLICY)
    assert [p['id'] for p in result['deep_dive']] == ['2601.00001v2']
    assert result['quick_skim'] == []


def test_opt_in_and_smoke_budget(monkeypatch):
    original = {'stats': {}, 'deep_dive': [paper('old', 9)]}
    assert selection.apply_daily_selection([], original, None) is original
    monkeypatch.setenv('DPR_SMOKE_TEST', '1')
    result = selection.apply_daily_selection([paper('a', 9), paper('b', 8)], {'stats': {}}, POLICY)
    assert result['deep_dive'] == []
    assert len(result['quick_skim']) == 1
