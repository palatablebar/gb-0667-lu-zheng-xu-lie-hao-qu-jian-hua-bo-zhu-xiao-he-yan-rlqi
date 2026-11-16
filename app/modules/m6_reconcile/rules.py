from app.intervals import count,overlaps

def check_state(state):
    issued=sum(count(x) for x in state['issued'].values())
    retired=sum(count(x) for x in state['retired'].values())
    available=sum(count(v) for owners in state['holders'].values() for v in owners.values())
    collisions=[]
    for batch,owners in state['holders'].items():
        spans=[(a,b,owner) for owner,values in owners.items() for a,b in values]
        for i,(a,b,owner) in enumerate(spans):
            for c,d,other in spans[i+1:]:
                if a<d and c<b:collisions.append({'batch':batch,'owner':owner,'other':other})
            if overlaps(state['retired'].get(batch,[]),a,b):collisions.append({'batch':batch,'owner':owner,'other':'已注销'})
    return {'issued':str(issued),'available':str(available),'retired':str(retired),'delta':str(issued-available-retired),'collisions':collisions,'balanced':issued==available+retired and not collisions}
