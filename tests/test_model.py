from copy import deepcopy
from app.modules.m3_model.service import execute
from app.modules.m3_model.rules import deduplicate
from app.intervals import normalize,subtract,count

def test_sample_available(sample):assert sample['model']['available']=='1080'

def test_sample_holders(sample):assert len(sample['model']['rows'])==24

def test_sample_duplicate_explained(sample):
    # TRAP-14
    assert any(r['code']=='DUPLICATE' for r in sample['model']['quarantine'])

def test_half_open_boundary():
    # TRAP-23
    assert normalize([(1,4),(4,7)])==[(1,7)];assert count([(1,4),(4,7)])==6

def test_subtraction_splits_holding():assert subtract([(1,11)],4,7)==[(1,4),(7,11)]

def test_order_independent(normalized):
    # TRAP-19
    assert execute(normalized)['rows']==execute(list(reversed(normalized)))['rows']

def test_conflicting_id_all_quarantined(normalized):
    first=deepcopy(normalized[0]);second=deepcopy(first);second['raw']['owner']='另一家公司'
    accepted,bad=deduplicate([first,second]);assert accepted==[];assert [r['code'] for r in bad]==['CONFLICT','CONFLICT']

def test_duplicate_issue_cannot_revive_retired(normalized):
    extra=deepcopy(normalized[0]);extra['event_id']='ZI';extra['utc']='2026-11-10T00:00:00+00:00'
    out=execute(normalized+[extra]);assert out['quarantine'][-1]['code']=='OVERLAP';assert out['issued']=='1200'


def test_serial_leading_zeros_retained(normalized):
    from app.modules.m2_contract.rules import convert
    row=normalized[0]|{'raw':normalized[0]['raw']|{'start':'000001','end':'000010'}}
    result=execute([convert(row)])
    assert result['rows'][0]['start']=='000001'
    assert result['rows'][0]['end']=='000010'
