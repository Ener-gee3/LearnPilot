from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_health_endpoint():
    res = client.get('/health')
    assert res.status_code == 200
    assert res.json()['status'] == 'online'


def test_generate_endpoint_with_stub(monkeypatch):
    async def fake_generate_response(mode, topic, code_snippet=None):
        return {
            'mode': mode,
            'explanation': f'Explained {topic}',
            'real_world_application': 'Demo',
            'resources': [],
            'quiz': None,
            'steps': ['s1'],
            'image_url': None,
            'raw': '## Concept\nDemo',
            'raw_clean': '## Concept\nDemo',
            'real_world': 'Demo',
        }

    monkeypatch.setattr(main.AIEngine, 'generate_response', fake_generate_response)

    res = client.post('/generate', json={'topic': 'Binary Search', 'mode': 'Concept-First Learning'})
    assert res.status_code == 200
    body = res.json()
    assert body['mode'] == 'Concept-First Learning'
    assert 'Binary Search' in body['explanation']


def test_profile_and_progress_flow():
    headers = {'X-User-Id': 'test-user'}

    res = client.get('/v2/profile', headers=headers)
    assert res.status_code == 200
    assert res.json()['success'] is True

    res = client.post('/v2/profile', headers=headers, json={'daily_minutes': 45, 'weak_topics': ['graphs']})
    assert res.status_code == 200
    assert res.json()['data']['daily_minutes'] == 45

    res = client.post('/v2/progress', headers=headers, json={'topic': 'graphs', 'score': 0.5, 'source': 'quiz'})
    assert res.status_code == 200

    res = client.get('/v2/progress', headers=headers)
    assert res.status_code == 200
    data = res.json()['data']
    assert 'weak_topics' in data


def test_knowledge_base_and_exports():
    headers = {'X-User-Id': 'kb-user'}
    res = client.post(
        '/v2/knowledge-base/docs',
        headers=headers,
        json={'course_id': 'csc603', 'title': 'Trees', 'body': 'Binary trees are hierarchical data structures.'},
    )
    assert res.status_code == 200

    res = client.get('/v2/knowledge-base/docs/csc603', headers=headers)
    assert res.status_code == 200
    assert len(res.json()['data']['documents']) >= 1

    res = client.get('/v2/integrations/export/markdown/csc603', headers=headers)
    assert res.status_code == 200
    assert '# Study Pack: csc603' in res.json()['data']['markdown']
