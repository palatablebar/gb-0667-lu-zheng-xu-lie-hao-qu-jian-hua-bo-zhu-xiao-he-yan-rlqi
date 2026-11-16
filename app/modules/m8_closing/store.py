# 月末关账差异账持久化：与流水线批次库并存的独立表。
# 不变量：
#  1) 重新生成失败保留旧版——新版本在同一事务内整体替换，异常即回滚；
#  2) 换凭据不丢记录——凭据只追加，原始凭据软保留；
#  3) 重跑核对不新增记录——(期间,批号,起,止) 唯一键复用条目；
#  4) 同区间不出现互斥结论——状态迁移走白名单，终态不可回退。

import json
import sqlite3
from app.store import connect
from app.errors import DomainError
from .rules import entry_key, can_transition, STATUS_LABELS

SCHEMA = '''
CREATE TABLE IF NOT EXISTS closing_ledgers(
  id TEXT PRIMARY KEY,
  period TEXT NOT NULL,
  version INTEGER NOT NULL,
  status TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  source_batches TEXT NOT NULL,
  snapshot TEXT NOT NULL,
  regenerations INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created TEXT DEFAULT CURRENT_TIMESTAMP,
  updated TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS closing_entries(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ledger_id TEXT NOT NULL,
  interval_key TEXT NOT NULL,
  batch TEXT NOT NULL,
  lo INTEGER NOT NULL,
  hi INTEGER NOT NULL,
  width INTEGER NOT NULL,
  status TEXT NOT NULL,
  sources TEXT NOT NULL,
  evidence TEXT NOT NULL DEFAULT '[]',
  superseded INTEGER NOT NULL DEFAULT 0,
  created TEXT DEFAULT CURRENT_TIMESTAMP,
  updated TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(ledger_id, interval_key)
);
CREATE TABLE IF NOT EXISTS closing_evidence(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ledger_id TEXT NOT NULL,
  interval_key TEXT NOT NULL,
  kind TEXT NOT NULL,
  ref TEXT NOT NULL,
  detail TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS closing_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ledger_id TEXT NOT NULL,
  interval_key TEXT NOT NULL,
  old_status TEXT,
  new_status TEXT NOT NULL,
  reason TEXT NOT NULL,
  created TEXT DEFAULT CURRENT_TIMESTAMP
);
'''


def init():
    with connect() as db:
        db.executescript(SCHEMA)


def _row_to_entry(row):
    data = dict(row)
    data['lo'] = int(data['lo'])
    data['hi'] = int(data['hi'])
    data['sources'] = json.loads(data['sources'])
    data['evidence'] = json.loads(data['evidence'])
    data['status_label'] = STATUS_LABELS.get(data['status'], data['status'])
    data['start'] = str(data['lo']).zfill(data['width'])
    data['end'] = str(data['hi'] - 1).zfill(data['width'])
    data['quantity'] = str(data['hi'] - data['lo'])
    data['superseded'] = bool(data['superseded'])
    return data


def create_ledger(ledger_id, period, source_hash, source_batches, entries):
    """单事务创建正式差异账；任一步失败整体回滚，不留半账。"""
    init()
    with connect() as db:
        try:
            db.execute(
                'INSERT INTO closing_ledgers(id,period,version,status,source_hash,source_batches,snapshot) '
                "VALUES(?,?,1,'OPEN',?,?,?)",
                (ledger_id, period, source_hash, json.dumps(source_batches, ensure_ascii=False),
                 json.dumps(entries, ensure_ascii=False)))
            _insert_entries(db, ledger_id, entries)
        except sqlite3.Error as exc:
            raise DomainError('LEDGER_WRITE', f'差异账写入失败，旧版保留：{exc}', 500)
    return read_ledger(ledger_id)


def _insert_entries(db, ledger_id, entries):
    for e in entries:
        db.execute(
            'INSERT INTO closing_entries(ledger_id,interval_key,batch,lo,hi,width,status,sources,evidence) '
            'VALUES(?,?,?,?,?,?,?,?,?)',
            (ledger_id, entry_key(e['batch'], e['lo'], e['hi']), e['batch'], e['lo'], e['hi'],
             e['width'], e['status'], json.dumps(e['sources'], ensure_ascii=False),
             json.dumps(e.get('evidence', []), ensure_ascii=False)))


