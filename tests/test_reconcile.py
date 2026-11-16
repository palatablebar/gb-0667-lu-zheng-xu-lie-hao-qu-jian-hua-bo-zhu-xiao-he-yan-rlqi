from app.modules.m6_reconcile.rules import check_state
from app.modules.m6_reconcile.service import execute

def test_sample_balanced(sample):assert sample['reconcile']['balanced'] is True

def test_sample_account_totals(sample):assert sample['reconcile']['issued']=='1200';assert sample['reconcile']['available']=='1080';assert sample['reconcile']['retired']=='120'

def test_sample_event_conservation(sample):assert sample['reconcile']['input']==sample['reconcile']['accepted']+sample['reconcile']['isolated']==41

def test_lost_certificate_detected():
    out=check_state({'issued':{'b':[(1,11)]},'holders':{'b':{'a':[(1,5)]}},'retired':{}});assert out['delta']=='6';assert not out['balanced']

def test_cross_owner_collision_detected():
    state={'issued':{'b':[(1,11)]},'holders':{'b':{'a':[(1,6)],'c':[(5,10)]}},'retired':{}};assert check_state(state)['collisions'][0]['other']=='c'

def test_retired_owned_collision_detected():
    state={'issued':{'b':[(1,11)]},'holders':{'b':{'a':[(1,6)]}},'retired':{'b':[(5,10)]}};assert not check_state(state)['balanced']

def test_empty_ledger_balances():assert check_state({'issued':{},'holders':{},'retired':{}})['balanced']
