/* 上传面板 — 支持 URL 输入 + 批量文件拖拽/选择 + 处理意图/导出设置 */

'use client'

import { useState, useRef, useCallback, useEffect } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8006'

// 正在追踪的任务
type TaskStatus = 'queued' | 'processing' | 'completed' | 'failed'

interface TrackedTask {
  id: string
  filename: string
  progress: number
  step_label: string
  status: TaskStatus
}

// 分类项（从后端 API 动态加载）
interface CategoryItem {
  name: string
  doc_count: number
  folder_url: string | null
  is_custom: boolean
}

// 预定义分类（仅作为 API 不可用时的 fallback）
const FALLBACK_CATEGORIES = ['投诉维权', '学习笔记', '技术文档', '市场分析', '会议纪要', '创意素材', '法律法规', '其他']

interface UploadPanelProps {
  onUploadComplete?: () => void
}

export default function UploadPanel({ onUploadComplete }: UploadPanelProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [messages, setMessages] = useState<{ text: string; type: 'success' | 'error' | 'info' }[]>([])
  const [urlInput, setUrlInput] = useState('')
  const [urlLoading, setUrlLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── 任务进度追踪 ──
  const [trackedTasks, setTrackedTasks] = useState<TrackedTask[]>([])

  // 添加追踪任务
  const trackTask = (taskId: string, filename: string) => {
    const newTask: TrackedTask = {
      id: taskId, filename, progress: 0, step_label: '排队等待', status: 'queued' as TaskStatus,
    }
    setTrackedTasks(prev => [newTask, ...prev].slice(0, 20))
  }

  // 轮询更新追踪任务进度
  useEffect(() => {
    const activeTasks = trackedTasks.filter(t => t.status === 'queued' || t.status === 'processing')
    if (activeTasks.length === 0) return

    const interval = setInterval(async () => {
      for (const t of activeTasks) {
        try {
          const res = await fetch(`${API_URL}/api/tasks/${t.id}`)
          if (!res.ok) continue
          const data = await res.json()
          setTrackedTasks(prev => prev.map(pt =>
            pt.id === t.id
              ? { ...pt, progress: data.progress as number, step_label: (data.step_label || pt.step_label) as string, status: data.status as TaskStatus }
              : pt
          ))
        } catch {
          // 静默
        }
      }
    }, 1500)

    return () => clearInterval(interval)
  }, [trackedTasks])

  // ── 全局处理选项 ──
  const [intent, setIntent] = useState<'content' | 'style'>('content')
  const [exportFormat, setExportFormat] = useState<'doc' | 'word' | 'excel'>('doc')
  const [docType, setDocType] = useState<'doc' | 'skill' | 'both'>('doc')
  const [category, setCategory] = useState<string>('')
  const [customCategory, setCustomCategory] = useState<string>('')

  // 校验分类是否已选择（必须选择一个具体目录才能执行）
  const isCategoryValid = (): boolean => {
    if (!category || category === '') return false
    if (category === 'custom') return customCategory.trim().length > 0
    return true
  }

  // ── 动态分类列表（从 Google Drive 同步） ──
  const [categories, setCategories] = useState<CategoryItem[]>([])

  useEffect(() => {
    fetch(`${API_URL}/api/export/categories`)
      .then(res => res.json())
      .then((data: CategoryItem[]) => {
        if (Array.isArray(data) && data.length > 0) {
          setCategories(data)
        }
      })
      .catch(() => {
        // API 不可用时使用 fallback
        setCategories(FALLBACK_CATEGORIES.map(name => ({
          name, doc_count: 0, folder_url: null, is_custom: false,
        })))
      })
  }, [])

  const addMessage = (text: string, type: 'success' | 'error' | 'info' = 'info') => {
    setMessages(prev => [{ text, type }, ...prev].slice(0, 10))
  }

  // 构建处理选项 JSON
  const buildOptions = () => ({
    intent,
    export_format: exportFormat,
    doc_type: docType,
    category: category === 'custom' ? customCategory.trim() : category,
    auto_export: true,
  })

  // ── 解析多个 URL（换行、逗号分隔） ──
  const parseUrls = (input: string): string[] => {
    return input
      .split(/[\n,]+/)
      .map(s => s.trim())
      .filter(s => s.startsWith('http://') || s.startsWith('https://'))
  }

  const urlCount = parseUrls(urlInput).length

  // ── URL 提交（支持多个） ──
  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!isCategoryValid()) {
      addMessage('请先选择一个分类目录（或新建目录）', 'error')
      return
    }

    const urls = parseUrls(urlInput)
    if (urls.length === 0) {
      addMessage('请输入至少一个有效的 URL（以 http:// 或 https:// 开头）', 'error')
      return
    }

    if (urls.length > 20) {
      addMessage('单次最多提交 20 个 URL', 'error')
      return
    }

    setUrlLoading(true)
    addMessage(`⏳ 正在提交 ${urls.length} 个网页...`, 'info')

    let successCount = 0
    const options = buildOptions()
    // 并发提交所有 URL
    const results = await Promise.allSettled(
      urls.map(async (url) => {
        const res = await fetch(`${API_URL}/api/process/url`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url, options }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(data.detail || res.statusText)
        }
        return res.json()
      })
    )

    results.forEach((r, i) => {
      if (r.status === 'fulfilled') {
        addMessage(`✅ ${r.value.filename}`, 'success')
        trackTask(r.value.task_id, r.value.filename)
        successCount++
      } else {
        addMessage(`❌ ${urls[i]}: ${r.reason?.message || '失败'}`, 'error')
      }
    })

    if (successCount > 0) {
      setUrlInput('')
      onUploadComplete?.()
    }
    setUrlLoading(false)
  }

  // ── 拖拽事件 ──
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) uploadFiles(files)
  }, [intent, exportFormat, docType, category, customCategory])

  // ── 文件选择 ──
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      uploadFiles(Array.from(files))
    }
    // 重置 input，允许重复选择同一文件
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // ── 批量上传 ──
  const uploadFiles = async (files: File[]) => {
    if (files.length === 0) return

    if (!isCategoryValid()) {
      addMessage('请先选择一个分类目录（或新建目录）', 'error')
      return
    }

    setUploading(true)
    addMessage(`⏳ 正在上传 ${files.length} 个文件...`, 'info')

    const options = buildOptions()

    try {
      if (files.length === 1) {
        // 单文件：用原有接口
        const formData = new FormData()
        formData.append('file', files[0])
        formData.append('options', JSON.stringify(options))

        const res = await fetch(`${API_URL}/api/process`, {
          method: 'POST',
          body: formData,
        })

        if (res.ok) {
          const data = await res.json()
          addMessage(`✅ ${files[0].name} → 任务 ${data.task_id}`, 'success')
          trackTask(data.task_id, files[0].name)
        } else {
          addMessage(`❌ ${files[0].name} 上传失败: ${res.statusText}`, 'error')
        }
      } else {
        // 多文件：用批量接口
        const formData = new FormData()
        files.forEach(f => formData.append('files', f))
        formData.append('options', JSON.stringify(options))

        const res = await fetch(`${API_URL}/api/process/batch`, {
          method: 'POST',
          body: formData,
        })

        if (res.ok) {
          const data = await res.json()
          addMessage(`✅ ${data.count} 个文件已提交处理`, 'success')
          data.tasks.forEach((t: any) => {
            addMessage(`  📄 ${t.filename} → 任务 ${t.task_id}`, 'info')
            trackTask(t.task_id, t.filename)
          })
        } else {
          const data = await res.json().catch(() => ({ detail: res.statusText }))
          addMessage(`❌ 批量上传失败: ${data.detail || res.statusText}`, 'error')
        }
      }

      onUploadComplete?.()
    } catch {
      addMessage('❌ 连接失败，请确认后端服务已启动', 'error')
    } finally {
      setUploading(false)
    }
  }

  // 文件图标
  const getFileIcon = (filename: string): string => {
    const ext = filename.split('.').pop()?.toLowerCase() || ''
    const icons: Record<string, string> = {
      mp4: '🎬', mov: '🎬', avi: '🎬', mkv: '🎬', webm: '🎬',
      mp3: '🎵', wav: '🎵', m4a: '🎵', flac: '🎵',
      pdf: '📕', docx: '📘', doc: '📘',
      pptx: '📙', ppt: '📙',
      xlsx: '📗', xls: '📗',
      jpg: '🖼️', jpeg: '🖼️', png: '🖼️',
      html: '🌐', htm: '🌐',
    }
    return icons[ext] || '📄'
  }

  return (
    <div className="space-y-5">
      {/* ── 处理设置栏 ── */}
      <div className="bg-surface-2 border border-white/[0.06] rounded-xl p-3 sm:p-5 space-y-4">
        <h2 className="text-sm sm:text-base font-semibold text-text-primary uppercase tracking-wider">处理设置</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* 处理意图 */}
          <div>
            <label className="text-sm text-text-tertiary mb-2 block">处理意图</label>
            <div className="flex gap-2">
              <button
                onClick={() => setIntent('content')}
                className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  intent === 'content'
                    ? 'bg-info/15 text-info border border-info/30'
                    : 'bg-surface-1 text-text-tertiary border border-white/5 hover:text-text-secondary'
                }`}
              >
                <div className="text-lg mb-1">📝</div>
                提取内容
                <div className="text-xs opacity-70 mt-0.5">文字/语音内容</div>
              </button>
              <button
                onClick={() => setIntent('style')}
                className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  intent === 'style'
                    ? 'bg-ai/15 text-ai border border-ai/30'
                    : 'bg-surface-1 text-text-tertiary border border-white/5 hover:text-text-secondary'
                }`}
              >
                <div className="text-lg mb-1">🎨</div>
                分析风格
                <div className="text-xs opacity-70 mt-0.5">视觉/设计风格</div>
              </button>
            </div>
          </div>

          {/* 导出格式 */}
          <div>
            <label className="text-sm text-text-tertiary mb-2 block">导出格式</label>
            <div className="flex gap-2">
              {([
                { key: 'doc', label: 'Google Doc', icon: '📄' },
                { key: 'word', label: 'Word', icon: '📘' },
                { key: 'excel', label: 'Excel', icon: '📗' },
              ] as const).map(f => (
                <button
                  key={f.key}
                  onClick={() => setExportFormat(f.key)}
                  className={`flex-1 px-3 py-3 rounded-lg text-sm font-medium transition-colors ${
                    exportFormat === f.key
                      ? 'bg-success/15 text-success border border-success/30'
                      : 'bg-surface-1 text-text-tertiary border border-white/5 hover:text-text-secondary'
                  }`}
                >
                  <div className="text-lg mb-1">{f.icon}</div>
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* 文档类型 */}
          <div>
            <label className="text-sm text-text-tertiary mb-2 block">文档类型</label>
            <div className="flex gap-2">
              {([
                { key: 'doc', label: '普通文档' },
                { key: 'skill', label: 'Skill 文档' },
                { key: 'both', label: '两者都导出' },
              ] as const).map(d => (
                <button
                  key={d.key}
                  onClick={() => setDocType(d.key)}
                  className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    docType === d.key
                      ? 'bg-warn/15 text-warn border border-warn/30'
                      : 'bg-surface-1 text-text-tertiary border border-white/5 hover:text-text-secondary'
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          {/* 分类文件夹 */}
          <div>
            <label className="text-sm text-text-tertiary mb-2 block">分类文件夹</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={`w-full px-3 py-2.5 rounded-lg bg-surface-1 border text-sm
                focus:outline-none focus:border-info/50 focus:ring-1 focus:ring-info/20 transition-colors
                ${!category || category === '' ? 'border-error/50 text-text-tertiary' : 'border-white/5 text-text-secondary'}`}
            >
              <option value="" disabled>── 请选择分类目录 ──</option>
              {categories.filter(c => !c.is_custom).map(cat => (
                <option key={cat.name} value={cat.name}>
                  {cat.name}{cat.doc_count > 0 ? ` (${cat.doc_count})` : ''}
                </option>
              ))}
              {categories.some(c => c.is_custom) && (
                <option disabled>── 自定义目录 ──</option>
              )}
              {categories.filter(c => c.is_custom).map(cat => (
                <option key={cat.name} value={cat.name}>
                  📂 {cat.name}{cat.doc_count > 0 ? ` (${cat.doc_count})` : ''}
                </option>
              ))}
              <option value="custom">📁 新建目录...</option>
            </select>
            {category === 'custom' && (
              <input
                type="text"
                value={customCategory}
                onChange={(e) => setCustomCategory(e.target.value)}
                placeholder="输入自定义目录名称"
                className="w-full mt-2 px-3 py-2 rounded-lg bg-surface-1 border border-white/5
                  text-text-secondary text-sm focus:outline-none focus:border-info/50
                  focus:ring-1 focus:ring-info/20 transition-colors
                  placeholder:text-text-tertiary"
              />
            )}
          </div>
        </div>

        {/* 当前设置摘要 */}
        <div className="flex items-center gap-2 text-xs text-text-tertiary pt-2 border-t border-white/[0.04] flex-wrap">
          <span>当前：</span>
          <span className={intent === 'content' ? 'text-info' : 'text-ai'}>
            {intent === 'content' ? '📝 提取内容' : '🎨 分析风格'}
          </span>
          <span>→</span>
          <span className="text-success">
            {exportFormat === 'doc' ? 'Google Doc' : exportFormat === 'word' ? 'Word' : 'Excel'}
          </span>
          <span>→</span>
          <span className="text-warn">
            {docType === 'doc' ? '普通文档' : docType === 'skill' ? 'Skill' : '两者'}
          </span>
          <span>→</span>
          <span className={!isCategoryValid() ? 'text-error' : 'text-text-secondary'}>
            {!category || category === '' ? '⚠️ 未选择目录' :
             category === 'custom' ? (customCategory.trim() ? `📁 ${customCategory}` : '⚠️ 请输入目录名') :
             `📂 ${category}`}
          </span>
          <span className="sm:ml-auto text-success/70">自动导出到 Google Drive</span>
        </div>
      </div>

      {/* ── URL 输入区域 ── */}
      <div>
        <h2 className="text-lg sm:text-xl font-semibold mb-3 text-text-primary">网页 / 视频抓取</h2>
        <form onSubmit={handleUrlSubmit} className="space-y-3">
          <textarea
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder={"输入 URL，每行一个，支持批量\n自动识别：网页文章 / 视频（1800+ 平台）\n抖音 / B站 / YouTube / TikTok / 小红书 / 快手 / 微博..."}
            disabled={urlLoading}
            rows={3}
            className="w-full px-4 py-3 rounded-xl bg-surface-1 border border-white/10
              text-text-primary placeholder:text-text-tertiary text-base
              focus:outline-none focus:border-info/50 focus:ring-1 focus:ring-info/20
              disabled:opacity-50 transition-colors resize-y min-h-[3rem]"
          />
          <div className="flex items-center justify-between">
            <span className="text-sm text-text-tertiary">
              {urlCount > 0 ? `已识别 ${urlCount} 个 URL（自动检测视频/网页）` : '每行一个 URL，或用逗号分隔'}
            </span>
            <button
              type="submit"
              disabled={urlLoading || urlCount === 0 || !isCategoryValid()}
              className="px-6 py-2.5 rounded-xl bg-info/10 text-info text-base font-medium
                hover:bg-info/20 disabled:opacity-40 disabled:cursor-not-allowed
                transition-colors whitespace-nowrap"
            >
              {urlLoading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  抓取中
                </span>
              ) : urlCount > 1 ? `批量抓取 (${urlCount})` : '抓取分析'}
            </button>
          </div>
        </form>
      </div>

      {/* ── 文件上传区域 ── */}
      <div>
        <h2 className="text-lg sm:text-xl font-semibold mb-3 text-text-primary">文件上传</h2>
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`
            relative flex flex-col items-center justify-center
            h-36 sm:h-48 rounded-xl border-2 border-dashed cursor-pointer
            transition-all duration-200
            ${isDragging
              ? 'border-info bg-info/5 scale-[1.01]'
              : 'border-white/10 hover:border-white/20 bg-surface-1'
            }
            ${uploading ? 'pointer-events-none opacity-60' : ''}
          `}
        >
          <div className="text-3xl sm:text-4xl mb-2 sm:mb-3">{uploading ? '⏳' : '📥'}</div>
          <p className="text-text-secondary text-sm sm:text-base text-center px-4">
            {uploading ? '上传处理中...' : '拖拽文件到此处，或点击选择'}
          </p>
          <p className="text-text-tertiary text-xs sm:text-sm mt-1 sm:mt-2 text-center px-4">
            视频 / 音频 / 图片 / PDF / Word / PPT / Excel / HTML
          </p>
          <p className="text-text-tertiary text-xs sm:text-sm mt-1 hidden sm:block">
            单次最多 20 个文件
          </p>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileSelect}
            accept=".mp4,.mov,.avi,.mkv,.webm,.mp3,.wav,.m4a,.flac,.ogg,.pdf,.docx,.pptx,.xlsx,.jpg,.jpeg,.png,.bmp,.html,.txt,.md"
          />
        </div>
      </div>

      {/* ── 任务进度追踪 ── */}
      {trackedTasks.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-base font-semibold text-text-primary">
            任务进度 <span className="text-sm text-text-tertiary font-normal">
              ({trackedTasks.filter(t => t.status === 'processing' || t.status === 'queued').length} 进行中)
            </span>
          </h3>
          {trackedTasks.map(t => (
            <div
              key={t.id}
              className={`bg-surface-2 border rounded-xl p-4 transition-all ${
                t.status === 'completed' ? 'border-success/20' :
                t.status === 'failed' ? 'border-error/20' :
                'border-white/[0.06]'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-base">{getFileIcon(t.filename)}</span>
                  <span className="text-sm font-medium text-text-primary truncate max-w-[200px]">{t.filename}</span>
                  <span className="text-xs font-mono text-text-tertiary">#{t.id}</span>
                </div>
                <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                  t.status === 'completed' ? 'bg-success/10 text-success' :
                  t.status === 'failed' ? 'bg-error/10 text-error' :
                  t.status === 'processing' ? 'bg-info/10 text-info' :
                  'bg-warn/10 text-warn'
                }`}>
                  {t.status === 'completed' ? '✅ 完成' :
                   t.status === 'failed' ? '❌ 失败' :
                   t.status === 'processing' ? '⚙️ 处理中' : '⏳ 排队'}
                </span>
              </div>

              {/* 进度条 */}
              {(t.status === 'processing' || t.status === 'queued') && (
                <>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-text-tertiary">{t.step_label}</span>
                    <span className="text-xs font-mono text-text-tertiary">{t.progress}%</span>
                  </div>
                  <div className="h-2 bg-surface-3 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ease-out ${
                        t.status === 'queued'
                          ? 'bg-warn/60 animate-pulse'
                          : 'bg-gradient-to-r from-info via-ai to-info'
                      }`}
                      style={{ width: `${Math.max(t.progress, 2)}%` }}
                    />
                  </div>
                </>
              )}

              {/* 完成状态 */}
              {t.status === 'completed' && (
                <div className="h-2 bg-surface-3 rounded-full overflow-hidden">
                  <div className="h-full w-full bg-success/60 rounded-full" />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── 消息列表 ── */}
      {messages.length > 0 && (
        <div className="space-y-2">
          {messages.map((msg, i) => (
            <p
              key={i}
              className={`text-base animate-fade-in ${
                msg.type === 'success' ? 'text-success' :
                msg.type === 'error' ? 'text-error' :
                'text-text-tertiary'
              }`}
            >
              {msg.text}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
