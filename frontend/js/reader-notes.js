// Notes live in this computer's document folder; browser cache preserves legacy/offline copies.
const readerNotesKey='yiread-notes-'+paperId;
let readerNotes={},readerNotesVersion=0,readerNotesLoaded=false;
function cachedReaderNotes(key=readerNotesKey){try {const data=JSON.parse(localStorage.getItem(key)||'{}');return data && !Array.isArray(data) && typeof data==='object'?data:{};}catch(error){return {};}}
function readReaderNotes(){return readerNotes;}
function cacheReaderNotes(){try {localStorage.setItem(readerNotesKey,JSON.stringify(readerNotes));}catch(error){}}
function sourceForNote(node){if(!node)return '';const parent=translatedBlocks[node.dataset.parent || node.dataset.block];return parent?.segments?.find(s=>s.id===node.dataset.block)?.text || paper?.pages.flatMap(p=>p.blocks).find(b=>b.id===(node.dataset.parent || node.dataset.block))?.text || '';}
function normalizedNoteSource(text){return String(text || '').replace(/\s+/g,' ').trim();}
function locateReaderNote(id,note){
  const nodes=Array.from(content.querySelectorAll('[data-block]'));
  const candidates=nodes.filter(n=>(n.dataset.parent || n.dataset.block)===(note.parent || id));
  const source=normalizedNoteSource(note.source);
  if(source){const exact=candidates.find(n=>{const text=normalizedNoteSource(sourceForNote(n));return text.startsWith(source) || (text.length>20 && source.startsWith(text)) || (source.length>80 && text.includes(source.slice(0,80)));});if(exact)return exact;}
  else {const direct=nodes.find(n=>n.dataset.block===id);if(direct)return direct;}
  return candidates[0] || null;
}
function displayedReaderNote(node){for(const [id,note] of Object.entries(readerNotes))if(note && typeof note==='object' && locateReaderNote(id,note)===node)return {id,note};return null;}
function applyReaderNotes(){
  const marked=new Map();
  for(const [id,note] of Object.entries(readerNotes)){
    if(!note || typeof note!=='object')continue;const node=locateReaderNote(id,note);if(!node)continue;
    const flags=marked.get(node) || {text:false,bookmark:false};flags.text ||= Boolean(note.text);flags.bookmark ||= Boolean(note.bookmark);marked.set(node,flags);
  }
  for(const node of content.querySelectorAll('[data-block]')){node.classList.toggle('has-reader-note',Boolean(marked.get(node)?.text));node.classList.toggle('is-bookmarked',Boolean(marked.get(node)?.bookmark));}
  if(typeof applyReaderExcerptMarks==='function')applyReaderExcerptMarks();
  document.getElementById('annotation-btn').disabled=!activeTranslation || !readerNotesLoaded;
  document.getElementById('notes-btn').disabled=!readerNotesLoaded;
  document.getElementById('notes-btn').textContent=readerNotesLoaded?'我的笔记 / 书签'+(Object.keys(readerNotes).length?' · '+Object.keys(readerNotes).length:''):'正在载入笔记…';
}
async function fetchReaderNotes(){const {data}=await apiAuthedGet('/api/notes/'+encodeURIComponent(paperId));readerNotes=data.notes || {};readerNotesVersion=data.version || 0;cacheReaderNotes();}
async function saveReaderNote(id,note){
  const request={paper_id:paperId,note_id:id,note,version:readerNotesVersion,operation_id:'note_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2)};
  if(note && typeof ReaderDrafts!=='undefined')ReaderDrafts.queue(paperId,request);
  try {const {data}=await apiPost('/api/notes',request);if(typeof ReaderDrafts!=='undefined')ReaderDrafts.acknowledged(paperId,request);if(!note && typeof ReaderDrafts!=='undefined'){ReaderDrafts.drop(paperId,id);ReaderDrafts.clear(paperId+'-note-'+id);}readerNotes=data.notes;readerNotesVersion=data.version;cacheReaderNotes();applyReaderNotes();}
  catch(error){if(error.code===409){if(typeof ReaderDrafts!=='undefined')ReaderDrafts.block(paperId,request);await fetchReaderNotes();applyReaderNotes();throw new Error('其他页面已更新笔记，已重新载入。你的输入仍保留，请核对后再次保存。');}throw error;}
}
async function loadReaderNotes(){
  const old={...cachedReaderNotes(readerNotesKey+'-legacy'),...cachedReaderNotes()};
  let migrated=false;try {migrated=localStorage.getItem(readerNotesKey+'-migrated')==='true';if(!migrated)localStorage.setItem(readerNotesKey+'-legacy',JSON.stringify(old));}catch(error){}
  try {await fetchReaderNotes();if(!migrated)for(const [id,note] of Object.entries(old)){if(readerNotes[id] || !note || typeof note!=='object')continue;await saveReaderNote(id,{text:typeof note.text==='string'?note.text:'',bookmark:Boolean(note.bookmark),parent:note.parent || id,quote:typeof note.quote==='string'?note.quote:'',source:typeof note.source==='string'?note.source:''});}try {localStorage.setItem(readerNotesKey+'-migrated','true');localStorage.removeItem(readerNotesKey+'-legacy');}catch(error){}}
  catch(error){readerNotes={...old,...readerNotes};cacheReaderNotes();showError('笔记载入或迁移失败：'+error.message+'。旧笔记仍保留，保存前请确认本地服务已运行。');}
  finally {readerNotesLoaded=true;applyReaderNotes();}
}
function readerNoteDialog(title){
  const dialog=el('dialog');dialog.setAttribute('aria-label',title);const heading=el('div','dialog-heading');heading.append(el('h2','',title));
  const close=el('button','quiet','关闭');close.type='button';close.onclick=()=>{dialog.close();dialog.remove();};heading.append(close);dialog.append(heading);
  dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);return dialog;
}
function editReaderNote(id,node,excerpt){
  const old=readerNotes[id] || (typeof ReaderDrafts!=='undefined'?ReaderDrafts.pending(paperId)[id]?.note || ReaderDrafts.read(paperId+'-note-'+id)?.context:null) || (excerpt?{quote:excerpt.quote,anchor:{quote:excerpt.quote,prefix:excerpt.prefix,suffix:excerpt.suffix}}:{}),parent=old.parent || node?.dataset.parent || id;
  const dialog=readerNoteDialog('阅读笔记与书签');const quote=old.quote || translations[node?.dataset.block] || paper?.pages.flatMap(p=>p.blocks).find(b=>b.id===parent)?.text || '';
  dialog.append(el('p','settings-note',quote.slice(0,350)));
  const label=el('label','reader-note-field');label.append(el('span','','阅读笔记'));const field=el('textarea');field.rows=7;field.maxLength=15000;field.value=typeof old.text==='string'?old.text:'';field.setAttribute('aria-label','阅读笔记');label.append(field);dialog.append(label);
  const bookmark=el('input');bookmark.type='checkbox';bookmark.checked=Boolean(old.bookmark);const markLabel=el('label','reader-bookmark-field');markLabel.append(bookmark,' 将此段加入书签');dialog.append(markLabel);
  const message=el('p','settings-note','笔记与书签保存在本机文献目录，关闭浏览器后仍可使用。');dialog.append(message);
  const draftId=paperId+'-note-'+id;if(typeof ReaderDrafts!=='undefined')ReaderDrafts.bind(draftId,field,message,typeof old.text==='string'?old.text:'',bookmark,{parent,page:old.page || Number(node?.dataset.page),quote:quote.slice(0,350),source:old.source || sourceForNote(node).slice(0,1500),...(old.anchor?{anchor:old.anchor}:{})});
  const save=el('button','primary','保存');save.type='button';const actions=el('div','dialog-actions');actions.append(save);dialog.append(actions);
  save.onclick=async()=>{save.disabled=true;try {
    if(field.value.length>15000)throw new Error('笔记限 15000 字符');
    const note=field.value.trim() || bookmark.checked?{text:field.value,bookmark:bookmark.checked,parent,page:old.page || Number(node?.dataset.page),quote:quote.slice(0,350),source:old.source || sourceForNote(node).slice(0,1500),...(old.anchor?{anchor:old.anchor}:{})}:null;
    await saveReaderNote(id,note);if(typeof ReaderDrafts!=='undefined')ReaderDrafts.clear(draftId);dialog.close();dialog.remove();
  }catch(error){message.textContent='保存失败：'+error.message;save.disabled=false;}};
  dialog.showModal();field.focus();
}
document.getElementById('annotation-btn').onclick=()=>{if(!activeTranslation || !readerNotesLoaded)return;const existing=displayedReaderNote(activeTranslation);editReaderNote(existing?.id || activeTranslation.dataset.block,activeTranslation);};
document.getElementById('notes-btn').onclick=async()=>{
  if(!readerNotesLoaded)return;const dialog=readerNoteDialog('我的笔记与书签');const list=el('div','reader-note-list');
  const add=el('button','primary','为当前段添加笔记 / 书签');add.id='list-add-note';add.type='button';add.disabled=!activeTranslation;
  add.onclick=()=>{dialog.close();document.getElementById('annotation-btn').click();};
  const hint=el('p','settings-note',activeTranslation?'先在译文中点击要记录的段落，再添加笔记；保存时可勾选「将此段加入书签」。':'请先切换到译文或双语对照，点击要记录的译文段落，再添加笔记。');
  dialog.append(add,hint,list);dialog.showModal();
  function renderList(){
    list.replaceChildren();const entries=Object.entries(readerNotes).filter(([,note])=>note && typeof note==='object').sort((a,b)=>(a[1].page || 0)-(b[1].page || 0));
    const pending=typeof ReaderDrafts!=='undefined'?Object.entries(Object.fromEntries([...ReaderDrafts.noteDrafts(paperId),...Object.entries(ReaderDrafts.pending(paperId))])).filter(([id])=>!readerNotes[id]):[];
    for(const [id,request] of pending){const row=el('section','reader-note-entry');row.append(el('p','settings-note',request.blocked?'草稿待核对（其他页面已更新）':request.draftOnly?'未保存草稿':'笔记待同步'),el('p','',request.note?.text || '文字批注'));const open=el('button','quiet','打开草稿');open.onclick=()=>{dialog.close();dialog.remove();editReaderNote(id,locateReaderNote(id,request.note));};row.append(open);list.append(row);}
    if(!entries.length && !pending.length)list.append(el('p','settings-note','还没有笔记或书签。点击上方「为当前段添加笔记 / 书签」开始记录，保存后会显示在这里。'));
    for(const [id,note] of entries){
      const entry=el('section','reader-note-entry');const jump=el('button','reader-note-jump','第 '+(note.page || '?')+' 页'+(note.bookmark?' · 书签':'')+(note.position_lost?' · 位置待核对':'')+' · '+(typeof note.quote==='string'?note.quote.slice(0,80):'阅读段落'));
      jump.type='button';jump.onclick=()=>{const target=locateReaderNote(id,note);if(!target){showError('当前文献没有找到原段落，可在列表中继续编辑这条笔记。');return;}dialog.close();dialog.remove();if(typeof jumpReaderTarget==='function')jumpReaderTarget(target);else{setMode('bilingual');target.scrollIntoView({block:'start',behavior:'auto'});activateTranslation(target,true);}};
      const edit=el('button','quiet','编辑');edit.type='button';edit.onclick=()=>{dialog.close();dialog.remove();editReaderNote(id,locateReaderNote(id,note));};
      const remove=el('button','quiet','删除');remove.type='button';remove.onclick=async()=>{remove.disabled=true;try {await saveReaderNote(id,null);renderList();}catch(error){showError(error.message);remove.disabled=false;}};
      const actions=el('div','reader-note-actions');actions.append(edit,remove);entry.append(jump,el('p','',typeof note.text==='string'?note.text:''),actions);list.append(entry);
    }
  }
  renderList();try {await fetchReaderNotes();applyReaderNotes();if(dialog.open)renderList();}catch(error){showError('暂时无法刷新本机笔记：'+error.message);}
};
applyReaderNotes();
const readerNotesReady=readerReady.then(()=>paper && loadReaderNotes());
let noteOutboxBusy=false;
async function syncPendingReaderNotes(){
  if(noteOutboxBusy || !readerNotesLoaded || typeof ReaderDrafts==='undefined')return;
  noteOutboxBusy=true;
  try{for(const request of Object.values(ReaderDrafts.pending(paperId))){
    if(request.blocked)continue;
    try{const {data}=await apiPost('/api/notes',request);ReaderDrafts.acknowledged(paperId,request);readerNotes=data.notes;readerNotesVersion=data.version;cacheReaderNotes();applyReaderNotes();showError('暂存的笔记已同步到本机文献。');}
    catch(error){if(error.code===409){ReaderDrafts.block(paperId,request);showError('暂存笔记与其他页面冲突，请打开对应笔记核对草稿后保存。');}else break;}
  }}finally{noteOutboxBusy=false;}
}
readerNotesReady.then(syncPendingReaderNotes);
window.addEventListener('focus',syncPendingReaderNotes);
window.addEventListener('online',syncPendingReaderNotes);
setInterval(()=>{if(!document.hidden)syncPendingReaderNotes();},30000);

