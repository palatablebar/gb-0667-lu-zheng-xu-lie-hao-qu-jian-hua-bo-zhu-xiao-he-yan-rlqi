from app.modules.m5_quarantine.service import execute
from app.modules.m5_quarantine.rules import classify,filter_rows

def test_sample_bad_count(sample):assert sample['quarantine']['count']==5

def test_sample_reason_counts(sample):assert sum(r['count'] for r in sample['quarantine']['reasons'])==5

def test_sample_line_evidence(sample):assert all(r['line']>1 for r in sample['quarantine']['rows'])

def test_empty_quarantine():assert execute([])=={'count':0,'selected':0,'reasons':[],'rows':[],'recoverable':0}

def test_code_filter():assert filter_rows([{'code':'A'},{'code':'B'}],'A')==[{'code':'A'}]

def test_recoverable_counts():assert execute([{'code':'NULL_VALUE'},{'code':'RETIRED'}])['recoverable']==1

def test_reason_sort_stable():assert [r['code'] for r in classify([{'code':'Z'},{'code':'A'}])]==['A','Z']
