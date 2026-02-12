/* DeepDistill 根布局 */

import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'DeepDistill — 多源内容深度蒸馏引擎',
  description: '从视频/音频/图片/文档中提炼结构化知识',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh" className="dark">
      <body className="min-h-screen bg-surface-0 text-text-primary antialiased">
        {children}
      </body>
    </html>
  )
}
