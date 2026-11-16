from .rules import deduplicate,allocate
from app.modules.m4_calculate.service import apply_retirement
from app.intervals import count
from app.reasons import issue

def execute(rows):
    ordered,bad=deduplicate(rows)
    state={'holders':{},'issued':{},'retired':{}}
    accepted=[]
    for row in ordered:
        code=apply_retirement(state,row) if row['action']=='retire' else allocate(state,row)
        if code:bad.append(issue(row,code));continue
        accepted.append(row)
    holdings=[]
    for batch,owners in sorted(state['holders'].items()):
        for owner,intervals in sorted(owners.items()):
            for a,b in intervals:holdings.append({'batch':batch,'owner':owner,'start':str(a).zfill(state.get('widths',{}).get(batch,1)),'end':str(b-1).zfill(state.get('widths',{}).get(batch,1)),'quantity':str(b-a)})
    return {'rows':holdings,'events':accepted,'state':state,'quarantine':bad,'issued':str(sum(count(v) for v in state['issued'].values())),'available':str(sum(count(v) for owners in state['holders'].values() for v in owners.values()))}
