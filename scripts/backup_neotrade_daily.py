#!/usr/bin/env python3
"""NeoTrade3 每日增量备份：NEO 生产盘 -> DATA 备份盘（APFS）。

由 launchd（com.neotrade3.backup_daily）每天 04:47 以 .venv/bin/python 触发
（该二进制已有可移动磁盘访问授权；/bin/bash 在 launchd 上下文会被 TCC 拒绝）。

安全约束（fail-closed）：
1. NEO 未挂载或核心库缺失/异常小时，退出 EX_CONFIG(78)，绝不同步空目录
2. DATA 未挂载时跳过当日（exit 0，不算失败）
3. rsync --delete-after 使目标为源的镜像；配合护栏 1，不会把备份清成空
"""

import os
import subprocess
import sys
import time

SRC = "/Volumes/NEO/NeoTradeDB/var"
DST = "/Volumes/DATA/NeoTradeDB.daily/var"
DATA_MOUNT = "/Volumes/DATA"
LOG_DIR = os.path.expanduser("~/Library/Logs/NeoTrade3")
LOG = os.path.join(LOG_DIR, "neotrade3_backup_daily.log")
CORE_DB = os.path.join(SRC, "db", "stock_data.db")
MIN_CORE_BYTES = 1_000_000_000  # 1GB

EX_CONFIG = 78

RSYNC = [
    "/usr/bin/rsync", "-rlt", "--delete-after",
    "--exclude", "._*", "--exclude", ".DS_Store",
    "--exclude", "tmp/", "--exclude", "cache/",
    "--exclude", "*.db-shm", "--exclude", "*.db-wal",
    SRC + "/", DST + "/",
]


def log(msg: str) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def main() -> int:
    # 护栏 1：生产盘与核心库必须就位且体积正常
    if not os.path.isdir(SRC) or not os.path.isfile(CORE_DB):
        log("ABORT: NEO source missing or core db absent (fail-closed)")
        return EX_CONFIG
    core_size = os.path.getsize(CORE_DB)
    if core_size < MIN_CORE_BYTES:
        log(f"ABORT: core db size {core_size} < {MIN_CORE_BYTES} (fail-closed)")
        return EX_CONFIG

    # 护栏 2：备份盘不在位则跳过当日
    if not os.path.isdir(DATA_MOUNT):
        log("SKIP: DATA volume not mounted; will retry tomorrow")
        return 0
    os.makedirs(DST, exist_ok=True)

    log(f"START rsync NEO->DATA (core db {core_size} bytes)")
    with open(LOG, "a", encoding="utf-8") as fh:
        proc = subprocess.run(RSYNC, stdout=fh, stderr=fh, timeout=3500)
    if proc.returncode == 0:
        log("DONE rsync ok")
    else:
        log(f"FAIL rsync exit={proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
