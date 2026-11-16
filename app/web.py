from fastapi.templating import Jinja2Templates
from app.config import ROOT,TITLE,SHORT,PAGES,VERSION
from app import store
from app.pipeline import run
templates=Jinja2Templates(directory=ROOT/'app/templates')

def render(request,page,rid=None):
    if page=='closing':
        from app.modules.m8_closing import store as closing_store
        from app.modules.m8_closing.handler import SAMPLE_PAYLOAD
        from app.modules.m8_closing import service
        ledger=closing_store.read_ledger(rid) if rid else service.generate(SAMPLE_PAYLOAD)
        context={'title':TITLE,'short':SHORT,'pages':PAGES,'page':page,'page_title':dict(PAGES)[page],
                 'version':VERSION,'history':store.history(),'ledger':ledger,
                 'summary':service.pending_summary(ledger),
                 'result':{'manifest':{'run_id':ledger['id']},'revision':ledger['version'],
                           'reviewed':ledger['status']=='CLOSED','created_at':ledger['created'],
                           'reconcile':{'issued':'—','available':'—','retired':'—','delta':'—'},
                           'quarantine':{'count':ledger['pending']}}}
        return templates.TemplateResponse(request=request,name='closing.html',context=context)
    result=store.read(rid) if rid else store.save(run({'sample':'dirty'}))
    return templates.TemplateResponse(request=request,name=f'{page}.html',context={'title':TITLE,'short':SHORT,'pages':PAGES,'page':page,'page_title':dict(PAGES)[page],'version':VERSION,'result':result,'section':result[page],'history':store.history()})
