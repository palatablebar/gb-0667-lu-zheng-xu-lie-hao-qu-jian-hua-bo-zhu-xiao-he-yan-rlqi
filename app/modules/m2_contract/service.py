from .rules import convert
from app.errors import DomainError
from app.reasons import issue

def execute(rows):
    good=[];bad=[]
    for row in rows:
        try:good.append(convert(row))
        except DomainError as exc:bad.append(issue(row,exc.code,exc.detail))
    return {'rows':good,'quarantine':bad,'accepted':len(good),'columns':[{'field':k,'type':v} for k,v in [('event_id','保形文本'),('batch','保形文本'),('start / end','闭区间序列号'),('time','带偏移时间'),('version','正整数')]]}
