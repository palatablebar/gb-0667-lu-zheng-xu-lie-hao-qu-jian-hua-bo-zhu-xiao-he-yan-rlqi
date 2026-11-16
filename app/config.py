from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
TITLE = '绿证序列号区间划拨与注销核验'
SHORT = 'certfolio'
VERSION = '2026.11.1'
COLUMNS = ['event_id', 'batch', 'action', 'owner', 'target', 'start', 'end', 'time', 'version', 'note']
PAGES = [('intake', '证书采信'), ('contract', '规则契约'), ('model', '区间划拨'), ('calculate', '注销核验'), ('quarantine', '问题隔离'), ('reconcile', '持仓对账'), ('batches', '批次归档')]
MAX_BYTES = 2_000_000
MAX_ROWS = 10000
NULLS = frozenset(['', '-', 'N/A', 'NULL', '未知'])
