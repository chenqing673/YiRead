"""Conservative geometric reading order: columns separated by persistent gutters."""
import statistics


def gutter(items):
    # Short labels, equations and full-width headings do not establish a column.
    body=[i for i in items if .10 <= i['box'][2]-i['box'][0] <= .70]
    if len(body)<4:return None
    edges=sorted({v for i in body for v in (i['box'][0],i['box'][2])})
    height=statistics.median(max(.001,i['box'][3]-i['box'][1]) for i in body)
    best=None
    for a,b in zip(edges,edges[1:]):
        # Journal gutters can be only 10–14 pt on a ~600 pt page. A 2.5%
        # minimum rejected real two-column articles (while wide test gutters passed).
        if b-a<.008:continue
        x=(a+b)/2
        left=[i for i in body if i['box'][2]<=x]
        right=[i for i in body if i['box'][0]>=x]
        if min(len(left),len(right))<2:continue
        crossing=len(body)-len(left)-len(right)
        if crossing>max(1,int(len(body)*.08)):continue
        overlap=min(max(i['box'][3] for i in left),max(i['box'][3] for i in right))-max(min(i['box'][1] for i in left),min(i['box'][1] for i in right))
        if overlap<height*1.5:continue
        score=(b-a)*min(len(left),len(right))/(1+crossing)
        if best is None or score>best[0]:best=(score,x)
    return best[1] if best else None


def order_items(items,depth=0):
    if not items:return []
    # Determine columns separately above/below genuinely full-width material.
    # The abstract and body on a first page often use different column widths.
    wide=sorted([i for i in items if i['box'][2]-i['box'][0]>.70],key=lambda i:i['box'][1]) if depth<8 else []
    if wide:
        remaining=[i for i in items if i not in wide];result=[]
        for barrier in wide:
            center=(barrier['box'][1]+barrier['box'][3])/2
            before=[i for i in remaining if (i['box'][1]+i['box'][3])/2<center]
            result.extend(order_items(before,depth+1));result.append(barrier)
            used={id(i) for i in before};remaining=[i for i in remaining if id(i) not in used]
        return result+order_items(remaining,depth+1)
    x=gutter(items) if depth<8 else None
    if x is None:return sorted(items,key=lambda i:(round(i['box'][1],5),i['box'][0]))
    left=[i for i in items if i['box'][2]<=x]
    right=[i for i in items if i['box'][0]>=x]
    spanning=sorted([i for i in items if i['box'][0]<x<i['box'][2]],key=lambda i:i['box'][1])
    result=[]
    # Full-width headings/captions divide the page into independent column bands.
    for barrier in spanning:
        center=(barrier['box'][1]+barrier['box'][3])/2
        before_left=[i for i in left if (i['box'][1]+i['box'][3])/2<center]
        before_right=[i for i in right if (i['box'][1]+i['box'][3])/2<center]
        result.extend(order_items(before_left+before_right,depth+1));result.append(barrier)
        used={id(i) for i in before_left+before_right}
        left=[i for i in left if id(i) not in used];right=[i for i in right if id(i) not in used]
    result.extend(order_items(left,depth+1));result.extend(order_items(right,depth+1))
    return result


def unrotate_rect(rect,rotation):
    x0,y0,x1,y1=rect
    if rotation==90:return [y0,1-x1,y1,1-x0]
    if rotation==180:return [1-x1,1-y1,1-x0,1-y0]
    if rotation==270:return [1-y1,x0,1-y0,x1]
    return list(rect)


def ordered_blocks(blocks,separators=(),rotation=0):
    """Reorder existing records without changing IDs, text, coordinates or saved files."""
    items=[]
    for block in blocks:
        rects=block.get('rects') or []
        if rects:
            # Detect columns from actual lines, not tall paragraph bounding boxes.
            # Old blocks may also include both page headers or a margin line number.
            items.extend({'box':unrotate_rect(rect,rotation),'block':block} for rect in rects)
        elif block.get('reading_bbox'):items.append({'box':block['reading_bbox'],'block':block})
        else:return blocks  # No geometry: do not invent a reading order.
    items.extend({'box':box,'separator':True} for box in separators)
    result=[];seen=set()
    for item in order_items(items):
        if item.get('separator'):continue
        block=item['block']
        if block['id'] not in seen:seen.add(block['id']);result.append(block)
    return result
