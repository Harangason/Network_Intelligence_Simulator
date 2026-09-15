from uuid import uuid4

from backend.app import create_app


def test_project_gallery_lists_saved_names_and_new_empty_projects():
    client = create_app().test_client()
    project = 'gallery-' + uuid4().hex
    headers = {'X-Project-ID': project}
    payload = {'project_name': 'Temperaturregelung', 'project_description': 'Drei Sensoren und zwei Ventile',
               'engineering_wizard_settings': {'project_name': 'Temperaturregelung', 'model_type': 'custom'}}
    first = client.patch('/api/engineering/workflow/context?view=summary', json=payload, headers=headers)
    assert first.status_code == 200, first.json
    retry = client.patch('/api/engineering/workflow/context?view=summary', json=payload, headers=headers)
    assert retry.status_code == 200
    listing = client.get('/api/engineering/projects').json
    matches = [row for row in listing['items'] if row['project_id'] == project]
    assert len(matches) == 1
    assert matches[0]['name'] == payload['project_name']
    assert matches[0]['description'] == ''
    assert matches[0]['statuses']['engineering_model'] == 'EMPTY'
    assert 'context' not in matches[0]
    assert listing['total'] >= listing['count']
    page = client.get('/api/engineering/projects?offset=1').json
    assert not any(row['project_id'] == listing['items'][0]['project_id'] for row in page['items'])
    assert client.get('/api/engineering/projects?offset=invalid').status_code == 400
