// Text-level notes use exact quote plus surrounding text, never guessed sentence offsets.
const excerptButton=el('button','quiet','为选中文字记笔记');excerptButton.id='excerpt-note-btn';excerptButton.hidden=true;
document.querySelector('.segment-actions').append(excerptButton);
let selectedExcerpt=null;
document.addEventListener('selectionchange',()=>{
  if(document.querySelector('dialog[open]'))return;
  const selection=window.getSelection();selectedExcerpt=null;excerptButton.hidden=true;
  if(!selection || selection.isCollapsed || !selection.rangeCount)return;
  const range=selection.getRangeAt(0),start=range.startContainer.parentElement,end=range.endContainer.parentElement;
  const node=start?.closest('[data-block]'),prose=start?.closest('.reading-prose,td,th');
  if(!node || !prose || end?.closest('.reading-prose,td,th')!==prose || !content.contains(node))return;
  const quote=selection.toString();if(!quote.trim() || quote.length>350)return;
  const before=range.cloneRange();before.selectNodeContents(node);before.setEnd(range.startContainer,range.startOffset);
  const offset=before.toString().length,text=node.textContent;
  selectedExcerpt={node,quote,prefix:text.slice(Math.max(0,offset-24),offset),suffix:text.slice(offset+quote.length,offset+quote.length+24)};
  excerptButton.hidden=false;
});
excerptButton.onmousedown=event=>event.preventDefault();
excerptButton.onclick=()=>{
  if(!selectedExcerpt)return;
  const selection=selectedExcerpt;excerptButton.hidden=true;selectedExcerpt=null;
  editReaderNote(selection.node.dataset.block+'_n'+Date.now().toString(36),selection.node,selection);
};
function applyReaderExcerptMarks(){
  for(const node of content.querySelectorAll('[data-block]')){
    const notes=Object.entries(readerNotes).filter(([,note])=>note.anchor && locateReaderNote('',note)===node);
    const signature=JSON.stringify([node.dataset.renderedText,notes.map(([id,n])=>[id,n.anchor])]);
    if(node.dataset.excerptSignature===signature)continue;node.dataset.excerptSignature=signature;
    for(const mark of node.querySelectorAll('mark.reader-excerpt'))mark.replaceWith(...mark.childNodes);
    node.normalize();
    for(const [id,note] of notes){
      const {quote,prefix,suffix}=note.anchor;const text=node.textContent;const matches=[];
      for(let i=text.indexOf(quote);i>=0;i=text.indexOf(quote,i+1)){
        const left=!prefix || text.slice(Math.max(0,i-prefix.length),i)===prefix;
        const right=!suffix || text.slice(i+quote.length,i+quote.length+suffix.length)===suffix;
        if(left&&right)matches.push(i);
      }
      note.position_lost=matches.length!==1;if(note.position_lost)continue;
      const start=matches[0],end=start+quote.length;const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);const pieces=[];let offset=0;
      for(let textNode; (textNode=walker.nextNode());){const next=offset+textNode.data.length;if(next>start&&offset<end)pieces.push({node:textNode,start:Math.max(0,start-offset),end:Math.min(textNode.data.length,end-offset)});offset=next;}
      for(const piece of pieces.reverse()){
        let textNode=piece.node;if(piece.end<textNode.data.length)textNode.splitText(piece.end);if(piece.start)textNode=textNode.splitText(piece.start);
        const mark=el('mark','reader-excerpt');mark.dataset.note=id;textNode.replaceWith(mark);mark.append(textNode);
      }
    }
  }
}
readerNotesReady.then(applyReaderExcerptMarks);
