const {JSDOM}=require('jsdom');
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const dom=new JSDOM(fs.readFileSync('frontend/index.html','utf8'),{url:'http://127.0.0.1:8765/',runScripts:'outside-only'});
const w=dom.window,d=w.document,run=code=>vm.runInContext(code,dom.getInternalVMContext());
let attempts=0,mode='lock';const names=[];
w.setTimeout=fn=>setTimeout(fn,0);
w.fetch=async(url,options={})=>{
  let data={};
  if(url==='/api/token')data={token:'fixture'};
  else if(url==='/api/library')data={items:[]};
  else if(url==='/api/import'){
    attempts++;names.push(options.body.get('file').name);
    const code=mode==='invalid'?400:mode==='lock' && attempts===1?503:200;
    if(code!==200)return {ok:false,status:code,json:async()=>({status:'error',message:'fixture failure'})};
    data={duplicate:attempts>2};
  }
  return {ok:true,status:200,json:async()=>({status:'ok',data})};
};
for(const s of d.querySelectorAll('script[src]'))run(fs.readFileSync('frontend/'+s.getAttribute('src').split('?')[0],'utf8'));
(async()=>{
  w.testFile=new w.File(['%PDF-1.7'],'locked.pdf',{type:'application/pdf'});
  await run('importFiles([testFile])');
  assert.equal(attempts,2);assert.match(d.getElementById('import-status').textContent,/已导入 1/);
  assert.equal(d.getElementById('import-btn').disabled,false);
  mode='invalid';await run('importFiles([testFile])');assert.equal(attempts,3);
  assert.equal(run('failedImports.length'),1);assert.match(d.getElementById('import-status').textContent,/重试失败文件/);
  mode='recovered';await run('importFiles([...failedImports])');assert.equal(attempts,4);
  assert.equal(run('failedImports.length'),0);assert.match(d.getElementById('import-status').textContent,/跳过 1/);
  assert.equal(new Set(names).size,1);
  console.log('PASS import UI: temporary failures retry safely; invalid PDFs do not loop; failed files can be retried without reselection');
})().then(()=>dom.window.close()).catch(error=>{console.error(error);dom.window.close();process.exitCode=1;});