def read_ledger(ledger_id):
    init()
    with connect() as db:
        row = db.execute('SELECT * FROM closing_ledgers WHERE id=?', (ledger_id,)).fetchone()
        if not row:
            raise DomainError('LEDGER_MISSING', '差异账不存在', 404)
        entries = [_row_to_entry(r) for r in db.execute(
            'SELECT * FROM closing_entries WHERE ledger_id=? ORDER BY batch,lo', (ledger_id,))]
        evidence = [dict(r) for r in db.execute(
            'SELECT * FROM closing_evidence WHERE ledger_id=? ORDER BY id', (ledger_id,))]
        audit = [dict(r) for r in db.execute(
            'SELECT * FROM closing_audit WHERE ledger_id=? ORDER BY id', (ledger_id,))]
    ledger = dict(row)
    ledger['source_batches'] = json.loads(ledger['source_batches'])
    ledger['entries'] = entries
    ledger['evidence_log'] = evidence
    ledger['audit'] = audit
    ledger['pending'] = sum(1 for e in entries if not e['superseded'] and e['status'] not in ('TRANSFERRED', 'CANCELLED'))
    ledger['final'] = sum(1 for e in entries if not e['superseded'] and e['status'] in ('TRANSFERRED', 'CANCELLED'))
    return ledger


def find_by_period(period):
    init()
    with connect() as db:
        row = db.execute('SELECT id FROM closing_ledgers WHERE period=? ORDER BY version DESC LIMIT 1',
                         (period,)).fetchone()
    return row['id'] if row else None


def list_ledgers():
    init()
    with connect() as db:
        rows = db.execute(
            'SELECT id,period,version,status,regenerations,last_error,created,updated '
            'FROM closing_ledgers ORDER BY updated DESC,id DESC LIMIT 100').fetchall()
    return [dict(r) for r in rows]


def regenerate(ledger_id, source_hash, source_batches, new_entries, expected_version):
    """重新生成：CAS 版本 + 同事务整体替换。失败抛错并保留旧版，记录失败次数。"""
    init()
    with connect() as db:
        row = db.execute('SELECT version,source_hash FROM closing_ledgers WHERE id=?', (ledger_id,)).fetchone()
        if not row:
            raise DomainError('LEDGER_MISSING', '差异账不存在', 404)
        if row['version'] != expected_version:
            raise DomainError('STALE_VERSION', '版本已变更，请重新加载', 409)
        if row['source_hash'] == source_hash:
            # 输入未变：重跑核对不新增记录、不升版本，直接返回现账。
            return read_ledger(ledger_id), False
        try:
            # 保留旧条目（superseded=1），不物理删除，满足“换凭据不能丢失记录”。
            db.execute('UPDATE closing_entries SET superseded=1,updated=CURRENT_TIMESTAMP WHERE ledger_id=?',
                       (ledger_id,))
            _reconcile_entries(db, ledger_id, new_entries)
            db.execute(
                'UPDATE closing_ledgers SET version=version+1,source_hash=?,source_batches=?,snapshot=?,'
                'regenerations=regenerations+1,last_error=NULL,updated=CURRENT_TIMESTAMP WHERE id=?',
                (source_hash, json.dumps(source_batches, ensure_ascii=False),
                 json.dumps(new_entries, ensure_ascii=False), ledger_id))
        except sqlite3.Error as exc:
            raise DomainError('REGEN_FAILED', f'重新生成失败，已保留旧版：{exc}', 500)
    return read_ledger(ledger_id), True


def _reconcile_entries(db, ledger_id, new_entries):
    """重跑不新增重复记录：同键复用，仅在状态机允许时更新受影响区间。"""
    for e in new_entries:
        key = entry_key(e['batch'], e['lo'], e['hi'])
        existing = db.execute(
            'SELECT id,status,superseded FROM closing_entries WHERE ledger_id=? AND interval_key=?',
            (ledger_id, key)).fetchone()
        if existing is None:
            db.execute(
                'INSERT INTO closing_entries(ledger_id,interval_key,batch,lo,hi,width,status,sources) '
                'VALUES(?,?,?,?,?,?,?,?)',
                (ledger_id, key, e['batch'], e['lo'], e['hi'], e['width'], e['status'],
                 json.dumps(e['sources'], ensure_ascii=False)))
            db.execute('INSERT INTO closing_audit(ledger_id,interval_key,old_status,new_status,reason) '
                       'VALUES(?,?,NULL,?,?)', (ledger_id, key, e['status'], '重跑新增区间'))
            continue
        if existing['superseded']:
            db.execute('UPDATE closing_entries SET superseded=0,updated=CURRENT_TIMESTAMP WHERE id=?',
                       (existing['id'],))
        if existing['status'] != e['status']:
            if not can_transition(existing['status'], e['status']):
                raise DomainError(
                    'MUTEX_STATUS',
                    f'区间{key}存在互斥结论：{existing["status"]}不能改为{e["status"]}', 409)
            db.execute('UPDATE closing_entries SET status=?,sources=?,updated=CURRENT_TIMESTAMP WHERE id=?',
                       (e['status'], json.dumps(e['sources'], ensure_ascii=False), existing['id']))
            db.execute('INSERT INTO closing_audit(ledger_id,interval_key,old_status,new_status,reason) '
                       'VALUES(?,?,?,?,?)', (ledger_id, key, existing['status'], e['status'], '重跑状态迁移'))


