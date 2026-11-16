from app.intervals import covered,overlaps,subtract,normalize,count

def retire(state,row):
    batch=row['batch'];lo=row['lo'];hi=row['hi'];owner=row['owner']
    if overlaps(state['retired'].get(batch,[]),lo,hi):return 'RETIRED'
    holdings=state['holders'].get(batch,{}).get(owner,[])
    if not covered(holdings,lo,hi):return 'NOT_OWNED'
    state['holders'][batch][owner]=subtract(holdings,lo,hi)
    state['retired'][batch]=normalize(state['retired'].get(batch,[])+[(lo,hi)])
    return None

def retirement_rows(state):
    return [{'batch':batch,'start':str(a).zfill(state.get('widths',{}).get(batch,1)),'end':str(b-1).zfill(state.get('widths',{}).get(batch,1)),'quantity':str(b-a),'status':'已注销'} for batch,intervals in sorted(state['retired'].items()) for a,b in intervals]
