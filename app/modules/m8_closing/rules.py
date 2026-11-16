# 月末关账差异账：纯规则层。
# 裁决原则：未回执区间按期进入正式差异账，标记为“待确认”，绝不写成“已划出”；
# 凭据补回后只修正受影响区间；同一区间同一时刻只允许一个互斥结论。

from app.errors import DomainError as ClosingError

# 互斥状态机：同一区间在任一版本中只能处于下列状态之一。
PENDING = 'PENDING'          # 待确认差异：未取得受理回执，不能记为已划出
TRANSFERRED = 'TRANSFERRED'  # 已划出：受理回执齐备，三源一致
CANCELLED = 'CANCELLED'      # 已注销：注销登记齐备且与持仓一致
INTERNAL_ONLY = 'INTERNAL_ONLY'   # 内部有、外部无
REGISTER_ONLY = 'REGISTER_ONLY'   # 登记有、内部无
RECEIPT_GAP = 'RECEIPT_GAP'       # 回执缺口：有内部划拨/注销指令但无受理回执
CONFLICT = 'CONFLICT'             # 三源互斥冲突，需人工裁决

# 终态：进入终态后状态机关闭，不再接受普通凭据，只能由更正流程冲回。
TERMINAL = frozenset([TRANSFERRED, CANCELLED])
# 待确认类：正式差异账中挂账、等待凭据补回的状态。
PENDING_STATES = frozenset([PENDING, INTERNAL_ONLY, REGISTER_ONLY, RECEIPT_GAP, CONFLICT])

# 允许的状态迁移（补回凭据只修正受影响区间）。非法迁移一律拒绝，保证不出现互斥结论。
TRANSITIONS = {
    PENDING: frozenset([TRANSFERRED, CANCELLED, INTERNAL_ONLY, REGISTER_ONLY, RECEIPT_GAP, CONFLICT]),
    INTERNAL_ONLY: frozenset([TRANSFERRED, CANCELLED, CONFLICT]),
    REGISTER_ONLY: frozenset([TRANSFERRED, CANCELLED, CONFLICT]),
    RECEIPT_GAP: frozenset([TRANSFERRED, CANCELLED, CONFLICT]),
    CONFLICT: frozenset([TRANSFERRED, CANCELLED]),
    TRANSFERRED: frozenset(),
    CANCELLED: frozenset(),
}

STATUS_LABELS = {
    PENDING: '待确认',
    TRANSFERRED: '已划出',
    CANCELLED: '已注销',
    INTERNAL_ONLY: '内部独有',
    REGISTER_ONLY: '登记独有',
    RECEIPT_GAP: '回执缺口',
    CONFLICT: '三源冲突',
}

SOURCES = ('internal', 'exchange', 'registry')
SOURCE_LABELS = {'internal': '内部持仓', 'exchange': '交易所回执', 'registry': '注销登记'}


def can_transition(old, new):
    """同一区间不出现互斥结论：终态不可回退，迁移必须在白名单内。"""
    if old == new:
        return False
    return new in TRANSITIONS.get(old, frozenset())


def merge_points(intervals):
    """收集所有区间端点作为分割点；序列号为 Python 整数，不经过浮点。"""
    points = set()
    for lo, hi in intervals:
        points.add(lo)
        points.add(hi)
    return sorted(points)


def present(intervals, lo, hi):
    return any(a <= lo and b >= hi for a, b in intervals)


def classify_segment(lo, hi, flags):
    """依据三源在原子分段上的有无，裁决唯一结论，绝不并置互斥状态。"""
    internal, exchange, registry = flags['internal'], flags['exchange'], flags['registry']
    if internal and exchange and registry:
        # 注销登记覆盖且回执齐备：注销成立；否则为已划出
        return CANCELLED if registry else TRANSFERRED
    if internal and exchange and not registry:
        return TRANSFERRED
    if internal and not exchange and not registry:
        # 无受理回执：挂账待确认，禁止记为已划出
        return PENDING
    if internal and not exchange and registry:
        # 有内部指令与注销登记、缺交易所受理回执
        return RECEIPT_GAP
    if not internal and exchange and not registry:
        # 外部有回执、内部持仓缺失
        return REGISTER_ONLY
    if not internal and not exchange and registry:
        return REGISTER_ONLY
    if not internal and exchange and registry:
        return REGISTER_ONLY
    # internal 有、exchange 无、registry 有但性质互斥时归冲突；其余组合归冲突待裁决
    return CONFLICT


