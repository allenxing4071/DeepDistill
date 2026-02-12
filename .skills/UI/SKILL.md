# DeepDistill UI 设计体系

## 触发词
用户说"UI 规范"、"设计系统"、"样式"、"页面视觉"、"前端"时执行本 Skill。

## 必须遵守的 Rules
- 新建/修改页面前先阅读本 Skill 了解设计令牌（R0 要求）
- 新经验写入本文件"经验沉淀"区（R8 要求）

## 设计哲学

融合三大顶级设计体系，服务于 **内容处理工具 + 知识管理** 场景：

| 来源 | 借鉴要素 |
|------|---------|
| **Vercel Geist** | 极简暗色、高对比 Mono 字体优先、无装饰网格 |
| **Grafana Node Graph** | 管线拓扑节点、状态色环、连线箭头 |
| **Linear** | CSS 变量架构、语义状态色、模块化面板 |
| **Apple HIG** | SF 字体栈、动效克制（不花哨但有呼吸感） |

核心原则：**"内容为王，界面退后。状态一目了然，操作零学习成本。"**

> 与 KKline / FlowEdge 共用同一套设计语言（暗色终端风格），保持视觉一致性。

---

## 1. 色彩系统（Design Tokens）

### 1.1 背景层级（4 级深度）

```css
--bg-0: #06070a;       /* 页面底色 — 最深 */
--bg-1: #0b0d12;       /* 卡片/面板背景 */
--bg-2: #10131a;       /* 次级容器/表头 */
--bg-3: #161a24;       /* 悬停高亮/激活态 */
--bg-hover: #1c2030;   /* 交互悬停 */
--bg-elevated: rgba(255,255,255,0.03);  /* 弹出层/抽屉 */
```

> 规则：层级越高数字越大越亮。弹出层/模态用 `--bg-elevated` 叠加半透明。

### 1.2 语义色（6 种 + glow 变体）

```css
/* 成功/完成/运行中 */
--green: #00d68f;
--green-dim: rgba(0,214,143,0.10);       /* badge/tag 背景 */
--green-glow: rgba(0,214,143,0.35);      /* 节点光晕 */

/* 错误/失败 */
--red: #ff5370;
--red-dim: rgba(255,83,112,0.10);
--red-glow: rgba(255,83,112,0.35);

/* 警告/处理中/排队 */
--amber: #ffb347;
--amber-dim: rgba(255,179,71,0.10);
--amber-glow: rgba(255,179,71,0.35);

/* 信息/链接/主操作 */
--blue: #4a90ff;
--blue-dim: rgba(74,144,255,0.10);
--blue-glow: rgba(74,144,255,0.35);

/* AI 分析/智能处理 */
--purple: #a78bfa;
--purple-dim: rgba(167,139,250,0.10);

/* 视频分析/视觉相关 */
--cyan: #22d3ee;
--cyan-dim: rgba(34,211,238,0.10);

/* 未激活/休眠 */
--idle: #2a2e3a;
--idle-text: #545870;
```

### 1.3 文字层级

```css
--t1: #eaecf0;    /* 主文字 — 标题/数值 */
--t2: #8b90a3;    /* 次文字 — 描述/正文 */
--t3: #545870;    /* 辅助 — 标签/时间戳 */
```

### 1.4 边界

```css
--border: rgba(255,255,255,0.06);     /* 默认分割线 */
--border-h: rgba(255,255,255,0.10);   /* 悬停高亮边框 */
```

---

## 2. 字体栈

```css
--mono: 'SF Mono','Fira Code','JetBrains Mono',Menlo,Consolas,monospace;
--sans: -apple-system,BlinkMacSystemFont,'SF Pro Display','Inter','Segoe UI',sans-serif;
```

### 使用规则

| 场景 | 字体 | 字号 | 字重 |
|------|------|------|------|
| 数值/进度/耗时 | `--mono` | 14-34px | 700 |
| 时间戳/文件路径/代码 | `--mono` | 11-12px | 500 |
| 标题/标签 | `--sans` | 12-14px | 600 |
| 正文/描述 | `--sans` | 13-14px | 400 |
| 全大写标签 | `--sans` | 10-12px | 600, `letter-spacing: 0.8-1.5px, text-transform: uppercase` |

