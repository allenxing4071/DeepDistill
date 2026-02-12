"""
DeepDistill 入口文件
启动 FastAPI 服务（Web UI + API）。

启动方式：
  uvicorn deepdistill.api:app --host 0.0.0.0 --port 8006
  或
  python -m deepdistill.main
"""

from __future__ import annotations

import logging
import sys

import uvicorn

from .config import cfg


def setup_logging() -> None:
    """配置日志格式"""
    logging.basicConfig(
        level=getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger("deepdistill")
    logger.info("=" * 50)
    logger.info("  DeepDistill v0.1.0 — 多源内容深度蒸馏引擎")
    logger.info("=" * 50)

    # 确保目录存在
    cfg.ensure_dirs()

    # 打印配置警告
    for w in cfg.validate():
        logger.warning(f"⚠️  {w}")

    logger.info(f"设备: {cfg.get_device()}")
    logger.info(f"API 端口: {cfg.API_PORT}")

    uvicorn.run(
        "deepdistill.api:app",
        host="0.0.0.0",
        port=cfg.API_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
