/* 结果列表页 — 展示所有已完成的蒸馏结果 */

'use client'

import { useState, useEffect, useRef } from 'react'
import Header from '@/components/Header'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8006'

interface Task {
  id: string
  filename: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  progress: number
  created_at: string
  result: any
  error: string | null
  options?: {
    intent?: string
    export_format?: string
    doc_type?: string
    category?: string
    auto_export?: boolean
  }
  export_result?: ExportItem | ExportItem[] | { error: string }
}

export default function ResultsPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'completed' | 'failed'>('all')

  useEffect(() => {
    fetchTasks()
    const interval = setInterval(fetchTasks, 5000)
    return () => clearInterval(interval)
  }, [])

  const fetchTasks = async () => {
    try {
      const res = await fetch(`${API_URL}/api/tasks?limit=100`)
      if (res.ok) {
        const data = await res.json()
        setTasks(data)
      }
    } catch {
      // 静默
    } finally {
      setLoading(false)
    }
  }

  const filtered = tasks.filter(t => {
    if (filter === 'completed') return t.status === 'completed'
    if (filter === 'failed') return t.status === 'failed'
    return true
  })

  const stats = {
    total: tasks.length,
    completed: tasks.filter(t => t.status === 'completed').length,
    processing: tasks.filter(t => t.status === 'processing' || t.status === 'queued').length,
    failed: tasks.filter(t => t.status === 'failed').length,
  }

  return (
    <div className="min-h-screen">
      <Header />
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {/* 统计卡片 */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
          <StatCard label="总任务" value={stats.total} color="text-text-primary" />
          <StatCard label="已完成" value={stats.completed} color="text-success" />
          <StatCard label="处理中" value={stats.processing} color="text-info" />
          <StatCard label="失败" value={stats.failed} color="text-error" />
        </div>

        {/* 筛选 */}
        <div className="flex items-center gap-2 mb-6">
          <span className="text-base text-text-tertiary mr-2">筛选：</span>
          {(['all', 'completed', 'failed'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                filter === f
                  ? 'bg-info/10 text-info'
                  : 'text-text-tertiary hover:text-text-secondary hover:bg-surface-2'
              }`}
            >
              {{ all: '全部', completed: '已完成', failed: '失败' }[f]}
            </button>
          ))}
        </div>

        {/* 结果列表 */}
        {loading ? (
          <div className="text-center py-16 text-text-tertiary">加载中...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-text-tertiary">
            <div className="text-4xl mb-3">📋</div>
            <p className="text-base">暂无结果</p>
            <p className="text-sm mt-1">处理完成后结果会显示在这里</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map(task => (
              <ResultCard key={task.id} task={task} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-surface-2 border border-white/[0.06] rounded-xl p-3 sm:p-5">
      <div className="text-xs sm:text-sm text-text-tertiary mb-1">{label}</div>
      <div className={`text-2xl sm:text-3xl font-bold font-mono ${color}`}>{value}</div>
    </div>
  )
}

// 预定义分类
const CATEGORIES = ['投诉维权', '学习笔记', '技术文档', '市场分析', '会议纪要', '创意素材', '法律法规', '其他']

// 导出格式选项
const FORMATS = [
  { key: 'doc',   label: '📄 普通文档',  desc: '标准格式，摘要+要点+原文' },
  { key: 'skill', label: '🧠 Skill 文档', desc: '结构化知识文档，适合项目开发' },
  { key: 'both',  label: '📄+🧠 两者都导出', desc: '同时生成普通文档和 Skill 文档' },
]

// 导出结果类型
interface ExportItem {
  doc_url: string
  title: string
  category?: string
  folder_url?: string
  is_raw?: boolean  // 标记为源文件（未经 AI 加工的原始文本）
}

function ResultCard({ task }: { task: Task }) {
  const [expanded, setExpanded] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportResults, setExportResults] = useState<ExportItem[]>(() => {
    // 初始化：如果任务已有自动导出结果，直接使用
    if (task.export_result && !('error' in task.export_result)) {
      return Array.isArray(task.export_result) ? task.export_result : [task.export_result]
    }
    return []
  })
  const [exportError, setExportError] = useState<string | null>(() => {
    // 初始化：如果自动导出失败，显示错误
    if (task.export_result && 'error' in task.export_result) {
      return (task.export_result as { error: string }).error
    }
    return null
  })
  const [showExportMenu, setShowExportMenu] = useState(false)
  const [selectedFormat, setSelectedFormat] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  // 点击外部关闭菜单
  useEffect(() => {
    if (!showExportMenu) return
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowExportMenu(false)
        setSelectedFormat(null)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [showExportMenu])

  const handleExportGoogleDocs = async (fmt: string, category?: string) => {
    setShowExportMenu(false)
    setSelectedFormat(null)
    setExporting(true)
    setExportError(null)
    try {
      const res = await fetch(`${API_URL}/api/tasks/${task.id}/export/google-docs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: category || null, format: fmt }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || '导出失败')
      }
      const data = await res.json()
      // both 返回数组，其他返回单个对象
      if (Array.isArray(data)) {
        setExportResults(data)
      } else {
        setExportResults([data])
      }
    } catch (err: any) {
      setExportError(err.message || '导出失败')
    } finally {
      setExporting(false)
    }
  }

  const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
    queued:     { label: '排队中', color: 'text-warn',    bg: 'bg-warn/10' },
    processing: { label: '处理中', color: 'text-info',    bg: 'bg-info/10' },
    completed:  { label: '已完成', color: 'text-success', bg: 'bg-success/10' },
    failed:     { label: '失败',   color: 'text-error',   bg: 'bg-error/10' },
  }

  const config = statusConfig[task.status] || statusConfig.queued
  const ext = task.filename.split('.').pop()?.toLowerCase() || ''
  const icons: Record<string, string> = {
    mp4: '🎬', mov: '🎬', avi: '🎬', mkv: '🎬', webm: '🎬',
    mp3: '🎵', wav: '🎵', m4a: '🎵', flac: '🎵',
    pdf: '📕', docx: '📘', doc: '📘',
    pptx: '📙', ppt: '📙',
    xlsx: '📗', xls: '📗',
    jpg: '🖼️', jpeg: '🖼️', png: '🖼️',
    html: '🌐', htm: '🌐',
  }
  const icon = icons[ext] || '📄'

  return (
    <div className="bg-surface-2 border border-white/[0.06] rounded-xl overflow-hidden hover:border-white/10 transition-colors">
      {/* 头部 */}
      <div
        className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-3 sm:p-5 cursor-pointer gap-3"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-wrap">
          <span className="text-lg sm:text-xl">{icon}</span>
          <span className="font-medium text-text-primary text-sm sm:text-base truncate max-w-[200px] sm:max-w-none">{task.filename}</span>
          <span className={`text-xs sm:text-sm font-bold px-2 sm:px-2.5 py-0.5 sm:py-1 rounded ${config.bg} ${config.color} uppercase tracking-wider shrink-0`}>
            {config.label}
          </span>
          {/* 处理选项标签 */}
          {task.options?.intent === 'style' && (
            <span className="text-xs px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 hidden sm:inline">🎨 风格分析</span>
          )}
          {task.options?.export_format && task.options.export_format !== 'doc' && (
            <span className="text-xs px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 hidden sm:inline">
              {task.options.export_format === 'word' ? '📝 Word' : '📊 Excel'}
            </span>
          )}
          {task.options?.category && (
            <span className="text-xs px-2 py-0.5 rounded bg-surface-1 text-text-tertiary hidden sm:inline">
              {task.options.category}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          {/* 导出到 Google Docs — 格式 + 分类两级选择 */}
          {task.status === 'completed' && exportResults.length === 0 && (
            <div ref={menuRef} className="relative" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={() => { setShowExportMenu(!showExportMenu); setSelectedFormat(null) }}
                disabled={exporting}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium
                  bg-[#4285f4]/10 text-[#4285f4] hover:bg-[#4285f4]/20
                  disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                title="导出到 Google Docs"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM6 20V4h7v5h5v11H6z"/>
                </svg>
                {exporting ? '导出中...' : '导出 Docs ▾'}
              </button>
              {/* 两级下拉菜单 */}
              {showExportMenu && (
                <div className="absolute right-0 top-full mt-1 w-56 sm:w-60 bg-surface-1 border border-white/10
                  rounded-xl shadow-xl z-50 py-1 animate-fade-in max-h-[70vh] overflow-y-auto">
                  {!selectedFormat ? (
                    <>
                      <div className="px-4 py-2 text-xs text-text-tertiary uppercase tracking-wider">选择格式</div>
                      {FORMATS.map(f => (
                        <button
                          key={f.key}
                          onClick={() => setSelectedFormat(f.key)}
                          className="w-full text-left px-4 py-2.5 hover:bg-white/5 transition-colors group"
                        >
                          <div className="text-sm text-text-primary font-medium group-hover:text-info">{f.label}</div>
                          <div className="text-xs text-text-tertiary mt-0.5">{f.desc}</div>
                        </button>
                      ))}
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => setSelectedFormat(null)}
                        className="w-full text-left px-4 py-2 text-xs text-text-tertiary hover:text-text-secondary transition-colors flex items-center gap-1"
                      >
                        ← 返回格式选择
                      </button>
                      <div className="px-4 py-2 text-xs text-text-tertiary uppercase tracking-wider">
                        {FORMATS.find(f => f.key === selectedFormat)?.label} — 选择分类
                      </div>
                      {CATEGORIES.map(cat => (
                        <button
                          key={cat}
                          onClick={() => handleExportGoogleDocs(selectedFormat, cat)}
                          className="w-full text-left px-4 py-2 text-sm text-text-secondary
                            hover:bg-white/5 hover:text-text-primary transition-colors"
                        >
                          {cat}
                        </button>
                      ))}
                      <div className="border-t border-white/5 mt-1 pt-1">
                        <button
                          onClick={() => handleExportGoogleDocs(selectedFormat)}
                          className="w-full text-left px-4 py-2 text-sm text-text-tertiary
                            hover:bg-white/5 hover:text-text-secondary transition-colors"
                        >
                          不分类（根目录）
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
          {/* 已导出：显示链接（支持多个） */}
          {exportResults.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap" onClick={(e) => e.stopPropagation()}>
              {exportResults.map((item, idx) => {
                // 根据文件扩展名、标题、is_raw 标记判断显示图标
                const isRaw = item.is_raw || item.title.includes('[源文件]')
                const isSkill = item.title.includes('[SKILL]')
                const isWord = item.title.endsWith('.docx')
                const isExcel = item.title.endsWith('.xlsx')
                let linkLabel = '📄 文档'
                let linkStyle = 'bg-success/10 text-success hover:bg-success/20'
                if (isRaw) {
                  linkLabel = '📋 源文件'
                  linkStyle = 'bg-amber-500/10 text-amber-400 hover:bg-amber-500/20'
                } else if (isSkill) linkLabel = '🧠 Skill'
                if (isWord) linkLabel = isSkill ? '🧠 Skill (Word)' : '📝 Word'
                if (isExcel) linkLabel = '📊 Excel'

                return (
                  <a
                    key={idx}
                    href={item.doc_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${linkStyle}`}
                    title={isRaw ? '完整原始文本（未经 AI 加工）' : item.title}
                  >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
                    </svg>
                    {linkLabel}
                  </a>
                )
              })}
              {exportResults[0]?.category && (
                <span className="text-xs text-text-tertiary bg-surface-1 px-2 py-0.5 rounded">
                  {exportResults[0].category}
                </span>
              )}
            </div>
          )}
          <span className="text-xs sm:text-sm text-text-tertiary font-mono hidden sm:inline">
            {new Date(task.created_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}
          </span>
          <span className="text-text-tertiary text-sm sm:text-base">{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* 展开详情 */}
      {expanded && (
        <div className="px-3 sm:px-5 pb-4 sm:pb-5 border-t border-white/[0.04]">
          {task.status === 'processing' && (
            <div className="mt-4">
              <div className="h-1.5 bg-surface-3 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-info to-ai rounded-full transition-all duration-500"
                  style={{ width: `${task.progress}%` }}
                />
              </div>
              <p className="text-sm text-text-tertiary mt-2">进度: {task.progress}%</p>
            </div>
          )}

          {task.status === 'completed' && task.result && (
            <div className="mt-4 space-y-4">
              {/* 摘要 */}
              {task.result.ai_result?.summary && (
                <div className="p-4 bg-surface-1 rounded-lg border-l-2 border-ai">
                  <h4 className="text-sm text-ai font-bold uppercase tracking-wider mb-2">AI 摘要</h4>
                  <p className="text-base text-text-secondary leading-relaxed">
                    {task.result.ai_result.summary}
                  </p>
                </div>
              )}

              {/* 关键词 */}
              {task.result.ai_result?.keywords && task.result.ai_result.keywords.length > 0 && (
                <div>
                  <h4 className="text-sm text-text-tertiary font-bold uppercase tracking-wider mb-2">关键词</h4>
                  <div className="flex flex-wrap gap-2">
                    {task.result.ai_result.keywords.map((kw: string, i: number) => (
                      <span key={i} className="text-sm px-3 py-1 rounded-full bg-info/10 text-info">
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* 要点 */}
              {task.result.ai_result?.key_points && task.result.ai_result.key_points.length > 0 && (
                <div>
                  <h4 className="text-sm text-text-tertiary font-bold uppercase tracking-wider mb-2">核心要点</h4>
                  <ul className="space-y-2">
                    {task.result.ai_result.key_points.map((point: string, i: number) => (
                      <li key={i} className="text-base text-text-secondary flex items-start gap-2">
                        <span className="text-info mt-0.5">•</span>
                        {point}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 视频分析 */}
              {task.result.has_video_analysis && task.result.video_analysis && (
                <div>
                  <h4 className="text-sm text-text-tertiary font-bold uppercase tracking-wider mb-2">视频分析</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {task.result.video_analysis.scenes && (
                      <div className="p-4 bg-surface-1 rounded-lg">
                        <div className="text-sm text-text-tertiary mb-1">场景数</div>
                        <div className="text-xl font-bold text-info">{task.result.video_analysis.scenes.length}</div>
                      </div>
                    )}
                    {task.result.video_analysis.style?.summary && (
                      <div className="p-4 bg-surface-1 rounded-lg">
                        <div className="text-sm text-text-tertiary mb-1">视觉风格</div>
                        <div className="text-base text-text-secondary">{task.result.video_analysis.style.summary}</div>
                      </div>
                    )}
                    {task.result.video_analysis.cinematography?.summary && (
                      <div className="p-4 bg-surface-1 rounded-lg">
                        <div className="text-sm text-text-tertiary mb-1">拍摄手法</div>
                        <div className="text-base text-text-secondary">{task.result.video_analysis.cinematography.summary}</div>
                      </div>
                    )}
                    {task.result.video_analysis.transitions && task.result.video_analysis.transitions.length > 0 && (
                      <div className="p-4 bg-surface-1 rounded-lg">
                        <div className="text-sm text-text-tertiary mb-1">转场</div>
                        <div className="text-base text-text-secondary">{task.result.video_analysis.transitions.length} 个转场</div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* 图片风格分析 */}
              {task.result.image_style && !task.result.image_style.error && (
                <div>
                  <h4 className="text-sm text-text-tertiary font-bold uppercase tracking-wider mb-2">图片风格分析</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {task.result.image_style.color_palette && (
                      <div className="p-4 bg-surface-1 rounded-lg">
                        <div className="text-sm text-text-tertiary mb-1">色彩风格</div>
                        <div className="text-base text-text-secondary">
                          {task.result.image_style.color_palette.color_temperature}，{task.result.image_style.color_palette.saturation_level}
                        </div>
                      </div>
                    )}
                    {task.result.image_style.lighting && (
                      <div className="p-4 bg-surface-1 rounded-lg">
                        <div className="text-sm text-text-tertiary mb-1">光影</div>
                        <div className="text-base text-text-secondary">{task.result.image_style.lighting.lighting_style}</div>
                      </div>
                    )}
                    {task.result.image_style.composition && (
                      <div className="p-4 bg-surface-1 rounded-lg">
                        <div className="text-sm text-text-tertiary mb-1">构图</div>
                        <div className="text-base text-text-secondary">
                          视觉重心: {task.result.image_style.composition.visual_center}
                        </div>
                      </div>
                    )}
                    {task.result.image_style.complexity && (
                      <div className="p-4 bg-surface-1 rounded-lg">
                        <div className="text-sm text-text-tertiary mb-1">复杂度</div>
                        <div className="text-base text-text-secondary">{task.result.image_style.complexity.level}</div>
                      </div>
                    )}
                    {task.result.image_style.summary && (
                      <div className="sm:col-span-2 p-4 bg-surface-1 rounded-lg">
                        <div className="text-sm text-text-tertiary mb-1">风格总结</div>
                        <div className="text-base text-text-secondary">{task.result.image_style.summary}</div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* 视觉素材 */}
              {task.result.visual_assets?.prompts && task.result.visual_assets.prompts.length > 0 && (
                <div>
                  <h4 className="text-sm text-text-tertiary font-bold uppercase tracking-wider mb-2">视觉素材 Prompt</h4>
                  <div className="space-y-2">
                    {task.result.visual_assets.prompts.map((p: any, i: number) => (
                      <div key={i} className="p-4 bg-surface-1 rounded-lg">
                        <div className="text-sm text-ai font-medium mb-1">{p.title}</div>
                        <div className="text-sm text-text-tertiary font-mono break-all">{p.prompt}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 原始文本预览 */}
              {task.result.raw_text && (
                <div>
                  <h4 className="text-sm text-text-tertiary font-bold uppercase tracking-wider mb-2">原始文本预览</h4>
                  <pre className="p-4 bg-surface-1 rounded-lg text-sm text-text-tertiary font-mono overflow-auto max-h-40 whitespace-pre-wrap">
                    {task.result.raw_text.slice(0, 1000)}
                    {task.result.raw_text.length > 1000 ? '\n...(已截断)' : ''}
                  </pre>
                </div>
              )}
            </div>
          )}

          {task.error && (
            <div className="mt-4 p-4 bg-error/5 rounded-lg border-l-2 border-error">
              <p className="text-base text-error">{task.error}</p>
            </div>
          )}

          {/* 导出错误提示 */}
          {exportError && (
            <div className="mt-4 p-4 bg-warn/5 rounded-lg border-l-2 border-warn">
              <p className="text-base text-warn">导出失败: {exportError}</p>
            </div>
          )}

          <div className="mt-4 text-sm text-text-tertiary font-mono">
            任务 ID: {task.id}
          </div>
        </div>
      )}
    </div>
  )
}
