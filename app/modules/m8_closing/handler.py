from fastapi import APIRouter, Body
from app.errors import DomainError
from . import service, store

router = APIRouter(prefix='/api/closing', tags=['closing'])

SAMPLE_PAYLOAD = {
    'period': '2026-11',
    'sources': [
        # 批号 00001：内部已划拨、交易所回执未到 → 待确认，禁止记已划出
        {'batch': '00001', 'source': 'internal', 'start': '9007199254740994000', 'end': '9007199254740994039'},
        # 批号 00002：内部 + 交易所回执齐备 → 已划出
        {'batch': '00002', 'source': 'internal', 'start': '9007199254740995000', 'end': '9007199254740995039'},
        {'batch': '00002', 'source': 'exchange', 'start': '9007199254740995000', 'end': '9007199254740995039'},
        # 批号 00003：三源齐备且有注销登记 → 已注销
        {'batch': '00003', 'source': 'internal', 'start': '9007199254740996000', 'end': '9007199254740996019'},
        {'batch': '00003', 'source': 'exchange', 'start': '9007199254740996000', 'end': '9007199254740996019'},
        {'batch': '00003', 'source': 'registry', 'start': '9007199254740996000', 'end': '9007199254740996019'},
        # 批号 00004：注销登记先到、交易所回执未到 → 回执缺口
        {'batch': '00004', 'source': 'internal', 'start': '9007199254740997000', 'end': '9007199254740997009'},
        {'batch': '00004', 'source': 'registry', 'start': '9007199254740997000', 'end': '9007199254740997009'},
    ],
}


@router.get('')
def sample():
    """GET 返回演示期间的正式差异账（不存在则按样例生成）。"""
    return service.generate(SAMPLE_PAYLOAD)


@router.post('/generate')
def generate(payload: dict = Body(default={})):
    if not isinstance(payload, dict):
        raise DomainError('PARAMS', '请求体必须是对象')
    return service.generate(payload)


@router.post('/evidence')
def evidence(payload: dict = Body(...)):
    return service.supplement(payload)


@router.post('/close')
def close(payload: dict = Body(...)):
    return service.close(payload)


@router.get('/ledgers')
def ledgers():
    return {'rows': store.list_ledgers()}


@router.get('/ledger/{ledger_id}')
def ledger(ledger_id: str):
    return store.read_ledger(ledger_id)
