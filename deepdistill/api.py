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
  自动导出到 Google Drive（可选）
       ↓
  API 返回 / SSE 实时推送进度

并发与资源保护：
  - Semaphore 限制同时处理的管线任务数（默认 3）
  - 文件上传大小限制（单文件 2GB，批量总大小 10GB）
  - 任务字典自动清理（24h 过期 + 最多 1000 条）
  - API 返回时截断大文本，完整文本仅在导出时使用
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Query, HTTPException, Body, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import cfg

logger = logging.getLogger("deepdistill.api")

# ── 并发控制 ──
# 限制同时执行的管线任务数，防止 CPU/内存/GPU 资源耗尽
MAX_CONCURRENT_PIPELINES = int(os.getenv("DEEPDISTILL_MAX_CONCURRENT", "3"))
_pipeline_semaphore = asyncio.Semaphore(MAX_CONCURRENT_PIPELINES)

# ── 文件大小限制 ──
MAX_SINGLE_FILE_SIZE = int(os.getenv("DEEPDISTILL_MAX_FILE_SIZE", str(2 * 1024 * 1024 * 1024)))  # 2GB
MAX_BATCH_TOTAL_SIZE = int(os.getenv("DEEPDISTILL_MAX_BATCH_SIZE", str(10 * 1024 * 1024 * 1024)))  # 10GB

# ── 任务管理 ──
MAX_TASKS = int(os.getenv("DEEPDISTILL_MAX_TASKS", "1000"))
TASK_EXPIRE_HOURS = int(os.getenv("DEEPDISTILL_TASK_EXPIRE_HOURS", "24"))

# ── API 返回时文本截断阈值（完整文本保留在内存中，仅 API 响应时截断） ──
API_TEXT_TRUNCATE = int(os.getenv("DEEPDISTILL_API_TEXT_TRUNCATE", "5000"))

# ── 任务存储（内存，后续可换 Redis） ──
_tasks: dict[str, dict] = {}


def _cleanup_old_tasks():
    """清理过期任务，防止内存无限增长"""
    if len(_tasks) <= MAX_TASKS:
        return

    now = datetime.now(timezone.utc)
    expired_ids = []
    for tid, task in _tasks.items():
        try:
            created = datetime.fromisoformat(task["created_at"])
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_hours = (now - created).total_seconds() / 3600
            # 已完成/失败的任务超过 TASK_EXPIRE_HOURS 后清理
            if task["status"] in ("completed", "failed") and age_hours > TASK_EXPIRE_HOURS:
                expired_ids.append(tid)
        except Exception:
            pass

    for tid in expired_ids:
        del _tasks[tid]
        logger.info(f"清理过期任务: {tid}")

    # 如果清理后仍超限，强制删除最旧的已完成任务
    if len(_tasks) > MAX_TASKS:
        completed = [(tid, t) for tid, t in _tasks.items() if t["status"] in ("completed", "failed")]
        completed.sort(key=lambda x: x[1].get("created_at", ""))
        remove_count = len(_tasks) - MAX_TASKS
        for tid, _ in completed[:remove_count]:
            del _tasks[tid]
            logger.info(f"强制清理任务（超限）: {tid}")


def _task_to_api_response(task: dict) -> dict:
    """将内部任务数据转为 API 响应（截断大文本字段，保护内存和带宽）"""
    resp = dict(task)
    result = resp.get("result")
    if result and isinstance(result, dict):
        result = dict(result)
        # API 返回时截断大文本，完整文本仅在导出时通过内部 _tasks 访问
        for key in ("raw_text", "extracted_text"):
            text = result.get(key, "")
            if isinstance(text, str) and len(text) > API_TEXT_TRUNCATE:
                result[key] = text[:API_TEXT_TRUNCATE] + f"\n\n... (已截断，完整文本 {len(text)} 字符，请通过导出获取)"
        resp["result"] = result
    return resp


# ── 处理选项模型 ──
class ProcessOptions(BaseModel):
    intent: str = "content"        # "content" | "style"
    export_format: str = "doc"     # "doc" | "word" | "excel"
    doc_type: str = "doc"          # "doc" | "skill" | "both"
    category: str | None = None    # 分类文件夹
    auto_export: bool = True       # 处理完自动导出


