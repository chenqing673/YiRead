// Full DOM integration of the independent reader scripts. No browser/user data/model calls.
const {JSDOM}=require('jsdom');
const fs=require('node:fs');const assert=require('node:assert/strict');const vm=require('node:vm');
const html=fs.readFileSync('frontend/reader.html','utf8');
const dom=new JSDOM(html,{url:'http://127.0.0.1:8765/reader.html?id=domtest',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window,d=w.document;
const run=code=>vm.runInContext(code,dom.getInternalVMContext());
let notes={notes:{},version:0},calls=[],posts=[],offline=false;
const paper={pages:[1,2,3].map(page=>({page,width:600,height:800,blocks:[{id:'p'+page+'_a',text:'Compound '+page+' gave 75% yield.'},{id:'p'+page+'_b',text:'Reaction was stirred for 3 hours.'}]}))};
const translation={engine:'openai-compatible',target_lang:'zh',blocks:paper.pages.flatMap(p=>p.blocks.map(b=>({id:b.id,translation:b.text.includes('Compound')?'化合物'+p.page+'的收率为75%。':'反应搅拌3小时。'})))};
const layout={pages:paper.pages.map(p=>({...p,blocks:p.blocks.map((b,i)=>({...b,rects:[[.1,.1+i*.1,.5,.14+i*.1]]}))}))};
w.fetch=async(url,options={})=>{
  calls.push(url);let data={};const body=options.body?JSON.parse(options.body):null;
  if(offline && options.method==='POST')throw new Error('offline');
  if(options.method==='POST')posts.push({url,body});
  if(url==='/api/token')data={token:'dom-token'};
  else if(url.startsWith('/api/item/'))data={title:'DOM test',file_name:'fixture.pdf'};
  else if(url.startsWith('/api/paper/'))data=paper;
  else if(url.startsWith('/api/pdf-layout/'))data=layout;
  else if(url.startsWith('/api/translation/status/'))data={status:'completed',progress:100};
  else if(url.startsWith('/api/translation/') && options.method!=='POST')data=translation;
  else if(url.startsWith('/api/notes/') && options.method!=='POST')data=notes;
  else if(url==='/api/notes'){
    if(body.version!==notes.version)return {ok:false,status:409,json:async()=>({status:'error',message:'conflict'})};
    if(body.note)notes.notes[body.note_id]=body.note;else delete notes.notes[body.note_id];notes.version++;data=notes;
  }else if(url==='/api/translation')data={status:'pending',job_id:'fixture-job',failed:{},pages:body.pages};
  else if(url==='/api/settings')data={base_url:'https://api.deepseek.com',model:'deepseek-flash',has_key:false,aligned:false,batch:true,concurrency:1};
  return {ok:true,status:200,json:async()=>({status:'ok',data:JSON.parse(JSON.stringify(data))})};
};
w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
w.HTMLElement.prototype.scrollTo=function(value){this.scrollTop=value.top || 0;this.scrollLeft=value.left || 0;};
w.HTMLElement.prototype.scrollIntoView=function(){d.getElementById('translation-scroll').scrollTop=Number(this.dataset.page || 1)*200;};
w.HTMLElement.prototype.getBoundingClientRect=function(){return {top:0,left:0,right:600,bottom:800,width:600,height:800};};
w.confirm=()=>true;
for(const script of d.querySelectorAll('script[src]'))run(fs.readFileSync('frontend/'+script.getAttribute('src').split('?')[0],'utf8'));
const settle=()=>new Promise(resolve=>setTimeout(resolve,40));
async function main(){
  await settle();await run('readerNotesReady');
  assert.equal(d.querySelectorAll('[data-block]').length,6);
  assert.equal(d.getElementById('annotation-btn').closest('.translation-header')!==null,true);
  assert.equal(d.querySelector('.translation-label').textContent,'译文');
  assert.equal(d.querySelector('.translation-header').querySelector('small'),null);
  const postsBeforeHelp=posts.length;d.querySelector('[data-help]').click();
  const help=d.querySelector('.yiread-help[open]');assert.ok(help);assert.match(help.textContent,/将此段加入书签/);
  assert.match(help.textContent,/逐句翻译默认关闭/);assert.equal(posts.length,postsBeforeHelp);
  help.querySelector('.dialog-heading button').click();assert.equal(d.querySelector('.yiread-help'),null);
  d.getElementById('notes-btn').click();await settle();d.getElementById('list-add-note').click();
  let noteEntry=d.querySelector('dialog[open]');assert.ok(noteEntry.querySelector('textarea'));noteEntry.querySelector('button').click();
  d.getElementById('translate-btn').click();let dialog=d.querySelector('dialog[open]');assert.ok(dialog);
  const scope=dialog.querySelector('select');scope.value='range';scope.dispatchEvent(new w.Event('change'));const pages=dialog.querySelectorAll('input[type=number]');pages[0].value='2';pages[1].value='3';dialog.querySelector('input[type=checkbox]').checked=false;
  dialog.querySelector('form').dispatchEvent(new w.Event('submit',{cancelable:true}));await settle();
  assert.deepEqual(posts.find(p=>p.url==='/api/translation').body.pages,[2,3]);
  console.log('PASS DOM scope: real dialog selects pages without triggering requests on open');
  d.getElementById('annotation-btn').click();dialog=d.querySelector('dialog[open]');let field=dialog.querySelector('textarea');field.value='刷新也不丢的草稿';field.dispatchEvent(new w.Event('input'));dialog.querySelector('button').click();
  d.getElementById('annotation-btn').click();dialog=d.querySelector('dialog[open]');field=dialog.querySelector('textarea');assert.equal(field.value,'刷新也不丢的草稿');
  offline=true;dialog.querySelector('.primary').click();await settle();assert.match(dialog.textContent,/保存失败/);dialog.querySelector('button').click();
  assert.equal(Object.keys(run("ReaderDrafts.pending('domtest')")).length,1);offline=false;await run('syncPendingReaderNotes()');assert.equal(Object.keys(notes.notes).length,1);
  assert.equal(Object.keys(run("ReaderDrafts.pending('domtest')")).length,0);
  console.log('PASS DOM draft/outbox: input survives reopening; failed save is synced after recovery');
  run('currentStatus={status:"completed"}');
  for(const mode of ['translation','source']){
    run('setMode('+JSON.stringify(mode)+')');
    d.getElementById('page-select').value='2';d.getElementById('page-select').dispatchEvent(new w.Event('change'));
    assert.equal(run('content.dataset.mode'),mode);
    assert.equal(d.querySelector('button[data-mode="'+mode+'"]').getAttribute('aria-pressed'),'true');
    d.getElementById('return-reading-btn').click();
  }
  run('setMode("bilingual")');
  d.getElementById('page-select').value='3';d.getElementById('page-select').dispatchEvent(new w.Event('change'));assert.equal(run('activeTranslation.dataset.block'),'p3_a');
  d.getElementById('return-reading-btn').click();assert.equal(run('activeTranslation.dataset.block'),'p1_a');
  const sheet=d.querySelector('[data-pdf-page="2"]');sheet.dispatchEvent(new w.MouseEvent('click',{bubbles:true,clientX:180,clientY:176}));assert.equal(run('activeTranslation.dataset.block'),'p2_b');
  console.log('PASS DOM navigation: page jump/back and original-page reverse lookup preserve stable block IDs');
  const node=d.querySelector('[data-block="p1_a"] .reading-prose');const range=d.createRange();range.setStart(node.firstChild,0);range.setEnd(node.firstChild,4);w.getSelection().removeAllRanges();w.getSelection().addRange(range);d.dispatchEvent(new w.Event('selectionchange'));
  assert.equal(d.getElementById('excerpt-note-btn').hidden,false);d.getElementById('excerpt-note-btn').click();dialog=d.querySelector('dialog[open]');field=dialog.querySelector('textarea');field.value='文字批注';field.dispatchEvent(new w.Event('input'));dialog.querySelector('.primary').click();await settle();
  const anchored=Object.values(notes.notes).find(n=>n.anchor);assert.equal(anchored.anchor.quote,'化合物1');assert.equal(d.querySelectorAll('mark.reader-excerpt').length,1);
  console.log('PASS DOM excerpts: exact selected text receives a note and safe highlight');
  d.querySelector('button[data-settings]').click();await settle();dialog=d.querySelector('dialog[open]');assert.equal(dialog.querySelector('[name=aligned]').checked,false);assert.equal(dialog.querySelector('[name=batch]').checked,true);assert.equal(dialog.querySelector('[name=concurrency]').value,'1');
  console.log('PASS DOM settings: sentence mode remains off, batching on, concurrency bounded');
}
main().then(()=>dom.window.close()).catch(error=>{console.error(error);dom.window.close();process.exitCode=1;});

