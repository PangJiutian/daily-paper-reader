"""Bounded live checks; never log credentials, URLs, or response bodies."""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from llm import LLMClient


def configurations(env):
    key = env.get('DEEPSEEK_API_KEY') or env.get('SUMMARY_API_KEY') or ''
    base = env.get('DEEPSEEK_BASE_URL') or env.get('SUMMARY_BASE_URL') or 'https://api.deepseek.com'
    model = env.get('SUMMARY_MODEL') or env.get('DEEPSEEK_MODEL') or 'deepseek-v4-flash'
    result = [('pipeline_effective', key, base, model)]
    if env.get('DEEPSEEK_API_KEY'):
        result.append(('deepseek', env['DEEPSEEK_API_KEY'], env.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com', env.get('DEEPSEEK_MODEL') or 'deepseek-v4-flash'))
    if env.get('SUMMARY_API_KEY'):
        result.append(('summary', env['SUMMARY_API_KEY'], env.get('SUMMARY_BASE_URL') or base, env.get('SUMMARY_MODEL') or model))
    return result


def check(key, base, model):
    if not key.strip() or not model.strip():
        return {'status': 'failed', 'reason': 'missing_key_or_model'}
    url = LLMClient._build_chat_completions_url(base)
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return {'status': 'failed', 'reason': 'invalid_https_base_url'}
    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': 'Return only this JSON object: {"ok": true}'}],
        'max_tokens': 128,
        'stream': False,
        'response_format': {'type': 'json_object'},
    }
    if 'deepseek' in model.lower():
        payload['thinking'] = {'type': 'disabled'}
    try:
        response = requests.post(url, headers={'Authorization': 'Bearer ' + key}, json=payload, timeout=(10, 60), allow_redirects=False)
    except requests.RequestException:
        return {'status': 'failed', 'reason': 'network_or_timeout'}
    if response.status_code != 200:
        return {'status': 'failed', 'http_status': response.status_code}
    try:
        data = response.json()
        choice = data['choices'][0]
        valid = json.loads(choice['message']['content']) == {'ok': True}
        usage = data.get('usage') or {}
        return {
            'status': 'passed' if valid and choice.get('finish_reason') == 'stop' else 'failed',
            'http_status': 200,
            'json_valid': valid,
            'total_tokens': usage.get('total_tokens'),
            'returned_model_matches': data.get('model') == model,
        }
    except (ValueError, KeyError, IndexError, TypeError):
        return {'status': 'failed', 'reason': 'invalid_response', 'http_status': 200}


def main():
    seen = {}
    reports = []
    for label, key, base, model in configurations(os.environ):
        identity = (key, base.rstrip('/'), model)
        if identity not in seen:
            seen[identity] = check(key, base, model)
        reports.append({'configuration': label, **seen[identity]})
    report = {'unique_requests': len(seen), 'results': reports}
    output = json.dumps(report, indent=2)
    print(output)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write('```json\n' + output + '\n```\n')
    return 0 if all(row['status'] == 'passed' for row in reports) else 1


if __name__ == '__main__':
    sys.exit(main())