def split_into_segments(batch, source_map):
    """把一个批号下三源区间切成互不重叠的原子分段并逐段裁决。"""
    all_intervals = []
    for intervals in source_map.values():
        all_intervals.extend(intervals)
    points = merge_points(all_intervals)
    segments = []
    for lo, hi in zip(points, points[1:]):
        if lo >= hi:
            continue
        flags = {name: present(source_map.get(name, []), lo, hi) for name in SOURCES}
        if not any(flags.values()):
            continue
        status = classify_segment(lo, hi, flags)
        segments.append({
            'batch': batch,
            'lo': lo,
            'hi': hi,
            'width': width_of(source_map, lo),
            'status': status,
            'sources': sorted(name for name, ok in flags.items() if ok),
        })
    return segments


def width_of(source_map, value):
    width = 1
    for intervals in source_map.values():
        for a, b in intervals:
            if a <= value < b:
                width = max(width, len(str(b - 1)) if b - 1 > 0 else 1)
    return width


def adjacent(a, b):
    return a['batch'] == b['batch'] and a['status'] == b['status'] and a['hi'] == b['lo'] \
        and a['sources'] == b['sources']


def merge_adjacent(segments):
    """合并相邻且结论一致的分段，保持区间为闭区间对外展示。"""
    out = []
    for seg in sorted(segments, key=lambda s: (s['batch'], s['lo'])):
        if out and adjacent(out[-1], seg):
            out[-1]['hi'] = seg['hi']
        else:
            out.append(dict(seg))
    return out


def entry_key(batch, lo, hi):
    return f'{batch}:{lo}:{hi}'


# ---- 输入校验：来源批次、区间与期间 -------------------------------------

def validate_period(period):
    if not isinstance(period, str) or not period.strip():
        raise ClosingError('PERIOD', '关账期间不能为空')
    text = period.strip()
    if len(text) > 16 or any(ch in text for ch in ' \t\r\n/\\'):
        raise ClosingError('PERIOD', '关账期间格式无效（示例：2026-11）')
    return text


def validate_intervals(rows):
    """校验来源批次行；序列号按整数解析，文本原值保留，大整数不走浮点。"""
    if not isinstance(rows, list) or not rows:
        raise ClosingError('SOURCE_EMPTY', '至少提交一条来源批次区间')
    cleaned = []
    seen = set()
    for idx, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ClosingError('SOURCE_ROW', f'第{idx}行必须是对象')
        batch = str(row.get('batch', '')).strip()
        source = str(row.get('source', '')).strip()
        if not batch:
            raise ClosingError('BATCH', f'第{idx}行批号缺失')
        if source not in SOURCES:
            raise ClosingError('SOURCE_KIND', f'第{idx}行来源必须是 internal/exchange/registry')
        try:
            lo = int(str(row.get('start', '')).strip())
            hi = int(str(row.get('end', '')).strip())
        except (TypeError, ValueError):
            raise ClosingError('SERIAL', f'第{idx}行序列号不是整数')
        if lo < 0 or hi < lo:
            raise ClosingError('RANGE', f'第{idx}行区间起止错误')
        hi_open = hi + 1  # 闭区间转半开
        token = (source, batch, lo, hi_open)
        if token in seen:
            raise ClosingError('DUP_SOURCE', f'第{idx}行来源批次区间重复')
        seen.add(token)
        cleaned.append({'source': source, 'batch': batch, 'lo': lo, 'hi': hi_open,
                        'width': max(len(str(lo)), len(str(hi))),
                        'raw': {'batch': batch, 'source': source,
                                'start': str(row.get('start', '')).strip(),
                                'end': str(row.get('end', '')).strip()}})
    return cleaned


def group_sources(cleaned):
    grouped = {}
    for row in cleaned:
        batch_map = grouped.setdefault(row['batch'], {name: [] for name in SOURCES})
        batch_map[row['source']].append((row['lo'], row['hi']))
    return grouped


def batch_widths(cleaned):
    widths = {}
    for row in cleaned:
        widths[row['batch']] = max(widths.get(row['batch'], 1), row['width'])
    return widths
