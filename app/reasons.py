REASONS = {'COLUMN_COUNT': '字段数量不一致', 'NULL_VALUE': '必填值缺失', 'SERIAL': '序列号格式错误', 'RANGE': '区间起止错误', 'TIME': '时间缺少偏移或无效', 'ACTION': '未知业务动作', 'VERSION': '版本无效', 'DUPLICATE': '重复事件已剔除', 'CONFLICT': '事件号存在异值', 'OVERLAP': '证书区间已签发', 'NOT_OWNED': '区间超出持仓', 'OWNER': '持有人无效', 'RETIRED': '区间已注销'}
def issue(row, code, detail=''):
    return {'line': row.get('line', 0), 'code': code, 'detail': detail or REASONS.get(code, code), 'raw': row.get('raw', row)}