def _parse_options(options_str: str | None) -> dict:
    """从 form field 解析处理选项"""
    if not options_str:
        return ProcessOptions().model_dump()
    try:
        data = json.loads(options_str)
        return ProcessOptions(**data).model_dump()
    except Exception:
        return ProcessOptions().model_dump()


async def _periodic_cleanup():
    """后台定期清理过期任务和临时文件"""
    while True:
        await asyncio.sleep(600)  # 每 10 分钟检查一次
        try:
            _cleanup_old_tasks()
            # 清理超过 24 小时的上传临时文件
            upload_dir = cfg.DATA_DIR / "uploads"
            if upload_dir.exists():
                now = datetime.now(timezone.utc).timestamp()
                for f in upload_dir.iterdir():
                    if f.is_file():
                        age_hours = (now - f.stat().st_mtime) / 3600
                        if age_hours > TASK_EXPIRE_HOURS:
                            f.unlink(missing_ok=True)
                            logger.debug(f"清理临时文件: {f.name}")
        except Exception as e:
            logger.warning(f"定期清理异常: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    cfg.ensure_dirs()
    logger.info("DeepDistill API 启动")
    logger.info(f"设备: {cfg.get_device()}")
    logger.info(f"并发限制: {MAX_CONCURRENT_PIPELINES} 个管线任务")
    logger.info(f"文件大小限制: 单文件 {MAX_SINGLE_FILE_SIZE // (1024*1024)}MB, 批量 {MAX_BATCH_TOTAL_SIZE // (1024*1024)}MB")
    for w in cfg.validate():
        logger.warning(f"⚠️  {w}")

    # 启动后台清理任务
    cleanup_task = asyncio.create_task(_periodic_cleanup())

    yield

    cleanup_task.cancel()
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


# ── Prompt 模板与监控（与 KKline 一致） ──
@app.get("/api/prompts")
async def list_prompts():
    """列出所有 prompt 模板及其调用统计（含汇总）"""
    from .ai_analysis.prompt_stats import prompt_stats
    return {
        "prompts": prompt_stats.snapshot(),
        "summary": prompt_stats.summary(),
    }


@app.get("/api/prompts/stats/summary")
async def prompts_summary():
    """Prompt 调用全局汇总"""
    from .ai_analysis.prompt_stats import prompt_stats
    return prompt_stats.summary()


@app.get("/api/prompts/{name}")
async def get_prompt(name: str):
    """获取单个 prompt 详情（含模板内容、调用记录、统计）"""
    from .ai_analysis.extractor import get_prompt_content
    from .ai_analysis.prompt_stats import prompt_stats

    name_clean = name.strip().removesuffix(".txt") if name.endswith(".txt") else name.strip()
    content = get_prompt_content(name_clean)
    detail = prompt_stats.get_detail(name_clean)
    if content is None and detail.get("file_lines", 0) == 0 and detail.get("total_calls", 0) == 0:
        raise HTTPException(status_code=404, detail=f"Prompt 模板 '{name_clean}' 不存在")
    return detail


# ── 实时状态检测（各模型/服务连通性） ──
@app.get("/api/status")
async def get_status():
    """检测所有模型和服务的实时状态，返回每个组件的连通性"""
    import httpx
    import os

    results: dict[str, dict] = {}

    # 1. Ollama 本地模型
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("http://host.docker.internal:11434/api/tags")
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                target = cfg.AI_MODEL
                has_target = any(target in m for m in models)
                results["ollama"] = {
                    "status": "running" if has_target else "ready",
                    "detail": f"{len(models)} 个模型已加载" if models else "无模型",
                    "models": models[:10],
                    "target_model": target,
                    "target_loaded": has_target,
                }
            else:
                results["ollama"] = {"status": "error", "detail": f"HTTP {r.status_code}"}
    except Exception as e:
        results["ollama"] = {"status": "offline", "detail": str(e)[:80]}

    # 2. DeepSeek API
    if cfg.DEEPSEEK_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(
                    "https://api.deepseek.com/models",
                    headers={"Authorization": f"Bearer {cfg.DEEPSEEK_API_KEY}"},
                )
                if r.status_code == 200:
                    results["deepseek"] = {"status": "ready", "detail": "API 连接正常", "model": "deepseek-chat"}
                else:
                    results["deepseek"] = {"status": "error", "detail": f"HTTP {r.status_code}"}
        except Exception as e:
            results["deepseek"] = {"status": "error", "detail": str(e)[:80]}
    else:
        results["deepseek"] = {"status": "unconfigured", "detail": "未配置 API Key"}

    # 3. Qwen API
    if cfg.QWEN_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(
                    "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
                    headers={"Authorization": f"Bearer {cfg.QWEN_API_KEY}"},
                )
                if r.status_code == 200:
                    results["qwen"] = {"status": "ready", "detail": "API 连接正常", "model": "qwen-max"}
                else:
                    results["qwen"] = {"status": "error", "detail": f"HTTP {r.status_code}"}
        except Exception as e:
            results["qwen"] = {"status": "error", "detail": str(e)[:80]}
    else:
        results["qwen"] = {"status": "unconfigured", "detail": "未配置 API Key"}

    # 4. Whisper ASR
    results["whisper"] = {
        "status": "ready",
        "detail": f"模型: {cfg.ASR_MODEL}",
        "model": cfg.ASR_MODEL,
        "device": cfg.get_device(),
    }

    # 5. OCR
    results["ocr"] = {
        "status": "ready",
        "detail": f"引擎: {cfg.OCR_ENGINE}",
        "engine": cfg.OCR_ENGINE,
        "languages": cfg.OCR_LANGUAGES,
    }

    # 6. Google Drive
    if cfg.GOOGLE_DOCS_ENABLED:
        has_cred = cfg.GOOGLE_DOCS_CREDENTIALS_PATH.exists()
        has_token = cfg.GOOGLE_DOCS_TOKEN_PATH.exists()
        if has_cred and has_token:
            results["google_drive"] = {"status": "ready", "detail": f"文件夹: {cfg.GOOGLE_DOCS_FOLDER_NAME}"}
        elif has_cred:
            results["google_drive"] = {"status": "error", "detail": "需要重新授权"}
        else:
            results["google_drive"] = {"status": "unconfigured", "detail": "未配置凭据"}
    else:
        results["google_drive"] = {"status": "disabled", "detail": "未启用"}

    # 7. Stable Diffusion（图片生成 — 设计文档中的融合输出层组件）
    sd_url = os.getenv("SD_WEBUI_URL", "http://host.docker.internal:7860")
    sd_detail = "未启动"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{sd_url}/sdapi/v1/sd-models")
            if r.status_code == 200:
                results["stable_diffusion"] = {"status": "running", "detail": "WebUI 运行中"}
            else:
                results["stable_diffusion"] = {"status": "error", "detail": f"HTTP {r.status_code}"}
    except Exception:
        # 若存在 sd.result（宿主机 watcher 写入的失败原因），展示给用户
        _sd_result_file = _SERVICE_CTL_DIR / "sd.result"
        if _sd_result_file.exists():
            try:
                raw = _sd_result_file.read_text(encoding="utf-8").strip()
                data = json.loads(raw) if raw else {}
                if not data.get("ok") and data.get("msg"):
                    sd_detail = data.get("msg", sd_detail)
            except Exception:
                pass
        else:
            # 无 result 文件时提示：可能宿主机未运行 service-watcher.sh
            sd_detail = "未启动（需在宿主机运行 scripts/service-watcher.sh 后点击启动）"
        results["stable_diffusion"] = {"status": "offline", "detail": sd_detail}

    # 8. 活跃任务数
    active = sum(1 for t in _tasks.values() if t["status"] in ("queued", "processing"))
    results["pipeline"] = {
        "status": "running" if active > 0 else "ready",
        "detail": f"{active} 个任务处理中" if active else "空闲",
        "active_tasks": active,
        "total_tasks": len(_tasks),
    }

    return results


# ── 服务启停控制（通过信号文件与宿主机 watcher 交互） ──

# 可控服务清单：服务名 → 信号文件前缀
_CONTROLLABLE_SERVICES = {
    "ollama": "ollama",
    "stable_diffusion": "sd",
}

# 信号文件目录（挂载到宿主机的 data/.service-ctl/）
_SERVICE_CTL_DIR = Path(os.getenv("SERVICE_CTL_DIR", "/app/data/.service-ctl"))


@app.post("/api/services/{service_name}/{action}")
async def control_service(service_name: str, action: str):
    """
    启停宿主机上的本地服务。
    通过写入信号文件，由宿主机上的 service-watcher.sh 执行实际操作。

    - service_name: ollama | stable_diffusion
    - action: start | stop
    """
    if service_name not in _CONTROLLABLE_SERVICES:
        raise HTTPException(400, f"不支持的服务: {service_name}，可选: {list(_CONTROLLABLE_SERVICES.keys())}")
    if action not in ("start", "stop"):
        raise HTTPException(400, f"不支持的操作: {action}，可选: start, stop")

    prefix = _CONTROLLABLE_SERVICES[service_name]
    _SERVICE_CTL_DIR.mkdir(parents=True, exist_ok=True)

    prefix = _CONTROLLABLE_SERVICES[service_name]
    _SERVICE_CTL_DIR.mkdir(parents=True, exist_ok=True)

    # 清除旧的结果文件
    result_file = _SERVICE_CTL_DIR / f"{prefix}.result"
    try:
        result_file.unlink(missing_ok=True)
    except Exception:
        pass

    # 写入信号文件（宿主机 watcher 检测到后执行操作）
    signal_file = _SERVICE_CTL_DIR / f"{prefix}.{action}"
    signal_file.write_text(f"{action} at {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"服务控制: {service_name} → {action}（信号文件: {signal_file}）")

    # 立即返回，前端通过轮询 /api/status 来获取最新状态
    return JSONResponse({
        "service": service_name,
        "action": action,
        "ok": True,
        "msg": f"{'启动' if action == 'start' else '停止'}指令已发送",
    })


# ── 文件上传处理（支持处理选项） ──
@app.post("/api/process")
async def process_file(
    file: UploadFile = File(...),
    options: str | None = Form(None),
):
    """上传文件并启动处理管线，支持处理选项"""
    # 清理过期任务
    _cleanup_old_tasks()

    task_id = str(uuid.uuid4())[:8]
    opts = _parse_options(options)

    # 保存上传文件到临时目录（流式写入，检查大小）
    upload_dir = cfg.DATA_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{task_id}_{file.filename}"

    total_size = 0
    with open(file_path, "wb") as f:
        while chunk := await file.read(8 * 1024 * 1024):  # 8MB 分块读取
            total_size += len(chunk)
            if total_size > MAX_SINGLE_FILE_SIZE:
                f.close()
                file_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"文件过大（{total_size // (1024*1024)}MB），单文件限制 {MAX_SINGLE_FILE_SIZE // (1024*1024)}MB"
                )
            f.write(chunk)

    # 创建任务记录
    _tasks[task_id] = {
        "id": task_id,
        "filename": file.filename,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "progress": 0,
        "step_label": "排队等待",
        "result": None,
        "error": None,
        "options": opts,
        "export_result": None,
    }

    # 异步启动处理（受并发限制）
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
        "step_label": "排队等待",
        "result": None,
        "error": None,
        "options": ProcessOptions().model_dump(),
        "export_result": None,
    }

    asyncio.create_task(_run_pipeline(task_id, file_path))

    return {"task_id": task_id, "status": "queued", "filename": file_path.name}


