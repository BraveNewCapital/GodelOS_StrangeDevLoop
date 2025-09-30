import requests
import time

API_BASE_URL = 'http://localhost:8000'
FILE_PATH = 'tmp/test_upload.txt'
TIMEOUT = 60

# Upload file
with open(FILE_PATH, 'rb') as f:
    files = {'file': (FILE_PATH, f)}
    data = {'filename': FILE_PATH.split('/')[-1], 'file_type': 'txt'}
    r = requests.post(f'{API_BASE_URL}/api/knowledge/import/file', files=files, data=data)
    print('Upload status:', r.status_code)
    resp = r.json()
    print('Upload response:', resp)
    import_id = resp.get('import_id')
    assert import_id, 'No import_id returned'

# Poll progress
start = time.time()
while True:
    pr = requests.get(f'{API_BASE_URL}/api/knowledge/import/progress/{import_id}')
    print('Progress:', pr.json())
    status = pr.json().get('status')
    if status in ('completed', 'failed'):
        print('Final status:', status)
        break
    if time.time() - start > TIMEOUT:
        print('Timeout waiting for completion')
        break
    time.sleep(2)
