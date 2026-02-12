"""
DeepDistill API 层
提供健康检查、文件处理、任务状态、SSE 进度流等端点。

数据流架构：
  文件上传 / 路径指定
       ↓
  Pipeline（6 层管线处理）
       ↓
  结构化结果 (JSON / Markdown)
       ↓
  API 返回 / SSE 实时推送进度
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import cfg

logger = logging.getLogger("deepdistill.api")

# ── 任务存储（内存，后续可换 Redis） ──
_tasks: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    cfg.ensure_dirs()
    logger.info("DeepDistill API 启动")
    logger.info(f"设备: {cfg.get_device()}")
    for w in cfg.validate():
        logger.warning(f"⚠️  {w}")
    yield
    logger.info("DeepDistill API 关闭")


app = FastAPI(
    title="DeepDistill API",
    description="多源内容深度蒸馏引擎 — 从视频/音频/图片/文档中提炼结构化知识",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — 允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 健康检查 ──
@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0", "device": cfg.get_device()}


# ── 系统配置 ──
@app.get("/api/config")
async def get_config():
    return cfg.to_dict()


# ── 文件上传处理 ──
@app.post("/api/process")
async def process_file(file: UploadFile = File(...)):
    """上传文件并启动处理管线"""
    # 生成任务 ID
    task_id = str(uuid.uuid4())[:8]

    # 保存上传文件到临时目录
    upload_dir = cfg.DATA_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{task_id}_{file.filename}"

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 创建任务记录
    _tasks[task_id] = {
        "id": task_id,
        "filename": file.filename,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "progress": 0,
        "result": None,
        "error": None,
    }

    # 异步启动处理
    asyncio.create_task(_run_pipeline(task_id, file_path))

    return {"task_id": task_id, "status": "queued", "filename": file.filename}


# ── 通过路径处理（本地文件） ──
@app.post("/api/process/local")
async def process_local(path: str = Query(..., description="本地文件路径")):
    """处理本地文件（不上传）"""
    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")

    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {
        "id": task_id,
        "filename": file_path.name,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "progress": 0,
        "result": None,
        "error": None,
    }

    asyncio.create_task(_run_pipeline(task_id, file_path))

    return {"task_id": task_id, "status": "queued", "filename": file_path.name}


# ── 查询任务状态 ──
@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _tasks[task_id]


# ── 任务列表 ──
@app.get("/api/tasks")
async def list_tasks(limit: int = Query(20, ge=1, le=100)):
    tasks = sorted(_tasks.values(), key=lambda t: t["created_at"], reverse=True)
    return tasks[:limit]


# ── 管线执行（异步） ──
async def _run_pipeline(task_id: str, file_path: Path):
    """在后台执行处理管线"""
    task = _tasks[task_id]
    try:
        task["status"] = "processing"
        task["progress"] = 10

        from .pipeline import Pipeline
        pipeline = Pipeline(output_dir=cfg.OUTPUT_DIR)

        # 在线程池中执行（避免阻塞事件循环）
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, pipeline.process, file_path)

        if result:
            task["status"] = "completed"
            task["progress"] = 100
            task["result"] = result.to_dict()
        else:
            task["status"] = "failed"
            task["error"] = "不支持的格式或处理失败"

    except Exception as e:
        logger.error(f"任务 {task_id} 失败: {e}", exc_info=True)
        task["status"] = "failed"
        task["error"] = str(e)
