let papers = [], filter = 'all', loading = false, importBusy = false;
const container = document.getElementById('library');
const search = document.getElementById('search-input');
const mottos=[
  '日事日毕，日清日高。','求真务实，精益求精。','知行合一，笃行致远。','积跬步，至千里。',
  '专注当下，持续精进。','严谨求证，踏实前行。','把今天的事做好。','以耐心积累，以行动突破。',
  '学而不思则罔，思而不学则殆。','温故而知新。','知之为知之，不知为不知。','敏而好学，不耻下问。',
  '博学之，审问之，慎思之，明辨之，笃行之。','三人行，必有我师焉。','千里之行，始于足下。','合抱之木，生于毫末。',
  '锲而不舍，金石可镂。','不积小流，无以成江海。','纸上得来终觉浅，绝知此事要躬行。','问渠那得清如许？为有源头活水来。',
  '读书破万卷，下笔如有神。','宝剑锋从磨砺出，梅花香自苦寒来。','业精于勤，荒于嬉。','行成于思，毁于随。',
  '路漫漫其修远兮，吾将上下而求索。','吾生也有涯，而知也无涯。','尽信书，则不如无书。','学然后知不足。',
  '凡事预则立，不预则废。','欲穷千里目，更上一层楼。','长风破浪会有时，直挂云帆济沧海。','少壮不努力，老大徒伤悲。'
];
let mottoHistory=[],lastMotto='';
function initializeMotto() {
  try {
    const stored=JSON.parse(sessionStorage.getItem('yiread-motto-history') || '[]');
    if(Array.isArray(stored))mottoHistory=[...new Set(stored.filter(text=>mottos.includes(text)))];
    lastMotto=sessionStorage.getItem('yiread-motto') || lastMotto;
  }catch(error){}
  let available=mottos.filter(text=>!mottoHistory.includes(text) && text!==lastMotto);
  if(!available.length){mottoHistory=[];available=mottos.filter(text=>text!==lastMotto);}
  const motto=available[Math.floor(Math.random()*available.length)];
  mottoHistory.push(motto);lastMotto=motto;
  try {sessionStorage.setItem('yiread-motto',motto);sessionStorage.setItem('yiread-motto-history',JSON.stringify(mottoHistory));}catch(error){}
  document.getElementById('library-motto').textContent=motto;
}
initializeMotto();
// Browser Back may restore the page without running this script again.
window.addEventListener('pageshow',event=>{if(event.persisted)initializeMotto();});
function renderLibrary() {
  const keyword = search.value.trim().toLocaleLowerCase();
  let items = papers.filter(paper => (!keyword || [paper.title,paper.file_name,paper.doi,paper.journal,paper.year,...(paper.authors || []),...(paper.tags || [])].join(' ').toLocaleLowerCase().includes(keyword)) && (filter === 'all' || (filter==='favorite' ? paper.favorite : filter==='read' ? paper.is_read : filter === 'completed' ? paper.translation_status?.status === 'completed' : paper.translation_status?.status !== 'completed')));
  items.sort(document.getElementById('sort-select').value === 'title' ? (a,b) => (a.title || a.id).localeCompare(b.title || b.id) : (a,b) => (b.created_at || '').localeCompare(a.created_at || ''));
  document.getElementById('library-count').textContent = papers.length;
  container.replaceChildren();
  if (!items.length) {
    const empty = el('div','empty-state'); empty.append(el('h3','', papers.length ? '没有找到匹配的文献' : '你的下一次发现，从这里开始'), el('p','',papers.length ? '试试其他关键词，或切换筛选条件。' : '点击「导入 PDF」，或将文件拖拽到页面。'));
    container.append(empty); return;
  }
  for (const paper of items) {
    const ts = paper.translation_status;
    const card = el('article','paper-item'); const top = el('div','card-top');
    top.append(el('span','pdf-icon','PDF'),el('span','badge' + (ts?.status === 'failed' ? ' failed' : ''),statusText(ts)));
    const title = el('h3'); const link = el('a','',paper.title || paper.id); link.href = 'reader.html?id=' + encodeURIComponent(paper.id); title.append(link);
    const file = el('p','file-name',paper.file_name || 'PDF 文献'); file.title = paper.file_name || '';
    const bibliography=el('p','bibliography',[paper.authors?.slice(0,2).join(', '),paper.journal,paper.year,paper.doi].filter(Boolean).join(' · '));
    const tags=el('div','paper-tags');for(const tag of paper.tags || [])tags.append(el('span','badge',tag));
    const meta = el('div','card-meta'); meta.append(el('span','',(paper.created_at || '').slice(0,10)),el('span','',formatSize(paper.file_size)));
    const actions = el('div','card-actions'); const read = el('a','button read-link','开始阅读 ↗'); read.href = link.href;
    const detail = el('a','button quiet','详情'); detail.href = 'detail.html?id=' + encodeURIComponent(paper.id);
    const translate = el('button','quiet',ts?.status === 'completed' ? '重新翻译' : ts?.status === 'failed' ? '重试翻译' : ['partial','paused'].includes(ts?.status) ? '继续翻译' : '翻译全文'); translate.disabled = ['pending','running'].includes(ts?.status);
    translate.onclick = async () => {
      translate.disabled = true;
      try { const job = await apiPost('/api/translation',{paper_id:paper.id,force:ts?.status === 'completed'}); showError(job.data.status === 'completed' ? '译文已就绪' : '翻译已加入队列，完成后可双语阅读'); await loadLibrary(); }
      catch(error) { translate.disabled = false; }
    };
    const favorite=el('button','quiet',paper.favorite?'★ 已收藏':'☆ 收藏');favorite.setAttribute('aria-pressed',String(Boolean(paper.favorite)));
    favorite.onclick=async()=>{try {const {data}=await apiPost('/api/metadata',{paper_id:paper.id,favorite:!paper.favorite});Object.assign(paper,data);renderLibrary();}catch(error){}};
    const readState=el('button','quiet',paper.is_read?'已读':'标为已读');readState.onclick=async()=>{try {const {data}=await apiPost('/api/metadata',{paper_id:paper.id,is_read:!paper.is_read});Object.assign(paper,data);renderLibrary();}catch(error){}};
    actions.append(read,detail,favorite,readState,translate); card.append(top,title,bibliography,file,tags,meta,actions); container.append(card);
  }
}
async function loadLibrary() {
  if (loading) return; loading = true;
  try { const data = await apiFetch('/api/library',{},true); papers = data.data.items; renderLibrary(); }
  catch(error) { if (!papers.length) { container.replaceChildren(); const empty=el('div','empty-state'); empty.append(el('h3','','暂时无法加载文献库'),el('p','',error.message)); const retry=el('button','','重新加载'); retry.onclick=loadLibrary; empty.append(retry); container.append(empty); } }
  finally { loading = false; }
}
async function importFiles(files) {
  if (importBusy || !files.length) return;
  importBusy=true; const button=document.getElementById('import-btn'); button.disabled=true;
  const status=document.getElementById('import-status'); let count=0,duplicates=0;
  try {
    for (const file of files) {
      if (!file.name.toLowerCase().endsWith('.pdf') || file.size > 50*1024*1024) { showError(file.name + '：仅支持 50 MB 以内的 PDF'); continue; }
      status.textContent='正在导入 ' + file.name + '…';
      try {
        for (let attempt=0;attempt<2;attempt++) {
          const token=await ensureToken(); const form=new FormData(); form.append('file',file);
          try {const {data}=await apiFetch('/api/import',{method:'POST',headers:{'X-Token':token},body:form},true);if(data.duplicate)duplicates++;else count++;break; }
          catch(error) { if (error.code !== 403 || attempt) throw error; }
        }
      } catch(error) { showError(file.name + '：' + error.message); }
    }
    status.textContent='已导入 ' + count + ' 篇文献'+(duplicates?'，跳过 '+duplicates+' 篇重复文件':''); await loadLibrary();
  } finally { importBusy=false;button.disabled=false;document.getElementById('file-input').value=''; }
}
document.getElementById('import-btn').onclick=()=>document.getElementById('file-input').click();
document.getElementById('file-input').onchange=event=>importFiles(Array.from(event.target.files));
search.oninput=renderLibrary; document.getElementById('search-btn').onclick=renderLibrary;
document.getElementById('sort-select').onchange=renderLibrary;
container.dataset.view='list';
try {localStorage.removeItem('yiread-library-view');}catch(error){}
document.querySelectorAll('[data-filter]').forEach(button=>button.onclick=()=>{ filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(node=>node.classList.toggle('active',node===button));renderLibrary(); });
let dragDepth=0;
window.addEventListener('dragenter',event=>{ if (event.dataTransfer.types.includes('Files')) { event.preventDefault();dragDepth++;document.body.classList.add('dragging'); } });
window.addEventListener('dragover',event=>event.preventDefault());
window.addEventListener('dragleave',()=>{ if (--dragDepth<=0) document.body.classList.remove('dragging'); });
window.addEventListener('drop',event=>{event.preventDefault();dragDepth=0;document.body.classList.remove('dragging');importFiles(Array.from(event.dataTransfer.files));});
loadLibrary();
setInterval(()=>{if (!document.hidden && papers.some(p=>['pending','running'].includes(p.translation_status?.status))) loadLibrary();},3000);
window.addEventListener('focus',loadLibrary);
