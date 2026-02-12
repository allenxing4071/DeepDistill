"""
网页抓取模块
从 URL 抓取网页内容，提取正文文本，保存为本地 HTML 文件供管线处理。
支持：普通网页、文章页、博客等。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger("deepdistill.ingestion.web_fetcher")


def fetch_url(url: str, save_dir: Path) -> Path:
    """
    抓取 URL 内容并保存为本地 HTML 文件。

    Args:
        url: 目标网页 URL
        save_dir: 保存目录

    Returns:
        保存的 HTML 文件路径

    Raises:
        ValueError: URL 格式无效
        RuntimeError: 抓取失败
    """
    # 验证 URL
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"无效的 URL: {url}")

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"仅支持 http/https 协议: {url}")

    import httpx

    logger.info(f"抓取网页: {url}")

    try:
        with httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"HTTP 错误 {e.response.status_code}: {url}")
    except httpx.ConnectError:
        raise RuntimeError(f"无法连接: {url}")
    except httpx.TimeoutException:
        raise RuntimeError(f"请求超时: {url}")
    except Exception as e:
        raise RuntimeError(f"抓取失败: {e}")

    # 检查内容类型
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        logger.warning(f"非 HTML 内容: {content_type}，尝试按 HTML 处理")

    html_content = response.text

    # 生成文件名（从 URL 提取有意义的名称）
    filename = _url_to_filename(url)
    save_dir.mkdir(parents=True, exist_ok=True)
    file_path = save_dir / filename

    # 在 HTML 中注入原始 URL 元信息（供后续处理使用）
    html_with_meta = _inject_source_meta(html_content, url)
    file_path.write_text(html_with_meta, encoding="utf-8")

    logger.info(f"网页已保存: {file_path} ({len(html_content)} 字符)")
    return file_path


def _url_to_filename(url: str) -> str:
    """从 URL 生成有意义的文件名"""
    parsed = urlparse(url)
    # 取域名 + 路径
    domain = parsed.netloc.replace("www.", "").replace(".", "_")
    path = parsed.path.strip("/").replace("/", "_")

    if path:
        name = f"{domain}_{path}"
    else:
        name = domain

    # 清理非法字符
    name = re.sub(r'[^\w\-]', '_', name)
    # 限制长度
    name = name[:80]

    return f"{name}.html"


def _inject_source_meta(html: str, url: str) -> str:
    """在 HTML 头部注入来源 URL 元信息"""
    meta_tag = f'<meta name="deepdistill-source-url" content="{url}">'

    if "<head>" in html.lower():
        # 在 <head> 后插入
        idx = html.lower().index("<head>") + len("<head>")
        return html[:idx] + "\n" + meta_tag + "\n" + html[idx:]
    elif "<html>" in html.lower():
        idx = html.lower().index("<html>") + len("<html>")
        return html[:idx] + "\n<head>\n" + meta_tag + "\n</head>\n" + html[idx:]
    else:
        return meta_tag + "\n" + html