---

## 3. 组件规范

### 3.1 Topbar

```css
height: 64px;
background: rgba(6,7,10,0.88);
backdrop-filter: blur(24px) saturate(1.8);
border-bottom: 1px solid var(--border);
position: sticky; top: 0; z-index: 100;
```

- Logo：22px, font-weight 700, gradient 文字（`--purple` → `--blue`）
- 导航链接：14px, `--blue` 色, hover 时背景 `--blue-dim`, border-radius 6px
- 状态胶囊（sys-pill）：圆角 100px, 内含 6px 状态圆点

### 3.2 统计卡片（Stats Grid）

```css
display: grid;
grid-template-columns: repeat(N, 1fr);
gap: 1px;
background: var(--border);  /* 利用 gap 做分割线 */
border-radius: 12px;
overflow: hidden;

/* 每个卡片 */
.stat {
  background: var(--bg-2);
  padding: 22px 16px;
  text-align: center;
}
.stat-label { font-size: 12px; color: var(--t3); text-transform: uppercase; }
.stat-val   { font-family: var(--mono); font-size: 32px; font-weight: 700; }
```

### 3.3 数据表格

```css
.tbl th {
  font-size: 12px; color: var(--t3);
  text-transform: uppercase; letter-spacing: 0.8px;
  background: var(--bg-1); border-bottom: 1px solid var(--border);
}
.tbl td {
  font-size: 14px; color: var(--t2);
  border-bottom: 1px solid var(--border);
}
.tbl tr:hover td { background: var(--bg-2); }
```

### 3.4 面板/卡片

```css
background: var(--bg-2);
border: 1px solid var(--border);
border-radius: 12px;
padding: 22px;
transition: border-color 0.2s;

&:hover { border-color: var(--border-h); }
```

### 3.5 Badge / Tag

```css
/* 状态标签 */
.tag-success  { background: var(--green-dim);  color: var(--green); }
.tag-error    { background: var(--red-dim);    color: var(--red); }
.tag-pending  { background: var(--amber-dim);  color: var(--amber); }
.tag-ai       { background: var(--purple-dim); color: var(--purple); }
.tag-video    { background: var(--cyan-dim);   color: var(--cyan); }

font-size: 13px; font-weight: 700;
padding: 4px 12px; border-radius: 5px;
text-transform: uppercase; letter-spacing: 0.5px;
```

---

## 4. 管线拓扑可视化（Pipeline View）

> DeepDistill 的核心可视化：展示 6 层管线的处理状态和数据流向。

### 4.1 节点视觉

```
尺寸：56×56px 圆形
外环：3px 状态色环
内部：24×24 图标（SVG 或 emoji）
下方：节点名（11px, --t2, 居中）
下方2：状态文字（10px, 状态色, 居中）
```

### 管线节点定义

| 节点 | 图标 | 对应层 | 说明 |
|------|------|--------|------|
| 输入 | 📥 | Layer 1 | 文件格式识别 |
| ASR | 🎙️ | Layer 2 | 语音转文字 |
| OCR | 👁️ | Layer 2 | 图片文字提取 |
| 文档 | 📄 | Layer 2 | 文档/网页提取 |
| 视频分析 | 🎬 | Layer 3 | 镜头/场景/风格 |
| AI 提炼 | 🧠 | Layer 4 | LLM 结构化分析 |
| 融合 | 🔗 | Layer 5 | 去重/合并/输出 |
| 知识库 | 📚 | Layer 6 | 飞书/Notion/Obsidian |

### 4.2 节点状态动画

| 状态 | 外环色 | 动画 | CSS |
|------|--------|------|-----|
| **processing** | `--blue` | 旋转环 | `animation: spin 2s linear infinite` |
| **success** | `--green` | 呼吸 | `animation: breathe 3s ease-in-out infinite` |
| **error** | `--red` | 脉冲 | `animation: pulse 1s ease infinite` |
| **queued** | `--amber` | 闪烁 | `animation: blink 1.5s ease infinite` |
| **idle** | `--idle` | 无 | `opacity: 0.5` |
| **skipped** | `--idle` | 无 | `opacity: 0.3; filter: grayscale(1)` |

