from .rules import check_state

def execute(intake,model,quarantine):
    check=check_state(model['state'])
    accepted=len(model['events']);isolated=quarantine['count']
    rows=[{'account':'输入事件','value':intake['input']},{'account':'有效事件','value':accepted},{'account':'隔离事件','value':isolated},{'account':'签发证书','value':check['issued']},{'account':'可用证书','value':check['available']},{'account':'注销证书','value':check['retired']}]
    return check|{'rows':rows,'input':intake['input'],'accepted':accepted,'isolated':isolated,'row_delta':intake['input']-accepted-isolated,'balanced':check['balanced'] and intake['input']==accepted+isolated}
