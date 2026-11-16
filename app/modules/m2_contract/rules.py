import re
from datetime import datetime,timezone
from app.config import NULLS
from app.errors import DomainError

def convert(row):
    raw=row['raw'];r={k:v.strip() for k,v in raw.items()}
    for key in ('event_id','batch','action','owner','start','end','time','version'):
        if r[key] in NULLS:raise DomainError('NULL_VALUE',key+'不能为空')
    if r['action'] not in ('issue','transfer','retire'):raise DomainError('ACTION','动作无效')
    if not re.fullmatch(r'[0-9]+',r['start']) or not re.fullmatch(r'[0-9]+',r['end']):raise DomainError('SERIAL','序列号必须为数字文本')
    if len(r['start'])>40 or len(r['end'])>40:raise DomainError('SERIAL','序列号不得超过40位')
    lo,hi=int(r['start']),int(r['end'])+1
    if lo>=hi:raise DomainError('RANGE','末号早于首号')
    if not r['version'].isdigit() or int(r['version'])<1:raise DomainError('VERSION','版本须为正整数')
    try:
        t=datetime.fromisoformat(r['time'].replace('Z','+00:00'))
        if t.tzinfo is None:raise ValueError()
    except ValueError:raise DomainError('TIME','时间必须带偏移')
    return r|{'line':row['line'],'raw':raw,'lo':lo,'hi':hi,'utc':t.astimezone(timezone.utc).isoformat(),'version':int(r['version']),'quantity':str(hi-lo),'width':max(len(r['start']),len(r['end']))}
