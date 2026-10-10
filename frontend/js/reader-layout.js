// Optional page layout uses local geometry and cached translations, never a model.
class ReaderPageLayout {
  constructor(paperId, scroll, openFlow) {
    this.paperId=paperId;this.scroll=scroll;this.openFlow=openFlow;this.generation=0;this.states=new Map();
    this.zoom=Number(localStorage.getItem('yiread-layout-zoom')) || 100;
    if(![100,125,150,200].includes(this.zoom))this.zoom=100;
    this.resizeObserver=typeof ResizeObserver==='function'?new ResizeObserver(()=>this.resize()):null;
    this.resizeObserver?.observe(scroll);
    window.addEventListener('resize',()=>this.resize());
    document.fonts?.ready.then(()=>this.resize());
  }
  reset(){this.generation++;this.states.clear();}
  setZoom(value){this.zoom=[100,125,150,200].includes(Number(value))?Number(value):100;localStorage.setItem('yiread-layout-zoom',this.zoom);this.resize();}
  async update(paper, outputs) {
    const generation=this.generation;
    const pending=paper.pages.map(page=>{
      const section=document.getElementById('page-'+page.page);
      const signature=JSON.stringify(page.blocks.map(b=>[b.id,outputs[b.id]?.translation || '']));
      const existing=this.states.get(page.page);
      if(existing?.signature===signature){this.fit(existing);return null;}
      return {page,section,signature};
    }).filter(Boolean);
    // Two read-only layout requests at a time, independent of model concurrency.
    const worker=async()=>{
      while(pending.length && generation===this.generation){
        const task=pending.shift();
        try{
          const {data}=await apiFetch('/api/translation-layout/'+encodeURIComponent(this.paperId)+'/'+task.page.page,{},true);
          if(generation!==this.generation || !task.section.isConnected)continue;
          if(!data?.width || !data?.blocks || !data.background)throw new Error('排版数据不完整');
          this.apply(task.section,data,task.signature);
        }catch(error){
          if(generation!==this.generation || !task.section.isConnected)continue;
          this.fallback(task.section,'本页暂无法保持原版式，已展示完整译文。');
        }
      }
    };
    await Promise.all([worker(),worker()]);
  }
  fallback(section,message){
    const nodes=Array.from(section.querySelectorAll('[data-block]'));
    const heading=section.querySelector('.page-title');section.replaceChildren(heading);
    section.classList.remove('layout-ready');section.append(el('p','layout-note',message));
    for(const node of nodes){node.classList.remove('layout-textbox','layout-preserved','layout-hidden','layout-overflow');node.removeAttribute('style');const body=node.querySelector('.layout-contents');if(body)node.replaceChildren(...body.childNodes);section.append(node);}
    this.states.delete(Number(section.dataset.page));
  }
  apply(section,plan,signature){
    const nodes=Array.from(section.querySelectorAll('[data-block]'));const heading=section.querySelector('.page-title');
    section.replaceChildren(heading);section.classList.add('layout-ready');
    const canvas=el('div','layout-canvas');const sheet=el('div','layout-paper');
    sheet.style.width=plan.width+'px';sheet.style.height=plan.height+'px';
    const background=el('img','layout-background');background.alt='第 '+plan.page+' 页，保留图表的原版排版背景';background.loading='lazy';background.decoding='async';background.src=plan.background;
    background.onerror=()=>{if(section.contains(background))this.fallback(section,'页面背景未载入，已展示完整译文。可切回连续阅读后重试。');};
    sheet.append(background);canvas.append(sheet);section.append(canvas);
    const preserved=el('details','layout-preserved-list');const summary=el('summary');preserved.append(summary);let count=0;
    const state={plan,signature,section,canvas,sheet,positioned:[]};
    for(const node of nodes){
      const entry=plan.blocks.find(b=>b.id===node.dataset.block);
      node.classList.remove('layout-textbox','layout-preserved','layout-hidden','layout-overflow');node.removeAttribute('style');
      const body=node.querySelector('.layout-contents');if(body)node.replaceChildren(...body.childNodes);
      if(entry?.placement==='replace'){
        const [x0,y0,x1,y1]=entry.box;node.classList.add('layout-textbox');
        node.dataset.layoutX=x0;
        let height=(y1-y0)*plan.height;
        // PDF glyph bounds are shorter than a browser line box. Use only the
        // small blank gap below a single line, never another paragraph's space.
        if(height<(entry.font_size || 10)*1.4){
          const next=plan.blocks.filter(b=>b!==entry && b.box && b.box[1]>=y1 && b.box[0]<x1 && b.box[2]>x0).reduce((y,b)=>Math.min(y,b.box[1]),1);
          height=Math.max(height,Math.min((entry.font_size || 10)*1.3,(next-y0)*plan.height-2,height+5));
        }
        Object.assign(node.style,{left:(x0*plan.width)+'px',top:(y0*plan.height)+'px',width:((x1-x0)*plan.width)+'px',height:height+'px',fontWeight:entry.bold || entry.kind==='heading'?'600':'400'});
        sheet.append(node);state.positioned.push({node,entry});
      }else if(entry?.placement==='untranslated' || node.classList.contains('placeholder')){
        node.classList.add('layout-hidden');preserved.append(node);
      }else{
        node.classList.add('layout-preserved');node.dataset.layoutReason=entry?.reason || '没有可靠位置';preserved.append(node);count++;
      }
    }
    summary.textContent=count+' 个区域保留原文 · 展开查看完整译文';
    preserved.hidden=!count;section.append(preserved);
    if(!count && !state.positioned.length)section.append(el('p','layout-note','本页保留原文，暂无可排入的译文。'));
    this.states.set(plan.page,state);this.resize();
  }
  fit(state){
    for(const {node,entry} of state.positioned){
      let body=node.querySelector('.layout-contents');
      if(!body){body=el('div','layout-contents');body.append(...node.childNodes);node.append(body);}
      node.querySelector('.layout-full-text')?.remove();node.classList.remove('layout-overflow');
      let size=Math.max(10,Math.min(32,entry.font_size || 10));node.style.fontSize=size+'px';
      if(!body.clientHeight)continue; // Hidden panes are measured when made visible.
      while(size>9 && (body.scrollHeight>body.clientHeight+1 || body.scrollWidth>body.clientWidth+1)){size=Math.max(9,size-.5);node.style.fontSize=size+'px';}
      if(body.scrollHeight>body.clientHeight+1 || body.scrollWidth>body.clientWidth+1){
        node.classList.add('layout-overflow');const button=el('button','layout-full-text','查看完整译文');
        button.title='此段超出原文字区域，切到连续阅读查看全部内容';
        button.onclick=event=>{event.stopPropagation();this.openFlow(node.dataset.parent || node.dataset.block);};node.append(button);
      }
    }
  }
  resize(){
    for(const state of this.states.values()){
      if(!state.section.isConnected)continue;
      const available=state.section.clientWidth || this.scroll.clientWidth || state.plan.width;
      const scale=available/state.plan.width*this.zoom/100;
      state.canvas.style.width=(state.plan.width*scale)+'px';state.canvas.style.height=(state.plan.height*scale)+'px';state.sheet.style.transform='scale('+scale+')';this.fit(state);
    }
  }
}
