async function loadDetail() {
  const id = new URLSearchParams(location.search).get('id'); const info=document.getElementById('info');
  if (!id) { info.textContent='缺少文献编号，请返回文献库重新打开。'; return; }
  try {
    const {data:item}=await apiFetch('/api/item/' + encodeURIComponent(id));
    document.getElementById('title').textContent=item.title || item.id; document.title=(item.title || item.id) + ' · YiRead';
    const list=el('dl');
    for (const [label,value] of [['文件名称',item.file_name],['文件大小',formatSize(item.file_size)],['导入时间',(item.created_at || '').replace('T',' ').slice(0,19)]]) list.append(el('dt','',label),el('dd','',value || '—'));
    info.replaceChildren(list);
    const form=el('form','settings-form metadata-form');const fields={};
    for(const [name,label,value] of [['title','标题',item.title],['authors','作者（用分号分隔）',item.authors?.join('; ')],['journal','期刊',item.journal],['year','年份',item.year],['doi','DOI',item.doi],['tags','标签（用分号分隔）',item.tags?.join('; ')]]) {
      const row=el('label','',label);const input=el('input');input.name=name;input.value=value || '';if(name==='title')input.required=true;if(name==='year'){input.type='number';input.min='1800';input.max='2100';}fields[name]=input;row.append(input);form.append(row);
    }
    for(const [name,label] of [['favorite','收藏'],['is_read','已读']]) {const row=el('label');const wrap=el('span');const input=el('input');input.type='checkbox';input.style.width='auto';input.checked=Boolean(item[name]);fields[name]=input;wrap.append(input,' '+label);row.append(wrap);form.append(row);}
    const message=el('p','settings-note','识别结果可能不完整；可手动核对并修正。标签可用于课题、反应类型和目标化合物。');
    const save=el('button','primary','保存文献信息');save.type='submit';const extract=el('button','','从 PDF 识别信息');extract.type='button';
    extract.onclick=async()=>{extract.disabled=true;try {const {data}=await apiPost('/api/metadata/extract',{paper_id:id});for(const name of ['title','journal','year','doi'])fields[name].value=data[name] || '';fields.authors.value=data.authors?.join('; ') || '';message.textContent='已从原始 PDF 识别并保存，请核对信息。';}catch(error){message.textContent=error.message;}finally{extract.disabled=false;}};
    form.onsubmit=async event=>{event.preventDefault();save.disabled=true;try {const body={paper_id:id};for(const name of ['title','journal','year','doi'])body[name]=fields[name].value;for(const name of ['authors','tags'])body[name]=fields[name].value.split(/[;；]/).map(v=>v.trim()).filter(Boolean);body.favorite=fields.favorite.checked;body.is_read=fields.is_read.checked;const {data}=await apiPost('/api/metadata',body);document.getElementById('title').textContent=data.title;message.textContent='已保存，文献库中可按作者、期刊、DOI 和标签搜索。';}catch(error){message.textContent=error.message;}finally{save.disabled=false;}};
    const buttons=el('div','dialog-actions');buttons.append(extract,save);form.append(message,buttons);info.append(form);
    const reader=document.getElementById('reader-btn'); reader.disabled=false;reader.onclick=()=>location.href='reader.html?id=' + encodeURIComponent(id);
    const remove=document.getElementById('delete-btn'); remove.disabled=false;
    remove.onclick=async()=>{
      if (!confirm('将这篇文献移入回收站？原始 PDF、译文和笔记可从文献库恢复。')) return;
      remove.disabled=true;
      try { await apiPost('/api/delete/' + encodeURIComponent(id),{}); for(const key of ['yiread-progress-'+id,'yiread-notes-'+id,'yiread-notes-'+id+'-legacy','yiread-notes-'+id+'-migrated'])localStorage.removeItem(key); location.href='index.html'; }
      catch(error) { remove.disabled=false; }
    };
  } catch(error) {info.textContent=error.message;}
}
loadDetail();
