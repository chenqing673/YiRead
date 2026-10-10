// Original figures/tables are local PDF crops; no model or external image calls.
class ReaderFlowMedia {
  constructor(paperId,isFlow,focus){this.paperId=paperId;this.isFlow=isFlow;this.focus=focus;this.manifest=null;this.loading=null;this.applied=new WeakSet();}
  async update(paper){
    if(!this.isFlow())return;
    try{
      if(!this.manifest){
        if(!this.loading)this.loading=apiFetch('/api/reading-media/'+encodeURIComponent(this.paperId),{},true).then(r=>this.manifest=r.data).finally(()=>this.loading=null);
        await this.loading;
      }
      if(!this.isFlow())return;
      const active=document.querySelector('.translation-text.reading-active');
      const top=active?.getBoundingClientRect().top;
      for(const page of this.manifest?.pages || []){
        const section=document.getElementById('page-'+page.page);
        if(!section || this.applied.has(section))continue;
        section.querySelector('.media-load-note')?.remove();
        for(const asset of page.assets || []){
          const figure=el('figure','reader-original-media');figure.dataset.media=asset.id;figure.dataset.page=page.page;
          const header=el('figcaption','media-heading',(asset.kind==='table'?'原表':'原图')+' · 第 '+page.page+' 页');
          const enlarge=el('button','quiet','放大查看');enlarge.type='button';header.append(enlarge);
          const image=el('img');image.src=asset.url;image.alt=(asset.kind==='table'?'原始表格':'原始图形')+'，第 '+page.page+' 页';image.loading='lazy';image.decoding='async';image.style.aspectRatio=asset.width+' / '+asset.height;
          const retry=el('button','quiet media-image-retry','图表未载入，点击重试');retry.hidden=true;
          image.onerror=()=>retry.hidden=false;image.onload=()=>retry.hidden=true;
          retry.onclick=()=>{retry.hidden=true;image.src=asset.url+'&retry='+Date.now();};
          figure.append(header,image,retry);
          const inspect=()=>{
            const dialog=el('dialog','media-inspect');dialog.setAttribute('aria-label','原图表放大');
            const close=el('button','quiet','关闭放大');close.type='button';close.onclick=()=>dialog.close();
            const full=el('img');full.src=asset.url;full.alt=image.alt;dialog.append(close,full);dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();
          };
          enlarge.onclick=event=>{event.stopPropagation();inspect();};image.ondblclick=inspect;
          figure.onclick=()=>this.focus(asset,page.page,figure);
          const nodes=Array.from(section.querySelectorAll('[data-block]'));
          const anchor=nodes.find(n=>(n.dataset.parent || n.dataset.block)===asset.anchor);
          if(anchor)anchor.before(figure);else section.append(figure);
          const covered=nodes.filter(n=>(asset.covered || []).includes(n.dataset.parent || n.dataset.block));
          if(covered.length){
            const details=el('details','media-text-details');details.append(el('summary','',asset.kind==='table'?'展开表格文字译文':'展开图中文字译文'));
            figure.after(details);for(const node of covered)details.append(node);
            if(active && details.contains(active))details.open=true;
          }
        }
        this.applied.add(section);
      }
      if(active?.isConnected && Number.isFinite(top))document.getElementById('translation-scroll').scrollTop+=active.getBoundingClientRect().top-top;
    }catch(error){
      if(error.code===404 || !this.isFlow())return;
      const section=document.querySelector('.reading-page');if(!section || section.querySelector('.media-load-note'))return;
      const note=el('p','media-load-note settings-note','原图表暂未载入，正文仍可阅读。');const retry=el('button','quiet','重试图表');
      retry.onclick=()=>{note.remove();this.manifest=null;this.update(paper);};note.append(retry);section.querySelector('.page-title').after(note);
    }
  }
}
