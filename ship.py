"""ship.py：日志复制（基线：整段重发、offset 不落盘、重复不判）。"""
from __future__ import annotations


class Ship:
    def __init__(self, snapshot_every: int = 4):
        self.snapshot_every = snapshot_every
        self.log = []
        self.applied = {}
        self.offset = 0
        self.snapshot_offset = 0
        self.snapshot = {}
        self.appends = 0
        self.duplicates = 0
        self.catches = 0
        self.wal = []

    def append(self, key: str, value: str) -> dict:
        self.appends += 1
        self.log.append((self.appends, key, value))
        self.applied[key] = value
        self.wal.append(("append", key, value))
        if self.appends % self.snapshot_every == 0:
            self.snapshot = dict(self.applied)
            self.snapshot_offset = self.appends
        return {"offset": self.appends}

    def sync(self, offset: int) -> dict:
        """基线：整段重发，不看 offset、不判重复。"""
        entries = [{"offset": item[0], "key": item[1], "value": item[2]} for item in self.log]
        self.offset = self.appends
        return {"entries": entries, "offset": self.offset, "snapshot_offset": self.snapshot_offset}

    def recover(self) -> dict:
        raise NotImplementedError("重启恢复还没实现")

    def state(self) -> dict:
        return {"offset": self.offset, "snapshot_offset": self.snapshot_offset,
                "appends": self.appends, "duplicates": self.duplicates, "catches": self.catches}
