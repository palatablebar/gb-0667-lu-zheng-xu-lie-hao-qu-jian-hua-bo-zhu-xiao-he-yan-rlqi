import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.errors import DomainError
from app.modules.m8_closing import service, store
from app.modules.m8_closing.handler import SAMPLE_PAYLOAD
from app.modules.m8_closing.rules import can_transition, split_into_segments, validate_intervals


@pytest.fixture
def ledger():
    return service.generate(SAMPLE_PAYLOAD)


def _entry(led, label):
    return next(e for e in led['entries'] if e['status_label'] == label and not e['superseded'])


# ---- 裁决：未回执区间进入正式差异账，但不能写成已划出 --------------------

def test_unreceipted_interval_is_pending_not_transferred(ledger):
    pending = _entry(ledger, '待确认')
    assert pending['status'] == 'PENDING'
    assert pending['sources'] == ['internal']
    assert pending['quantity'] == '40'
    # 正式账里该区间绝不能并置“已划出”
    assert all(not (e['interval_key'] == pending['interval_key'] and e['status'] == 'TRANSFERRED')
               for e in ledger['entries'])


def test_three_sources_resolve_to_cancelled(ledger):
    cancelled = _entry(ledger, '已注销')
    assert cancelled['status'] == 'CANCELLED'
    assert set(cancelled['sources']) == {'internal', 'exchange', 'registry'}


def test_receipt_gap_is_segregated(ledger):
    gap = _entry(ledger, '回执缺口')
    assert gap['status'] == 'RECEIPT_GAP'
    assert 'exchange' not in gap['sources']


def test_big_integer_and_leading_zero_preserved():
    led = service.generate({'period': '2026-12', 'sources': [
        {'batch': '00042', 'source': 'internal',
         'start': '9007199254740994000', 'end': '9007199254740994099'}]})
    e = led['entries'][0]
    assert e['batch'] == '00042'
    assert e['start'] == '9007199254740994000' and e['end'] == '9007199254740994099'
    assert e['quantity'] == '100'


def test_segment_classification_has_single_verdict():
    grouped = {'b': {'internal': [(1, 5)], 'exchange': [], 'registry': []}}
    segs = split_into_segments('b', grouped['b'])
    assert len(segs) == 1 and segs[0]['status'] == 'PENDING'


def test_state_machine_blocks_mutual_exclusive_transitions():
    assert can_transition('PENDING', 'TRANSFERRED')
    assert can_transition('RECEIPT_GAP', 'CANCELLED')
    # 终态不可回退；待确认不能直接跳过凭据变成已注销以外的互斥态
    assert not can_transition('TRANSFERRED', 'PENDING')
    assert not can_transition('CANCELLED', 'TRANSFERRED')
    assert not can_transition('PENDING', 'PENDING')


def test_invalid_source_rejected():
    with pytest.raises(DomainError) as exc:
        validate_intervals([{'batch': 'b', 'source': 'bogus', 'start': '1', 'end': '2'}])
    assert exc.value.code == 'SOURCE_KIND'
    with pytest.raises(DomainError):
        validate_intervals([{'batch': 'b', 'source': 'internal', 'start': '9', 'end': '2'}])


# ---- 补回凭据：只修正受影响区间，CAS 与互斥校验 -------------------------

def test_evidence_only_changes_target_interval(ledger):
    pending = _entry(ledger, '待确认')
    before = {e['interval_key']: e['status'] for e in ledger['entries']}
    out = service.supplement({'ledger_id': ledger['id'], 'interval_key': pending['interval_key'],
                              'kind': 'exchange_receipt', 'ref': 'RCP-1', 'detail': '',
                              'target_status': 'TRANSFERRED', 'version': 1})
    after = {e['interval_key']: e['status'] for e in out['entries'] if not e['superseded']}
    changed = [k for k in before if before[k] != after.get(k)]
    assert changed == [pending['interval_key']]
    assert out['version'] == 2
    # 凭据留痕追加，原始记录未被覆盖
    assert len(out['evidence_log']) == 1 and out['evidence_log'][0]['ref'] == 'RCP-1'


def test_stale_evidence_version_rejected(ledger):
    pending = _entry(ledger, '待确认')
    service.supplement({'ledger_id': ledger['id'], 'interval_key': pending['interval_key'],
                        'kind': 'exchange_receipt', 'ref': 'RCP-1', 'detail': '',
                        'target_status': 'TRANSFERRED', 'version': 1})
    with pytest.raises(DomainError) as exc:
        service.supplement({'ledger_id': ledger['id'], 'interval_key': pending['interval_key'],
                            'kind': 'exchange_receipt', 'ref': 'RCP-2', 'detail': '',
                            'target_status': 'TRANSFERRED', 'version': 1})
    assert exc.value.status == 409 and exc.value.code == 'STALE_VERSION'


