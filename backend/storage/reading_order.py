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
        if b-a<.025:continue
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
    x=gutter(items) if depth<3 else None
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
        result.extend(order_items(before_left,depth+1));result.extend(order_items(before_right,depth+1));result.append(barrier)
        used={id(i) for i in before_left+before_right}
        left=[i for i in left if id(i) not in used];right=[i for i in right if id(i) not in used]
    result.extend(order_items(left,depth+1));result.extend(order_items(right,depth+1))
    return result


def ordered_blocks(blocks):
    """Reorder existing records without changing IDs, text, coordinates or saved files."""
    items=[]
    for block in blocks:
        box=block.get('reading_bbox')
        if not box:
            rects=block.get('rects') or []
            if not rects:return blocks  # No geometry: do not invent a reading order.
            box=[min(r[0] for r in rects),min(r[1] for r in rects),max(r[2] for r in rects),max(r[3] for r in rects)]
        items.append({'box':box,'block':block})
    return [i['block'] for i in order_items(items)]
