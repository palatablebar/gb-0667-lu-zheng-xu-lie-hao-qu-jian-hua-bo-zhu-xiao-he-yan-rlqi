import pytest
from app import store
from app.manifest import digest
from app.modules.m7_batches.rules import validate
from app.modules.m7_batches.service import evidence_csv
from app.errors import DomainError

def test_sample_manifest_hash(sample):assert len(sample['manifest']['sha256'])==64

def test_sample_idempotency(sample):
    first=store.save(sample);second=store.save(sample);assert first['created'];assert not second['created'];assert len(store.history())==1

def test_sample_review_cas(sample):
    # TRAP-26
    first=store.save(sample);reviewed=store.review(first['manifest']['run_id'],1);assert reviewed['revision']==2
    with pytest.raises(DomainError) as exc:store.review(first['manifest']['run_id'],1)
    assert exc.value.status==409

def test_sample_csv_matches_evidence(sample):
    out=evidence_csv(sample);assert out.startswith('\ufeff');assert 'NULL_VALUE' in out;assert len(out.splitlines())==6

def test_unknown_parameter_rejected():
    with pytest.raises(DomainError):validate({'magic':1},{})

def test_hash_changes_with_input():assert digest(b'a',{})!=digest(b'b',{})

def test_missing_run_404():
    with pytest.raises(DomainError) as exc:store.read('missing')
    assert exc.value.status==404
