# 绿证序列号区间划拨与注销核验 深度登记

使用者：新能源证书核算员。核心规则：使用整数区间集合做证书划拨与注销，禁止重复占用和超出持仓，证书编号保形，按事件时间和版本重放且注销不可复活。

## 功能模块
| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 证书采信 | 执行证书采信并复核证据 | `GET /intake` `POST /api/intake` | `app/modules/m1_intake/service.py` `app/modules/m1_intake/rules.py` | `tests/test_intake.py` |
| M2 规则契约 | 执行规则契约并复核证据 | `GET /contract` `POST /api/contract` | `app/modules/m2_contract/service.py` `app/modules/m2_contract/rules.py` | `tests/test_contract.py` |
| M3 区间划拨 | 执行区间划拨并复核证据 | `GET /model` `POST /api/model` | `app/modules/m3_model/service.py` `app/modules/m3_model/rules.py` | `tests/test_model.py` |
| M4 注销核验 | 执行注销核验并复核证据 | `GET /calculate` `POST /api/calculate` | `app/modules/m4_calculate/service.py` `app/modules/m4_calculate/rules.py` | `tests/test_calculate.py` |
| M5 问题隔离 | 执行问题隔离并复核证据 | `GET /quarantine` `POST /api/quarantine` | `app/modules/m5_quarantine/service.py` `app/modules/m5_quarantine/rules.py` | `tests/test_quarantine.py` |
| M6 持仓对账 | 执行持仓对账并复核证据 | `GET /reconcile` `POST /api/reconcile` | `app/modules/m6_reconcile/service.py` `app/modules/m6_reconcile/rules.py` | `tests/test_reconcile.py` |
| M7 批次归档 | 执行批次归档并复核证据 | `GET /batches` `POST /api/batches` | `app/modules/m7_batches/service.py` `app/modules/m7_batches/rules.py` | `tests/test_batches.py` |
| M8 月末关账 | 生成正式差异账、补受理凭据、关账 | `GET /closing` `POST /api/closing/generate` `POST /api/closing/evidence` `POST /api/closing/close` | `app/modules/m8_closing/service.py` `app/modules/m8_closing/rules.py` `app/modules/m8_closing/store.py` | `tests/test_closing.py` |

## 陷阱登记
| TRAP | 现象 | 朴素实现 | 处理 | 位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | 历史编码 | 直接转换或覆盖产生误判 | 按数据字典处理并保留来源证据 | `app/modules/m1_intake/rules.py` | `tests/test_intake.py::test_legacy_encoding` |
| TRAP-02 | BOM表头 | 直接转换或覆盖产生误判 | 按数据字典处理并保留来源证据 | `app/modules/m1_intake/rules.py` | `tests/test_intake.py::test_utf8_bom_header` |
| TRAP-07 | 缺失哨兵 | 直接转换或覆盖产生误判 | 按数据字典处理并保留来源证据 | `app/modules/m2_contract/rules.py` | `tests/test_contract.py::test_null_serial` |
| TRAP-08 | 编码保形 | 直接转换或覆盖产生误判 | 按数据字典处理并保留来源证据 | `app/modules/m2_contract/rules.py` | `tests/test_contract.py::test_batch_leading_zero` |
| TRAP-09 | 大整数 | 直接转换或覆盖产生误判 | 按数据字典处理并保留来源证据 | `app/modules/m2_contract/rules.py` | `tests/test_contract.py::test_sample_big_serial_preserved` |
| TRAP-14 | 重复异值 | 直接转换或覆盖产生误判 | 按数据字典处理并保留来源证据 | `app/modules/m3_model/rules.py` | `tests/test_model.py::test_sample_duplicate_explained` |
| TRAP-18 | 空态区分 | 直接转换或覆盖产生误判 | 按数据字典处理并保留来源证据 | `app/modules/m1_intake/rules.py` | `tests/test_intake.py::test_empty_states` |
| TRAP-19 | 规则优先级 | 直接转换或覆盖产生误判 | 按数据字典处理并保留来源证据 | `app/modules/m3_model/rules.py` | `tests/test_model.py::test_order_independent` |
| TRAP-23 | 区间端点 | 直接转换或覆盖产生误判 | 按数据字典处理并保留来源证据 | `app/modules/m3_model/rules.py` | `tests/test_model.py::test_half_open_boundary` |
| TRAP-26 | 陈旧版本 | 直接转换或覆盖产生误判 | 按数据字典处理并保留来源证据 | `app/store.py` | `tests/test_batches.py::test_sample_review_cas` |
| TRAP-27 | 无回执记已划出 | 未等受理回执即按已划出销账 | 未回执区间按期进正式差异账，落待确认/回执缺口，禁止并置已划出 | `app/modules/m8_closing/rules.py` | `tests/test_closing.py::test_unreceipted_interval_is_pending_not_transferred` |
| TRAP-28 | 同区间互斥结论 | 凭据补回直接覆盖状态，出现已划出/已注销并存 | 白名单状态机，终态不可回退，非法迁移拒绝 | `app/modules/m8_closing/rules.py` `app/modules/m8_closing/store.py` | `tests/test_closing.py::test_terminal_status_cannot_be_reversed` |
| TRAP-29 | 重生成覆盖旧版 | 重新生成差异账失败时半批覆盖正式账 | 单事务整体替换，异常回滚保留旧版并登记 last_error | `app/modules/m8_closing/store.py` | `tests/test_closing.py::test_failed_regeneration_keeps_old_version` |
| TRAP-30 | 重跑新增/丢记录 | 重跑与换凭据产生重复行或物理删除历史 | 区间键唯一复用，旧行与凭据软保留，输入未变不升版 | `app/modules/m8_closing/store.py` | `tests/test_closing.py::test_same_input_rerun_creates_no_records` |

## 对账规则
签发=可用+已划出+已注销，持有人区间不重叠

## 月末关账裁决
未回执区间进正式差异账但只挂待确认，不记已划出；补回凭据仅迁移受影响区间并递增版本（CAS）；同区间状态机保证唯一互斥结论；重生成单事务替换、失败保留旧版；有待确认差异不得关账。

## 已知不覆盖
不覆盖外部登记系统同步、跨批次证书合并；演示范围为单个上传文件完整重放。

## 证据
每个事件保留CSV逻辑记录结束行号与原值；隔离记录附原因码。运行摘要包含输入SHA256、规则版本、参数和耗时。持久化为单次事务；重复输入复用运行ID。
