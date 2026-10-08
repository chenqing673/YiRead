// Restricted document formatting. All source content remains text, never executable HTML.
function appendReadingInline(parent,text) {
  const pattern=/\*\*([^*\n]+)\*\*|\^\{([^{}\n]+)\}|\^(\d+|[a-z]|[+-])|_\{([^{}\n]+)\}|_(\d+)|\b(H2O|CO2|N2|O2|H2|Na2CO3|K2CO3|Cs2CO3|MgSO4|Na2SO4)\b|\b(1H|13C|19F|31P)(?=\s*NMR\b)/g;
  let start=0;
  for(const match of text.matchAll(pattern)) {
    if(match.index>start)parent.append(text.slice(start,match.index));
    if(match[7]) {
      const isotope=match[7].match(/^(\d+)([A-Z])$/);parent.append(el('sup','',isotope[1]),isotope[2]);
    } else if(match[6]) {
      for(const part of match[6].split(/(\d+)/).filter(Boolean))parent.append(/^\d+$/.test(part)?el('sub','',part):part);
    } else parent.append(el(match[1]?'strong':match[2] || match[3]?'sup':'sub','',match[1] || match[2] || match[3] || match[4] || match[5]));
    start=match.index+match[0].length;
  }
  if(start<text.length)parent.append(text.slice(start));
}
function readingTableCells(line) {
  let value=line.trim();
  if(value.startsWith('|'))value=value.slice(1);
  if(value.endsWith('|')&&!value.endsWith('\\|'))value=value.slice(0,-1);
  return value.split(/(?<!\\)\|/).map(cell=>cell.trim().replace(/\\\|/g,'|'));
}
function renderReadingText(node,text,units=[]) {
  node.replaceChildren();
  if(units.length && units.every(unit=>Number.isInteger(unit.start)&&Number.isInteger(unit.end)&&unit.start>=0&&unit.end>unit.start&&unit.end<=text.length)) {
    const paragraph=el('p','reading-prose');let offset=0;
    for(const unit of units) {
      if(unit.start<offset){renderReadingText(node,text);return;}
      if(unit.start>offset)paragraph.append(text.slice(offset,unit.start));
      const sentence=el('span','reading-sentence');sentence.dataset.follow=unit.id;
      appendReadingInline(sentence,text.slice(unit.start,unit.end));paragraph.append(sentence);offset=unit.end;
    }
    if(offset<text.length)paragraph.append(text.slice(offset));
    node.append(paragraph);node.dataset.renderedText=text;return;
  }
  const lines=text.split('\n');let index=0;
  while(index<lines.length) {
    const header=readingTableCells(lines[index]);
    const separator=index+1<lines.length ? readingTableCells(lines[index+1]) : [];
    if(lines[index].includes('|') && header.length>1 && header.length<=50 && separator.length===header.length && separator.every(cell=>/^:?-{3,}:?$/.test(cell))) {
      const wrap=el('div','reading-table-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','译文表格，可横向滚动');
      const table=el('table','reading-table');const head=el('thead');const row=el('tr');
      const align=separator.map(value=>value.endsWith(':')?(value.startsWith(':')?'center':'right'):'left');
      header.forEach((value,i)=>{const cell=el('th');cell.setAttribute('scope','col');cell.style.textAlign=align[i];appendReadingInline(cell,value);row.append(cell);});head.append(row);table.append(head);
      const body=el('tbody');index+=2;
      while(index<lines.length && lines[index].includes('|')) {
        const values=readingTableCells(lines[index]);if(values.length!==header.length)break;
        const row=el('tr');values.forEach((value,i)=>{const cell=el('td');cell.style.textAlign=align[i];appendReadingInline(cell,value);row.append(cell);});body.append(row);index++;
      }
      table.append(body);wrap.append(table);node.append(wrap);continue;
    }
    if(!lines[index].trim()) {node.append(el('div','reading-paragraph-gap'));index++;continue;}
    const heading=lines[index].match(/^#{1,4}\s+(.+)$/);
    const paragraph=el(heading?'h3':'p','reading-prose');appendReadingInline(paragraph,heading?heading[1]:lines[index]);node.append(paragraph);index++;
  }
  node.dataset.renderedText=text;
}
