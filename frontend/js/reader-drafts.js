// Only user input is stored here; saved document data remains on the local server.
const ReaderDrafts={
  key(id){return 'yiread-draft-'+id;},
  read(id){try{return JSON.parse(localStorage.getItem(this.key(id)) || 'null');}catch(error){return null;}},
  clear(id){try{localStorage.removeItem(this.key(id));}catch(error){}},
  pendingKey(id){return 'yiread-note-outbox-'+id;},
  pending(id){try{return JSON.parse(localStorage.getItem(this.pendingKey(id)) || '{}');}catch(error){return {};}},
  queue(id,request){const data=this.pending(id);data[request.note_id]=request;localStorage.setItem(this.pendingKey(id),JSON.stringify(data));},
  acknowledged(id,request){const data=this.pending(id);if(data[request.note_id]?.operation_id===request.operation_id){delete data[request.note_id];localStorage.setItem(this.pendingKey(id),JSON.stringify(data));}},
  block(id,request){const data=this.pending(id);if(data[request.note_id]?.operation_id===request.operation_id){data[request.note_id].blocked=true;localStorage.setItem(this.pendingKey(id),JSON.stringify(data));}},
  drop(id,noteId){const data=this.pending(id);delete data[noteId];localStorage.setItem(this.pendingKey(id),JSON.stringify(data));},
  noteDrafts(id){
    const prefix=this.key(id+'-note-'),values=[];
    for(let i=0;i<localStorage.length;i++){
      const key=localStorage.key(i);if(!key?.startsWith(prefix))continue;
      try{const d=JSON.parse(localStorage.getItem(key));if(d?.context)values.push([key.slice(prefix.length),{note:{...d.context,text:d.text,bookmark:Boolean(d.bookmark)},draftOnly:true}]);}catch(error){}
    }
    return values;
  },
  bind(id,field,message,base,extra,context){
    const draft=this.read(id);
    if(draft && typeof draft.text==='string'){
      field.value=draft.text;if(extra&&typeof draft.bookmark==='boolean')extra.checked=draft.bookmark;
      message.textContent=draft.base!==base?'已恢复草稿；保存的内容已变化，请核对后再保存。':'已恢复未保存的草稿。';
    }
    const store=()=>{
      try{
        if(field.value===base && !extra){this.clear(id);message.textContent='未修改';return;}
        localStorage.setItem(this.key(id),JSON.stringify({text:field.value,base,bookmark:extra?.checked,context,at:Date.now()}));
        message.textContent='草稿已暂存在当前浏览器；点击保存后写入本机文献。';
      }catch(error){message.textContent='浏览器无法暂存草稿，请及时保存或复制内容。';}
    };
    field.addEventListener('input',store);if(extra)extra.addEventListener('change',store);
    return store;
  }
};
