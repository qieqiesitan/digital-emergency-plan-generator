from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
r = client.post('/api/v1/auth/login', json={
    'email': 'qa_e2e_test@test.com',
    'password': 'test123456'
})
token = r.json()['data']['access_token']
headers = {'Authorization': 'Bearer ' + token}

try:
    r3 = client.get('/api/v1/plans/enterprise-summary', headers=headers)
    print('Status:', r3.status_code)
    if r3.status_code == 200:
        items = r3.json().get('data', [])
        print('enterprises:', len(items))
        for it in items[:3]:
            n = it.get('enterprise_name', '')[:20]
            ind = it.get('industry', '') or '(none)'
            print('  -', n, '| industry=', ind)
    else:
        print('ERROR body:', r3.text[:500])
except Exception as e:
    import traceback
    traceback.print_exc()
