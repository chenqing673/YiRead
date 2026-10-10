const paperId = new URLSearchParams(location.search).get('id');
let paper, item, translations = {}, currentStatus, pollBusy = false, observedPage = 1;
const content = document.getElementById('reader-content');
const translateButton = document.getElementById('translate-btn');
const translationScroll=document.getElementById('translation-scroll');
const pdfFollower=new PdfFollower(paperId);
let readerLayoutMode=localStorage.getItem('yiread-layout')==='page'?'page':'flow';
let layoutChanging=false;
let readerLoading=true,translationRefreshNeeded=true,refreshSerial=0;
const pageLayout=new ReaderPageLayout(paperId,translationScroll,id=>setReaderLayout('flow',id),()=>{translationRefreshNeeded=true;});
const flowMedia=new ReaderFlowMedia(paperId,()=>readerLayoutMode==='flow',(asset,page)=>{
  pdfFollower.blocks.set(asset.id,{page,rects:[asset.box],kind:'figure'});pdfFollower.focus(asset.id,true);
  observedPage=page;document.getElementById('page-select').value=page;
});
let activeTranslation=null;
let activeSentence=null;
let translatedBlocks={},translationShape='';
let fontSize = Math.max(14, Math.min(24, Number(localStorage.getItem('yiread-font')) || 17));
function setFont() { document.documentElement.style.setProperty('--reading-font', fontSize + 'px'); localStorage.setItem('yiread-font',fontSize);if(paper)requestAnimationFrame(updateReadingPosition); }
setFont();
document.getElementById('font-minus').onclick=()=>{fontSize=Math.max(14,fontSize-1);setFont();};
document.getElementById('font-plus').onclick=()=>{fontSize=Math.min(24,fontSize+1);setFont();};
function setMode(mode) {
  content.dataset.mode=mode;document.body.classList.remove('mode-source','mode-translation');
  if (mode !== 'bilingual') document.body.classList.add('mode-' + mode);
  document.querySelectorAll('[data-mode]').forEach(button=>{if(button.tagName==='BUTTON') {button.classList.toggle('active',button.dataset.mode===mode);button.setAttribute('aria-pressed',String(button.dataset.mode===mode));}});
  localStorage.setItem('yiread-mode',mode);
  requestAnimationFrame(()=>{pageLayout.resize();if(activeTranslation && mode==='bilingual'){updateReadingPosition();pdfFollower.focus(activeSentence?.dataset.follow || activeTranslation.dataset.block,true);}});
}
function updateLayoutControls(){
  content.dataset.layout=readerLayoutMode;
  document.querySelectorAll('button[data-layout]').forEach(button=>{const active=button.dataset.layout===readerLayoutMode;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
  document.getElementById('layout-hint').hidden=readerLayoutMode!=='page';
  document.getElementById('layout-zoom-label').hidden=readerLayoutMode!=='page';
  for(const id of ['font-minus','font-plus']){const button=document.getElementById(id);button.disabled=readerLayoutMode==='page';button.title=readerLayoutMode==='page'?'原版排版请使用版式缩放':'';}
  document.getElementById('layout-zoom').value=pageLayout.zoom;
}
async function setReaderLayout(mode,targetId){
  if(layoutChanging || readerLoading)return;
  const previous=activeTranslation?.dataset.block;
  const parentId=targetId || activeTranslation?.dataset.parent || previous;
  readerLayoutMode=mode==='page'?'page':'flow';localStorage.setItem('yiread-layout',readerLayoutMode);updateLayoutControls();
  if(!paper)return;
  layoutChanging=true;content.inert=true;content.setAttribute('aria-busy','true');
  document.querySelectorAll('button[data-layout]').forEach(b=>b.disabled=true);
  document.getElementById('page-select').disabled=true;document.getElementById('layout-zoom').disabled=true;
  activeTranslation=null;activeSentence=null;
  try{buildPages();await refreshTranslations();}
  finally{
    layoutChanging=false;content.inert=false;content.removeAttribute('aria-busy');
    document.querySelectorAll('button[data-layout]').forEach(b=>b.disabled=false);
    document.getElementById('page-select').disabled=false;document.getElementById('layout-zoom').disabled=false;
  }
  const nodes=Array.from(content.querySelectorAll('[data-block]'));
  const target=nodes.find(n=>n.dataset.block===previous && !targetId) || nodes.find(n=>(n.dataset.parent || n.dataset.block)===parentId);
  if(target){
    if(typeof readerNavigationUntil==='number')readerNavigationUntil=Date.now()+650;
    if(readerLayoutMode==='page' && target.closest('details'))target.closest('.reading-page').scrollIntoView({block:'start',behavior:'auto'});
    else{target.closest('details')?.setAttribute('open','');target.scrollIntoView({block:'center',behavior:'auto'});}
    activateTranslation(target,true);
  }
  else updateReadingPosition();
}
document.querySelectorAll('button[data-layout]').forEach(button=>button.onclick=()=>{setReaderLayout(button.dataset.layout).catch(error=>showError(error.message));});
document.getElementById('layout-zoom').onchange=event=>{
  const target=activeTranslation;
  if(typeof readerNavigationUntil==='number')readerNavigationUntil=Date.now()+650;
  pageLayout.setZoom(event.target.value);
  if(target?.isConnected){target.scrollIntoView({block:'center',behavior:'auto'});activateTranslation(target,true);}
};
updateLayoutControls();
document.querySelectorAll('button[data-mode]').forEach(button=>button.onclick=()=>setMode(button.dataset.mode));
setMode(['source','translation'].includes(localStorage.getItem('yiread-mode')) ? localStorage.getItem('yiread-mode') : 'bilingual');
document.getElementById('back-top').onclick=()=>{translationScroll.scrollTo({top:0,behavior:'smooth'});pdfFollower.page(1);};
function updateStatus(ts) {
  currentStatus=ts;
  if(typeof showTranslationProgress==='function')showTranslationProgress(ts);
  const active=['pending','running'].includes(ts.status);
  document.getElementById('translation-status').textContent=statusText(ts) + (ts.error ? '：' + ts.error : '');
  translateButton.disabled=active;
  translateButton.textContent=active ? (ts.status==='pending' ? '排队中…' : '正在翻译…') : ts.status==='failed' ? '继续翻译' : ts.status==='completed' ? '重新翻译' : '翻译全文';
}
function buildPages() {
  pageLayout.reset();
  content.replaceChildren(); const select=document.getElementById('page-select');select.replaceChildren();
  for (const page of paper.pages) {
    const option=el('option','',String(page.page));option.value=page.page;select.append(option);
    const section=el('section','reading-page');section.id='page-' + page.page;section.dataset.page=page.page;
    section.append(el('h2','page-title','PAGE ' + String(page.page).padStart(2,'0')));
    if (!page.blocks.length) section.append(el('p','block-text placeholder','本页没有可提取的文字。请打开原始 PDF 查看图片或扫描内容。'));
    for (const original of page.blocks) {
      if(original.role==='diagram-label')continue;
      const segments=translatedBlocks[original.id]?.segments;
      for(const block of segments?.length && (readerLayoutMode==='flow' || translatedBlocks[original.id]?.layout_version===1) ? segments : [original]) {
      const target=el('div','block-text translation-text');target.dataset.block=block.id;target.dataset.page=page.page;target.tabIndex=0;
      target.dataset.parent=original.id;
      if(segments?.length)pdfFollower.blocks.set(block.id,{page:page.page,rects:block.rects || []});
      target.onclick=event=>activateTranslation(target,true,event.target?.closest?.('[data-follow]') || sentenceAtReadingLine(target,event.clientY));
      target.onfocus=()=>activateTranslation(target,true);
      target.onkeydown=event=>{if(event.key==='Enter')activateTranslation(target,true);};
      section.append(target);
      }
    }
    content.append(section);
  }
  select.onchange=()=>navigateReaderPage(select.value);
  if (!paper.pages.length) document.getElementById('status').textContent='这份文献没有可阅读的页面。';
}
function navigateReaderPage(value){
  const section=document.getElementById('page-'+value);if(!section)return;
  const target=Array.from(section.querySelectorAll('[data-block]')).find(n=>!n.classList.contains('layout-hidden') && (!n.closest('details') || n.closest('details').open));
  if(target && typeof jumpReaderTarget==='function')jumpReaderTarget(target,undefined,true);
  else{
    if(typeof rememberReaderPosition==='function')rememberReaderPosition();
    if(typeof readerNavigationUntil==='number')readerNavigationUntil=Date.now()+650;
    section.scrollIntoView({block:'start',behavior:'auto'});observedPage=Number(value);
    activeTranslation?.classList.remove('reading-active');activeSentence?.classList.remove('reading-sentence-active');activeTranslation=null;activeSentence=null;
    for(const id of ['edit-current-btn','retry-current-btn','restore-current-btn','annotation-btn'])document.getElementById(id).disabled=true;
  }
  document.getElementById('page-select').value=value;pdfFollower.page(value);
}
async function refreshTranslations() {
  const serial=++refreshSerial;
  let result;
  try {result=await apiFetch('/api/translation/' + encodeURIComponent(paperId),{},true);}
  catch(error) {if(serial!==refreshSerial)return;if(error.code===404){translationRefreshNeeded=false;if(readerLayoutMode==='flow')flowMedia.update(paper);return;}throw error;}
  if(serial!==refreshSerial)return;
  translations={};
  translatedBlocks=Object.fromEntries((result.data.blocks || []).map(block=>[block.id,block]));
  const shape=JSON.stringify((result.data.blocks || []).filter(b=>b.segments?.length).map(b=>[b.id,b.layout_version || 0,b.segments.map(s=>s.id)]));
  if(shape!==translationShape) {
    const top=translationScroll.scrollTop;const active=activeTranslation?.dataset.block;
    translationShape=shape;buildPages();activeTranslation=null;activeSentence=null;
    translationScroll.scrollTo({top,behavior:'auto'});
    const match=Array.from(content.querySelectorAll('[data-block]')).find(n=>n.dataset.block===active);
    if(match)activateTranslation(match,true);
  }
  let legacy=false;
  for (const block of result.data.blocks || []) {
    if (block.translation?.startsWith('[译文]') && !result.data.engine) {legacy=true;continue;}
    translations[block.id]=block.translation;
    for(const segment of block.segments || [])translations[segment.id]=segment.translation;
  }
  for(const page of paper.pages)for(const original of page.blocks) {
    const output=translatedBlocks[original.id];
    for(const target of output?.segments?.length ? output.segments : output ? [output] : []) {
      if(output.segments?.length)pdfFollower.blocks.set(target.id,{page:page.page,rects:target.rects || []});
      for(const unit of target.reading_units || [])pdfFollower.blocks.set(unit.id,{page:page.page,rects:unit.rects,kind:unit.kind});
    }
  }
  content.querySelectorAll('[data-block]').forEach(node=>{
    const text=translations[node.dataset.block];
    const value=text || '这一段还没有译文';
    const parent=translatedBlocks[node.dataset.parent || node.dataset.block];
    const target=parent?.segments?.find(s=>s.id===node.dataset.block) || parent;
    const units=target?.reading_units || [];
    const alignmentShape=JSON.stringify(units.map(unit=>[unit.id,unit.start,unit.end,unit.kind,unit.rects]));
    if (node.dataset.renderedText!==value || node.dataset.alignmentShape!==alignmentShape) {
      renderReadingText(node,value,units);node.dataset.alignmentShape=alignmentShape;
      if(activeTranslation===node)activeSentence=null;
    }
    node.classList.toggle('placeholder',!text);
  });
  if(typeof applyReaderNotes==='function')applyReaderNotes();
  const fresh=readerLayoutMode==='page' ? await pageLayout.update(paper,translatedBlocks,result.data.revision || '') : true;
  if(serial!==refreshSerial)return;
  translationRefreshNeeded=!fresh;
  if(readerLayoutMode==='flow')flowMedia.update(paper);
  document.getElementById('export-btn').disabled=!Object.keys(translations).length;
  if (legacy) document.getElementById('status').textContent='检测到旧版模拟译文。请配置翻译服务并重新翻译，获得真实译文。';
}
async function pollStatus() {
  if (!paperId || pollBusy || layoutChanging || document.hidden || !paper) return;
  pollBusy=true;
  try {
    const {data:ts}=await apiFetch('/api/translation/status/' + encodeURIComponent(paperId),{},true);
    const changed=translationRefreshNeeded || !currentStatus || ts.status!==currentStatus.status || ts.progress!==currentStatus.progress || ts.completed!==currentStatus.completed;
    updateStatus(ts);
    if(changed) {translationRefreshNeeded=true;await refreshTranslations();updateReadingPosition();}
  } catch(error) {translationRefreshNeeded=true;document.getElementById('translation-status').textContent='状态更新失败，将自动重试';}
  finally {pollBusy=false;}
}
translateButton.onclick=async()=>{
  translateButton.disabled=true;
  try {const {data:job}=await apiPost('/api/translation',{paper_id:paperId,force:currentStatus?.status==='completed'});updateStatus(job);document.getElementById('status').textContent='';await pollStatus();}
  catch(error) {translateButton.disabled=false;}
};
document.getElementById('export-btn').onclick=()=>{
  const text=['# ' + (item.title || paperId)];
  for (const page of paper.pages) {text.push('\n## 第 ' + page.page + ' 页');for (const block of page.blocks) {if (block.role!=='diagram-label' && translations[block.id]) text.push(translations[block.id]);}}
  downloadText((item.title || paperId).replace(/[\\/:*?"<>|]/g,'_') + ' - 译文.md',text.join('\n\n'));
};
function sentenceAtReadingLine(node,pointerY) {
  const spans=Array.from(node?.querySelectorAll('[data-follow]') || []);
  const viewport=translationScroll.getBoundingClientRect();
  const y=Number.isFinite(pointerY)?pointerY:viewport.top+readingLineOffset(viewport.bottom-viewport.top);
  let selected=null,distance=Infinity;
  for(const span of spans) {
    const boxes=span.getClientRects ? Array.from(span.getClientRects()) : [span.getBoundingClientRect()];
    for(const box of boxes) {
      const gap=y<box.top?box.top-y:y>box.bottom?y-box.bottom:0;
      if(gap<distance){distance=gap;selected=span;}
    }
  }
  return selected;
}
function activateTranslation(node,force=false,sentence) {
  if(!node)return;
  if(activeTranslation!==node) {
    activeTranslation?.classList.remove('reading-active');node.classList.add('reading-active');activeTranslation=node;
  }
  observedPage=Number(node.dataset.page);
  document.getElementById('page-select').value=observedPage;
  const anchor=sentence || sentenceAtReadingLine(node);
  if(activeSentence!==anchor){activeSentence?.classList.remove('reading-sentence-active');anchor?.classList.add('reading-sentence-active');activeSentence=anchor;}
  pdfFollower.focus(anchor?.dataset.follow || node.dataset.block,force);
  const parent=translatedBlocks[node.dataset.parent || node.dataset.block];
  const target=parent?.segments?.find(s=>s.id===node.dataset.block) || parent;
  for(const id of ['edit-current-btn','retry-current-btn','restore-current-btn'])document.getElementById(id).disabled=!target?.translation || ['pending','running'].includes(currentStatus?.status);
  document.getElementById('restore-current-btn').disabled=!(target?.history?.length || parent?.history?.length) || ['pending','running'].includes(currentStatus?.status);
  document.getElementById('restore-current-btn').textContent=!target?.history?.length && parent?.history?.length ? '恢复原段上一版' : '恢复上一版';
  if(typeof applyReaderNotes==='function')applyReaderNotes();
}

function selectedTranslation() {
  if(!activeTranslation)throw new Error('请先点击一个译文段落');
  const block_id=activeTranslation.dataset.parent || activeTranslation.dataset.block;
    const parent=translatedBlocks[block_id];
  const segment=parent?.segments?.find(s=>s.id===activeTranslation.dataset.block);
  if(!parent)throw new Error('当前段落暂无译文');
  return {paper_id:paperId,block_id,segment_id:segment?.id,target:segment || parent,parent};
}
document.getElementById('edit-current-btn').onclick=()=>{
  try {
    const selection=selectedTranslation();const dialog=el('dialog');dialog.setAttribute('aria-label','修订当前译文');
    const heading=el('h2','','修订当前译文');const source=el('p','settings-note',selection.target.text || paper.pages.flatMap(p=>p.blocks).find(b=>b.id===selection.block_id)?.text);
    const field=el('textarea');field.value=selection.target.translation;field.rows=12;field.setAttribute('aria-label','译文内容');field.style.width='100%';
    const draftId=paperId+'-edit-'+(selection.segment_id || selection.block_id);const draftStatus=el('p','settings-note');ReaderDrafts.bind(draftId,field,draftStatus,selection.target.translation);
    const cancel=el('button','','取消');const save=el('button','primary','保存修订');
    const close=()=>{dialog.close();dialog.remove();};cancel.onclick=close;
    save.onclick=async()=>{save.disabled=true;try {await apiPost('/api/translation/edit',{paper_id:paperId,block_id:selection.block_id,segment_id:selection.segment_id,translation:field.value,base_translation:selection.target.translation});ReaderDrafts.clear(draftId);await refreshTranslations();updateReadingPosition();close();}catch(error){save.disabled=false;}};
    const actions=el('div','dialog-actions');actions.append(cancel,save);dialog.append(heading,source,field,draftStatus,actions);document.body.append(dialog);dialog.showModal();
  } catch(error){showError(error.message);}
};
document.getElementById('retry-current-btn').onclick=async()=>{
  try {const s=selectedTranslation();if(!confirm('将调用已配置模型重译当前小段，可能产生费用。继续吗？'))return;const {data:job}=await apiPost('/api/translation',{paper_id:paperId,block_id:s.block_id,segment_id:s.segment_id,force:true,aligned:true});updateStatus(job);updateReadingPosition();}catch(error){}
};
document.getElementById('restore-current-btn').onclick=async()=>{
  try {const s=selectedTranslation();await apiPost('/api/translation/restore',{paper_id:paperId,block_id:s.block_id,segment_id:s.target.history?.length ? s.segment_id : undefined});await refreshTranslations();updateReadingPosition();}catch(error){}
};
document.getElementById('align-btn').onclick=async()=>{
  if(!confirm('将按原文逐句重新翻译全文，让每个译句直接对应 PDF 中的原句，并使用当前术语表。模型请求数会增加，可能触发限流或产生费用；旧段落译文会记录为上一版。继续吗？'))return;
  try {const {data:job}=await apiPost('/api/translation',{paper_id:paperId,force:true,aligned:true});updateStatus(job);}catch(error){}
};
let scrollPending=false;
function updateReadingPosition() {
  if(typeof readerNavigationUntil==='number' && Date.now()<readerNavigationUntil)return;
  if(!paper || document.body.className.split(' ').includes('mode-source'))return;
  let nodes=Array.from(content.querySelectorAll('[data-block]')).filter(node=>!node.classList.contains('layout-hidden') && (!node.closest('details') || node.closest('details').open));
  if(readerLayoutMode==='page'){
    const section=blockAtReadingLine(Array.from(content.querySelectorAll('.reading-page')),translationScroll.getBoundingClientRect());
    if(section){
      nodes=nodes.filter(n=>n.dataset.page===section.dataset.page);
      if(!nodes.length){
        const page=Number(section.dataset.page);
        if(observedPage!==page)pdfFollower.page(page);
        observedPage=page;document.getElementById('page-select').value=page;
        activeTranslation?.classList.remove('reading-active');activeSentence?.classList.remove('reading-sentence-active');activeTranslation=null;activeSentence=null;
        for(const id of ['edit-current-btn','retry-current-btn','restore-current-btn','annotation-btn'])document.getElementById(id).disabled=true;
      }
    }
  }
  if(readerLayoutMode==='page' && activeTranslation?.classList.contains('layout-textbox')){
    const column=Number(activeTranslation.dataset.layoutX);
    nodes=nodes.filter(node=>!node.classList.contains('layout-textbox') || Math.abs(Number(node.dataset.layoutX)-column)<.15);
  }
  const node=blockAtReadingLine(nodes,translationScroll.getBoundingClientRect());
  activateTranslation(node,false);
  const max=translationScroll.scrollHeight-translationScroll.clientHeight;
  document.getElementById('reading-progress').style.width=(max>0?translationScroll.scrollTop/max*100:100)+'%';
  localStorage.setItem('yiread-progress-' + paperId,JSON.stringify({page:observedPage,block:activeTranslation?.dataset.block,top:translationScroll.scrollTop}));
}
translationScroll.addEventListener('scroll',()=>{
  if(scrollPending)return;scrollPending=true;
  requestAnimationFrame(()=>{updateReadingPosition();scrollPending=false;});
},{passive:true});
window.addEventListener('resize',()=>{updateReadingPosition();if(activeTranslation)pdfFollower.focus(activeSentence?.dataset.follow || activeTranslation.dataset.block,true);});
async function loadReader() {
  readerLoading=true;
  document.querySelectorAll('button[data-layout]').forEach(b=>b.disabled=true);
  document.getElementById('page-select').disabled=true;
  const status=document.getElementById('status');
  let saved;try {saved=JSON.parse(localStorage.getItem('yiread-progress-' + paperId));}catch(error){}
  if (!paperId) {status.textContent='缺少文献编号，请返回文献库重新打开。';return;}
  try {
    const results=await Promise.all([apiFetch('/api/item/' + encodeURIComponent(paperId)),apiFetch('/api/paper/' + encodeURIComponent(paperId))]);
    item=results[0].data;paper=results[1].data;
    document.getElementById('title').textContent=item.title || paperId;document.title=(item.title || paperId) + ' · YiRead';
    document.getElementById('meta').textContent=paper.pages.length + ' 页 · ' + (item.authors?.join('、') || item.file_name || '本地文献');
    document.getElementById('pdf-link').href='/api/source/' + encodeURIComponent(paperId);
    status.textContent='';buildPages();
    try {const layout=await apiFetch('/api/pdf-layout/' + encodeURIComponent(paperId),{},true);pdfFollower.load(layout.data);}
    catch(error) {pdfFollower.fail('原始 PDF 预览暂不可用：' + error.message + '。请确认原文件存在并重启更新后的服务。');}
    content.querySelectorAll('[data-block]').forEach(node=>{node.textContent='这一段还没有译文';node.classList.add('placeholder');});
    await refreshTranslations();await pollStatus();
    requestAnimationFrame(()=>{
      if(saved?.page)observedPage=saved.page;
      const target=Array.from(content.querySelectorAll('[data-block]')).find(node=>node.dataset.block===saved?.block);
      if(target) {if(Number.isFinite(saved.top))translationScroll.scrollTo({top:saved.top,behavior:'auto'});else target.scrollIntoView({block:'start'});activateTranslation(target,true);}
      else if(saved?.page) {document.getElementById('page-' + saved.page)?.scrollIntoView({block:'start'});pdfFollower.page(saved.page);}
      else activateTranslation(content.querySelectorAll('[data-block]')[0],true);
    });
    translateButton.disabled=['pending','running'].includes(currentStatus?.status);
  } catch(error) {status.textContent='无法打开文献：' + error.message;const retry=el('button','','重试加载');retry.onclick=loadReader;status.append(' ',retry);}
  finally{readerLoading=false;document.querySelectorAll('button[data-layout]').forEach(b=>b.disabled=false);document.getElementById('page-select').disabled=false;}
}
const readerReady=loadReader();
setInterval(()=>{if(translationRefreshNeeded || ['pending','running'].includes(currentStatus?.status)) pollStatus();},3000);
window.addEventListener('focus',pollStatus);
