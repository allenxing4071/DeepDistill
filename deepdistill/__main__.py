"""
DeepDistill CLI 入口
支持命令行处理文件和启动服务。

用法：
  python -m deepdistill                  # 启动 API 服务
  python -m deepdistill process <file>   # 处理单个文件
  python -m deepdistill process <dir>    # 批量处理目录
  python -m deepdistill config           # 查看当前配置
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from .config import cfg
from .main import setup_logging


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """DeepDistill — 多源内容深度蒸馏引擎"""
    setup_logging()
    if ctx.invoked_subcommand is None:
        # 无子命令时启动 API 服务
        from .main import main
        main()


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="输出目录")
@click.option("--format", "-f", "fmt", type=click.Choice(["markdown", "json"]), default=None, help="输出格式")
def process(path: str, output: str | None, fmt: str | None):
    """处理文件或目录，提炼结构化知识"""
    logger = logging.getLogger("deepdistill.cli")
    cfg.ensure_dirs()

    target = Path(path)
    output_dir = Path(output) if output else cfg.OUTPUT_DIR

    if target.is_file():
        logger.info(f"📄 处理文件: {target.name}")
        _process_file(target, output_dir, fmt)
    elif target.is_dir():
        files = _collect_files(target)
        logger.info(f"📁 发现 {len(files)} 个可处理文件")
        for f in files:
            _process_file(f, output_dir, fmt)
    else:
        click.echo(f"❌ 无效路径: {path}", err=True)
        sys.exit(1)


@cli.command()
def config():
    """查看当前配置"""
    click.echo(json.dumps(cfg.to_dict(), indent=2, ensure_ascii=False))


def _process_file(file_path: Path, output_dir: Path, fmt: str | None):
    """处理单个文件（调用管线）"""
    logger = logging.getLogger("deepdistill.cli")
    try:
        from .pipeline import Pipeline
        pipeline = Pipeline(output_dir=output_dir, output_format=fmt)
        result = pipeline.process(file_path)
        if result:
            logger.info(f"  ✅ 完成: {result.output_path}")
        else:
            logger.warning(f"  ⚠️  跳过: {file_path.name}（不支持的格式或处理失败）")
    except Exception as e:
        logger.error(f"  ❌ 失败: {file_path.name} — {e}")


# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {
    # 视频
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
    # 音频
    ".mp3", ".wav", ".m4a", ".flac", ".ogg",
    # 文档
    ".pdf", ".docx", ".pptx", ".xlsx",
    # 图片
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp",
    # 网页
    ".html", ".htm",
}


def _collect_files(directory: Path) -> list[Path]:
    """收集目录中所有可处理的文件"""
    files = []
    for f in sorted(directory.rglob("*")):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(f)
    return files


if __name__ == "__main__":
    cli()
