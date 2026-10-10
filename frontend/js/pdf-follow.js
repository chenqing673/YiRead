// Select the paragraph crossing the reading line, rather than using scroll percentages.
function readingLineOffset(height) {return Math.min(140, height * .3);}
function blockAtReadingLine(nodes, viewport) {
  const line = viewport.top + readingLineOffset(viewport.bottom - viewport.top);
  let best = null, distance = Infinity;
  for (const node of nodes) {
    const box = node.getBoundingClientRect();
    if (box.bottom < viewport.top || box.top > viewport.bottom) continue;
    if (box.top <= line && box.bottom >= line) return node;
    const gap = Math.min(Math.abs(box.top-line),Math.abs(box.bottom-line));
    if (gap < distance) {best=node;distance=gap;}
  }
  return best;
}
function pdfBlockKind(page,block){
  const rects=(block.rects || []).filter(r=>r.length===4 && r.every(Number.isFinite));
  // Legacy imports stored one whole page as one source block. Do not call it a paragraph.
  if(page.blocks.length===1 && rects.length>=15 && Math.max(...rects.map(r=>r[3]))-Math.min(...rects.map(r=>r[1]))>.55)return 'page';
  return block.kind;
}
class PdfFollower {
  constructor(paperId) {
    this.paperId=paperId;this.enabled=true;this.pages=new Map();this.blocks=new Map();this.active=null;
    this.scroll=document.getElementById('pdf-scroll');this.canvas=document.getElementById('pdf-pages');
    this.message=document.getElementById('pdf-sync-status');
    const button=document.getElementById('follow-btn');
    button.onclick=()=>{this.enabled=!this.enabled;button.textContent='跟随译文：' + (this.enabled?'开':'关');button.setAttribute('aria-pressed',String(this.enabled));if(this.enabled&&this.active)this.focus(this.active,true);};
    document.getElementById('pdf-zoom').onchange=event=>{
      this.canvas.style.width=event.target.value + '%';
      if(this.active&&this.enabled)this.focus(this.active,true);
    };
  }
  load(layout) {
    this.canvas.replaceChildren();this.pages.clear();this.blocks.clear();
    for(const page of layout.pages) {
      const sheet=el('div','pdf-sheet');sheet.dataset.pdfPage=page.page;
      sheet.style.aspectRatio=page.width + ' / ' + page.height;
      const image=el('img','pdf-image');image.src='/api/pdf-page/' + encodeURIComponent(this.paperId) + '/' + page.page;
      image.alt='原始 PDF 第 ' + page.page + ' 页';image.loading='lazy';image.decoding='async';
      const overlay=el('div','pdf-highlight-layer');overlay.setAttribute('aria-hidden','true');
      const error=el('div','pdf-page-error','页面加载失败，点击重试');error.hidden=true;
      const retry=()=>{error.hidden=true;image.src='/api/pdf-page/' + encodeURIComponent(this.paperId) + '/' + page.page + '?retry=' + Date.now();};
      image.ondblclick=()=>{
        const dialog=el('dialog','pdf-inspect');dialog.setAttribute('aria-label','原页放大');const close=el('button','quiet','关闭放大');close.onclick=()=>{dialog.close();dialog.remove();};
        const enlarged=el('img');enlarged.src=image.src;enlarged.alt=image.alt;dialog.append(close,enlarged);document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove());dialog.showModal();
      };
      image.onerror=()=>error.hidden=false;error.onclick=retry;error.setAttribute('role','button');error.tabIndex=0;error.onkeydown=event=>{if(event.key==='Enter')retry();};
      sheet.onclick=event=>{
        const box=sheet.getBoundingClientRect(),x=(event.clientX-box.left)/box.width,y=(event.clientY-box.top)/box.height;let picked=null,area=Infinity;
        for(const [id,block] of this.blocks)if(block.page===page.page)for(const r of block.rects || [])if(x>=r[0]&&x<=r[2]&&y>=r[1]&&y<=r[3]){const size=(r[2]-r[0])*(r[3]-r[1]);if(size<area){picked=id;area=size;}}
        if(picked&&this.onPick)this.onPick(picked);
      };
      sheet.append(image,overlay,error);this.canvas.append(sheet);this.pages.set(page.page,{sheet,overlay});
      for(const block of page.blocks) this.blocks.set(block.id,{page:page.page,rects:block.rects || [],kind:pdfBlockKind(page,block)});
    }
    this.message.textContent='滚动右侧译文，色块会跟随对应原文。';
  }
  fail(message) {this.message.textContent=message;}
  focus(blockId,force=false) {
    const changed=this.active!==blockId;this.active=blockId;
    const block=this.blocks.get(blockId);
    if(!this.enabled)return;
    if(!changed&&!force)return;
    for(const page of this.pages.values())page.overlay.replaceChildren();
    if(!block) {this.message.textContent='该段暂无可靠定位信息。';return;}
    const view=this.pages.get(block.page);if(!view)return;
    for(const rect of block.kind==='page'?[]:block.rects) {
      if(rect.length!==4 || rect.some(value=>!Number.isFinite(value)||value<0||value>1)||rect[2]<=rect[0]||rect[3]<=rect[1])continue;
      const highlight=el('div','pdf-highlight');
      highlight.classList.toggle('pdf-highlight-current',block.kind==='sentence'||block.kind==='sentence-order');
      highlight.style.left=(rect[0]*100)+'%';highlight.style.top=(rect[1]*100)+'%';
      highlight.style.width=((rect[2]-rect[0])*100)+'%';highlight.style.height=((rect[3]-rect[1])*100)+'%';
      view.overlay.append(highlight);
    }
    document.getElementById('pdf-position').textContent='第 ' + block.page + ' 页';
    this.message.textContent=block.kind==='page' ? '此旧版文本块覆盖整页，目前仅定位页面，不用黄色覆盖整页；可靠匹配的译句仍可单独跟随。' : block.rects.length ? block.kind==='sentence' ? '橙色标出当前译句对应的原文；点击译句可直接定位。' : block.kind==='sentence-order' ? '橙色按句序对应原文（已核对数字）；旧译文未经语义校验，点击「逐句对齐重译」可改善。' : '黄色标出对应原文段落；此段暂无可靠句子对应，可逐句对齐重译。' : '已定位到第 ' + block.page + ' 页；该段文字无法精确匹配，暂不显示色块。';
    for(const n of [block.page-1,block.page+1]){const nearby=this.pages.get(n)?.sheet.querySelector?.('img');if(nearby)nearby.loading='eager';}
    const rect=block.rects[0];this.scrollTo(view,rect ? (rect[1]+rect[3])/2 : 0,rect ? rect[0] : 0);
  }
  scrollTo(view,y,x=0) {
    const pane=this.scroll.getBoundingClientRect(),box=view.sheet.getBoundingClientRect();
    const top=this.scroll.scrollTop+box.top-pane.top-(this.scroll.clientTop||0)+y*box.height-readingLineOffset(this.scroll.clientHeight);
    const left=this.scroll.scrollLeft+box.left-pane.left-(this.scroll.clientLeft||0)+x*box.width-this.scroll.clientWidth*.1;
    this.scroll.scrollTo({top:Math.max(0,top),left:Math.max(0,left),behavior:'auto'});
  }
  page(number) {
    number=Number(number);const view=this.pages.get(number);if(!view)return;
    document.getElementById('pdf-position').textContent='第 '+number+' 页';
    if(this.blocks.get(this.active)?.page!==number){
      this.active=null;for(const page of this.pages.values())page.overlay.replaceChildren();
      this.message.textContent='已定位到第 '+number+' 页；点击译文段落可显示对应色块。';
    }
    this.scrollTo(view,0);
  }
}