# ── URL 网页抓取处理（支持处理选项） ──
class UrlRequest(BaseModel):
    url: str
    options: ProcessOptions | None = None


@app.post("/api/process/url")
async def process_url(body: UrlRequest):
    """智能处理 URL：自动检测视频（1800+ 平台）或网页内容"""
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL 不能为空")

    task_id = str(uuid.uuid4())[:8]
    opts = body.options.model_dump() if body.options else ProcessOptions().model_dump()

    # 从 URL 提取显示名称
    from urllib.parse import urlparse
    parsed = urlparse(url)
    display_name = parsed.netloc + (parsed.path if parsed.path != "/" else "")
    if len(display_name) > 60:
        display_name = display_name[:57] + "..."

    _tasks[task_id] = {
        "id": task_id,
        "filename": display_name,
        "source_url": url,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "progress": 0,
        "step_label": "排队等待（智能识别中）",
        "result": None,
        "error": None,
        "options": opts,
        "export_result": None,
    }

    asyncio.create_task(_run_url_pipeline(task_id, url))

    return {"task_id": task_id, "status": "queued", "filename": display_name, "url": url}


async def _run_url_pipeline(task_id: str, url: str):
    """
    智能 URL 处理管线：
    1. 先用 yt-dlp 探测 URL 是否包含视频（支持 1800+ 平台）
    2. 有视频 → 下载视频 → ASR 语音转文字 → AI 提炼
    3. 无视频 → httpx 抓取网页 → 文本提取 → AI 提炼
    """
    task = _tasks[task_id]
    opts = task.get("options", {})

    # 等待并发槽位
    active = sum(1 for t in _tasks.values() if t["status"] == "processing")
    if active >= MAX_CONCURRENT_PIPELINES:
        task["step_label"] = f"排队中（前方 {active} 个任务）"

    file_path = None
    is_video = False
    async with _pipeline_semaphore:
        try:
            task["status"] = "processing"
            task["progress"] = 2
            task["step_label"] = "正在智能识别内容类型"
            upload_dir = cfg.DATA_DIR / "uploads"
            loop = asyncio.get_event_loop()

            # ── Step 1: 智能探测 — yt-dlp 检测是否为视频 ──
            from .ingestion.video_downloader import (
                probe_video, download_video, _get_platform_hint, VideoCookieRequired,
            )
            try:
                video_info = await loop.run_in_executor(None, probe_video, url)
            except VideoCookieRequired as e:
                # 确认是视频平台但需要 Cookie → 直接报错，不降级为网页
                task["status"] = "failed"
                task["error"] = str(e)
                task["step_label"] = f"{e.platform} 需要 Cookie"
                logger.warning(f"URL 任务 {task_id}: {e}")
                return

            if video_info:
                # ── 视频路径：yt-dlp 下载 → ASR 转文字 ──
                is_video = True
                platform = _get_platform_hint(url)
                title = video_info.get("title", "")
                duration = video_info.get("duration", 0)
                task["filename"] = f"[{platform}] {title[:40]}" if title else task["filename"]
                task["progress"] = 5
                task["step_label"] = f"检测到{platform}视频（{duration}s），正在下载"

                file_path = await loop.run_in_executor(None, download_video, url, upload_dir)

                task["progress"] = 15
                task["step_label"] = f"视频下载完成，开始语音转文字"
            else:
                # ── 网页路径：httpx 抓取 HTML ──
                task["progress"] = 5
                task["step_label"] = "未检测到视频，正在抓取网页"
                from .ingestion.web_fetcher import fetch_url, fetch_url_with_browser
                from .processing import extract_text
                from .ai_analysis.extractor import _is_likely_verification_or_empty_page

                file_path = await loop.run_in_executor(None, fetch_url, url, upload_dir)

                # 若得到的是验证页/无正文，用无头浏览器重新抓取真实渲染内容后再分析
                text = extract_text(file_path, "webpage")
                if _is_likely_verification_or_empty_page(text):
                    try:
                        task["step_label"] = "检测到验证页，使用浏览器重新抓取页面内容"
                        file_path = await loop.run_in_executor(
                            None, fetch_url_with_browser, url, upload_dir
                        )
                        logger.info(f"URL 任务 {task_id}: 浏览器抓取完成，继续分析")
                    except Exception as e:
                        logger.warning(f"URL 任务 {task_id}: 浏览器抓取失败，将使用原始结果: {e}")

                task["progress"] = 10
                task["step_label"] = "网页抓取完成，开始分析"

            # ── Step 2: 执行管线 ──
            def _on_progress(pct: int, label: str):
                base = 15 if is_video else 10
                mapped = int(base + (pct - 5) * (95 - base) / 95)
                task["progress"] = min(mapped, 95)
                task["step_label"] = label

            pipeline_timeout = int(os.getenv("DEEPDISTILL_PIPELINE_TIMEOUT", "3600"))

            from .pipeline import Pipeline
            pipeline = Pipeline(
                output_dir=cfg.OUTPUT_DIR,
                intent=opts.get("intent", "content"),
                doc_type=opts.get("doc_type", "doc"),
                progress_callback=_on_progress,
            )

            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, pipeline.process, file_path),
                    timeout=pipeline_timeout,
                )
            except asyncio.TimeoutError:
                task["status"] = "failed"
                task["error"] = f"处理超时（>{pipeline_timeout}s），内容可能过大"
                task["step_label"] = "处理超时"
                logger.error(f"URL 任务 {task_id} 处理超时（{pipeline_timeout}s）")
                return

            if result:
                task["status"] = "completed"
                task["progress"] = 100
                task["step_label"] = "处理完成"
                task["result"] = result.to_dict()

                # ── Step 3: 自动导出 ──
                if opts.get("auto_export") and cfg.GOOGLE_DOCS_ENABLED:
                    task["step_label"] = "正在导出到 Google Drive"
                    await _auto_export(task_id)
                    task["step_label"] = "导出完成"
            else:
                task["status"] = "failed"
                task["error"] = "不支持的格式或处理失败"

        except Exception as e:
            logger.error(f"URL 任务 {task_id} 失败: {e}", exc_info=True)
            task["status"] = "failed"
            task["error"] = str(e)
        finally:
            # 清理下载的临时文件
            try:
                if file_path and file_path.exists() and "uploads" in str(file_path):
                    file_path.unlink(missing_ok=True)
            except Exception:
                pass


