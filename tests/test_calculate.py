from copy import deepcopy
from app.modules.m3_model.service import execute
from app.modules.m4_calculate.rules import retire,retirement_rows

def test_sample_retired_count(sample):assert sample['calculate']['retired']=='120'

def test_sample_retirement_evidence(sample):assert len(sample['calculate']['events'])==12

def test_sample_retired_ranges(sample):assert len(sample['calculate']['rows'])==12

def test_retirement_mutates_only_owned_range():
    state={'holders':{'b':{'a':[(10,20)]}},'retired':{}}
    row={'batch':'b','owner':'a','lo':12,'hi':15}
    assert retire(state,row) is None;assert state['holders']['b']['a']==[(10,12),(15,20)]

def test_repeated_retirement_rejected():
    state={'holders':{'b':{'a':[(10,20)]}},'retired':{}};row={'batch':'b','owner':'a','lo':12,'hi':15}
    retire(state,row);before=deepcopy(state);assert retire(state,row)=='RETIRED';assert state==before

def test_unknown_holding_rejected():
    assert retire({'holders':{},'retired':{}},{'batch':'b','owner':'x','lo':1,'hi':2})=='NOT_OWNED'

def test_partial_retirement_crossing_gap_rejected():
    state={'holders':{'b':{'a':[(1,3),(5,8)]}},'retired':{}};assert retire(state,{'batch':'b','owner':'a','lo':2,'hi':6})=='NOT_OWNED'
