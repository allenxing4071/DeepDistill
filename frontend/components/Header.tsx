/* 顶部导航栏 — DeepDistill 暗色终端风格 */

'use client'

export default function Header() {
  return (
    <header className="sticky top-0 z-50 h-16 flex items-center justify-between px-6 border-b border-white/[0.06] bg-surface-0/90 backdrop-blur-xl">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <span className="text-xl font-bold bg-gradient-to-r from-ai to-info bg-clip-text text-transparent">
          DeepDistill
        </span>
        <span className="text-xs text-text-tertiary font-mono">v0.1.0</span>
      </div>

      {/* 导航 */}
      <nav className="flex items-center gap-1">
        <NavLink href="/" active>处理面板</NavLink>
        <NavLink href="/results">结果列表</NavLink>
        <NavLink href="/settings">设置</NavLink>
      </nav>

      {/* 状态 */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-2 text-xs">
          <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse-slow" />
          <span className="text-text-secondary font-mono">READY</span>
        </div>
      </div>
    </header>
  )
}

function NavLink({ href, active, children }: { href: string; active?: boolean; children: React.ReactNode }) {
  return (
    <a
      href={href}
      className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
        active
          ? 'bg-info/10 text-text-primary'
          : 'text-info hover:bg-info/10'
      }`}
    >
      {children}
    </a>
  )
}