# ── 批量文件上传处理（支持处理选项） ──
@app.post("/api/process/batch")
async def process_batch(
    files: list[UploadFile] = File(...),
    options: str | None = Form(None),
):
    """批量上传文件并启动处理管线，每个文件创建独立任务"""
    if not files:
        raise HTTPException(status_code=400, detail="未提供文件")

    if len(files) > 20:
        raise HTTPException(status_code=400, detail="单次最多上传 20 个文件")

    # 清理过期任务
    _cleanup_old_tasks()

    opts = _parse_options(options)
    upload_dir = cfg.DATA_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    task_ids = []
    batch_total_size = 0

    for file in files:
        task_id = str(uuid.uuid4())[:8]
        file_path = upload_dir / f"{task_id}_{file.filename}"

        # 流式写入，检查单文件和批量总大小
        file_size = 0
        with open(file_path, "wb") as f:
            while chunk := await file.read(8 * 1024 * 1024):  # 8MB 分块
                file_size += len(chunk)
                batch_total_size += len(chunk)
                if file_size > MAX_SINGLE_FILE_SIZE:
                    f.close()
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件 {file.filename} 过大（{file_size // (1024*1024)}MB），单文件限制 {MAX_SINGLE_FILE_SIZE // (1024*1024)}MB"
                    )
                if batch_total_size > MAX_BATCH_TOTAL_SIZE:
                    f.close()
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"批量总大小超限（{batch_total_size // (1024*1024)}MB），限制 {MAX_BATCH_TOTAL_SIZE // (1024*1024)}MB"
                    )
                f.write(chunk)

        _tasks[task_id] = {
            "id": task_id,
            "filename": file.filename,
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "progress": 0,
            "step_label": "排队等待",
            "result": None,
            "error": None,
            "options": opts,
            "export_result": None,
        }

        asyncio.create_task(_run_pipeline(task_id, file_path))
        task_ids.append({"task_id": task_id, "filename": file.filename})

    return {"count": len(task_ids), "tasks": task_ids}


