import pytest
from app.modules.m2_contract.rules import convert
from app.modules.m2_contract.service import execute
from app.errors import DomainError

def test_sample_big_serial_preserved(sample):
    # TRAP-09
    assert sample['contract']['rows'][0]['start']=='9007199254740994000'

def test_batch_leading_zero(normalized):
    # TRAP-08
    assert normalized[0]['batch']=='00001'

def test_sample_contract_isolation(sample):assert len(sample['contract']['quarantine'])==2

def test_null_serial(normalized):
    # TRAP-07
    row=normalized[0]|{'raw':normalized[0]['raw']|{'start':'N/A'}}
    with pytest.raises(DomainError) as e:convert(row)
    assert e.value.code=='NULL_VALUE'

def test_reverse_range(normalized):
    row=normalized[0]|{'raw':normalized[0]['raw']|{'start':'20','end':'10'}}
    assert execute([row])['quarantine'][0]['code']=='RANGE'

def test_naive_timestamp_rejected(normalized):
    row=normalized[0]|{'raw':normalized[0]['raw']|{'time':'2026-11-01T12:00:00'}}
    assert execute([row])['quarantine'][0]['code']=='TIME'

def test_unknown_action(normalized):
    row=normalized[0]|{'raw':normalized[0]['raw']|{'action':'restore'}}
    assert execute([row])['quarantine'][0]['code']=='ACTION'


def test_serial_digit_limit_is_recoverable(normalized):
    row=normalized[0]|{'raw':normalized[0]['raw']|{'start':'1'*5000}}
    assert execute([row])['quarantine'][0]['code']=='SERIAL'
