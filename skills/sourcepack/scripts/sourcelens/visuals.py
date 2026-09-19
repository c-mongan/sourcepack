"""Bounded overview and exact-time priority, independent of image similarity."""
from .contracts import ContractError

def overview_times(start_ms,duration_ms,count,frame_ms=40):
    if not 1<=count<=12 or duration_ms<=0:raise ContractError('Invalid visual budget')
    end=max(start_ms,start_ms+duration_ms-frame_ms)
    return sorted(set(round(start_ms+(end-start_ms)*i/max(1,count-1)) for i in range(count)))

def select_frames(candidates,duration_ms,requested_ms,remaining):
    requests=sorted(set(requested_ms))
    if len(requests)>remaining or not 0<=remaining<=144:raise ContractError('Requested frames exceed remaining budget')
    if any(not 0<=t<duration_ms for t in requests):raise ContractError('Requested frame outside source')
    selected={}
    for t in requests:
        after=[x for x in candidates if x['source_pts_ms']>=t]
        if not after:raise ContractError('Requested frame unavailable')
        x=min(after,key=lambda x:x['source_pts_ms']);selected[x['source_pts_ms']]={**x,'requested_ms':t,'reason':'requested'}
    ordered=sorted(candidates,key=lambda x:x['source_pts_ms'])
    priority=([ordered[-1],ordered[0]] if ordered else [])+[x for x in ordered if x.get('reason')=='scene']+ordered
    for x in priority:
        if len(selected)>=remaining:break
        selected.setdefault(x['source_pts_ms'],x)
    return sorted(selected.values(),key=lambda x:x['source_pts_ms'])