# ── 查询任务状态 ──
@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_to_api_response(_tasks[task_id])


# ── 任务列表 ──
@app.get("/api/tasks")
async def list_tasks(limit: int = Query(20, ge=1, le=100)):
    tasks = sorted(_tasks.values(), key=lambda t: t["created_at"], reverse=True)
    return [_task_to_api_response(t) for t in tasks[:limit]]


# ── Google Docs 分类列表（动态读取 Drive 目录 + 预定义合并） ──
@app.get("/api/export/categories")
async def list_export_categories():
    """
    列出所有可用的导出分类（预定义 + Google Drive 已有的自定义目录）。
    前端启动时调用此接口，确保分类下拉列表与 Drive 实际目录同步。
    """
    try:
        from .export.google_docs import get_exporter
        loop = asyncio.get_event_loop()
        exporter = get_exporter()
        categories = await loop.run_in_executor(None, exporter.list_categories)
        return categories
    except Exception as e:
        # Drive 不可用时 fallback 到预定义列表
        logger.warning(f"读取 Drive 分类失败，使用预定义列表: {e}")
        from .export.google_docs import GoogleDocsExporter
        return [
            {"name": name, "doc_count": 0, "folder_url": None, "is_custom": False}
            for name in GoogleDocsExporter.CATEGORIES
        ]


