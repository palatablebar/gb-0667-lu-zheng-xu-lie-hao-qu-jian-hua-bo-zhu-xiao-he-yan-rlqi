from .rules import retire,retirement_rows
from app.intervals import count

def apply_retirement(state,row):return retire(state,row)

def execute(model):
    rows=retirement_rows(model['state'])
    return {'rows':rows,'retired':str(sum(int(r['quantity']) for r in rows)),'events':[{'event_id':r['event_id'],'owner':r['owner'],'quantity':r['quantity'],'line':r['line'],'status':'已注销'} for r in model['events'] if r['action']=='retire']}
