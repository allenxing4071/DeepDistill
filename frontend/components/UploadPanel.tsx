/* 文件上传面板 — 拖拽上传 + 点击选择 */

'use client'

import { useState, useRef, useCallback } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8006'

interface UploadPanelProps {
  onUploadComplete?: () => void
}

export default function UploadPanel({ onUploadComplete }: UploadPanelProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

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
    if (files.length > 0) uploadFile(files[0])
  }, [])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) uploadFile(files[0])
  }

  const uploadFile = async (file: File) => {
    setUploading(true)
    setMessage('')

    try {
      const formData = new FormData()
      formData.append('file', file)

      const res = await fetch(`${API_URL}/api/process`, {
        method: 'POST',
        body: formData,
      })

      if (res.ok) {
        const data = await res.json()
        setMessage(`✅ 任务已创建: ${data.task_id}`)
        onUploadComplete?.()
      } else {
        setMessage(`❌ 上传失败: ${res.statusText}`)
      }
    } catch (err) {
      setMessage(`❌ 连接失败，请确认后端服务已启动`)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div>
      <h2 className="text-lg font-semibold mb-4 text-text-primary">上传文件</h2>

      {/* 拖拽区域 */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`
          relative flex flex-col items-center justify-center
          h-48 rounded-xl border-2 border-dashed cursor-pointer
          transition-all duration-200
          ${isDragging
            ? 'border-info bg-info/5 scale-[1.01]'
            : 'border-white/10 hover:border-white/20 bg-surface-1'
          }
          ${uploading ? 'pointer-events-none opacity-60' : ''}
        `}
      >
        <div className="text-4xl mb-3">{uploading ? '⏳' : '📥'}</div>
        <p className="text-text-secondary text-sm">
          {uploading ? '上传处理中...' : '拖拽文件到此处，或点击选择'}
        </p>
        <p className="text-text-tertiary text-xs mt-2">
          支持：视频 / 音频 / 图片 / PDF / Word / PPT / Excel / HTML
        </p>

        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={handleFileSelect}
          accept=".mp4,.mov,.avi,.mkv,.webm,.mp3,.wav,.m4a,.flac,.ogg,.pdf,.docx,.pptx,.xlsx,.jpg,.jpeg,.png,.bmp,.html"
        />
      </div>

      {/* 消息 */}
      {message && (
        <p className="mt-3 text-sm text-text-secondary animate-fade-in">{message}</p>
      )}
    </div>
  )
}
