"""
视频平台下载器（通用 + 抖音专用 fallback）

通用方案：yt-dlp 支持 1800+ 视频网站
抖音专用：yt-dlp Douyin 提取器有已知 bug（#9667），
         当 yt-dlp 失败时自动切换到抖音专用下载器：
         解析短链接 → 移动端 API 获取无水印视频 → 直接下载

Cookie 支持：
  将 Netscape 格式的 Cookie 文件放到 config/cookies/ 目录，
  按域名命名：douyin.txt / tiktok.txt / bilibili.txt 等。
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import requests as http_requests

logger = logging.getLogger("deepdistill.ingestion.video_downloader")

# yt-dlp 超时配置（秒）
PROBE_TIMEOUT = int(os.getenv("DEEPDISTILL_VIDEO_PROBE_TIMEOUT", "60"))
DOWNLOAD_TIMEOUT = int(os.getenv("DEEPDISTILL_VIDEO_DOWNLOAD_TIMEOUT", "600"))
MAX_VIDEO_SIZE = os.getenv("DEEPDISTILL_MAX_VIDEO_SIZE", "500M")

# Cookie 文件目录（Netscape 格式）
COOKIE_DIR = Path(os.getenv("DEEPDISTILL_COOKIE_DIR", "config/cookies"))

# 需要 Cookie 的关键词
_COOKIE_REQUIRED_KEYWORDS = ["cookie", "login", "sign in", "logged in"]

# 抖音域名标识
_DOUYIN_HOSTS = {"douyin.com", "iesdouyin.com"}


# ─── 工具函数 ───

def _get_platform_hint(url: str) -> str:
    """从 URL 推断平台名称（仅用于日志和显示）"""
    host = urlparse(url).netloc.lower()
    hints = {
        "douyin": "抖音", "tiktok": "TikTok", "bilibili": "B站", "b23.tv": "B站",
        "youtube": "YouTube", "youtu.be": "YouTube", "xiaohongshu": "小红书",
        "xhslink": "小红书", "kuaishou": "快手", "weibo": "微博",
        "twitter": "Twitter/X", "x.com": "Twitter/X", "instagram": "Instagram",
        "vimeo": "Vimeo", "dailymotion": "Dailymotion", "facebook": "Facebook",
        "twitch": "Twitch",
    }
    for keyword, name in hints.items():
        if keyword in host:
            return name
    return urlparse(url).netloc


def _is_douyin_url(url: str) -> bool:
    """判断是否为抖音 URL（含短链接）"""
    host = urlparse(url).netloc.lower()
    return any(d in host for d in _DOUYIN_HOSTS)


def _find_cookie_file(url: str) -> Path | None:
    """根据 URL 域名查找对应的 Cookie 文件"""
    if not COOKIE_DIR.exists():
        return None

    host = urlparse(url).netloc.lower()
    domain_map = {
        "douyin": "douyin.txt", "tiktok": "tiktok.txt",
        "bilibili": "bilibili.txt", "b23.tv": "bilibili.txt",
        "xiaohongshu": "xiaohongshu.txt", "xhslink": "xiaohongshu.txt",
        "kuaishou": "kuaishou.txt", "weibo": "weibo.txt",
        "instagram": "instagram.txt", "facebook": "facebook.txt",
    }
    for keyword, filename in domain_map.items():
        if keyword in host:
            cookie_path = COOKIE_DIR / filename
            if cookie_path.exists():
                return cookie_path

    default_cookie = COOKIE_DIR / "default.txt"
    return default_cookie if default_cookie.exists() else None


def _load_cookies_as_dict(cookie_file: Path) -> dict[str, str]:
    """将 Netscape 格式 Cookie 文件解析为 dict"""
    cookies = {}
    with open(cookie_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split("\t")
                if len(parts) >= 7:
                    cookies[parts[5]] = parts[6]
    return cookies


def _is_cookie_error(stderr: str) -> bool:
    """检查 yt-dlp 错误信息是否表示需要 Cookie"""
    return any(kw in stderr.lower() for kw in _COOKIE_REQUIRED_KEYWORDS)


class VideoCookieRequired(RuntimeError):
    """视频平台需要 Cookie 才能下载"""
    def __init__(self, platform: str, url: str):
        self.platform = platform
        self.url = url
        super().__init__(
            f"{platform} 视频需要 Cookie 才能下载。\n"
            f"请将浏览器导出的 Cookie 文件（Netscape 格式）放到 config/cookies/ 目录，"
            f"文件名为 {platform.lower().replace('/', '_')}.txt\n"
            f"详细教程见 config/cookies/README.md"
        )


# ─── 抖音专用下载器 ───

def _douyin_resolve_url(url: str) -> str:
    """解析抖音短链接，获取真实 URL 和视频 ID"""
    logger.info(f"解析抖音短链接: {url}")
    try:
        r = http_requests.head(
            url, allow_redirects=True, timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"},
        )
        resolved = r.url
        logger.info(f"解析结果: {resolved}")
        return resolved
    except Exception as e:
        logger.warning(f"短链接解析失败: {e}")
        return url


def _douyin_extract_video_id(url: str) -> str | None:
    """从抖音 URL 提取视频 ID（aweme_id）"""
    # 从 URL 路径提取: /video/7604065517855163505
    match = re.search(r"/video/(\d+)", url)
    if match:
        return match.group(1)
    # 从 URL 参数提取
    match = re.search(r"aweme_id=(\d+)", url)
    if match:
        return match.group(1)
    # 从短链接路径提取纯数字
    match = re.search(r"/(\d{15,})/?", url)
    if match:
        return match.group(1)
    return None


def _douyin_download(url: str, save_dir: Path) -> tuple[Path, dict]:
    """
    抖音专用下载器（绕过 yt-dlp Douyin 提取器 bug #9667）：
    1. 解析短链接 → 获取 aweme_id
    2. 请求移动端分享页面 iesdouyin.com/share/video/{id}/
    3. 从 _ROUTER_DATA 提取视频元信息和播放地址
    4. 将 playwm（带水印）转为 play（无水印）URL
    5. 直接下载 mp4 文件

    Returns:
        (视频文件路径, 视频元信息 dict)

    Raises:
        RuntimeError: 下载失败
        VideoCookieRequired: 需要 Cookie
    """
    save_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: 解析短链接 → 获取 video_id
    resolved_url = _douyin_resolve_url(url)
    video_id = _douyin_extract_video_id(resolved_url)
    if not video_id:
        video_id = _douyin_extract_video_id(url)
    if not video_id:
        raise RuntimeError(f"无法从抖音链接提取视频 ID: {url}")

    logger.info(f"抖音视频 ID: {video_id}")

    # Step 2: 读取 Cookie（抖音需要 Cookie 才能获取视频信息）
    cookie_file = _find_cookie_file(url)
    if not cookie_file:
        raise VideoCookieRequired("抖音", url)

    cookies = _load_cookies_as_dict(cookie_file)
    if not cookies:
        raise VideoCookieRequired("抖音", url)

    # Step 3: 请求移动端分享页面（比 PC 端更稳定，返回完整视频数据）
    share_url = f"https://www.iesdouyin.com/share/video/{video_id}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                       "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                       "Version/16.0 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    logger.info(f"请求抖音移动端分享页: {share_url}")
    resp = http_requests.get(share_url, headers=headers, cookies=cookies, timeout=15)

    if resp.status_code != 200:
        raise RuntimeError(f"抖音分享页请求失败: HTTP {resp.status_code}")

    # Step 4: 从 _ROUTER_DATA 提取视频信息
    router_match = re.search(
        r"window\._ROUTER_DATA\s*=\s*({.*?})\s*</script>", resp.text, re.DOTALL,
    )
    if not router_match:
        raise RuntimeError(
            "抖音页面结构变化，无法提取视频数据。\n"
            "可能原因：Cookie 过期或视频不存在"
        )

    try:
        router_data = json.loads(router_match.group(1))
    except json.JSONDecodeError:
        raise RuntimeError("抖音视频数据 JSON 解析失败")

    # 从 _ROUTER_DATA 中定位视频详情
    # 路径: loaderData -> "video_(id)/page" -> videoInfoRes -> item_list[0]
    video_url = None
    title = ""
    duration = 0

    try:
        # 尝试标准路径
        loader = router_data.get("loaderData", {})
        page_data = None
        for key in loader:
            if "video" in key and "page" in key:
                page_data = loader[key]
                break

        if page_data:
            items = page_data.get("videoInfoRes", {}).get("item_list", [])
            if items:
                item = items[0]
                title = item.get("desc", "")
                video_obj = item.get("video", {})
                duration = video_obj.get("duration", 0)
                if isinstance(duration, (int, float)) and duration > 1000:
                    duration = int(duration // 1000)  # 毫秒转秒

                # 获取播放地址
                play_addr = video_obj.get("play_addr", {})
                url_list = play_addr.get("url_list", [])
                if url_list:
                    video_url = url_list[0]
    except (KeyError, IndexError, TypeError) as e:
        logger.warning(f"标准路径提取失败: {e}")

    # 兜底：递归搜索
    if not video_url:
        def _recursive_find(obj, depth=0):
            if depth > 12:
                return None, "", 0
            if isinstance(obj, dict):
                if "desc" in obj and "video" in obj:
                    d = obj.get("desc", "")
                    v = obj["video"]
                    dur = v.get("duration", 0)
                    pa = v.get("play_addr", {}).get("url_list", [])
                    if pa:
                        return pa[0], d, dur
                for val in obj.values():
                    r = _recursive_find(val, depth + 1)
                    if r[0]:
                        return r
            elif isinstance(obj, list):
                for item in obj:
                    r = _recursive_find(item, depth + 1)
                    if r[0]:
                        return r
            return None, "", 0

        video_url, title, duration = _recursive_find(router_data)
        if isinstance(duration, (int, float)) and duration > 1000:
            duration = int(duration // 1000)

    if not video_url:
        raise RuntimeError(
            "抖音视频地址提取失败。可能原因：\n"
            "1. Cookie 已过期，请重新导出\n"
            "2. 视频已被删除或设为私密\n"
            "3. 抖音页面结构已更新"
        )

    # Step 5: 转换为无水印 URL（playwm → play）
    nowm_url = video_url.replace("/playwm/", "/play/")
    logger.info(f"抖音视频: {title[:60]}（{duration}s），开始下载")

    # Step 6: 下载视频文件
    dl_headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                       "AppleWebKit/605.1.15",
        "Referer": "https://www.douyin.com/",
    }

    dl_resp = http_requests.get(nowm_url, headers=dl_headers, stream=True, timeout=120)
    if dl_resp.status_code != 200:
        # 无水印失败，尝试原始 URL（带水印也能用于 ASR）
        logger.warning(f"无水印 URL 失败({dl_resp.status_code})，尝试原始 URL")
        dl_resp = http_requests.get(video_url, headers=dl_headers, stream=True, timeout=120)
        if dl_resp.status_code != 200:
            raise RuntimeError(f"抖音视频下载失败: HTTP {dl_resp.status_code}")

    file_path = save_dir / f"{video_id}.mp4"
    total = 0
    with open(file_path, "wb") as f:
        for chunk in dl_resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
            total += len(chunk)

    size_mb = total / 1024 / 1024
    logger.info(f"抖音视频下载完成: {file_path.name} ({size_mb:.1f}MB)")

    info = {
        "title": title,
        "duration": duration,
        "id": video_id,
        "extractor": "Douyin-Direct",
    }
    return file_path, info


# ─── 通用入口 ───

def probe_video(url: str) -> dict | None:
    """
    探测 URL 是否包含可下载的视频。

    对抖音 URL：直接返回基本信息（跳过 yt-dlp 的已知 bug）
    对其他 URL：使用 yt-dlp --dump-json 探测

    Returns:
        视频元信息 dict，或 None（非视频/不支持）

    Raises:
        VideoCookieRequired: 确认是视频平台但需要 Cookie
    """
    platform = _get_platform_hint(url)
    logger.info(f"探测视频: {platform} - {url}")

    # ── 抖音专用路径（绕过 yt-dlp Douyin 提取器 bug #9667）──
    if _is_douyin_url(url):
        logger.info("检测到抖音 URL，使用专用下载器")
        resolved = _douyin_resolve_url(url)
        video_id = _douyin_extract_video_id(resolved) or _douyin_extract_video_id(url)
        if video_id:
            return {
                "title": f"抖音视频 {video_id}",
                "duration": 0,
                "id": video_id,
                "extractor": "Douyin-Direct",
                "_douyin_direct": True,  # 标记使用专用下载器
            }
        logger.warning(f"无法从抖音 URL 提取视频 ID: {url}")
        return None

    # ── 通用 yt-dlp 路径 ──
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        "--no-check-certificates",
        url,
    ]

    cookie_file = _find_cookie_file(url)
    if cookie_file:
        cmd.insert(-1, "--cookies")
        cmd.insert(-1, str(cookie_file))

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=PROBE_TIMEOUT,
        )
    except FileNotFoundError:
        logger.warning("yt-dlp 未安装，跳过视频探测")
        return None
    except subprocess.TimeoutExpired:
        logger.warning(f"视频探测超时（{PROBE_TIMEOUT}s）: {url}")
        return None

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if _is_cookie_error(stderr):
            logger.warning(f"{platform} 需要 Cookie: {stderr[:200]}")
            raise VideoCookieRequired(platform, url)
        logger.debug(f"非视频 URL: {url}")
        return None

    try:
        first_line = result.stdout.strip().split("\n")[0]
        info = json.loads(first_line)
        logger.info(
            f"探测到视频: {info.get('title', '未知')} "
            f"(时长: {info.get('duration', '?')}s)"
        )
        return info
    except (json.JSONDecodeError, IndexError):
        logger.warning(f"视频元信息解析失败: {url}")
        return None


def download_video(url: str, save_dir: Path) -> Path:
    """
    下载视频到本地。
    抖音 URL 使用专用下载器，其他平台使用 yt-dlp。

    Returns:
        下载的视频文件路径
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    platform = _get_platform_hint(url)

    # ── 抖音专用路径 ──
    if _is_douyin_url(url):
        file_path, _info = _douyin_download(url, save_dir)
        return file_path

    # ── 通用 yt-dlp 路径 ──
    logger.info(f"开始下载 {platform} 视频: {url}")
    output_template = str(save_dir / "%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--no-check-certificates",
        "-f", "best[ext=mp4]/bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "--max-filesize", MAX_VIDEO_SIZE,
        "-o", output_template,
        "--print", "after_move:filepath",
        "--no-simulate",
        "--no-warnings",
        url,
    ]

    cookie_file = _find_cookie_file(url)
    if cookie_file:
        cmd.insert(-1, "--cookies")
        cmd.insert(-1, str(cookie_file))

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=DOWNLOAD_TIMEOUT,
            cwd=str(save_dir),
        )
    except FileNotFoundError:
        raise RuntimeError("yt-dlp 未安装。请运行: pip install yt-dlp")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{platform} 视频下载超时（>{DOWNLOAD_TIMEOUT}s）")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        error_msg = stderr[-500:] if len(stderr) > 500 else stderr
        logger.error(f"yt-dlp 下载失败: {error_msg}")
        if _is_cookie_error(error_msg):
            raise RuntimeError(
                f"{platform} 视频下载失败：需要 Cookie。"
                f"请将 Cookie 文件放到 config/cookies/ 目录。"
            )
        raise RuntimeError(f"{platform} 视频下载失败: {error_msg}")

    output_lines = result.stdout.strip().split("\n")
    file_path_str = output_lines[-1].strip() if output_lines else ""

    if file_path_str and Path(file_path_str).exists():
        file_path = Path(file_path_str)
    else:
        video_exts = {".mp4", ".webm", ".mkv", ".flv", ".avi", ".mov", ".m4a", ".mp3"}
        candidates = [
            f for f in save_dir.iterdir()
            if f.suffix.lower() in video_exts and f.stat().st_size > 0
        ]
        if not candidates:
            raise RuntimeError(f"{platform} 视频下载完成但未找到文件")
        file_path = max(candidates, key=lambda f: f.stat().st_mtime)

    size_mb = file_path.stat().st_size / 1024 / 1024
    logger.info(f"{platform} 视频下载完成: {file_path.name} ({size_mb:.1f}MB)")
    return file_path