```css
@keyframes breathe {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.6; }
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50%      { transform: scale(1.08); }
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.4; }
}
```

### 4.3 连线规范

```
粗细：1.5px
默认色：rgba(255,255,255,0.08)
活跃色：rgba(状态色, 0.3)
跳过：dasharray 4,4 + idle 色

箭头：终点 6px 等腰三角形（SVG marker）
```

### 4.4 粒子流动（数据流可视化）

```
粒子大小：3px 圆点
颜色：跟随源节点状态色
透明度：0.6
流速：
  处理中 — 1s 一个周期
  完成 — 停止，最后一个粒子到达终点
  idle — 不显示

实现：独立 <canvas> 叠加在 SVG 上方，pointer-events: none
```

---

## 5. 处理进度条

> 文件处理时的实时进度展示。

```css
.progress-bar {
  height: 4px;
  background: var(--bg-3);
  border-radius: 2px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--blue), var(--purple));
  transition: width 0.3s ease;
  border-radius: 2px;
}
/* 不确定进度（如 AI 分析中） */
.progress-indeterminate .progress-fill {
  width: 30%;
  animation: indeterminate 1.5s ease-in-out infinite;
}
@keyframes indeterminate {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}
```

---

## 6. 结果展示卡片

> 处理完成后的结构化结果展示。

```css
.result-card {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 22px;
}

/* 文件信息头 */
.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.result-icon { font-size: 32px; }  /* 文件类型图标 */
.result-title { font-size: 16px; color: var(--t1); font-weight: 600; }
.result-meta { font-size: 12px; color: var(--t3); }

/* 摘要区 */
.result-summary {
  font-size: 14px; color: var(--t2);
  line-height: 1.6;
  padding: 16px;
  background: var(--bg-1);
  border-radius: 8px;
  border-left: 3px solid var(--purple);
}

/* 关键词标签 */
.keyword-tag {
  display: inline-block;
  background: var(--blue-dim);
  color: var(--blue);
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 100px;
  margin: 2px 4px;
}

/* 核心观点列表 */
.key-point {
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
  color: var(--t2);
}
.key-point::before {
  content: '→';
  color: var(--green);
  margin-right: 8px;
  font-weight: 700;
}
```

---

## 7. 文件类型图标映射

| 文件类型 | 图标 | 颜色 |
|----------|------|------|
| 视频 (mp4/mov) | 🎬 | `--cyan` |
| 音频 (mp3/wav) | 🎵 | `--purple` |
| PDF | 📕 | `--red` |
| Word | 📘 | `--blue` |
| PPT | 📙 | `--amber` |
| Excel | 📗 | `--green` |
| 图片 (JPG/PNG) | 🖼️ | `--cyan` |
| 网页 (HTML) | 🌐 | `--blue` |

---

## 8. 页面导航体系（规划）

| 路径 | 页面 | 定位 |
|------|------|------|
| `/` | 处理面板 | 上传文件 → 实时处理 → 查看结果 |
| `/results` | 结果列表 | 历史处理记录 + 搜索 |
| `/pipeline` | 管线监控 | 6 层管线状态拓扑图 |
| `/settings` | 设置 | 模型选择/输出格式/API Key 配置 |

---

## 9. 响应式断点

```css
@media (max-width: 1024px) {
  .main { grid-template-columns: 1fr; }
  .pipeline-topo { overflow-x: auto; }
}
@media (max-width: 768px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .result-card { padding: 16px; }
}
```

---

## 10. 技术约束

- **框架**：Next.js + React（与 KKline Admin / FlowEdge 前端一致）
- **样式**：Tailwind CSS + CSS 变量（Design Tokens）
- **图表**：轻量 Canvas 绘制，不引入重型图表库
- **管线拓扑**：SVG 节点 + Canvas 粒子层
- **数据刷新**：SSE 实时推送处理进度 + REST 查询结果

---

## 经验沉淀

<!-- UI/前端相关经验追加到此处 -->
