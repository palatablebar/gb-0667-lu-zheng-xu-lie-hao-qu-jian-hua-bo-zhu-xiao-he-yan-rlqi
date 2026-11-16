import json
from collections import defaultdict
from app.reasons import issue
from app.intervals import normalize,covered,overlaps,subtract

def deduplicate(rows):
    groups=defaultdict(list)
    for row in rows:groups[row['event_id']].append(row)
    accepted=[];bad=[]
    for key,items in sorted(groups.items()):
        variants={json.dumps(x['raw'],sort_keys=True,ensure_ascii=False) for x in items}
        if len(variants)>1:
            bad.extend(issue(x,'CONFLICT') for x in items);continue
        accepted.append(items[0]);bad.extend(issue(x,'DUPLICATE') for x in items[1:])
    return sorted(accepted,key=lambda r:(r['utc'],r['event_id'])),bad

def allocate(state,row):
    batch=row['batch'];owner=row['owner'];lo=row['lo'];hi=row['hi']
    holders=state['holders'].setdefault(batch,{})
    issued=state['issued'].setdefault(batch,[])
    current=holders.get(owner,[])
    if row['action']=='issue':
        if overlaps(issued,lo,hi):return 'OVERLAP'
        state['issued'][batch]=normalize(issued+[(lo,hi)])
        state.setdefault('widths',{})[batch]=max(state.get('widths',{}).get(batch,0),row.get('width',1))
        holders[owner]=normalize(current+[(lo,hi)])
    else:
        if not row['target'] or row['target']==owner:return 'OWNER'
        if not covered(current,lo,hi):return 'NOT_OWNED'
        holders[owner]=subtract(current,lo,hi)
        holders[row['target']]=normalize(holders.get(row['target'],[])+[(lo,hi)])
    return None
