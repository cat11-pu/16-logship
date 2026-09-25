"""ship.py：日志复制（增量同步、位点落盘、幂等投递、崩溃恢复）。"""
from __future__ import annotations

import json
import os


class Ship:
    def __init__(self, snapshot_every: int = 4, wal_path: str | None = None):
        self.snapshot_every = snapshot_every
        self.wal_path = wal_path
        self.log = []
        self.applied = {}
        self.offset = 0
        self.snapshot_offset = 0
        self.snapshot = {}
        self.appends = 0
        self.duplicates = 0
        self.catches = 0

    def _wal_write(self, record: dict) -> None:
        if not self.wal_path:
            return
        with open(self.wal_path, "a", encoding="utf-8") as wal:
            wal.write(json.dumps(record, ensure_ascii=False) + "\n")
            wal.flush()
            os.fsync(wal.fileno())

    def append(self, key: str, value: str, offset: int | None = None) -> dict:
        # 重复投递同一位点：不重复应用，计入 duplicates。
        if offset is not None and 1 <= offset <= self.appends:
            self.duplicates += 1
            return {"offset": offset}
        self.appends += 1
        new_offset = self.appends
        if new_offset % self.snapshot_every == 0:
            # 快照覆盖位点 < snapshot_offset，增量从 snapshot_offset 起，边界不重叠。
            self.snapshot = dict(self.applied)
            self.snapshot_offset = new_offset
            self._wal_write({"op": "snapshot", "offset": new_offset, "state": self.snapshot})
        self.log.append((new_offset, key, value))
        self.applied[key] = value
        self._wal_write({"op": "append", "offset": new_offset, "key": key, "value": value})
        return {"offset": new_offset}

    def sync(self, offset: int) -> dict:
        """只返回位点之后的条目；位点超过日志长度时返回空，不报错。"""
        offset = max(0, offset)
        entries = [
            {"offset": item[0], "key": item[1], "value": item[2]}
            for item in self.log if item[0] > offset
        ]
        if 0 < offset < self.appends:
            self.catches += len(entries)
        self.offset = max(self.offset, self.appends)
        return {
            "entries": entries,
            "offset": self.offset,
            "snapshot_offset": self.snapshot_offset,
            "snapshot": dict(self.snapshot),
            "duplicates": self.duplicates,
            "catches": self.catches,
        }

    def recover(self) -> dict:
        """重放 WAL 恢复；尾部半条记录忽略；offset 单调不回退。"""
        if not self.wal_path or not os.path.exists(self.wal_path):
            return {"offset": self.offset, "appends": self.appends,
                    "snapshot_offset": self.snapshot_offset, "replayed": 0, "monotonic": True}
        previous_offset = self.offset
        previous_appends = self.appends
        snapshot_offset = 0
        snapshot = {}
        append_records = []
        with open(self.wal_path, "r", encoding="utf-8") as wal:
            for line in wal:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue  # 崩溃留下的尾部半条记录：忽略
                if record.get("op") == "snapshot":
                    snapshot_offset = int(record.get("offset", 0))
                    snapshot = dict(record.get("state") or {})
                elif record.get("op") == "append":
                    append_records.append(record)
        applied = dict(snapshot)
        log = []
        replayed = 0
        last_offset = snapshot_offset - 1
        high_water = 0
        for record in append_records:
            record_offset = int(record.get("offset", 0))
            high_water = max(high_water, record_offset)
            if record_offset < snapshot_offset:
                log.append((record_offset, record.get("key"), record.get("value")))
                continue
            if record_offset <= last_offset:
                self.duplicates += 1
                continue
            log.append((record_offset, record.get("key"), record.get("value")))
            applied[record.get("key")] = record.get("value")
            last_offset = record_offset
            replayed += 1
        self.log = log
        self.applied = applied
        self.snapshot = snapshot
        self.snapshot_offset = snapshot_offset
        self.appends = high_water
        self.offset = max(previous_offset, high_water)
        monotonic = self.appends >= previous_appends and self.offset >= previous_offset
        return {"offset": self.offset, "appends": self.appends,
                "snapshot_offset": self.snapshot_offset, "replayed": replayed,
                "monotonic": monotonic}

    def state(self) -> dict:
        return {"offset": self.offset, "snapshot_offset": self.snapshot_offset,
                "appends": self.appends, "duplicates": self.duplicates, "catches": self.catches}
