import urllib.request, json

body = json.dumps({'keyword': 'artificial intelligence', 'limit': 5, 'sources': ['web']}).encode()
req = urllib.request.Request(
    'http://127.0.0.1:8000/scrape', 
    data=body, 
    headers={'Content-Type': 'application/json'}
)
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
        print('Status:', data['status'])
        print('Total:', data['total_results'])
        for item in data['data'][:3]:
            src = item['source']
            txt = item['raw_text'][:70]
            print(f'  [{src}] {txt}')
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()
