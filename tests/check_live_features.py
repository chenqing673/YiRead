"""Read-only smoke check of the running local service. No model calls or writes."""
import json
from urllib.request import Request,build_opener,ProxyHandler

opener=build_opener(ProxyHandler({}))
root='http://127.0.0.1:8765'
def read(path,headers=None):
    with opener.open(Request(root+path,headers=headers or {}),timeout=10) as response:
        return response.read()

home=read('/').decode('utf-8')
reader=read('/reader.html?id=demo001').decode('utf-8')
assert 'data-view="list"' in home and 'data-filter="favorite"' in home
assert all(name in reader for name in ('edit-current-btn','retry-current-btn','restore-current-btn','align-btn'))
assert all(name in reader for name in ('notes-btn','annotation-btn','js/reader-notes.js','逐句对齐重译'))
token=json.loads(read('/api/token'))['data']['token']
settings=json.loads(read('/api/settings',{'X-Token':token}))['data']
assert 'glossary' in settings and 'aligned' in settings and 'api_key' not in settings
library=json.loads(read('/api/library'))['data']['items']
sentences=0
for item in library:
    pid=item['id']
    notes=json.loads(read('/api/notes/'+pid,{'X-Token':token}))['data']
    assert isinstance(notes['notes'],dict) and isinstance(notes['version'],int)
    from urllib.error import HTTPError
    try:
        result=json.loads(read('/api/translation/'+pid))['data']
    except HTTPError as error:
        assert error.code==404;continue
    for block in result.get('blocks',[]):
        for target in block.get('segments') or [block]:
            for unit in target.get('reading_units',[]):
                assert 0<=unit['start']<unit['end']<=len(target['translation'])
                assert unit['kind'] in ('sentence','sentence-order') and unit['rects']
                sentences+=1
print('PASS live service: provider/reader controls, durable notes, settings, sentence anchors:',sentences,'; no model calls or document writes')
