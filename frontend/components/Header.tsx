/* 顶部导航栏 — 响应式：桌面横排 / 移动端汉堡菜单 */

'use client'

import { useState } from 'react'
import { usePathname } from 'next/navigation'
import Link from 'next/link'

export default function Header() {
  const pathname = usePathname()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-surface-0/90 backdrop-blur-xl">
      <div className="h-14 flex items-center justify-between px-4 sm:px-6">
        {/* Logo */}
        <div className="flex items-center gap-2 sm:gap-3">
          <Link href="/" className="text-lg sm:text-xl font-bold bg-gradient-to-r from-ai to-info bg-clip-text text-transparent hover:opacity-80 transition-opacity">
            DeepDistill
          </Link>
          <span className="text-xs sm:text-sm text-text-tertiary font-mono">v0.1.0</span>
        </div>

        {/* 桌面导航 */}
        <nav className="hidden md:flex items-center gap-1">
          <NavLink href="/" active={pathname === '/'}>处理面板</NavLink>
          <NavLink href="/results" active={pathname === '/results'}>结果列表</NavLink>
          <NavLink href="/settings" active={pathname === '/settings'}>设置</NavLink>
        </nav>

        {/* 右侧：状态 + 汉堡 */}
        <div className="flex items-center gap-2">
          <StatusIndicator />
          {/* 汉堡按钮（移动端） */}
          <button
            className="md:hidden p-2 rounded-lg hover:bg-white/[0.06] transition-colors"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="菜单"
          >
            <svg className="w-5 h-5 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              {menuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* 移动端下拉菜单 */}
      {menuOpen && (
        <nav className="md:hidden border-t border-white/[0.06] bg-surface-0/95 backdrop-blur-xl px-4 py-3 space-y-1">
          <MobileNavLink href="/" active={pathname === '/'} onClick={() => setMenuOpen(false)}>处理面板</MobileNavLink>
          <MobileNavLink href="/results" active={pathname === '/results'} onClick={() => setMenuOpen(false)}>结果列表</MobileNavLink>
          <MobileNavLink href="/settings" active={pathname === '/settings'} onClick={() => setMenuOpen(false)}>设置</MobileNavLink>
        </nav>
      )}
    </header>
  )
}

function NavLink({ href, active, children }: { href: string; active?: boolean; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className={`px-4 py-2 rounded-md text-base font-medium transition-colors ${
        active
          ? 'bg-info/10 text-text-primary'
          : 'text-info hover:bg-info/10'
      }`}
    >
      {children}
    </Link>
  )
}

function MobileNavLink({ href, active, onClick, children }: { href: string; active?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={`block px-4 py-3 rounded-xl text-base font-medium transition-colors ${
        active
          ? 'bg-info/10 text-text-primary'
          : 'text-text-secondary hover:bg-white/[0.04]'
      }`}
    >
      {children}
    </Link>
  )
}

function StatusIndicator() {
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-full bg-surface-2 text-xs sm:text-sm">
      <span className="w-2 h-2 rounded-full bg-success animate-pulse-slow" />
      <span className="text-text-secondary font-mono">READY</span>
    </div>
  )
}
