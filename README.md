# logship

纯 Python 标准库的本机服务。

## 起服务

    python3 server.py 8000

浏览器打开 http://127.0.0.1:8000/ 看结果。

日志与位点落盘在 `ship.wal`（JSON 行），重启后 `POST /recover` 重放恢复，
尾部半条记录会被忽略，offset 单调不回退。

## 接口

- `POST /append` `{"key": ..., "value": ..., "offset": 可选}` → `{"offset": N}`；
  重复投递同一位点幂等，不重复应用，计入 `duplicates`。
- `GET /sync?offset=N` → 位点之后的增量条目 + `snapshot`/`snapshot_offset`；
  位点超过日志长度返回空。
- `GET /state` → `offset`/`snapshot_offset`/`appends`/`duplicates`/`catches`。
- `POST /recover` → 重放恢复，返回 `offset`/`replayed`/`monotonic` 等。

## 测试

    python3 -m unittest discover -s tests -v

## 验收自检

    python3 check_http.py