# ── 手动导出到 Google Docs（支持分类 + 格式选择） ──
class ExportRequest(BaseModel):
    category: str | None = None
    format: str | None = "doc"         # "doc" | "skill" | "both"
    export_format: str | None = "doc"  # "doc" | "word" | "excel"


@app.post("/api/tasks/{task_id}/export/google-docs")
async def export_to_google_docs(task_id: str, body: ExportRequest | None = None):
    """
    将任务结果导出到 Google Docs。
    - category: 分类子文件夹
    - format: "doc"(普通文档) / "skill"(Skill文档) / "both"(两者都导出)
    - export_format: "doc"(Google Doc) / "word"(Word) / "excel"(Excel)
    """
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = _tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成，无法导出")

    if not cfg.GOOGLE_DOCS_ENABLED:
        raise HTTPException(status_code=400, detail="Google Docs 导出未启用")

    category = body.category if body else None
    fmt = (body.format if body and body.format else "doc")
    export_format = (body.export_format if body and body.export_format else "doc")

    try:
        from .export.google_docs import get_exporter

        loop = asyncio.get_event_loop()
        exporter = get_exporter()
        result = await loop.run_in_executor(
            None, lambda: exporter.export_task_result(
                task, category=category, fmt=fmt, export_format=export_format
            )
        )
        # 保存导出结果到任务记录
        task["export_result"] = result
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"导出到 Google Docs 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


