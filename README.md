# 绿证序列号区间划拨与注销核验

供新能源证书核算员核对大整数序列号、前导零批号、重复注销、交叉划拨等数据问题。使用整数区间集合做证书划拨与注销，禁止重复占用和超出持仓，证书编号保形，按事件时间和版本重放且注销不可复活。

## 启动

```sh
docker compose up --build -d
```

访问 [工作台](http://localhost:18206/)，无需准备文件即可运行。

## 演示

1. 进入采信模块，选脏样例并运行。
2. 逐模块核对来源行、业务结果与隔离原因。
3. 切换干净样例比较差异；重复运行相同输入复用批次。
4. 对账通过后进入归档模块复核，可下载隔离证据CSV。

## 模块与入口

- 证书采信：`/intake`，`GET/POST /api/intake`。
- 规则契约：`/contract`，`GET/POST /api/contract`。
- 区间划拨：`/model`，`GET/POST /api/model`。
- 注销核验：`/calculate`，`GET/POST /api/calculate`。
- 问题隔离：`/quarantine`，`GET/POST /api/quarantine`。
- 持仓对账：`/reconcile`，`GET/POST /api/reconcile`。
- 批次归档：`/batches`，`GET/POST /api/batches`。

[接口文档](http://localhost:18206/docs)。

## 验证

```sh
docker compose config --quiet
docker compose exec -T app pytest -q
```

## 数据与定义

区间首末号为闭区间，内部转为半开区间。序列号使用Python整数运算，对外按文本输出，大整数不经过浮点。事件时间必须带偏移且先转UTC；同刻按事件号排序。事件号冲突全部隔离，相同事件只采信一条。注销不可撤销，重复签发不能恢复证书。全局签发=各持有人可用+已注销；划拨只是持有人变化。

定义见 `docs/DATA-DICTIONARY.md`，模块和测试映射见 `docs/DEPTH.md`。样例位于 `sample_data/`。SQLite存放于命名卷，重启保留批次。确认不再需要历史记录时，可用 `docker compose down -v` 重建数据。

## 已知范围

不覆盖外部登记系统同步、跨批次证书合并；演示范围为单个上传文件完整重放。

序列号最多40位，持仓和注销区间按签发宽度保留前导零。
