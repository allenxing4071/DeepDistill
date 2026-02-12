# DeepDistill

> 多源内容深度蒸馏引擎 — 从视频/音频/图片/文档中提炼结构化知识

## 项目简介

DeepDistill 从多种格式的内容（视频、音频、图片、文档、网页）中自动提取文本，通过 AI 深度分析生成结构化知识，并支持视觉素材再生成。

**核心特性：**

- **多源输入**：视频 (mp4/mov)、音频 (mp3/wav)、图片 (JPG/PNG)、文档 (PDF/Word/PPT)、网页 (HTML)
- **深度理解**：不只转文字，还分析视频的镜头、场景、动作、风格
- **AI 提炼**：LLM 结构化输出摘要、关键词、核心逻辑
- **本地优先**：默认全部本地处理，GPU (MPS) 加速，隐私可控
- **插件化**：ASR/OCR/LLM/视频分析模块可独立替换

## 快速开始

> 项目开发中，详细使用说明将在 MVP 完成后补充。

## 文档

- [产品需求文档 (PRD)](docs/PRD.md)

## 技术栈

| 能力 | 技术 |
|---|---|
| 语音转文字 | ffmpeg + faster-whisper |
| 图片 OCR | EasyOCR / PaddleOCR |
| 文档解析 | PyPDF2 / python-pptx / BeautifulSoup |
| 视频分析 | PySceneDetect / YOLOv8 / CLIP / MediaPipe |
| AI 提炼 | DeepSeek / Qwen (本地 + API) |
| 素材生成 | Stable Diffusion / RunwayML |

## License

MIT
