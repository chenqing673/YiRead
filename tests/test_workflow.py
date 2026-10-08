"""Isolated integration tests: never modify the user's document library or call a paid API."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib import request, error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from core import config, translator, translation_worker
from core.security import get_token
from server import YiReadHandler
from storage.jobs import create_translation_job, get_job
from storage.translation_store import get_translation
from storage.translation_status import get_translation_status
from utils.json_io import write_json_atomic
from pypdf import PdfWriter

class Provider(BaseHTTPRequestHandler):
    calls = []
    fail = False
    batch_mode = None
    throttle = 0
    def log_message(self, *args):
        pass
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.calls.append(payload)
        if self.throttle:
            type(self).throttle-=1;self.send_response(429);self.send_header('Retry-After','0');self.end_headers();return
        if self.fail:
            self.send_response(429); self.send_header('Retry-After','0'); self.end_headers(); return
        raw=payload['messages'][-1]['content']
        try:items=json.loads(raw).get('items')
        except (ValueError,AttributeError):items=None
        content='真实翻译测试：'+raw
        if items:
            output=[{'id':x['id'],'translation':'翻译：'+x['text']} for x in reversed(items)]
            if self.batch_mode=='omit':output=output[:-1]
            elif self.batch_mode=='duplicate':output.append(output[0])
            content=json.dumps({'translations':output})
        data=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':content}}],'usage':{'prompt_tokens':100,'completion_tokens':40,'total_tokens':140}}).encode()
        self.send_response(200);self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)

class Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.patches = [patch.object(config,"CONFIG_FILE",os.path.join(cls.temp.name,"config.json")),patch.object(translator,"SETTINGS_FILE",os.path.join(cls.temp.name,"translator.json"))]
        for item in cls.patches:item.start()
        write_json_atomic(config.CONFIG_FILE,{"data_dir":cls.temp.name})
        cls.provider=ThreadingHTTPServer(("127.0.0.1",0),Provider)
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),YiReadHandler)
        for server in (cls.provider,cls.server):threading.Thread(target=server.serve_forever,daemon=True).start()
        cls.base="http://127.0.0.1:" + str(cls.server.server_port)
        cls.provider_url="http://127.0.0.1:" + str(cls.provider.server_port) + "/v1"
        cls.opener=request.build_opener(request.ProxyHandler({}))
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.provider.shutdown()
        cls.server.server_close();cls.provider.server_close()
        translation_worker.EXECUTOR.shutdown(wait=True)
        for item in reversed(cls.patches):item.stop()
        cls.temp.cleanup()
    def call(self,path,body=None,token=True,raw=None,headers=None):
        values={"X-Token":get_token()} if token else {}
        values.update(headers or {})
        if body is not None:raw=json.dumps(body).encode();values["Content-Type"]="application/json"
        req=request.Request(self.base+path,data=raw,headers=values)
        try:
            with self.opener.open(req,timeout=5) as response:return response.status,json.load(response)
        except error.HTTPError as exc:return exc.code,json.load(exc)
    def seed(self,paper_id):
        folder=os.path.join(config.get_data_path("library"),paper_id)
        write_json_atomic(os.path.join(folder,"item.json"),{"id":paper_id,"title":"Test"})
        write_json_atomic(os.path.join(folder,"paper.json"),{"pages":[{"page":1,"blocks":[{"id":"p1_b1","text":"Hello"},{"id":"p1_b2","text":"World"}]}]})
    def configure(self):
        translator.save_settings({"base_url":self.provider_url,"model":"mock-model","api_key":"test-secret","target_lang":"zh","batch":False,"concurrency":1,"aligned":False})
    def wait_job(self,job_id):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            job=get_job(job_id)
            if job["status"] in ("completed","failed"):return job
            time.sleep(.02)
        self.fail("worker did not complete")
    def test_01_settings_hide_credentials(self):
        self.configure()
        code,data=self.call('/api/settings')
        self.assertEqual(code,200);self.assertTrue(data['data']['has_key']);self.assertNotIn('test-secret',json.dumps(data))
        self.assertEqual(self.call('/api/settings',token=False)[0],403)
        self.assertEqual(self.call('/api/settings',{'base_url':'file:///etc','model':'mock'})[0],400)
    def test_02_auto_translation_and_deduplication(self):
        self.configure();self.seed('auto')
        code,result=self.call('/api/translation',{'paper_id':'auto'})
        self.assertEqual(code,200)
        job=self.wait_job(result['data']['job_id']);self.assertEqual(job['status'],'completed')
        stored=get_translation('auto');self.assertEqual(len(stored['blocks']),2);self.assertEqual(stored['engine'],'openai-compatible')
        before=len(Provider.calls)
        second=self.call('/api/translation',{'paper_id':'auto'})[1]
        self.assertEqual(second['data']['job_id'],job['job_id']);self.assertEqual(len(Provider.calls),before)
        self.assertNotIn('translation',json.loads(Path(config.get_data_path('library'),'auto','paper.json').read_text()))
    def test_03_failure_retains_partial_and_retry_resumes(self):
        self.configure();self.seed('resume')
        job=create_translation_job('resume');calls=[]
        def partial(text,*args,**kwargs):
            calls.append(text)
            if text=='World':raise ValueError('temporary failure')
            return '你好'
        with patch.object(translation_worker,'translate',partial):translation_worker.run_translation_job(job['job_id'])
        self.assertEqual(get_translation_status('resume')['status'],'failed')
        self.assertEqual(len(get_translation('resume')['blocks']),1)
        retry=create_translation_job('resume');self.assertNotEqual(retry['job_id'],job['job_id'])
        with patch.object(translation_worker,'translate',return_value='世界') as mock:translation_worker.run_translation_job(retry['job_id']);mock.assert_called_once()
        self.assertEqual(get_translation_status('resume')['status'],'completed')
    def test_04_invalid_requests_and_ids(self):
        self.assertEqual(self.call('/api/translation',{'paper_id':'missing'})[0],404)
        self.assertEqual(self.call('/api/worker',{'job_id':'missing'})[0],404)
        self.assertEqual(self.call('/api/translation',raw=b'{',headers={'Content-Type':'application/json'})[0],400)
        self.assertEqual(self.call('/api/translation',{'paper_id':'../config'})[0],400)
        self.assertEqual(self.call('/api/delete/..',raw=b'')[0],400)
        self.assertEqual(self.call('/api/paper/%2e%2e')[0],400)
    def test_05_pdf_import_and_delete(self):
        pdf=PdfWriter();pdf.add_blank_page(width=100,height=100);stream=io.BytesIO();pdf.write(stream)
        payload=stream.getvalue();boundary='test-boundary'
        body=('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="sample.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode()+payload+('\r\n--'+boundary+'--\r\n').encode()
        code,result=self.call('/api/import',raw=body,headers={'Content-Type':'multipart/form-data; boundary="'+boundary+'"'})
        self.assertEqual(code,200);pid=result['data']['id']
        source=Path(config.get_data_path('library'),pid,'source.pdf');self.assertEqual(source.read_bytes(),payload)
        self.assertEqual(self.call('/api/paper/'+pid)[0],200)
        layout=self.call('/api/pdf-layout/'+pid)[1]['data']
        self.assertEqual(len(layout['pages']),1)
        with self.opener.open(self.base+'/api/pdf-page/'+pid+'/1') as response:
            self.assertEqual(response.headers['Content-Type'],'image/png')
            self.assertTrue(response.read().startswith(b'\x89PNG'))
        self.assertEqual(self.call('/api/pdf-page/'+pid+'/999')[0],404)
        self.assertEqual(self.call('/api/pdf-page/../1')[0],400)

        with self.opener.open(self.base+'/api/source/'+pid) as response:
            self.assertEqual(response.headers['Content-Type'],'application/pdf')
            self.assertEqual(response.read(),payload)
        self.assertEqual(self.call('/api/delete/'+pid,raw=b'')[0],200);self.assertFalse(source.exists())
        self.assertFalse(list(Path(config.get_data_path('upload')).iterdir()))
    def test_06_empty_pdf_fails_clearly(self):
        self.configure();self.seed('blank')
        write_json_atomic(os.path.join(config.get_data_path('library'),'blank','paper.json'),{'pages':[{'page':1,'blocks':[]}]})
        result=self.call('/api/translation',{'paper_id':'blank'})[1];job=self.wait_job(result['data']['job_id'])
        self.assertEqual(job['status'],'failed');self.assertIn('OCR',job['error'])
    def test_07_restart_and_in_progress_deletion(self):
        self.seed('pending');job=create_translation_job('pending')
        self.assertEqual(self.call('/api/delete/pending',raw=b'')[0],409)
        translation_worker.recover_jobs();self.assertEqual(get_job(job['job_id'])['status'],'paused')
        self.assertEqual(self.call('/api/delete/pending',raw=b'')[0],200)
    def test_08_provider_errors_are_safe(self):
        self.configure();Provider.fail=True
        try:
            with self.assertRaisesRegex(ValueError,'HTTP 429'):translator.translate('Hello',translator.settings(),'zh')
        finally:Provider.fail=False

    def test_09_retranslation_and_language_change(self):
        self.configure();self.seed('force')
        first=self.call('/api/translation',{'paper_id':'force'})[1]['data'];self.wait_job(first['job_id'])
        before=len(Provider.calls)
        second=self.call('/api/translation',{'paper_id':'force','force':True})[1]['data'];self.wait_job(second['job_id'])
        self.assertNotEqual(first['job_id'],second['job_id']);self.assertEqual(len(Provider.calls)-before,2)
        translator.save_settings({'target_lang':'en'})
        third=self.call('/api/translation',{'paper_id':'force'})[1]['data'];self.wait_job(third['job_id'])
        self.assertEqual(get_translation('force')['target_lang'],'en')
    def test_10_origin_and_static_content(self):
        self.assertEqual(self.call('/api/token',headers={'Host':'attacker.example'})[0],403)
        self.assertEqual(self.call('/api/token',headers={'Origin':'https://attacker.example'})[0],403)
        with self.opener.open(self.base+'/') as response:
            html=response.read().decode('utf-8');self.assertIn('导入 PDF',html);self.assertIn('lang="zh-CN"',html)
        self.assertEqual(self.call('/js/')[0],404)

    def test_11_changing_provider_never_reuses_old_key(self):
        self.configure()
        result=self.call('/api/settings',{'base_url':'https://api.deepseek.com','model':'deepseek-flash','api_key':''})[1]['data']
        self.assertFalse(result['has_key']);self.assertEqual(translator.settings()['api_key'],'')
        self.call('/api/settings',{'api_key':'new-service-key'})
        self.assertEqual(translator.settings()['api_key'],'new-service-key')
        self.call('/api/settings',{'model':'deepseek-v4-pro','api_key':''})
        self.assertEqual(translator.settings()['api_key'],'new-service-key')
        self.call('/api/settings',{'base_url':'https://api.deepseek.com/','api_key':''})
        self.assertEqual(translator.settings()['api_key'],'new-service-key')
        self.call('/api/settings',{'clear_key':True})
        self.assertEqual(translator.settings()['api_key'],'')

    def test_12_metadata_and_duplicate_detection(self):
        self.seed('catalog')
        self.assertEqual(self.call('/api/metadata',{'paper_id':'catalog','tags':['Ullmann','Ullmann'],'favorite':True,'is_read':True,'year':'2023','doi':'10.1234/example','authors':['A. Author'],'journal':'Test Journal'})[0],200)
        data=self.call('/api/item/catalog')[1]['data']
        self.assertEqual(data['tags'],['Ullmann']);self.assertTrue(data['favorite']);self.assertEqual(data['year'],2023)
        self.assertEqual(self.call('/api/metadata',{'paper_id':'catalog','tags':'invalid'})[0],400)
        self.assertEqual(self.call('/api/metadata',{'paper_id':'catalog','favorite':True},token=False)[0],403)
        import pymupdf
        from storage.importer import import_pdf
        path=os.path.join(self.temp.name,'duplicate.pdf')
        with pymupdf.open() as doc:
            page=doc.new_page();page.insert_text((50,80),'Test article (2023) DOI 10.1234/example')
            doc.set_metadata({'author':'A. Author; B. Author','title':'A chemistry article'})
            doc.save(path)
        first=import_pdf(path);second=import_pdf(path)
        self.assertEqual(first['id'],second['id']);self.assertTrue(second['duplicate']);self.assertEqual(first['doi'],'10.1234/example');self.assertEqual(first['year'],2023)
        self.assertEqual(first['authors'],['A. Author','B. Author'])

    def test_13_alignment_edit_restore_and_single_segment_retry(self):
        self.configure();self.seed('aligned')
        import pymupdf
        folder=Path(config.get_data_path('library'),'aligned')
        text=' '.join('Compound 12 (2.0 equiv) was stirred at 25 C for 3 h with a 75% isolated yield.' for _ in range(12))
        with pymupdf.open() as doc:
            page=doc.new_page();page.insert_textbox(pymupdf.Rect(50,50,550,700),text,fontsize=11);doc.save(folder/'source.pdf')
        original={'pages':[{'page':1,'blocks':[{'id':'legacy','text':text},{'id':'other','text':'Other source paragraph'}]}]}
        write_json_atomic(str(folder/'paper.json'),original)
        result=self.call('/api/translation',{'paper_id':'aligned','aligned':True})[1]['data'];self.assertEqual(self.wait_job(result['job_id'])['status'],'completed')
        stored=get_translation('aligned');block=stored['blocks'][0];self.assertGreater(len(block['segments']),1)
        self.assertTrue(all(s['rects'] for s in block['segments']))
        segment=block['segments'][0];payload={'paper_id':'aligned','block_id':'legacy','segment_id':segment['id']}
        previous=segment['translation'];self.assertEqual(self.call('/api/translation/edit',{**payload,'translation':'人工核对：25 °C，75% 收率'})[0],200)
        changed=get_translation('aligned');self.assertIn('人工核对',changed['blocks'][0]['translation']);self.assertEqual(changed['blocks'][1],stored['blocks'][1])
        self.assertEqual(self.call('/api/translation/restore',payload)[0],200);self.assertEqual(get_translation('aligned')['blocks'][0]['segments'][0]['translation'],previous)
        before=len(Provider.calls);retry=self.call('/api/translation',{**payload,'force':True})[1]['data'];self.assertEqual(self.wait_job(retry['job_id'])['status'],'completed')
        self.assertEqual(len(Provider.calls)-before,1);self.assertEqual(get_translation('aligned')['blocks'][1],stored['blocks'][1])
        self.assertEqual(json.loads((folder/'paper.json').read_text()),original)
        self.assertEqual(self.call('/api/translation/edit',{**payload,'segment_id':'nonexistent','translation':'invalid'})[0],404)
        # A forced parent retry keeps an accessible previous whole-paragraph version.
        prior=get_translation('aligned')['blocks'][0]['translation']
        whole=self.call('/api/translation',{'paper_id':'aligned','block_id':'legacy','force':True,'aligned':True})[1]['data'];self.wait_job(whole['job_id'])
        self.assertEqual(self.call('/api/translation/restore',{'paper_id':'aligned','block_id':'legacy'})[0],200)
        restored=get_translation('aligned')['blocks'][0];self.assertEqual(restored['translation'],prior);self.assertNotIn('segments',restored)

    def test_15_single_block_completion_does_not_mark_full_document_complete(self):
        self.configure();self.seed('oneonly')
        job=self.call('/api/translation',{'paper_id':'oneonly','block_id':'p1_b1','force':True})[1]['data'];self.assertEqual(self.wait_job(job['job_id'])['status'],'completed')
        self.assertEqual(get_translation_status('oneonly')['status'],'partial')
        full=self.call('/api/translation',{'paper_id':'oneonly'})[1]['data'];self.assertNotEqual(full['job_id'],job['job_id']);self.wait_job(full['job_id'])
        self.assertEqual(len(get_translation('oneonly')['blocks']),2);self.assertEqual(get_translation_status('oneonly')['status'],'completed')

    def test_14_glossary_validation_and_prompt(self):
        self.configure();translator.save_settings({'glossary':'workup = 后处理\nCDI = CDI','aligned':False})
        self.assertEqual(translator.public_settings()['glossary'],'workup = 后处理\nCDI = CDI')
        translator.translate('CDI, compound 12, 25 C, 2.0 equiv, 75%',translator.settings(),'zh')
        prompt=Provider.calls[-1]['messages'][0]['content'];self.assertIn('workup = 后处理',prompt);self.assertIn('Never invent or correct experimental values',prompt)
        self.assertEqual(self.call('/api/settings',{'glossary':'x'*10001})[0],400)
        self.assertEqual(self.call('/api/settings',{'aligned':'yes'})[0],400)

    def test_16_durable_notes_validation_version_conflicts_and_delete(self):
        self.seed('notes')
        self.assertEqual(self.call('/api/notes/notes',token=False)[0],403)
        self.assertEqual(self.call('/api/notes/missing')[0],404)
        self.assertEqual(self.call('/api/notes/notes')[1]['data'],{'notes':{},'version':0})
        note={'text':'核对 75% 收率 <script>literal</script>','bookmark':True,'parent':'p1_b1','quote':'引文','source':'Hello','page':99}
        body={'paper_id':'notes','note_id':'p1_b1_s1','note':note,'version':0}
        self.assertEqual(self.call('/api/notes',body,token=False)[0],403)
        code,response=self.call('/api/notes',body);self.assertEqual(code,200)
        saved=response['data'];self.assertEqual(saved['notes']['p1_b1_s1']['page'],1)
        disk=Path(config.get_data_path('library'),'notes','notes.json');self.assertTrue(disk.is_file())
        self.assertEqual(self.call('/api/notes/notes')[1]['data'],json.loads(disk.read_text(encoding='utf8')))
        self.assertEqual(self.call('/api/notes',{**body,'note':{**note,'text':'旧页覆盖'}})[0],409)
        self.assertEqual(self.call('/api/notes/notes')[1]['data'],saved)
        for invalid in ({**note,'text':'x'*15001},{**note,'bookmark':'true'},{**note,'parent':'other-paper-block'}):
            self.assertEqual(self.call('/api/notes',{**body,'version':1,'note':invalid})[0],400)
        self.assertEqual(self.call('/api/notes',{**body,'version':1,'note_id':'../escape'})[0],400)
        self.assertEqual(self.call('/api/notes',{**body,'version':1,'note':None})[1]['data']['notes'],{})
        from storage.translation_store import save_translation
        save_translation('notes',[{'id':'p1_b1','translation':'新译文'}],engine='openai-compatible')
        self.assertEqual(self.call('/api/notes/notes')[1]['data']['version'],2)
        self.assertEqual(self.call('/api/delete/notes',{})[0],200);self.assertFalse(disk.exists())

    def test_17_reading_anchors_are_readonly_and_refresh_after_manual_edits(self):
        import pymupdf
        self.seed('anchors');folder=Path(config.get_data_path('library'),'anchors')
        source='Compound 1 gave 75% yield. Compound 2 gave 80% yield.'
        with pymupdf.open() as doc:
            page=doc.new_page();page.insert_textbox(pymupdf.Rect(30,80,550,300),source,fontsize=12);doc.save(folder/'source.pdf')
        from storage.pdf_parser import parse_pdf
        from storage.translation_store import save_translation
        parsed=parse_pdf(folder/'source.pdf');parsed['pages'][0]['blocks'][0]['id']='p1_b1';write_json_atomic(str(folder/'paper.json'),parsed)
        save_translation('anchors',[{'id':'p1_b1','translation':'化合物1收率75%。化合物2收率80%。'}],engine='openai-compatible',target_lang='zh')
        disk=Path(config.get_data_path('translation'),'anchors.json');before=disk.read_bytes()
        block=self.call('/api/translation/anchors')[1]['data']['blocks'][0]
        self.assertEqual(len(block['reading_units']),2);self.assertEqual(disk.read_bytes(),before)
        self.assertEqual(self.call('/api/translation/edit',{'paper_id':'anchors','block_id':'p1_b1','translation':'合并的修订译文。'})[0],200)
        self.assertEqual(self.call('/api/translation/anchors')[1]['data']['blocks'][0]['reading_units'],[])

    def test_18_batch_ids_missing_items_and_usage(self):
        self.configure();translator.save_settings({'batch':True});self.seed('batch')
        before=len(Provider.calls)
        job=self.call('/api/translation',{'paper_id':'batch'})[1]['data'];finished=self.wait_job(job['job_id'])
        self.assertEqual(finished['status'],'completed');self.assertEqual(len(Provider.calls)-before,1)
        stored=get_translation('batch')['blocks'];self.assertEqual(stored[0]['translation'],'翻译：Hello');self.assertEqual(stored[1]['translation'],'翻译：World')
        self.assertEqual(finished['usage']['total_tokens'],140)
        self.seed('omit');Provider.batch_mode='omit';before=len(Provider.calls)
        try:
            job=self.call('/api/translation',{'paper_id':'omit'})[1]['data'];self.assertEqual(self.wait_job(job['job_id'])['status'],'completed')
            self.assertEqual(len(Provider.calls)-before,2);self.assertEqual(len(get_translation('omit')['blocks']),2)
        finally:Provider.batch_mode=None
        self.seed('duplicate');Provider.batch_mode='duplicate';before=len(Provider.calls)
        try:
            job=self.call('/api/translation',{'paper_id':'duplicate'})[1]['data'];self.wait_job(job['job_id'])
            self.assertEqual(len(Provider.calls)-before,3);self.assertIn('Hello',get_translation('duplicate')['blocks'][0]['translation'])
        finally:Provider.batch_mode=None

    def test_19_scope_failure_continues_and_selective_retry(self):
        self.configure();self.seed('scope')
        paper={'pages':[{'page':n,'blocks':[{'id':'p'+str(n),'text':str(n)}]} for n in range(1,4)]}
        write_json_atomic(str(Path(config.get_data_path('library'),'scope','paper.json')),paper)
        self.assertEqual(self.call('/api/translation',{'paper_id':'scope','pages':[0]})[0],400)
        job=self.call('/api/translation',{'paper_id':'scope','pages':[2]})[1]['data'];self.wait_job(job['job_id'])
        self.assertEqual([b['id'] for b in get_translation('scope')['blocks']],['p2']);self.assertEqual(get_translation_status('scope')['status'],'partial')
        self.seed('fail-list');paper={'pages':[{'page':1,'blocks':[{'id':str(n),'text':str(n)} for n in range(3)]}]}
        write_json_atomic(str(Path(config.get_data_path('library'),'fail-list','paper.json')),paper)
        def fail_middle(text,*args,**kwargs):
            if text=='1':raise translator.ProviderError('temporary')
            return '成功'+text
        with patch.object(translation_worker,'translate',fail_middle):
            job=self.call('/api/translation',{'paper_id':'fail-list'})[1]['data'];finished=self.wait_job(job['job_id'])
        self.assertEqual(set(finished['failed']),{'1'});self.assertEqual([b['id'] for b in get_translation('fail-list')['blocks']],['0','2'])
        with patch.object(translation_worker,'translate',return_value='补译') as mock:
            job=self.call('/api/translation',{'paper_id':'fail-list','retry_failed':True})[1]['data'];self.wait_job(job['job_id']);mock.assert_called_once()
        self.assertEqual(get_translation_status('fail-list')['status'],'completed')

    def test_20_pause_idempotency_and_edit_conflict(self):
        self.configure();self.seed('pause');entered=threading.Event();release=threading.Event()
        def delayed(text,*args,**kwargs):entered.set();release.wait(3);return '已译'
        with patch.object(translation_worker,'translate',delayed):
            job=self.call('/api/translation',{'paper_id':'pause'})[1]['data'];self.assertTrue(entered.wait(2))
            self.assertEqual(self.call('/api/translation/cancel',{'job_id':job['job_id']},token=False)[0],403)
            self.assertEqual(self.call('/api/translation/cancel',{'job_id':job['job_id']})[0],200);release.set()
            deadline=time.monotonic()+3
            while get_job(job['job_id'])['status']=='running' and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(get_job(job['job_id'])['status'],'paused');self.assertEqual(len(get_translation('pause')['blocks']),1)
        payload={'paper_id':'pause','note_id':'p1_b1','version':0,'operation_id':'same_operation','note':{'text':'note','parent':'p1_b1'}}
        self.assertEqual(self.call('/api/notes',payload)[0],200);self.assertEqual(self.call('/api/notes',payload)[1]['data']['version'],1)
        self.assertEqual(self.call('/api/notes',{**payload,'note':{'text':'different','parent':'p1_b1'}})[0],409)
        self.assertEqual(self.call('/api/translation/edit',{'paper_id':'pause','block_id':'p1_b1','base_translation':'stale','translation':'changed'})[0],409)

    def test_21_recoverable_delete_preserves_related_files(self):
        self.seed('recover');from storage.translation_store import save_translation
        save_translation('recover',[{'id':'p1_b1','translation':'保留译文'}],target_lang='zh',engine='openai-compatible')
        self.call('/api/notes',{'paper_id':'recover','note_id':'p1_b1','version':0,'note':{'text':'保留笔记','parent':'p1_b1'}})
        self.assertEqual(self.call('/api/trash',token=False)[0],403)
        result=self.call('/api/delete/recover',{})[1]['data'];self.assertTrue(result['recoverable']);self.assertIsNone(get_translation('recover'))
        self.assertEqual(self.call('/api/trash/restore',{'entry':'../other'})[0],400)
        self.assertEqual(self.call('/api/trash/restore',{'entry':result['entry']})[0],200)
        self.assertEqual(get_translation('recover')['blocks'][0]['translation'],'保留译文')
        self.assertEqual(self.call('/api/notes/recover')[1]['data']['notes']['p1_b1']['text'],'保留笔记')

    def test_22_transient_throttle_and_fatal_stop(self):
        self.configure();Provider.throttle=1;self.seed('throttle')
        job=self.call('/api/translation',{'paper_id':'throttle'})[1]['data'];self.assertEqual(self.wait_job(job['job_id'])['status'],'completed')
        self.seed('fatal')
        with patch.object(translation_worker,'translate',side_effect=translator.ProviderError('HTTP 401',fatal=True)) as mock:
            job=self.call('/api/translation',{'paper_id':'fatal'})[1]['data'];finished=self.wait_job(job['job_id']);mock.assert_called_once()
        self.assertEqual(finished['status'],'failed');self.assertEqual(len(finished['failed']),2)

    def test_23_checkpoint_reuses_successful_sentences_in_failed_parent(self):
        self.configure();translator.save_settings({'aligned':True});self.seed('unit-resume')
        units=[{'id':'sentence1','text':'First.'},{'id':'sentence2','text':'Second.'}]
        def first_run(text,*args,**kwargs):
            if text=='Second.':raise translator.ProviderError('temporary')
            return '第一句。'
        with patch.object(translation_worker,'aligned_sources',return_value=units),patch.object(translation_worker,'translate',first_run):
            job=self.call('/api/translation',{'paper_id':'unit-resume','block_id':'p1_b1','aligned':True})[1]['data'];finished=self.wait_job(job['job_id'])
        self.assertEqual(finished['status'],'failed');self.assertEqual(finished['unit_results'],{'sentence1':'第一句。'})
        with patch.object(translation_worker,'aligned_sources',return_value=units),patch.object(translation_worker,'translate',return_value='第二句。') as mock:
            job=self.call('/api/translation',{'paper_id':'unit-resume','retry_failed':True})[1]['data'];finished=self.wait_job(job['job_id']);mock.assert_called_once()
        self.assertEqual(finished['status'],'completed');self.assertEqual(get_translation('unit-resume')['blocks'][0]['translation'],'第一句。\n\n第二句。')

    def test_24_concurrency_stays_bounded_and_corrupt_trash_does_not_block_startup(self):
        self.configure();translator.save_settings({'concurrency':2});self.seed('bounded')
        paper={'pages':[{'page':1,'blocks':[{'id':str(n),'text':str(n)} for n in range(6)]}]}
        write_json_atomic(str(Path(config.get_data_path('library'),'bounded','paper.json')),paper)
        count=0;peak=0;guard=threading.Lock();both=threading.Event()
        def delayed(text,*args,**kwargs):
            nonlocal count,peak
            with guard:
                count+=1;peak=max(peak,count)
                if count==2:both.set()
            both.wait(2);time.sleep(.02)
            with guard:count-=1
            return text
        with patch.object(translation_worker,'translate',delayed):
            job=self.call('/api/translation',{'paper_id':'bounded'})[1]['data'];self.assertEqual(self.wait_job(job['job_id'])['status'],'completed')
        self.assertEqual(peak,2)
        from storage.trash import trash_root,recover_trash,list_trash
        bad=trash_root()/('f'*32);bad.mkdir();write_json_atomic(str(bad/'manifest.json'),{'paper_id':'bad'})
        recover_trash();self.assertNotIn('f'*32,[x['entry'] for x in list_trash()]);self.assertTrue(bad.exists())

    def test_25_json_io_retries_transient_windows_sharing_errors(self):
        from utils import json_io
        path=str(Path(self.temp.name,'sharing.json'));original_replace=os.replace;original_open=open
        calls=0
        def flaky_replace(source,target):
            nonlocal calls
            calls+=1
            if calls==1:raise PermissionError('sharing conflict')
            return original_replace(source,target)
        with patch.object(json_io.os,'replace',flaky_replace):json_io.write_json_atomic(path,{'saved':True})
        self.assertEqual(calls,2);calls=0
        def flaky_open(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==1:raise PermissionError('sharing conflict')
            return original_open(*args,**kwargs)
        with patch('builtins.open',flaky_open):self.assertEqual(json_io.read_json(path),{'saved':True})
        self.assertEqual(calls,2)

if __name__=='__main__':unittest.main(verbosity=2)
