# 月末关账差异账服务编排：校验来源批次 → 三源分割裁决 → 持久化正式账。

import hashlib
import json
from .rules import (
    validate_period, validate_intervals, group_sources, batch_widths,
    split_into_segments, merge_adjacent, entry_key, STATUS_LABELS, SOURCE_LABELS,
    TRANSFERRED, CANCELLED,
)
from . import store
from app.errors import DomainError


def source_hash(period, cleaned):
    body = json.dumps(
        {'period': period, 'sources': [(r['source'], r['batch'], str(r['lo']), str(r['hi'])) for r in cleaned]},
        sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


def build_entries(cleaned):
    """三源区间分割并裁决，合并相邻同结论分段；未回执区间落为待确认而非已划出。"""
    grouped = group_sources(cleaned)
    widths = batch_widths(cleaned)
    entries = []
    for batch in sorted(grouped):
        segments = split_into_segments(batch, grouped[batch])
        for seg in merge_adjacent(segments):
            seg['width'] = max(widths.get(batch, 1), seg['width'])
            seg['interval_key'] = entry_key(batch, seg['lo'], seg['hi'])
            seg['status_label'] = STATUS_LABELS[seg['status']]
            seg['source_labels'] = [SOURCE_LABELS[s] for s in seg['sources']]
            seg['start'] = str(seg['lo']).zfill(seg['width'])
            seg['end'] = str(seg['hi'] - 1).zfill(seg['width'])
            seg['quantity'] = str(seg['hi'] - seg['lo'])
            entries.append(seg)
    return entries


def source_batches_view(cleaned):
    """页面对账用：来源批次清单，保留文本原值与大整数保形。"""
    view = []
    for row in cleaned:
        view.append({'batch': row['batch'], 'source': row['source'],
                     'source_label': SOURCE_LABELS[row['source']],
                     'start': row['raw']['start'].zfill(row['width']),
                     'end': row['raw']['end'].zfill(row['width'])})
    return view


def generate(payload):
    """按期生成正式差异账；同期间已存在则走重跑（失败保留旧版）。"""
    period = validate_period(payload.get('period', ''))
    cleaned = validate_intervals(payload.get('sources', []))
    digest = source_hash(period, cleaned)
    entries = build_entries(cleaned)
    batches_view = source_batches_view(cleaned)
    ledger_id = 'CL-' + digest[:16]
    existing_id = store.find_by_period(period)
    if existing_id is None:
        return store.create_ledger(ledger_id, period, digest, batches_view, entries)
    current = store.read_ledger(existing_id)
    if current['source_hash'] == digest:
        # 输入完全一致：重跑核对不新增记录，直接返回现账。
        return current
    try:
        ledger, changed = store.regenerate(existing_id, digest, batches_view, entries, current['version'])
    except DomainError:
        store.mark_regen_failure(existing_id, '重新生成校验失败，旧版保留')
        raise
    return ledger


def supplement(payload):
    """补回受理凭据：只修正受影响区间，凭据追加不覆盖历史。"""
    ledger_id = payload.get('ledger_id')
    interval_key = payload.get('interval_key')
    kind = str(payload.get('kind', '')).strip()
    ref = str(payload.get('ref', '')).strip()
    detail = str(payload.get('detail', '')).strip()
    expected_version = payload.get('version')
    target = str(payload.get('target_status', '')).strip()
    if not isinstance(expected_version, int):
        raise DomainError('REVISION', '请提交整数版本')
    if target not in (TRANSFERRED, CANCELLED):
        raise DomainError('TARGET_STATUS', '凭据只能把待确认区间修正为已划出或已注销')
    if kind not in ('exchange_receipt', 'registry_notice', 'correction'):
        raise DomainError('EVIDENCE_KIND', '凭据类型无效')
    return store.attach_evidence(ledger_id, interval_key, kind, ref, detail, target,
                                 expected_version, '补回受理凭据，仅修正受影响区间')


def close(payload):
    ledger_id = payload.get('ledger_id')
    expected_version = payload.get('version')
    if not isinstance(expected_version, int):
        raise DomainError('REVISION', '请提交整数版本')
    return store.close_ledger(ledger_id, expected_version)


def pending_summary(ledger):
    """页面核对：来源批次、待确认差异、最终状态三视图汇总。"""
    entries = ledger['entries']
    active = [e for e in entries if not e['superseded']]
    by_status = {}
    for e in active:
        by_status.setdefault(e['status_label'], 0)
        by_status[e['status_label']] += 1
    return {
        'total_intervals': len(active),
        'pending': ledger['pending'],
        'final': ledger['final'],
        'by_status': by_status,
        'source_batch_count': len(ledger['source_batches']),
        'can_close': ledger['pending'] == 0 and ledger['status'] != 'CLOSED',
    }