# ── 自动导出（管线完成后调用） ──
async def _auto_export(task_id: str):
    """处理完成后自动导出到 Google Drive"""
    task = _tasks[task_id]
    opts = task.get("options", {})

    try:
        from .export.google_docs import get_exporter

        loop = asyncio.get_event_loop()
        exporter = get_exporter()
        result = await loop.run_in_executor(
            None, lambda: exporter.export_task_result(
                task,
                category=opts.get("category"),
                fmt=opts.get("doc_type", "doc"),
                export_format=opts.get("export_format", "doc"),
            )
        )
        task["export_result"] = result
        logger.info(f"任务 {task_id} 自动导出成功")
    except Exception as e:
        logger.error(f"任务 {task_id} 自动导出失败: {e}", exc_info=True)
        task["export_result"] = {"error": str(e)}


# ── 管线执行（异步，受并发限制） ──
async def _run_pipeline(task_id: str, file_path: Path):
    """在后台执行处理管线，通过 Semaphore 限制并发数，进度回调实时更新"""
    task = _tasks[task_id]
    opts = task.get("options", {})

    # 等待并发槽位
    active = sum(1 for t in _tasks.values() if t["status"] == "processing")
    if active >= MAX_CONCURRENT_PIPELINES:
        task["step_label"] = f"排队中（前方 {active} 个任务）"

    async with _pipeline_semaphore:
        try:
            task["status"] = "processing"
            task["progress"] = 5
            task["step_label"] = "准备处理"

            def _on_progress(pct: int, label: str):
                """Pipeline 进度回调 — 在线程池中被调用，直接写 task dict（线程安全：GIL）"""
                task["progress"] = pct
                task["step_label"] = label

            from .pipeline import Pipeline
            pipeline = Pipeline(
                output_dir=cfg.OUTPUT_DIR,
                intent=opts.get("intent", "content"),
                doc_type=opts.get("doc_type", "doc"),
                progress_callback=_on_progress,
            )

            # 在线程池中执行（避免阻塞事件循环）
            pipeline_timeout = int(os.getenv("DEEPDISTILL_PIPELINE_TIMEOUT", "3600"))

            loop = asyncio.get_event_loop()
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, pipeline.process, file_path),
                    timeout=pipeline_timeout,
                )
            except asyncio.TimeoutError:
                task["status"] = "failed"
                task["error"] = f"处理超时（>{pipeline_timeout}s），文件可能过大"
                task["step_label"] = "处理超时"
                logger.error(f"任务 {task_id} 处理超时（{pipeline_timeout}s）")
                return

            if result:
                task["status"] = "completed"
                task["progress"] = 100
                task["step_label"] = "处理完成"
                task["result"] = result.to_dict()

                # 自动导出
                if opts.get("auto_export") and cfg.GOOGLE_DOCS_ENABLED:
                    task["step_label"] = "正在导出到 Google Drive"
                    await _auto_export(task_id)
                    task["step_label"] = "导出完成"
            else:
                task["status"] = "failed"
                task["error"] = "不支持的格式或处理失败"

        except Exception as e:
            logger.error(f"任务 {task_id} 失败: {e}", exc_info=True)
            task["status"] = "failed"
            task["error"] = str(e)
        finally:
            # 清理上传的临时文件（处理完成后不再需要）
            try:
                if file_path.exists() and "uploads" in str(file_path):
                    file_path.unlink(missing_ok=True)
            except Exception:
                pass
