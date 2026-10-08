// Lightweight behavioral tests; no browser, external dependencies, or user data.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
class Element {
  constructor(tag='div') { this.tagName=tag.toUpperCase();this.children=[];this.dataset={};this.attributes={};this.style={setProperty(k,v){this[k]=v;}};this.value='';this._text='';this.events={};this.scrollTop=0;this.scrollLeft=0;this.clientHeight=600;this.clientWidth=600;this.scrollHeight=1200;this.className='';this.classList={toggle:(name,on)=>{const list=new Set(this.className.split(' ').filter(Boolean));if(on)list.add(name);else list.delete(name);this.className=[...list].join(' ');},add:(name)=>this.classList.toggle(name,true),remove:(...names)=>names.forEach(name=>this.classList.toggle(name,false))}; }
  set textContent(value){this._text=String(value);this.children=[];}
  get textContent(){return this._text+this.children.map(node=>typeof node==='string'?node:node.textContent).join('');}
  set innerHTML(value){throw new Error('Dynamic HTML must not be used to render document content');}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this._text='';this.children=nodes;}
  setAttribute(name,value){this.attributes[name]=value;}
  querySelectorAll(selector){const output=[];const visit=node=>{for(const child of node.children){if(typeof child==='string')continue;if(selector==='[data-block]'&&child.dataset.block)output.push(child);if(selector==='[data-follow]'&&child.dataset.follow)output.push(child);if(selector==='[data-page]'&&child.dataset.page)output.push(child);visit(child);}};visit(this);return output;}
  addEventListener(name,fn){this.events[name]=fn;}
  showModal(){this.open=true;}
  close(){this.open=false;}
  remove(){this.removed=true;}
  scrollTo(options){this.scrollTop=options.top;this.scrollLeft=options.left || 0;this.lastScroll=options;}
  focus(){this.focused=true;}
  scrollIntoView(){this.scrolled=true;}
  getBoundingClientRect(){return this.box || {top:0,bottom:600,left:0,width:600,height:600};}
}
function context(api, reader=false){
  const elements=new Map();const storage=new Map();const session=new Map();const listeners={};
  const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const document={getElementById:get,createElement:tag=>new Element(tag),querySelectorAll:()=>[],body:new Element('body'),documentElement:new Element('html'),hidden:false};
  document.documentElement.scrollHeight=2000;
  get('sort-select').value='recent';get('search-input').value='';
  const ctx=vm.createContext({document,location:{search:reader?'?id=sample':'',href:''},URLSearchParams,localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,String(v)),removeItem:k=>storage.delete(k)},setInterval:()=>0,setTimeout:()=>0,clearTimeout:()=>{},requestAnimationFrame:fn=>fn(),window:{addEventListener:(name,fn)=>listeners[name]=fn,scrollTo:()=>{}},apiFetch:api,apiPost:async()=>({data:{status:'pending'}}),console,innerHeight:800,scrollY:300});
  vm.runInContext(fs.readFileSync('frontend/js/providers.js','utf8'),ctx);
  vm.runInContext(fs.readFileSync('frontend/js/ui.js','utf8'),ctx);
  vm.runInContext(fs.readFileSync('frontend/js/pdf-follow.js','utf8'),ctx);
  vm.runInContext(fs.readFileSync('frontend/js/reading-format.js','utf8'),ctx);
  ctx.sessionStorage={getItem:key=>session.get(key)||null,setItem:(key,value)=>session.set(key,String(value))};
  ctx.apiAuthedGet=api;
  return {ctx,get,document,storage,listeners,session};
}
const settle=async()=>{for(let i=0;i<15;i++)await Promise.resolve();};
(async()=>{
  const themeRoot=new Element('html');themeRoot.dataset.theme='light';
  const themeButton=new Element('button');themeButton.dataset.theme='';
  const themeStore=new Map();
  const themeContext=vm.createContext({document:{documentElement:themeRoot,querySelectorAll:selector=>selector==='[data-theme]'?[themeRoot,themeButton]:selector==='button[data-theme]'?[themeButton]:[]},localStorage:{setItem:(key,value)=>themeStore.set(key,value)},setTimeout:()=>0,clearTimeout:()=>{}});
  vm.runInContext(fs.readFileSync('frontend/js/ui.js','utf8'),themeContext);
  function clickWithBubble(node){if(node.onclick)node.onclick();if(node!==themeRoot&&themeRoot.onclick)themeRoot.onclick();}
  clickWithBubble(themeButton);assert.equal(themeRoot.dataset.theme,'dark');assert.equal(themeStore.get('yiread-theme'),'dark');
  clickWithBubble(new Element('div'));assert.equal(themeRoot.dataset.theme,'dark');
  clickWithBubble(themeButton);assert.equal(themeRoot.dataset.theme,'light');
  assert.equal(themeRoot.onclick,undefined);
  console.log('PASS theme: one toggle per button click, no toggle on unrelated clicks');
  function descendants(node){return [node,...node.children.filter(n=>typeof n!=='string').flatMap(descendants)];}
  const formatting=context(async()=>({data:{}}));formatting.ctx.formatted=new Element();
  vm.runInContext("renderReadingText(formatted,'| 条目 | 收率 (%) |\\n| --- | ---: |\\n| **A** | 75.3 |\\n| B | 68.5 |\\n\\nH2O / 13C NMR / ^a / C_{6}H_{6} / compound 12')",formatting.ctx);
  const formattedNodes=descendants(formatting.ctx.formatted);const table=formattedNodes.find(n=>n.tagName==='TABLE');assert.ok(table);assert.equal(formattedNodes.filter(n=>n.tagName==='TR').length,3);
  assert.equal(formattedNodes.find(n=>n.tagName==='TH'&&n.textContent==='收率 (%)').style.textAlign,'right');
  assert.ok(formattedNodes.some(n=>n.tagName==='SUP'&&n.textContent==='13'));assert.ok(formattedNodes.some(n=>n.tagName==='SUB'&&n.textContent==='2'));assert.ok(formattedNodes.some(n=>n.tagName==='STRONG'&&n.textContent==='A'));
  assert.ok(formatting.ctx.formatted.textContent.includes('compound 12'));
  vm.runInContext("renderReadingText(formatted,'<img src=x onerror=alert(1)>\\n<script>alert(1)</script>\\n[link](javascript:alert(1))')",formatting.ctx);
  assert.ok(formatting.ctx.formatted.textContent.includes('<script>'));assert.ok(!descendants(formatting.ctx.formatted).some(n=>['IMG','SCRIPT','A'].includes(n.tagName)));
  console.log('PASS formatting: real tables, alignment, chemistry scripts, literal untrusted content');
  const attack='<img src=x onerror=alert(1)>';
  const papers=[{id:'sample',title:attack,file_name:'safe.pdf',file_size:2048,created_at:'2026-10-05',translation_status:{status:'completed'}},{id:'next',title:'Another document',file_name:'next.pdf',created_at:'2026-10-04',translation_status:{status:'failed'}}];
  const library=context(async()=>({data:{items:papers}}));
  vm.runInContext(fs.readFileSync('frontend/js/app.js','utf8'),library.ctx);await settle();
  const motto=library.get('library-motto').textContent;assert.ok(motto.length>0);assert.equal(library.session.get('yiread-motto'),motto);
  const mottoCount=vm.runInContext('mottos.length',library.ctx),seen=new Set([motto]);
  for(let i=1;i<mottoCount;i++){vm.runInContext('initializeMotto()',library.ctx);const next=library.get('library-motto').textContent;assert.ok(!seen.has(next));seen.add(next);}
  const last=library.get('library-motto').textContent;vm.runInContext('initializeMotto()',library.ctx);assert.notEqual(library.get('library-motto').textContent,last);
  assert.equal(library.get('library').children.length,2);
  assert.equal(library.get('library').dataset.view,'list');
  assert.ok(library.get('library').textContent.includes(attack));
  library.get('search-input').value='another';library.get('search-input').oninput();
  assert.equal(library.get('library').children.length,1);assert.ok(library.get('library').textContent.includes('Another document'));
  library.get('search-input').value='missing';library.get('search-input').oninput();assert.ok(library.get('library').textContent.includes('没有找到'));
  papers[0].tags=['Ullmann'];papers[0].doi='10.1234/example';papers[0].favorite=true;
  library.get('search-input').value='ullmann';library.get('search-input').oninput();assert.equal(library.get('library').children.length,1);
  library.get('search-input').value='10.1234/example';library.get('search-input').oninput();assert.equal(library.get('library').children.length,1);
  vm.runInContext("filter='favorite';renderLibrary()",library.ctx);assert.equal(library.get('library').children.length,1);
  console.log('PASS library: literal text rendering, search, empty state');
  let result={blocks:[{id:'b1',translation:'第一段翻译'}]};let status={status:'running',progress:50};let noteServer={notes:{},version:0};
  const reader=context(async url=>{
    if(url.startsWith('/api/item/'))return {data:{title:attack,file_name:'sample.pdf'}};
    if(url.startsWith('/api/pdf-layout/'))return {data:{pages:[{page:1,width:600,height:800,blocks:[{id:'b1',rects:[[.1,.2,.8,.25]]},{id:'b2',rects:[[.1,.5,.8,.55]]}]}]}};
    if(url.startsWith('/api/paper/'))return {data:{pages:[{page:1,blocks:[{id:'b1',text:attack},{id:'b2',text:'Second paragraph'}]}]}};
    if(url.startsWith('/api/translation/status/'))return {data:status};
    if(url.startsWith('/api/notes/'))return {data:JSON.parse(JSON.stringify(noteServer))};
    return {data:result};
  },true);
  vm.runInContext(fs.readFileSync('frontend/js/reader.js','utf8'),reader.ctx);await vm.runInContext('readerReady',reader.ctx);
  const targets=reader.get('reader-content').querySelectorAll('[data-block]');assert.equal(targets.length,2);
  assert.equal(targets[0].textContent,'第一段翻译');assert.equal(targets[1].textContent,'这一段还没有译文');
  const originalPage=reader.get('reader-content').children[0];
  result={blocks:[{id:'b1',translation:'第一段翻译'},{id:'b2',translation:attack}]};status={status:'completed',progress:100};
  await vm.runInContext('pollStatus()',reader.ctx);
  assert.equal(reader.get('reader-content').children[0],originalPage);assert.equal(targets[1].textContent,attack);assert.equal(reader.get('export-btn').disabled,false);
  reader.get('font-plus').onclick();assert.equal(reader.storage.get('yiread-font'),'18');
  vm.runInContext("setMode('source')",reader.ctx);assert.equal(reader.get('reader-content').dataset.mode,'source');
  vm.runInContext("setMode('bilingual')",reader.ctx);
  vm.runInContext("activateTranslation(content.querySelectorAll('[data-block]')[1],true)",reader.ctx);
  const pdfPages=reader.get('pdf-pages');const overlay=pdfPages.children[0].children[1];
  assert.equal(pdfPages.children[0].children[0].src,'/api/pdf-page/sample/1');
  assert.equal(overlay.children.length,1);assert.equal(overlay.children[0].style.top,'50%');
  const previousScroll=reader.get('pdf-scroll').lastScroll;reader.get('follow-btn').onclick();
  vm.runInContext("activateTranslation(content.querySelectorAll('[data-block]')[0],true)",reader.ctx);
  assert.equal(reader.get('pdf-scroll').lastScroll,previousScroll);
  reader.get('follow-btn').onclick();assert.equal(overlay.children[0].style.top,'20%');
  vm.runInContext("pdfFollower.focus('unknown-block',true)",reader.ctx);assert.equal(overlay.children.length,0);
  vm.runInContext("pdfFollower.focus('b2',true)",reader.ctx);
  reader.ctx.wholePageRects=Array.from({length:25},(_,i)=>[.1,.1+i*.03,.9,.12+i*.03]);
  assert.equal(vm.runInContext('pdfBlockKind({blocks:[{}]},{rects:wholePageRects})',reader.ctx),'page');
  assert.notEqual(vm.runInContext('pdfBlockKind({blocks:[{},{}]},{rects:wholePageRects})',reader.ctx),'page');
  vm.runInContext("pdfFollower.blocks.set('old-page',{page:1,rects:wholePageRects,kind:'page'});pdfFollower.focus('old-page',true)",reader.ctx);
  assert.equal(overlay.children.length,0);assert.ok(reader.get('pdf-sync-status').textContent.includes('仅定位页面'));
  vm.runInContext("pdfFollower.focus('b2',true)",reader.ctx);
  reader.get('pdf-zoom').onchange({target:{value:'150'}});assert.equal(pdfPages.style.width,'150%');assert.equal(overlay.children[0].style.top,'50%');
  const nodes=[new Element(),new Element(),new Element()];nodes[0].box={top:-80,bottom:40};nodes[1].box={top:40,bottom:220};nodes[2].box={top:220,bottom:500};
  reader.ctx.readingNodes=nodes;assert.equal(vm.runInContext('blockAtReadingLine(readingNodes,{top:0,bottom:600})',reader.ctx),nodes[1]);
  // Paragraph fallback never guesses a source line from translated paragraph height.
  vm.runInContext("pdfFollower.blocks.set('long',{page:1,rects:[[.1,.1,.8,.15],[.1,.5,.8,.55],[.1,.8,.8,.85]]})",reader.ctx);
  pdfPages.children[0].box={top:300,bottom:1300,left:20,width:600,height:1000};
  reader.get('pdf-scroll').box={top:100,bottom:700,left:20,width:600,height:600};reader.get('pdf-scroll').scrollTop=200;
  vm.runInContext("pdfFollower.focus('long',true,.5)",reader.ctx);
  assert.ok(overlay.children.every(n=>n.className==='pdf-highlight'));
  assert.equal(reader.get('pdf-scroll').lastScroll.top,385); // first source line at the 140px reading line
  const stableScroll=reader.get('pdf-scroll').lastScroll;
  vm.runInContext("pdfFollower.focus('long',false,.55)",reader.ctx);assert.equal(reader.get('pdf-scroll').lastScroll,stableScroll);
  vm.runInContext("pdfFollower.focus('long',false,.9)",reader.ctx);assert.equal(reader.get('pdf-scroll').lastScroll,stableScroll);
  reader.get('follow-btn').onclick();const pausedScroll=reader.get('pdf-scroll').lastScroll;
  vm.runInContext("pdfFollower.focus('long',false,.1)",reader.ctx);assert.equal(reader.get('pdf-scroll').lastScroll,pausedScroll);
  reader.get('follow-btn').onclick();assert.ok(overlay.children.every(n=>n.className==='pdf-highlight'));
  result={engine:'openai-compatible',blocks:[{id:'b1',translation:'合并译文',segments:[{id:'b1_s1',text:'First source.',translation:attack,rects:[[.1,.2,.8,.25]]},{id:'b1_s2',text:'Second source.',translation:'第二小段',rects:[[.1,.3,.8,.35]]}]}]};
  await vm.runInContext('refreshTranslations()',reader.ctx);
  const alignedTargets=reader.get('reader-content').querySelectorAll('[data-block]');assert.equal(alignedTargets.length,3);assert.equal(alignedTargets[0].textContent,attack);assert.equal(alignedTargets[1].dataset.parent,'b1');
  vm.runInContext("activateTranslation(content.querySelectorAll('[data-block]')[1],true)",reader.ctx);assert.equal(overlay.children[0].style.top,'30%');
  const alignedPage=reader.get('reader-content').children[0];await vm.runInContext('refreshTranslations()',reader.ctx);assert.equal(reader.get('reader-content').children[0],alignedPage);
  result.blocks[0].segments[0].translation='首句。次句。';
  result.blocks[0].segments[0].reading_units=[{id:'sentence-a',start:0,end:3,kind:'sentence-order',rects:[[.1,.21,.4,.25]]},{id:'sentence-b',start:3,end:6,kind:'sentence-order',rects:[[.4,.21,.8,.25],[.1,.26,.5,.3]]}];
  await vm.runInContext('refreshTranslations()',reader.ctx);
  const sentences=alignedTargets[0].querySelectorAll('[data-follow]');assert.equal(sentences.length,2);assert.equal(alignedTargets[0].textContent,'首句。次句。');
  sentences[0].getClientRects=()=>[{top:80,bottom:100},{top:100,bottom:120}];
  sentences[1].getClientRects=()=>[{top:120,bottom:140},{top:140,bottom:160}];
  vm.runInContext("activateTranslation(content.querySelectorAll('[data-block]')[0],true)",reader.ctx);
  assert.equal(vm.runInContext('activeSentence.dataset.follow',reader.ctx),'sentence-b');
  assert.equal(overlay.children.length,2);assert.equal(overlay.children[0].style.left,'40%');assert.ok(overlay.children.every(n=>n.className.includes('pdf-highlight-current')));
  const sentenceScroll=reader.get('pdf-scroll').lastScroll;vm.runInContext('updateReadingPosition()',reader.ctx);assert.equal(reader.get('pdf-scroll').lastScroll,sentenceScroll);
  alignedTargets[0].onclick({target:{closest:()=>sentences[0]},clientY:90});assert.equal(overlay.children.length,1);assert.equal(overlay.children[0].style.left,'10%');
  const stableSentence=sentences[0];await vm.runInContext('refreshTranslations()',reader.ctx);assert.equal(alignedTargets[0].querySelectorAll('[data-follow]')[0],stableSentence);
  reader.get('follow-btn').onclick();alignedTargets[0].onclick({target:{closest:()=>sentences[1]},clientY:150});assert.equal(overlay.children.length,1);
  reader.get('follow-btn').onclick();assert.equal(overlay.children.length,2);
  vm.runInContext("activateTranslation(content.querySelectorAll('[data-block]')[1],true)",reader.ctx);
  vm.runInContext(fs.readFileSync('frontend/js/reader-notes.js','utf8'),reader.ctx);
  reader.ctx.apiPost=async(url,body)=>{assert.equal(url,'/api/notes');assert.equal(body.version,noteServer.version);if(body.note)noteServer.notes[body.note_id]=JSON.parse(JSON.stringify(body.note));else delete noteServer.notes[body.note_id];noteServer.version++;return {data:JSON.parse(JSON.stringify(noteServer))};};
  await vm.runInContext('readerNotesReady',reader.ctx);assert.equal(reader.get('annotation-btn').disabled,false);
  reader.get('annotation-btn').onclick();const noteDialog=reader.document.body.children.at(-1);
  const noteNodes=descendants(noteDialog);noteNodes.find(n=>n.tagName==='TEXTAREA').value='<img src=x onerror=alert(1)> 核对收率';noteNodes.find(n=>n.tagName==='INPUT').checked=true;
  await noteNodes.find(n=>n.tagName==='BUTTON'&&n.textContent==='保存').onclick();
  const savedNotes=JSON.parse(reader.storage.get('yiread-notes-sample'));assert.equal(savedNotes.b1_s2.bookmark,true);assert.ok(savedNotes.b1_s2.text.includes('核对收率'));
  assert.ok(alignedTargets[1].className.includes('is-bookmarked'));
  await reader.get('notes-btn').onclick();const notesList=reader.document.body.children.at(-1);assert.ok(notesList.textContent.includes('<img'));assert.ok(!descendants(notesList).some(n=>n.tagName==='IMG'));
  descendants(notesList).find(n=>n.tagName==='BUTTON'&&n.textContent.startsWith('第 1 页')).onclick();assert.equal(vm.runInContext('activeTranslation.dataset.block',reader.ctx),'b1_s2');
  // Parent notes remain editable when old paragraphs are split into new segments.
  noteServer.notes.b1={text:'旧整段笔记',bookmark:true,parent:'b1',page:1,quote:'原段'};noteServer.version++;
  await vm.runInContext('(async()=>{await fetchReaderNotes();applyReaderNotes();})()',reader.ctx);
  vm.runInContext("activateTranslation(content.querySelectorAll('[data-block]')[0],true)",reader.ctx);
  reader.get('annotation-btn').onclick();const parentDialog=reader.document.body.children.at(-1);const parentNodes=descendants(parentDialog);
  assert.equal(parentNodes.find(n=>n.tagName==='TEXTAREA').value,'旧整段笔记');parentNodes.find(n=>n.tagName==='TEXTAREA').value='修订旧笔记';
  await parentNodes.find(n=>n.tagName==='BUTTON'&&n.textContent==='保存').onclick();assert.equal(noteServer.notes.b1.text,'修订旧笔记');assert.ok(!noteServer.notes.b1_s1);
  await reader.get('notes-btn').onclick();const deleteList=reader.document.body.children.at(-1);await descendants(deleteList).find(n=>n.tagName==='BUTTON'&&n.textContent==='删除').onclick();assert.equal(Object.keys(noteServer.notes).length,1);
  // A stale browser cache must never resurrect a note deleted in another tab.
  noteServer.notes={};noteServer.version++;await vm.runInContext('loadReaderNotes()',reader.ctx);assert.equal(Object.keys(vm.runInContext('readerNotes',reader.ctx)).length,0);
  reader.storage.delete('yiread-notes-sample-migrated');reader.storage.set('yiread-notes-sample',JSON.stringify({b1:{text:'待迁移笔记',bookmark:true,parent:'b1',page:1,quote:'本地旧引用'}}));
  await vm.runInContext('loadReaderNotes()',reader.ctx);assert.equal(noteServer.notes.b1.text,'待迁移笔记');assert.equal(reader.storage.get('yiread-notes-sample-migrated'),'true');assert.ok(!reader.storage.has('yiread-notes-sample-legacy'));
  reader.get('annotation-btn').onclick();const failedDialog=reader.document.body.children.at(-1);const failedNodes=descendants(failedDialog);failedNodes.find(n=>n.tagName==='TEXTAREA').value='保存冲突时保留的草稿';
  const validNotePost=reader.ctx.apiPost;
  reader.ctx.apiPost=async()=>{const error=new Error('conflict');error.code=409;throw error;};noteServer.version++;
  await failedNodes.find(n=>n.tagName==='BUTTON'&&n.textContent==='保存').onclick();assert.equal(failedDialog.open,true);assert.equal(failedNodes.find(n=>n.tagName==='TEXTAREA').value,'保存冲突时保留的草稿');assert.ok(failedDialog.textContent.includes('其他页面已更新'));
  reader.ctx.apiPost=validNotePost;await failedNodes.find(n=>n.tagName==='BUTTON'&&n.textContent==='保存').onclick();assert.equal(failedDialog.removed,true);assert.equal(noteServer.notes.b1.text,'保存冲突时保留的草稿');
  console.log('PASS notes: durable save, parent-note editing, deletion, cache consistency, safe display, source navigation');
  console.log('PASS reader: original PDF, matched highlight, follow on/off, reading line, stable translation updates');
  const settings=context(async()=>({data:{}}));
  const fields={base_url:new Element('input'),model:new Element('input'),api_key:new Element('input')};
  const controls=new Map(['provider-select','model-select','custom-model-label','provider-help','key-change-note'].map(id=>['#'+id,new Element(id.endsWith('select')?'select':'div')]));
  settings.ctx.form={elements:fields,dataset:{}};settings.ctx.root={querySelector:selector=>controls.get(selector)};
  const picker=vm.runInContext('setupProviderPicker(form,root)',settings.ctx);
  picker.load({base_url:'https://api.openai.com/v1',model:'gpt-4.1',has_key:true});
  assert.equal(controls.get('#provider-select').value,'openai');assert.equal(controls.get('#model-select').value,'gpt-4.1');
  assert.equal(controls.get('#custom-model-label').hidden,true);assert.ok(fields.api_key.placeholder.includes('密钥已保存'));
  const help=controls.get('#provider-help');const links=help.children[0].children;
  assert.ok(links.some(link=>link.href==='https://platform.openai.com/api-keys'));
  for(const link of links){assert.ok(link.href.startsWith('https://'));assert.equal(link.target,'_blank');assert.equal(link.rel,'noopener noreferrer');}
  fields.api_key.value='old-unsaved-key';controls.get('#provider-select').value='deepseek';controls.get('#provider-select').onchange();
  assert.equal(fields.base_url.value,'https://api.deepseek.com');assert.equal(fields.model.value,'deepseek-flash');assert.equal(fields.api_key.value,'');assert.equal(controls.get('#key-change-note').hidden,false);
  controls.get('#model-select').value='custom';controls.get('#model-select').onchange();assert.equal(controls.get('#custom-model-label').hidden,false);assert.equal(fields.model.value,'');
  picker.load({base_url:'http://127.0.0.1:1234/v1',model:'my-local-model',has_key:false});
  assert.equal(controls.get('#provider-select').value,'custom');assert.equal(fields.model.value,'my-local-model');assert.equal(controls.get('#custom-model-label').hidden,false);
  assert.equal(controls.get('#provider-help').children.length,1);
  picker.load({base_url:'https://api.openai.com/v1/',model:'future-model',has_key:true});
  assert.equal(controls.get('#provider-select').value,'openai');assert.equal(fields.model.value,'future-model');assert.equal(controls.get('#model-select').value,'custom');
  picker.saved({base_url:'https://api.deepseek.com',has_key:false});assert.ok(!fields.api_key.placeholder.includes('密钥已保存'));
  const providerOptions=controls.get('#provider-select').children;
  assert.equal(providerOptions.length,11);
  assert.ok(providerOptions.find(option=>option.value==='qwen').textContent.includes('新用户免费额度'));
  assert.ok(!providerOptions.find(option=>option.value==='siliconflow').textContent.includes('免费'));
  for(const id of ['zhipu','siliconflow','gemini','groq','openrouter','mistral']){
    fields.api_key.value='unsaved';controls.get('#provider-select').value=id;controls.get('#provider-select').onchange();
    const selectedEndpoint=fields.base_url.value,selectedModel=fields.model.value;
    assert.ok(selectedEndpoint.startsWith('https://'));assert.ok(selectedModel);assert.equal(fields.api_key.value,'');
    assert.ok(help.children[0].children.some(link=>link.textContent.includes('申请 API Key')));
    assert.ok(help.children[0].children.some(link=>link.textContent.includes('额度 / 价格说明')));
    picker.load({base_url:selectedEndpoint+'/',model:selectedModel,has_key:true});
    assert.equal(controls.get('#provider-select').value,id);assert.equal(fields.model.value,selectedModel);
  }
  controls.get('#provider-select').value='zhipu';controls.get('#provider-select').onchange();
  assert.ok(help.textContent.includes('免费 API'));assert.ok(controls.get('#model-select').children[0].textContent.includes('免费模型'));
  controls.get('#provider-select').value='deepseek';controls.get('#provider-select').onchange();
  assert.ok(!help.textContent.includes('免费 API'));assert.ok(!controls.get('#model-select').children[0].textContent.includes('免费模型'));
  console.log('PASS settings: provider models, quota labels/links, endpoint switch, custom configuration preservation');
  let attempts=0;const cleared=[];const apiCtx=vm.createContext({fetch:async()=>{attempts++;return attempts===1?{status:403,ok:false,json:async()=>({status:'error',message:'invalid token'})}:{status:200,ok:true,json:async()=>({status:'ok',data:{done:true}})};},ensureToken:async()=>attempts?'new-token':'stale-token',localStorage:{removeItem:key=>cleared.push(key)},showError:()=>{}});
  vm.runInContext(fs.readFileSync('frontend/js/api.js','utf8'),apiCtx);
  const response=await vm.runInContext("apiPost('/api/translation',{paper_id:'sample'})",apiCtx);
  assert.equal(response.data.done,true);assert.equal(attempts,2);assert.deepEqual(cleared,['token']);
  console.log('PASS API: expired token refresh and one safe retry');
})().catch(error=>{console.error(error);process.exitCode=1;});
