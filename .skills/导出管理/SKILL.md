# DeepDistill 导出管理

## 触发词
用户说"导出"、"Google Drive"、"分类"、"文件名"、"源文件"时执行本 Skill。

## 核心功能

DeepDistill 的导出层负责将 AI 分析结果导出到 Google Drive，支持自动分类、中文标题生成、源文件保留。

## 导出流程

```
AI 分析完成
    │
    ▼
_generate_short_title()  → 从 summary/keywords 提取 ≤8 字中文标题
    │
    ▼
_auto_categorize()       → 根据关键词自动推断分类（技术文档/市场分析/...）
    │
    ▼
export_task_result()     → 导出主文档 + 源文件
    │
    ├── 主文档（AI 提炼后的结构化内容）
    │   ├── Google Doc 格式（默认）
    │   ├── Word (.docx) 格式
    │   └── Excel (.xlsx) 格式
    │
    └── 源文件（完整原始文本，标注 [源文件]）
        └── 始终用 Google Doc 格式
```

## 文件命名规则

### 标题生成逻辑（_generate_short_title）

优先级：
1. **summary 中文摘要**：去除套话（"本文介绍了..."），跳过英文前缀，提取中文连续片段
2. **key_points 第一条**：同上逻辑
3. **keywords 中文关键词**：取第一个 ≤8 字的中文关键词
4. **summary 中文片段**：正则提取任意中文连续片段
5. **文件名**：如果包含中文则截取前 8 字
6. **兜底**：`未命名文档`

### 截断优化

- 在虚词（和/与/的/及/等/在/方面）处优先截断，保持语义完整
- 示例：`以太坊钱包安全与隐私保护` → `以太坊钱包安全`（在"与"处截断）

## 自动分类规则

| 分类 | 触发关键词（summary + keywords 中匹配） |
|---|---|
| 技术文档 | api, docker, python, 框架, 编程, 算法, 架构, ai, nlp... |
| 市场分析 | 市场, 交易, 投资, 加密, 比特币, 区块链, crypto, defi... |
| 学习笔记 | 教程, 学习, 入门, 指南, tutorial, guide, 笔记... |
| 创意素材 | 设计, 素材, 图片, 视频, ui, ux... |
| 会议纪要 | 会议, 纪要, 讨论, 决议, meeting... |
| 法律法规 | 法律, 法规, 条例, 合规, 监管... |
| 投诉维权 | 投诉, 维权, 举报, 违规, 欺诈... |
| 其他 | 以上均不匹配时的默认分类 |

**强制规则**：所有文件必须放入分类子目录，禁止放在 Google Drive 根目录。

## 核心代码文件

| 文件 | 职责 |
|---|---|
| `deepdistill/export/google_docs.py` | Google Drive 导出器（OAuth2 + 上传 + 分类） |
| `deepdistill/export/__init__.py` | 模块入口 |
| `deepdistill/api.py` 中 `_auto_export()` | 自动导出触发逻辑 |
| `deepdistill/api.py` 中 `export_to_google_docs()` | 手动导出 API 端点 |

## Google Drive 认证

- 凭证文件：`config/credentials.json`（OAuth2 Client ID）
- Token 缓存：`config/token.json`（自动刷新）
- 权限范围：`drive.file`（仅管理本应用创建的文件）

## 重试机制

- Google Drive 上传：最多 3 次重试，指数退避（2s → 4s → 8s）
- LLM 调用：最多 3 次重试，指数退避

## 导出格式详情

### Google Doc（默认）
- Markdown → HTML → Google Doc（自动转换）
- 支持标题层级、代码块、表格、引用

### Word (.docx)
- 使用 python-docx 生成
- 自定义字体、标题样式、段落格式

### Excel (.xlsx)
- 使用 openpyxl 生成
- 摘要 + 关键词 + 要点分 Sheet 展示

## 经验沉淀

### 经验：哈希值文件名问题
- 现象: URL 抓取的网页导出后文件名为哈希值（如 `d72b17233b...`）
- 根因: `_build_doc_markdown` 使用 `Path(filename).stem` 作为标题，URL 文件名是哈希
- 解决: 新增 `_generate_short_title()` 从 AI 分析结果提取中文短标题
- 验证: 导出后标题为"以太坊钱包"等中文名
- 关联: google_docs.py / _generate_short_title

### 经验：文件散落根目录
- 现象: 未指定 category 时文件放在 DeepDistill 根文件夹
- 根因: `export_markdown` 中 category 为 None 时使用根文件夹
- 解决: 新增 `_auto_categorize()` 自动推断分类，所有导出路径强制使用子文件夹
- 验证: 所有新文件均放入分类子目录
- 关联: google_docs.py / export_markdown / _upload_binary_to_drive

### 经验：英文标题问题
- 现象: 英文文章的 keywords 是英文，导致标题为英文
- 根因: 优先从 keywords 提取标题，但 keywords 可能是英文
- 解决: 改为优先从 summary（中文摘要）提取，跳过英文前缀，提取中文连续片段
- 验证: 英文文章也能生成中文标题（如 "以太坊钱包"）
- 关联: google_docs.py / _generate_short_title
