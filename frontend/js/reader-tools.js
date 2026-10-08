// Focused translation controls and reversible navigation; no chat or login engine.
const readerJumps=[];
let readerNavigationUntil=0;
function rememberReaderPosition(){
  readerJumps.push({block:activeTranslation?.dataset.block,top:translationScroll.scrollTop,mode:content.dataset.mode});
  if(readerJumps.length>20)readerJumps.shift();
  document.getElementById('return-reading-btn').hidden=false;
}
function jumpReaderTarget(target,sentence,preserveMode=false){
  if(!target)return;
  rememberReaderPosition();if(!preserveMode)setMode('bilingual');readerNavigationUntil=Date.now()+650;
  target.scrollIntoView({block:'start',behavior:'auto'});activateTranslation(target,true,sentence);
}
function returnReaderPosition(){
  const saved=readerJumps.pop();if(!saved)return;
  readerNavigationUntil=Date.now()+650;setMode(saved.mode || 'bilingual');translationScroll.scrollTo({top:saved.top,behavior:'auto'});
  const node=Array.from(content.querySelectorAll('[data-block]')).find(n=>n.dataset.block===saved.block);activateTranslation(node,true);
  document.getElementById('return-reading-btn').hidden=!readerJumps.length;
}
function showTranslationProgress(ts){
  const pane=document.getElementById('translation-task');
  const relevant=ts?.job_id && (['pending','running','failed','paused'].includes(ts.status) || ts.total);
  pane.hidden=!relevant;if(!relevant)return;
  pane.replaceChildren();const line=el('div','task-summary');
  line.append(el('span','',ts.message || statusText(ts)));
  if(ts.total)line.append(el('span','settings-note',(ts.completed || 0)+' / '+ts.total+' · 文献已译 '+(ts.document_progress || 0)+'%'));
  if(ts.usage?.total_tokens!=null)line.append(el('span','settings-note','本次用量 '+ts.usage.total_tokens.toLocaleString()+' tokens'));
  if(['pending','running'].includes(ts.status)){
    const stop=el('button','quiet',ts.cancel_requested?'正在暂停…':'暂停');stop.disabled=Boolean(ts.cancel_requested);
    stop.onclick=async()=>{stop.disabled=true;try{await apiPost('/api/translation/cancel',{job_id:ts.job_id});await pollStatus();}catch(error){stop.disabled=false;}};line.append(stop);
  }
  const failures=Object.entries(ts.failed || {});
  if(failures.length && !['pending','running'].includes(ts.status)){
    const retry=el('button','quiet','仅重试失败部分');retry.onclick=async()=>{
      retry.disabled=true;try{const {data}=await apiPost('/api/translation',{paper_id:paperId,retry_failed:true});updateStatus(data);await pollStatus();}catch(error){retry.disabled=false;}
    };line.append(retry);
    const detail=el('details','task-failures');detail.append(el('summary','',failures.length+' 个段落未完成'));
    for(const [id,failure] of failures){const row=el('button','quiet','第 '+failure.page+' 页 · '+failure.message);row.onclick=()=>jumpReaderTarget(Array.from(content.querySelectorAll('[data-block]')).find(n=>(n.dataset.parent || n.dataset.block)===id));detail.append(row);}
    pane.append(line,detail);
  }else pane.append(line);
}
function openTranslationScope(){
  if(!paper)return;
  const dialog=readerNoteDialog('翻译范围');
  const form=el('form','scope-form');
  const label=el('label');label.append('翻译范围');const scope=el('select');scope.setAttribute('aria-label','翻译范围');
  for(const [value,text] of [['all','全文'],['current','当前页（第 '+observedPage+' 页）'],['range','指定页码']]){const o=el('option','',text);o.value=value;scope.append(o);}label.append(scope);form.append(label);
  const range=el('div','scope-range');range.hidden=true;
  const inputs=[];for(const text of ['起始页','结束页']){const l=el('label');l.append(text);const input=el('input');input.type='number';input.min=1;input.max=paper.pages.length;input.value=text==='起始页'?observedPage:paper.pages.length;input.setAttribute('aria-label',text);inputs.push(input);l.append(input);range.append(l);}form.append(range);
  scope.onchange=()=>range.hidden=scope.value!=='range';
  const force=el('input');force.type='checkbox';force.checked=currentStatus?.status==='completed';
  const replace=el('label','reader-bookmark-field');replace.append(force,' 重新翻译所选范围（保留上一版文字）');form.append(replace);
  const message=el('p','settings-note','默认继续未译部分。调用已配置的翻译服务，可能产生费用；逐句翻译沿用设置中的选择。');form.append(message);
  const start=el('button','primary','开始翻译');start.type='submit';form.append(start);dialog.append(form);dialog.showModal();
  form.onsubmit=async event=>{
    event.preventDefault();let pages;
    if(scope.value==='current')pages=[observedPage];
    if(scope.value==='range'){
      const a=Number(inputs[0].value),b=Number(inputs[1].value);
      if(!Number.isInteger(a)||!Number.isInteger(b)||a<1||b>paper.pages.length||a>b){message.textContent='请输入有效页码，起始页不能大于结束页。';return;}
      pages=Array.from({length:b-a+1},(_,i)=>a+i);
    }
    start.disabled=true;
    try{const {data}=await apiPost('/api/translation',{paper_id:paperId,pages,force:force.checked});updateStatus(data);dialog.close();await pollStatus();}catch(error){message.textContent=error.message;start.disabled=false;}
  };
}
translateButton.onclick=openTranslationScope;
const returnButton=el('button','quiet','返回刚才的位置');returnButton.id='return-reading-btn';returnButton.hidden=true;returnButton.onclick=returnReaderPosition;
document.querySelector('.reader-toolbar').append(returnButton);
const task=el('div','translation-task');task.id='translation-task';task.hidden=true;task.setAttribute('aria-live','polite');document.querySelector('.reading-main').prepend(task);
readerReady.then(()=>{
  const select=document.getElementById('page-select');select.onchange=()=>{
    const target=document.getElementById('page-'+select.value)?.querySelector('[data-block]');
    if(target){jumpReaderTarget(target,undefined,true);pdfFollower.page(select.value);}else{rememberReaderPosition();document.getElementById('page-'+select.value)?.scrollIntoView({block:'start'});pdfFollower.page(select.value);}
  };
  pdfFollower.onPick=id=>{
    const sentence=Array.from(content.querySelectorAll('[data-follow]')).find(n=>n.dataset.follow===id);
    const target=sentence?.closest('[data-block]') || Array.from(content.querySelectorAll('[data-block]')).find(n=>n.dataset.block===id);
    jumpReaderTarget(target,sentence);
  };
  showTranslationProgress(currentStatus);
});
document.addEventListener('keydown',event=>{
  if(event.ctrlKey||event.metaKey||event.altKey||event.target.closest('input,textarea,select,[contenteditable="true"]')||document.querySelector('dialog[open]'))return;
  if(event.key==='j'||event.key==='k'){
    const nodes=Array.from(content.querySelectorAll('[data-block]'));const i=nodes.indexOf(activeTranslation);const next=nodes[i+(event.key==='j'?1:-1)];
    if(next){event.preventDefault();readerNavigationUntil=Date.now()+650;next.scrollIntoView({block:'start'});activateTranslation(next,true);}
  }else if(event.key==='n'){event.preventDefault();document.getElementById('annotation-btn').click();}
  else if(event.key==='Escape'&&readerJumps.length)returnReaderPosition();
});
