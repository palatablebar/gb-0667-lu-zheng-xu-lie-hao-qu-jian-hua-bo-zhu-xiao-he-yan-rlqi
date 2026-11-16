import pytest
from app.config import ROOT,COLUMNS
from app.modules.m1_intake.rules import parse,decode
from app.modules.m1_intake.service import source
from app.errors import DomainError

def test_utf8_bom_header():
    # TRAP-02
    data=parse((ROOT/'sample_data/dirty.csv').read_bytes());assert data['input']==41

def test_legacy_encoding():
    # TRAP-01
    data=parse((ROOT/'sample_data/legacy.csv').read_bytes());assert data['encoding']=='gb18030';assert data['rows'][0]['raw']['owner']=='华东风电'

def test_sample_source_rows(sample):assert len(sample['intake']['rows'])==41

def test_empty_states():
    # TRAP-18
    assert parse(b'')['state']=='EMPTY_FILE';assert parse(b'\n\n')['state']=='BLANK_ONLY';assert parse(','.join(COLUMNS).encode())['state']=='HEADER_ONLY'

def test_multiline_csv_is_one_record():
    raw=(ROOT/'sample_data/clean.csv').read_bytes().decode('utf-8-sig');raw=raw.replace('11月签发','"11月\n签发"',1)
    assert len(parse(raw.encode())['rows'])==36

def test_column_count_isolated():
    raw=(','.join(COLUMNS)+'\n'+','.join(['x']*11)).encode();assert parse(raw)['quarantine'][0]['code']=='COLUMN_COUNT'

def test_unknown_sample_rejected():
    with pytest.raises(DomainError):source({'sample':'../../secret'})

def test_oversize_rejected():
    with pytest.raises(DomainError) as e:decode(b'a'*2000001)
    assert e.value.status==413