def mark_regen_failure(ledger_id, message):
    """重新生成失败时只登记失败原因，绝不触碰已发布版本。"""
    init()
    with connect() as db:
        db.execute('UPDATE closing_ledgers SET last_error=?,updated=CURRENT_TIMESTAMP WHERE id=?',
                   (message, ledger_id))


def attach_evidence(ledger_id, interval_key, kind, ref, detail, target_status, expected_version, reason):
    """补回凭据：只修正受影响区间；凭据追加不覆盖；CAS 防并发。"""
    init()
    with connect() as db:
        ledger = db.execute('SELECT version FROM closing_ledgers WHERE id=?', (ledger_id,)).fetchone()
        if not ledger:
            raise DomainError('LEDGER_MISSING', '差异账不存在', 404)
        if ledger['version'] != expected_version:
            raise DomainError('STALE_VERSION', '版本已变更，请重新加载', 409)
        entry = db.execute(
            'SELECT id,status FROM closing_entries WHERE ledger_id=? AND interval_key=? AND superseded=0',
            (ledger_id, interval_key)).fetchone()
        if not entry:
            raise DomainError('ENTRY_MISSING', '待确认区间不存在或已被新版替代', 404)
        if not ref or not kind:
            raise DomainError('EVIDENCE', '凭据类型与受理号不能为空')
        old_status = entry['status']
        if old_status == target_status:
            raise DomainError('NO_CHANGE', '该区间已是目标结论，请勿重复提交凭据', 409)
        if not can_transition(old_status, target_status):
            raise DomainError(
                'MUTEX_STATUS',
                f'区间{interval_key}存在互斥结论：{old_status}不能改为{target_status}', 409)
        evidence = {'kind': kind, 'ref': ref, 'detail': detail or '', 'status': target_status}
        db.execute(
            'INSERT INTO closing_evidence(ledger_id,interval_key,kind,ref,detail) VALUES(?,?,?,?,?)',
            (ledger_id, interval_key, kind, ref, detail or ''))
        db.execute(
            'UPDATE closing_entries SET status=?,evidence=?,updated=CURRENT_TIMESTAMP WHERE id=?',
            (target_status, json.dumps([evidence], ensure_ascii=False), entry['id']))
        db.execute('INSERT INTO closing_audit(ledger_id,interval_key,old_status,new_status,reason) '
                   'VALUES(?,?,?,?,?)', (ledger_id, interval_key, old_status, target_status, reason))
        # 每次凭据修订都递增版本，旧版本号随后失效，保证乐观锁真正生效。
        db.execute('UPDATE closing_ledgers SET version=version+1,updated=CURRENT_TIMESTAMP WHERE id=?',
                   (ledger_id,))
    return read_ledger(ledger_id)


def close_ledger(ledger_id, expected_version):
    """关账：仍有挂账差异则拒绝，保证正式账不把未回执区间静默转结。"""
    init()
    with connect() as db:
        row = db.execute('SELECT version,status FROM closing_ledgers WHERE id=?', (ledger_id,)).fetchone()
        if not row:
            raise DomainError('LEDGER_MISSING', '差异账不存在', 404)
        if row['version'] != expected_version:
            raise DomainError('STALE_VERSION', '版本已变更，请重新加载', 409)
        pending = db.execute(
            'SELECT COUNT(*) AS n FROM closing_entries WHERE ledger_id=? AND superseded=0 '
            "AND status NOT IN ('TRANSFERRED','CANCELLED')", (ledger_id,)).fetchone()['n']
        if pending:
            raise DomainError('PENDING_OPEN', f'仍有{pending}个待确认差异，不能关账', 409)
        db.execute("UPDATE closing_ledgers SET status='CLOSED',updated=CURRENT_TIMESTAMP WHERE id=?",
                   (ledger_id,))
    return read_ledger(ledger_id)
