/* DeepDistill 首页 — 文件上传与处理面板 */

'use client'

import { useState } from 'react'
import Header from '@/components/Header'
import UploadPanel from '@/components/UploadPanel'
import TaskList from '@/components/TaskList'

export default function Home() {
  const [refreshKey, setRefreshKey] = useState(0)

  const handleUploadComplete = () => {
    setRefreshKey(prev => prev + 1)
  }

  return (
    <div className="min-h-screen">
      <Header />
      <main className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        {/* 上传区域 */}
        <UploadPanel onUploadComplete={handleUploadComplete} />

        {/* 任务列表 */}
        <TaskList key={refreshKey} />
      </main>
    </div>
  )
}
