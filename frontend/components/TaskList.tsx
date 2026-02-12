/* 任务列表 — 显示处理任务的状态和结果 */

'use client'

import { useState, useEffect } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8006'

interface Task {
  id: string
  filename: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  progress: number
  created_at: string
  result: any
  error: string | null
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  queued:      { label: '排队中', color: 'text-warn',    bg: 'bg-warn/10' },
  processing:  { label: '处理中', color: 'text-info',    bg: 'bg-info/10' },
  completed:   { label: '已完成', color: 'text-success', bg: 'bg-success/10' },
  failed:      { label: '失败',   color: 'text-error',   bg: 'bg-error/10' },
}

export default function TaskList() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)

  const fetchTasks = async () => {
    try {
      const res = await fetch(`${API_URL}/api/tasks`)
      if (res.ok) {
        const data = await res.json()
        setTasks(data)
      }
    } catch {
      // 后端未启动时静默
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTasks()
    // 轮询刷新（有处理中的任务时）
    const interval = setInterval(fetchTasks, 3000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="text-text-tertiary text-sm">加载中...</div>
    )
  }

  if (tasks.length === 0) {
    return (
      <div className="text-center py-16 text-text-tertiary">
        <div className="text-4xl mb-3">📭</div>
        <p>暂无处理任务</p>
        <p className="text-xs mt-1">上传文件开始第一次蒸馏</p>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-lg font-semibold mb-4 text-text-primary">
        处理任务 <span className="text-text-tertiary text-sm font-normal">({tasks.length})</span>
      </h2>

      <div className="space-y-3">
        {tasks.map(task => (
          <TaskCard key={task.id} task={task} />
        ))}
      </div>
    </div>
  )
}

function TaskCard({ task }: { task: Task }) {
  const config = STATUS_CONFIG[task.status] || STATUS_CONFIG.queued

  return (
    <div className="bg-surface-2 border border-white/[0.06] rounded-xl p-5 hover:border-white/10 transition-colors animate-fade-in">
      <div className="flex items-center justify-between mb-3">
        {/* 文件名 + 状态 */}
        <div className="flex items-center gap-3">
          <span className="text-lg">{getFileIcon(task.filename)}</span>
          <span className="font-medium text-text-primary">{task.filename}</span>
          <span className={`text-xs font-bold px-2 py-0.5 rounded ${config.bg} ${config.color} uppercase tracking-wider`}>
            {config.label}
          </span>
        </div>

        {/* 任务 ID */}
        <span className="text-xs text-text-tertiary font-mono">#{task.id}</span>
      </div>

      {/* 进度条 */}
      {task.status === 'processing' && (
        <div className="h-1 bg-surface-3 rounded-full overflow-hidden mb-3">
          <div
            className="h-full bg-gradient-to-r from-info to-ai rounded-full transition-all duration-500"
            style={{ width: `${task.progress}%` }}
          />
        </div>
      )}

      {/* AI 提炼结果预览 */}
      {task.status === 'completed' && task.result?.ai_result?.summary && (
        <div className="mt-3 p-3 bg-surface-1 rounded-lg border-l-2 border-ai">
          <p className="text-sm text-text-secondary leading-relaxed">
            {task.result.ai_result.summary}
          </p>
          {task.result.ai_result.keywords && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {task.result.ai_result.keywords.slice(0, 6).map((kw: string, i: number) => (
                <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-info/10 text-info">
                  {kw}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 错误信息 */}
      {task.error && (
        <p className="mt-2 text-xs text-error">{task.error}</p>
      )}
    </div>
  )
}

function getFileIcon(filename: string): string {
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