def test_terminal_status_cannot_be_reversed(ledger):
    cancelled = _entry(ledger, '已注销')
    with pytest.raises(DomainError) as exc:
        service.supplement({'ledger_id': ledger['id'], 'interval_key': cancelled['interval_key'],
                            'kind': 'correction', 'ref': 'X', 'detail': '',
                            'target_status': 'TRANSFERRED', 'version': 1})
    assert exc.value.code == 'MUTEX_STATUS'


def test_replacing_evidence_keeps_history(ledger):
    pending = _entry(ledger, '待确认')
    service.supplement({'ledger_id': ledger['id'], 'interval_key': pending['interval_key'],
                        'kind': 'exchange_receipt', 'ref': 'OLD', 'detail': '',
                        'target_status': 'TRANSFERRED', 'version': 1})
    led = store.read_ledger(ledger['id'])
    # 旧凭据仍在留痕表中（active 标记保留），未被物理删除
    assert any(ev['ref'] == 'OLD' for ev in led['evidence_log'])
    assert any(a['new_status'] == 'TRANSFERRED' for a in led['audit'])


# ---- 重生成：失败保留旧版、重跑不新增记录 -------------------------------

def test_same_input_rerun_creates_no_records(ledger):
    again = service.generate(SAMPLE_PAYLOAD)
    assert again['version'] == 1
    assert again['regenerations'] == 0
    assert len([e for e in again['entries'] if not e['superseded']]) == \
           len([e for e in ledger['entries'] if not e['superseded']])


def test_regeneration_preserves_old_rows_and_bumps_version():
    base = {'period': '2026-11', 'sources': [
        {'batch': 'B1', 'source': 'internal', 'start': '100', 'end': '199'},
        {'batch': 'B1', 'source': 'exchange', 'start': '100', 'end': '149'}]}
    first = service.generate(base)
    grown = service.generate({'period': '2026-11', 'sources': base['sources'] + [
        {'batch': 'B1', 'source': 'exchange', 'start': '150', 'end': '199'}]})
    assert grown['version'] == 2 and grown['regenerations'] == 1
    # 旧行软保留，未物理删除
    assert any(e['superseded'] for e in grown['entries'])
    # 受影响区间复用区间键，不产生重复活跃行
    keys = [e['interval_key'] for e in grown['entries'] if not e['superseded']]
    assert len(keys) == len(set(keys))


def test_failed_regeneration_keeps_old_version():
    base = {'period': '2026-11', 'sources': [
        {'batch': 'B1', 'source': 'internal', 'start': '100', 'end': '149'},
        {'batch': 'B1', 'source': 'exchange', 'start': '100', 'end': '149'}]}
    first = service.generate(base)
    # 新输入要求已划出终态回退，状态机拒绝，旧版必须保留
    with pytest.raises(DomainError) as exc:
        service.generate({'period': '2026-11', 'sources': [
            {'batch': 'B1', 'source': 'registry', 'start': '100', 'end': '149'}]})
    assert exc.value.code == 'MUTEX_STATUS'
    kept = store.read_ledger(first['id'])
    assert kept['version'] == 1
    assert any(e['status'] == 'TRANSFERRED' and not e['superseded'] for e in kept['entries'])
    assert kept['last_error']


# ---- 关账：有待确认差异时拒绝 -------------------------------------------

def test_close_blocked_while_pending(ledger):
    with pytest.raises(DomainError) as exc:
        service.close({'ledger_id': ledger['id'], 'version': 1})
    assert exc.value.code == 'PENDING_OPEN'


def test_close_succeeds_after_all_evidence(ledger):
    for label, target in (('待确认', 'TRANSFERRED'), ('回执缺口', 'CANCELLED')):
        entry = _entry(ledger, label)
        ledger = service.supplement({'ledger_id': ledger['id'], 'interval_key': entry['interval_key'],
                                     'kind': 'exchange_receipt', 'ref': 'R-' + label, 'detail': '',
                                     'target_status': target, 'version': ledger['version']})
    closed = service.close({'ledger_id': ledger['id'], 'version': ledger['version']})
    assert closed['status'] == 'CLOSED' and closed['pending'] == 0


# ---- API 与页面 ---------------------------------------------------------

def test_api_and_page_wiring():
    client = TestClient(app)
    assert client.get('/closing').status_code == 200
    data = client.get('/api/closing').json()
    lid = data['id']
    assert client.get('/api/closing/ledger/' + lid).status_code == 200
    assert client.get('/api/closing/ledgers').status_code == 200
    pending = next(e for e in data['entries'] if e['status'] == 'PENDING')
    ok = client.post('/api/closing/evidence', json={
        'ledger_id': lid, 'interval_key': pending['interval_key'], 'kind': 'exchange_receipt',
        'ref': 'R', 'target_status': 'TRANSFERRED', 'version': data['version']})
    assert ok.status_code == 200
    assert client.get('/closing?run=' + lid).status_code == 200


def test_missing_ledger_404():
    with pytest.raises(DomainError) as exc:
        store.read_ledger('CL-nope')
    assert exc.value.status == 404
