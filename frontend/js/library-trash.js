const trashButton=el('button','quiet','回收站');trashButton.type='button';document.querySelector('.workspace-actions').prepend(trashButton);
trashButton.onclick=async()=>{
  const dialog=el('dialog');dialog.setAttribute('aria-label','文献回收站');const heading=el('div','dialog-heading');heading.append(el('h2','','文献回收站'));
  const close=el('button','quiet','关闭');close.onclick=()=>{dialog.close();dialog.remove();};heading.append(close);dialog.append(heading);
  dialog.append(el('p','settings-note','移入回收站的原始 PDF、译文和笔记保存在本机，恢复后可继续阅读。'));
  const list=el('div','reader-note-list');dialog.append(list);document.body.append(dialog);dialog.showModal();
  dialog.addEventListener('close',()=>dialog.remove());
  async function refresh(){
    try{const {data}=await apiAuthedGet('/api/trash');list.replaceChildren();
      if(!data.items.length)list.append(el('p','settings-note','回收站为空'));
      for(const item of data.items){const row=el('section','reader-note-entry');row.append(el('p','',item.title),el('p','settings-note',item.deleted_at.slice(0,19).replace('T',' ')));
        const restore=el('button','quiet',item.state==='ready'?'恢复文献':'文件处理中');restore.disabled=item.state!=='ready';restore.onclick=async()=>{restore.disabled=true;try{await apiPost('/api/trash/restore',{entry:item.entry});await refresh();await loadLibrary();showError('文献已恢复');}catch(error){showError(error.message);restore.disabled=false;}};row.append(restore);list.append(row);
      }
    }catch(error){list.replaceChildren(el('p','settings-note',error.message));}
  }
  await refresh();
};
