/* 设置页 — Apple 级系统仪表盘：大字体 · 大留白 · 大卡片 · 实时状态 */

'use client'

import { useState, useEffect, useCallback } from 'react'
import Header from '@/components/Header'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8006'

// ── 类型 ──

interface HealthInfo { status: string; version: string; device: string }

interface ConfigInfo {
  asr: { model: string; language: string | null; device: string }
  ocr: { engine: string; languages: string[] }
  ai: { provider: string; model: string; fallback_providers: string[]; has_api_key: boolean; prompt_template: string }
  video_analysis: { level: string }
  output: { format: string }
  export: { google_docs: { enabled: boolean; folder_name: string; has_credentials: boolean; has_token: boolean } }
  timeouts: { pipeline: number; ffmpeg: number; transcribe: number }
  paths: { data: string; output: string; model_cache: string }
}

interface PromptWithStats {
  name: string
  label: string
  stage: string
  icon: string
  total_calls: number
  calls_1h: number
  total_tokens: number
  avg_duration_ms: number
  cache_hit_rate: number
  error_count: number
  last_call_at?: number
  file_lines: number
}

interface PromptSummary {
  total_calls: number
  total_tokens: number
  cache_hit_rate: number
  avg_success_rate: number
  estimated_cost_usd: number
}

interface PromptDetail extends PromptWithStats {
  content: string
  system_prompt: string
  variables: string[]
  file_size_bytes?: number
  recent_calls: Array<{ ts: number; duration_ms: number; total_tokens: number; success: boolean; error?: string; cache_hit: boolean }>
}

interface ServiceStatus {
  status: 'running' | 'ready' | 'error' | 'offline' | 'unconfigured' | 'disabled'
  detail: string
  models?: string[]
  model?: string
  target_model?: string
  target_loaded?: boolean
  engine?: string
  languages?: string[]
  device?: string
  active_tasks?: number
  total_tasks?: number
}

type StatusMap = Record<string, ServiceStatus>

// ── 状态主题 ──

const STATUS_THEME: Record<string, { dot: string; bg: string; text: string; label: string; pulse: boolean }> = {
  running:      { dot: 'bg-emerald-400', bg: 'bg-emerald-500/8',  text: 'text-emerald-400', label: '运行中', pulse: true },
  ready:        { dot: 'bg-emerald-400', bg: 'bg-emerald-500/8',  text: 'text-emerald-400', label: '就绪',   pulse: false },
  error:        { dot: 'bg-amber-400',   bg: 'bg-amber-500/8',    text: 'text-amber-400',   label: '异常',   pulse: false },
  offline:      { dot: 'bg-red-400',     bg: 'bg-red-500/8',      text: 'text-red-400',     label: '离线',   pulse: false },
  unconfigured: { dot: 'bg-zinc-500',    bg: 'bg-zinc-500/8',     text: 'text-zinc-400',    label: '未配置', pulse: false },
  disabled:     { dot: 'bg-zinc-600',    bg: 'bg-zinc-600/8',     text: 'text-zinc-500',    label: '已禁用', pulse: false },
}

function fmtSec(sec: number): string {
  if (sec >= 3600) return `${(sec / 3600).toFixed(0)} 小时`
  if (sec >= 60) return `${(sec / 60).toFixed(0)} 分钟`
  return `${sec} 秒`
}

function formatAgo(ts: number): string {
  const ago = Math.round(Date.now() / 1000 - ts)
  if (ago < 0) return '刚刚'
  if (ago < 60) return `${ago}s前`
  if (ago < 3600) return `${Math.round(ago / 60)}m前`
  if (ago < 86400) return `${Math.round(ago / 3600)}h前`
  return `${Math.round(ago / 86400)}d前`
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function formatDuration(ms: number): string {
  if (ms >= 60000) return `${(ms / 60000).toFixed(1)}min`
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms}ms`
}

function formatCost(usd: number): string {
  if (usd < 0.01) return `$${usd.toFixed(4)}`
  return `$${usd.toFixed(2)}`
}

// ── 主页面 ──

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthInfo | null>(null)
  const [config, setConfig] = useState<ConfigInfo | null>(null)
  const [status, setStatus] = useState<StatusMap | null>(null)
  const [prompts, setPrompts] = useState<PromptWithStats[]>([])
  const [promptSummary, setPromptSummary] = useState<PromptSummary | null>(null)
  const [promptSelected, setPromptSelected] = useState<string | null>(null)
  const [promptDetail, setPromptDetail] = useState<PromptDetail | null>(null)
  const [promptDetailLoading, setPromptDetailLoading] = useState(false)
  const [lastPromptRefresh, setLastPromptRefresh] = useState('--:--:--')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchAll = useCallback(async () => {
    try {
      const [h, c, s, pData] = await Promise.all([
        fetch(`${API_URL}/health`).then(r => r.json()),
        fetch(`${API_URL}/api/config`).then(r => r.json()),
        fetch(`${API_URL}/api/status`).then(r => r.json()),
        fetch(`${API_URL}/api/prompts`).then(r => r.json()).then(d => ({ prompts: d.prompts || [], summary: d.summary || null })).catch(() => ({ prompts: [], summary: null })),
      ])
      setHealth(h); setConfig(c); setStatus(s)
      setPrompts(pData.prompts); setPromptSummary(pData.summary); setError('')
      setLastPromptRefresh(new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }))
    } catch { setError('无法连接后端服务') }
    finally { setLoading(false) }
  }, [])

  const handleSelectPrompt = useCallback(async (name: string) => {
    if (promptSelected === name) {
      setPromptSelected(null)
      setPromptDetail(null)
      return
    }
    setPromptSelected(name)
    setPromptDetailLoading(true)
    try {
      const r = await fetch(`${API_URL}/api/prompts/${encodeURIComponent(name)}`)
      const d = await r.json()
      setPromptDetail(d as PromptDetail)
    } catch {
      setPromptDetail(null)
    } finally {
      setPromptDetailLoading(false)
    }
  }, [promptSelected])

  useEffect(() => {
    fetchAll()
    const iv = setInterval(fetchAll, 30000)
    return () => clearInterval(iv)
  }, [fetchAll])

  return (
    <div className="min-h-screen">
      <Header />
      <main className="max-w-6xl mx-auto px-4 sm:px-6 md:px-8 py-6 sm:py-8 md:py-10 space-y-8 md:space-y-10">

        {loading ? (
          <div className="flex items-center justify-center py-32">
            <div className="w-8 h-8 border-2 border-white/20 border-t-white/60 rounded-full animate-spin" />
            <span className="ml-4 text-lg text-text-tertiary">加载系统状态...</span>
          </div>
        ) : error ? (
          <div className="p-6 bg-red-500/5 border border-red-500/20 rounded-2xl text-red-400 text-base text-center">{error}</div>
        ) : (
          <>
            {/* ── 顶部 Hero ── */}
            <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
              <div>
                <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-text-primary tracking-tight">系统仪表盘</h1>
                <p className="text-sm sm:text-base md:text-lg text-text-tertiary mt-1 sm:mt-2">DeepDistill v{health?.version} · {health?.device?.toUpperCase()} · 实时监控</p>
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                <StatusPill status={health?.status === 'ok' ? 'running' : 'error'} label={health?.status === 'ok' ? '系统正常' : '系统异常'} />
                {status?.pipeline && (
                  <StatusPill
                    status={status.pipeline.status}
                    label={status.pipeline.status === 'running' ? `${status.pipeline.active_tasks} 个任务` : '空闲'}
                  />
                )}
              </div>
            </div>

            {/* ── AI 模型 ── */}
            <section>
              <SectionHeader title="AI 模型" subtitle="LLM 推理引擎与 Fallback 链路" />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
                <ModelCard
                  name="Ollama"
                  subtitle="本地推理"
                  model={config?.ai.model || 'qwen3:8b'}
                  status={status?.ollama}
                  isPrimary={config?.ai.provider === 'ollama'}
                  badge={config?.ai.provider === 'ollama' ? '主引擎' : undefined}
                  extra={status?.ollama?.models ? `已加载 ${status.ollama.models.length} 个模型` : undefined}
                  location="local"
                  serviceKey="ollama"
                  onRefresh={fetchAll}
                />
                <ModelCard
                  name="DeepSeek"
                  subtitle="云端 API"
                  model="deepseek-chat"
                  status={status?.deepseek}
                  isPrimary={config?.ai.provider === 'deepseek'}
                  badge={config?.ai.fallback_providers?.includes('deepseek') ? 'Fallback' : undefined}
                  location="cloud"
                />
                <ModelCard
                  name="Qwen"
                  subtitle="通义千问 API"
                  model="qwen-max"
                  status={status?.qwen}
                  isPrimary={config?.ai.provider === 'qwen'}
                  badge={config?.ai.fallback_providers?.includes('qwen') ? 'Fallback' : undefined}
                  location="cloud"
                />
              </div>
              {/* 链路 + 当前 Prompt 模板 */}
              <div className="mt-4 space-y-2">
                <div className="flex items-center gap-3 text-sm sm:text-base text-text-tertiary flex-wrap">
                  <span>调用链路</span>
                  {[config?.ai.provider, ...(config?.ai.fallback_providers || [])].filter((v, i, a) => a.indexOf(v) === i).map((p, i, arr) => (
                    <span key={p} className="flex items-center gap-2">
                      <span className={`font-semibold ${i === 0 ? 'text-emerald-400' : 'text-text-secondary'}`}>{p}</span>
                      {i < arr.length - 1 && <span className="text-text-tertiary/50">→</span>}
                    </span>
                  ))}
                </div>
                <div className="text-sm text-text-tertiary">
                  当前 Prompt 模板：<span className="font-mono text-text-secondary">{config?.ai.prompt_template ?? 'summarize'}</span>
                </div>
              </div>
            </section>

            {/* ── Prompt 监控（对标 KKline：行内展开、Tab 详情、缓存条） ── */}
            <section>
              <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2 mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-text-primary tracking-tight">Prompt 监控</h2>
                  <p className="text-base text-text-tertiary mt-1">AI 模板调用统计与分析 · 点击行展开详情</p>
                </div>
                <span className="text-sm text-text-tertiary font-mono">{lastPromptRefresh}</span>
              </div>
              {/* 汇总卡片 */}
              {promptSummary && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                  <SummaryCard label="总调用次数" value={String(promptSummary.total_calls)} icon="📞" />
                  <SummaryCard label="总 Token 消耗" value={formatTokens(promptSummary.total_tokens)} sub={formatCost(promptSummary.estimated_cost_usd)} icon="🪙" color="text-emerald-400" />
                  <SummaryCard label="缓存命中率" value={`${Math.round(promptSummary.cache_hit_rate * 100)}%`} icon="⚡" color={promptSummary.cache_hit_rate >= 0.3 ? 'text-emerald-400' : 'text-amber-400'} />
                  <SummaryCard label="成功率" value={`${Math.round(promptSummary.avg_success_rate * 100)}%`} icon="✅" color={promptSummary.avg_success_rate >= 0.95 ? 'text-emerald-400' : promptSummary.avg_success_rate >= 0.8 ? 'text-amber-400' : 'text-red-400'} />
                </div>
              )}
              <div className="space-y-1.5">
                {prompts.length === 0 ? (
                  <div className="px-6 py-8 text-center text-text-tertiary text-sm rounded-xl bg-white/[0.02] border border-white/[0.06]">暂无模板，请在后端 deepdistill/ai_analysis/prompts/ 目录添加 .txt 文件</div>
                ) : (
                  prompts.map((t: PromptWithStats) => (
                    <div key={t.name}>
                      <PromptRow
                        prompt={t}
                        selected={promptSelected === t.name}
                        isActive={config?.ai.prompt_template === t.name}
                        onSelect={() => handleSelectPrompt(t.name)}
                        formatAgo={formatAgo}
                        formatTokens={formatTokens}
                        formatDuration={formatDuration}
                      />
                      {promptSelected === t.name && (
                        <div className="mt-0 rounded-b-xl overflow-hidden border border-t-0 border-white/[0.06] bg-white/[0.01]">
                          {promptDetailLoading ? (
                            <div className="px-6 py-12 text-center text-text-tertiary">加载中...</div>
                          ) : promptDetail ? (
                            <PromptDetailPanel detail={promptDetail} onClose={() => { setPromptSelected(null); setPromptDetail(null) }} formatAgo={formatAgo} formatTokens={formatTokens} formatDuration={formatDuration} />
                          ) : null}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </section>

            {/* ── 处理引擎 ── */}
            <section>
              <SectionHeader title="处理引擎" subtitle="语音识别 · 文字识别 · 视频分析" />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
                <ModelCard
                  name="Whisper"
                  subtitle="语音转文字"
                  model={config?.asr.model || 'base'}
                  status={status?.whisper}
                  extra={`设备 ${config?.asr.device?.toUpperCase()}`}
                  location="local"
                />
                <ModelCard
                  name={config?.ocr.engine === 'easyocr' ? 'EasyOCR' : 'PaddleOCR'}
                  subtitle="文字识别"
                  model={config?.ocr.languages?.join(', ') || 'ch_sim, en'}
                  status={status?.ocr}
                  location="local"
                />
                <ModelCard
                  name="视频分析"
                  subtitle="增强分析层"
                  model={config?.video_analysis.level === 'off' ? '未启用' : config?.video_analysis.level || 'off'}
                  status={{
                    status: config?.video_analysis.level && config.video_analysis.level !== 'off' ? 'ready' : 'disabled',
                    detail: config?.video_analysis.level && config.video_analysis.level !== 'off' ? 'PySceneDetect + YOLOv8' : 'MVP 阶段',
                  }}
                  location="local"
                />
              </div>
            </section>

            {/* ── 导出与存储 ── */}
            <section>
              <SectionHeader title="导出与存储" subtitle="Google Drive · 输出格式 · 超时保护" />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
                {/* Google Drive */}
                <InfoPanel icon="📁" title="Google Drive" subtitle={config?.export.google_docs.folder_name || 'DeepDistill'}
                  dot={status?.google_drive?.status || 'disabled'} location="cloud">
                  <DetailRow label="凭据文件" value={config?.export.google_docs.has_credentials ? '已配置' : '未配置'} ok={config?.export.google_docs.has_credentials} />
                  <DetailRow label="授权令牌" value={config?.export.google_docs.has_token ? '已授权' : '未授权'} ok={config?.export.google_docs.has_token} />
                  <DetailRow label="连接状态" value={status?.google_drive?.detail || '-'} ok={status?.google_drive?.status === 'ready'} />
                </InfoPanel>

                {/* 输出配置 */}
                <InfoPanel icon="📄" title="输出配置" subtitle="格式与路径" location="local">
                  <DetailRow label="默认格式" value={config?.output.format?.toUpperCase() || '-'} />
                  <DetailRow label="数据目录" value={config?.paths.data || '-'} />
                  <DetailRow label="输出目录" value={config?.paths.output || '-'} />
                </InfoPanel>

                {/* 超时保护 */}
                <InfoPanel icon="⏱️" title="超时保护" subtitle="防止大文件阻塞" location="local">
                  <DetailRow label="总管线" value={fmtSec(config?.timeouts?.pipeline || 3600)} />
                  <DetailRow label="音轨提取" value={fmtSec(config?.timeouts?.ffmpeg || 600)} />
                  <DetailRow label="语音转录" value={fmtSec(config?.timeouts?.transcribe || 1800)} />
                </InfoPanel>
              </div>
            </section>

            {/* ── API 端点 ── */}
            <section>
              <SectionHeader title="API 端点" subtitle="11 个可用接口" />
              <div className="bg-white/[0.02] border border-white/[0.06] rounded-2xl overflow-hidden">
                <div className="grid grid-cols-1 md:grid-cols-2 md:divide-x divide-white/[0.04]">
                  {[
                    { method: 'GET',  path: '/health',                            desc: '健康检查' },
                    { method: 'GET',  path: '/api/config',                        desc: '系统配置' },
                    { method: 'GET',  path: '/api/status',                        desc: '实时状态' },
                    { method: 'POST', path: '/api/process',                       desc: '上传处理' },
                    { method: 'POST', path: '/api/process/batch',                 desc: '批量处理' },
                    { method: 'POST', path: '/api/process/url',                   desc: 'URL 抓取' },
                    { method: 'POST', path: '/api/process/local',                 desc: '本地文件' },
                    { method: 'GET',  path: '/api/tasks',                         desc: '任务列表' },
                    { method: 'GET',  path: '/api/tasks/{id}',                    desc: '任务详情' },
                    { method: 'POST', path: '/api/tasks/{id}/export/google-docs', desc: '导出 Drive' },
                    { method: 'GET',  path: '/api/export/categories',             desc: '分类列表' },
                  ].map((ep, i) => (
                    <div key={i} className="flex items-center gap-2 sm:gap-4 px-3 sm:px-6 py-3 sm:py-4 border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02] transition-colors">
                      <span className={`text-[10px] sm:text-xs font-bold font-mono px-1.5 sm:px-2.5 py-0.5 sm:py-1 rounded-md shrink-0 ${
                        ep.method === 'GET' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-blue-500/10 text-blue-400'
                      }`}>
                        {ep.method}
                      </span>
                      <code className="text-xs sm:text-sm font-mono text-text-secondary flex-1 truncate min-w-0">{ep.path}</code>
                      <span className="text-xs sm:text-sm text-text-tertiary whitespace-nowrap shrink-0 hidden sm:inline">{ep.desc}</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  )
}

// ── 子组件 ──

function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="mb-6">
      <h2 className="text-2xl font-bold text-text-primary tracking-tight">{title}</h2>
      <p className="text-base text-text-tertiary mt-1">{subtitle}</p>
    </div>
  )
}

function SummaryCard({ label, value, sub, icon, color }: {
  label: string; value: string; sub?: string; icon: string; color?: string
}) {
  return (
    <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4 flex items-center gap-3">
      <span className="text-2xl">{icon}</span>
      <div>
        <div className="text-xs text-text-tertiary uppercase tracking-wider">{label}</div>
        <div className={`text-lg font-bold font-mono ${color || 'text-text-primary'}`}>{value}</div>
        {sub && <div className="text-xs text-text-tertiary mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

function StatusDot({ status, size = 'sm' }: { status: string; size?: 'sm' | 'md' | 'lg' }) {
  const theme = STATUS_THEME[status] || STATUS_THEME.offline
  const s = size === 'lg' ? 'w-3.5 h-3.5' : size === 'md' ? 'w-3 h-3' : 'w-2.5 h-2.5'
  return (
    <span className="relative flex items-center justify-center">
      {theme.pulse && <span className={`absolute ${s} rounded-full ${theme.dot} animate-ping opacity-40`} />}
      <span className={`relative ${s} rounded-full ${theme.dot}`} />
    </span>
  )
}

function StatusPill({ status, label }: { status: string; label: string }) {
  const theme = STATUS_THEME[status] || STATUS_THEME.offline
  return (
    <div className={`flex items-center gap-2.5 px-4 py-2 rounded-full ${theme.bg} border border-white/[0.06]`}>
      <StatusDot status={status} size="md" />
      <span className={`text-sm font-semibold ${theme.text}`}>{label}</span>
    </div>
  )
}

/** 本地/云端标签 */
function LocationTag({ location }: { location: 'local' | 'cloud' }) {
  const isLocal = location === 'local'
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-md ${
      isLocal
        ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20'
        : 'bg-violet-500/10 text-violet-400 border border-violet-500/20'
    }`}>
      <span>{isLocal ? '🖥' : '☁️'}</span>
      {isLocal ? '本地' : '云端'}
    </span>
  )
}

function ModelCard({
  name, subtitle, model, status, isPrimary, badge, extra, location, serviceKey, onRefresh,
}: {
  name: string; subtitle: string; model: string; status?: ServiceStatus
  isPrimary?: boolean; badge?: string; extra?: string; location?: 'local' | 'cloud'
  serviceKey?: string; onRefresh?: () => void
}) {
  const s = status?.status || 'offline'
  const theme = STATUS_THEME[s] || STATUS_THEME.offline
  const [toggling, setToggling] = useState(false)

  const isRunning = s === 'running' || s === 'ready'
  const canControl = !!serviceKey

  const handleToggle = async () => {
    if (!serviceKey || toggling) return
    const action = isRunning ? 'stop' : 'start'
    setToggling(true)
    try {
      // 发送启停指令（立即返回）
      await fetch(`${API_URL}/api/services/${serviceKey}/${action}`, { method: 'POST' })
      // 轮询状态直到变化或超时
      const maxPolls = 15
      for (let i = 0; i < maxPolls; i++) {
        await new Promise(r => setTimeout(r, 2000))
        try {
          const statusResp = await fetch(`${API_URL}/api/status`)
          const statusData = await statusResp.json()
          const svcStatus = statusData[serviceKey]?.status
          const nowRunning = svcStatus === 'running' || svcStatus === 'ready'
          // 状态已变化，刷新并退出
          if ((action === 'stop' && !nowRunning) || (action === 'start' && nowRunning)) {
            onRefresh?.()
            return
          }
        } catch { /* 继续轮询 */ }
      }
      // 超时，也刷新一次
      onRefresh?.()
    } catch (e) {
      console.error('服务控制失败:', e)
    } finally {
      setToggling(false)
    }
  }

  return (
    <div className={`
      relative bg-white/[0.02] border rounded-xl sm:rounded-2xl p-4 sm:p-6 transition-all duration-300
      ${isPrimary ? 'border-emerald-500/25 shadow-[0_0_30px_-8px_rgba(16,185,129,0.12)]' : 'border-white/[0.06]'}
      hover:border-white/[0.14] hover:bg-white/[0.03]
    `}>
      {/* 右上角：角标 + 位置标签 */}
      <div className="absolute top-4 right-4 flex items-center gap-2">
        {location && <LocationTag location={location} />}
        {badge && (
          <span className={`text-xs font-bold px-3 py-1 rounded-full ${
            badge === '主引擎' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-zinc-500/15 text-zinc-400'
          }`}>
            {badge}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2.5 mb-4">
        <span className="text-lg font-bold text-text-primary">{name}</span>
        <StatusDot status={s} size="lg" />
      </div>

      <div className="text-sm text-text-tertiary mb-3">{subtitle}</div>

      <div className="font-mono text-lg font-semibold text-text-primary mb-3 truncate">{model}</div>

      <div className={`text-sm font-medium ${theme.text}`}>{theme.label} · {status?.detail || '-'}</div>

      {extra && <div className="text-sm text-text-tertiary mt-2">{extra}</div>}

      {/* 启停按钮 */}
      {canControl && (
        <div className="mt-4 pt-3 border-t border-white/[0.06]">
          <button
            onClick={handleToggle}
            disabled={toggling}
            className={`
              w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold
              transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed
              ${isRunning
                ? 'bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20'
                : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20'
              }
            `}
          >
            {toggling ? (
              <>
                <span className="w-4 h-4 border-2 border-current/30 border-t-current rounded-full animate-spin" />
                {isRunning ? '停止中...' : '启动中...'}
              </>
            ) : (
              <>
                <span className="text-base">{isRunning ? '⏹' : '▶'}</span>
                {isRunning ? '停止服务' : '启动服务'}
              </>
            )}
          </button>
        </div>
      )}

      {s === 'running' && (
        <div className="absolute bottom-0 left-5 right-5 h-[2px] rounded-full overflow-hidden">
          <div className="h-full bg-gradient-to-r from-transparent via-emerald-400/60 to-transparent animate-shimmer" />
        </div>
      )}
    </div>
  )
}

function InfoPanel({ icon, title, subtitle, dot, location, children }: {
  icon: string; title: string; subtitle: string; dot?: string; location?: 'local' | 'cloud'; children: React.ReactNode
}) {
  return (
    <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl sm:rounded-2xl p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4 sm:mb-5">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{icon}</span>
          <div>
            <div className="text-base font-bold text-text-primary">{title}</div>
            <div className="text-sm text-text-tertiary">{subtitle}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {location && <LocationTag location={location} />}
          {dot && <StatusDot status={dot} size="lg" />}
        </div>
      </div>
      <div className="space-y-3">{children}</div>
    </div>
  )
}

function DetailRow({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-text-tertiary">{label}</span>
      <span className={`text-sm font-mono font-medium ${
        ok === true ? 'text-emerald-400' : ok === false ? 'text-red-400' : 'text-text-secondary'
      }`}>
        {value}
      </span>
    </div>
  )
}

/** 单行 Prompt 模板（对标 KKline：点击展开、箭头、缓存条） */
function PromptRow({
  prompt,
  selected,
  isActive,
  onSelect,
  formatAgo,
  formatTokens,
  formatDuration,
}: {
  prompt: PromptWithStats
  selected: boolean
  isActive: boolean
  onSelect: () => void
  formatAgo: (ts: number) => string
  formatTokens: (n: number) => string
  formatDuration: (ms: number) => string
}) {
  const { name, label, stage, icon, total_calls, calls_1h, total_tokens, avg_duration_ms, cache_hit_rate, error_count, last_call_at, file_lines } = prompt
  const cachePct = Math.round(cache_hit_rate * 100)
  return (
    <div
      className={`flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 px-4 sm:px-6 py-3.5 sm:py-4 rounded-xl cursor-pointer transition-all border ${
        selected ? 'border-violet-500/40 bg-violet-500/5' : 'border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12] hover:bg-white/[0.03]'
      }`}
      onClick={onSelect}
    >
      <div className="min-w-0 flex-1 flex items-center gap-2.5">
        <span className="text-xl">{icon}</span>
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-text-primary">{label}</span>
            <span className="text-[11px] px-2 py-0.5 rounded bg-violet-500/15 text-violet-400 font-medium">{stage}</span>
            {isActive && <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400">当前使用</span>}
          </div>
          <div className="text-xs text-text-tertiary font-mono mt-0.5">{stage} {name}.txt · {file_lines}行</div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-4 sm:gap-5 text-sm shrink-0">
        <StatCell label="1H调用" value={`${calls_1h}（总${total_calls}）`} color={calls_1h > 0 ? 'text-emerald-400' : undefined} />
        <StatCell label="TOKEN" value={formatTokens(total_tokens)} color={total_tokens > 0 ? 'text-emerald-400' : undefined} />
        <StatCell label="平均耗时" value={avg_duration_ms > 0 ? formatDuration(avg_duration_ms) : '--'} color={avg_duration_ms > 0 ? 'text-amber-400' : undefined} />
        <div className="flex flex-col items-center min-w-[70px]">
          <span className="text-text-tertiary text-[11px] uppercase tracking-wider mb-1">缓存命中</span>
          <div className="flex items-center gap-1.5">
            <div className="w-10 h-1 rounded-full bg-white/10 overflow-hidden">
              <div className="h-full rounded-full bg-emerald-400/80 transition-all" style={{ width: `${cachePct}%` }} />
            </div>
            <span className={`text-xs font-mono ${cachePct > 0 ? 'text-emerald-400' : 'text-text-tertiary'}`}>{cachePct}%</span>
          </div>
        </div>
        <StatCell label="错误" value={String(error_count)} color={error_count > 0 ? 'text-red-400' : 'text-emerald-400'} />
        <StatCell label="最后调用" value={last_call_at ? formatAgo(last_call_at) : '--'} />
      </div>
      <div className="text-text-tertiary text-sm shrink-0 w-5 text-center">{selected ? '▼' : '▶'}</div>
    </div>
  )
}

/** 详情面板（对标 KKline：Tab 切换、语法高亮、调用记录表） */
function PromptDetailPanel({
  detail,
  onClose,
  formatAgo,
  formatTokens,
  formatDuration,
}: {
  detail: PromptDetail
  onClose: () => void
  formatAgo: (ts: number) => string
  formatTokens: (n: number) => string
  formatDuration: (ms: number) => string
}) {
  const [tab, setTab] = useState<'prompt' | 'system' | 'calls'>('prompt')
  const d = detail
  return (
    <div className="border-t border-white/[0.06]">
      <div className="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <span className="text-lg">{d.icon}</span>
          <span className="font-semibold text-text-primary">{d.label}</span>
          <span className="text-xs px-2 py-0.5 rounded bg-violet-500/15 text-violet-400">{d.stage}</span>
        </div>
        <button type="button" onClick={onClose} className="text-text-tertiary hover:text-text-primary text-lg leading-none p-2 rounded-lg hover:bg-white/[0.06]">×</button>
      </div>
      <div className="flex gap-1 px-4 sm:px-6 py-2 border-b border-white/[0.04] text-sm">
        <span className="text-text-tertiary font-mono">📄 {d.name}.txt</span>
        <span className="text-text-tertiary">·</span>
        <span className="text-text-tertiary">{d.file_lines} 行</span>
        {(d.file_size_bytes ?? 0) > 0 && <><span className="text-text-tertiary">·</span><span className="text-text-tertiary">{((d.file_size_bytes ?? 0) / 1024).toFixed(1)}KB</span></>}
        {d.variables?.length > 0 && <><span className="text-text-tertiary">·</span><span className="text-text-tertiary">变量: {d.variables.join(', ')}</span></>}
      </div>
      <div className="flex border-b border-white/[0.06]">
        {(['prompt', 'system', 'calls'] as const).map((t) => (
          <button key={t} type="button" onClick={() => setTab(t)} className={`px-4 sm:px-6 py-3 text-sm font-medium transition-colors border-b-2 ${
            tab === t ? 'text-emerald-400 border-emerald-400/60' : 'text-text-tertiary border-transparent hover:text-text-secondary'
          }`}>
            {t === 'prompt' ? 'Prompt 模板' : t === 'system' ? 'System Prompt' : `调用记录 (${d.recent_calls?.length ?? 0})`}
          </button>
        ))}
      </div>
      <div className="p-4 sm:p-6 max-h-[400px] overflow-auto">
        {tab === 'prompt' && (
          <pre className="text-sm text-text-secondary whitespace-pre-wrap font-mono break-words leading-relaxed" dangerouslySetInnerHTML={{ __html: highlightPrompt(d.content || '（文件为空）') }} />
        )}
        {tab === 'system' && (
          <pre className="text-sm text-text-secondary whitespace-pre-wrap font-mono break-words leading-relaxed" dangerouslySetInnerHTML={{ __html: highlightPrompt(d.system_prompt || '（无 System Prompt）') }} />
        )}
        {tab === 'calls' && (
          <div>
            {!d.recent_calls?.length ? (
              <div className="py-8 text-center text-text-tertiary text-sm">暂无调用记录</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-text-tertiary text-xs uppercase tracking-wider border-b border-white/[0.06]">
                    <th className="py-2 pr-4">时间</th>
                    <th className="py-2 pr-4">耗时</th>
                    <th className="py-2 pr-4">Token</th>
                    <th className="py-2 pr-4">缓存</th>
                    <th className="py-2">结果</th>
                  </tr>
                </thead>
                <tbody>
                  {d.recent_calls.map((c, i) => (
                    <tr key={i} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                      <td className="py-2 pr-4 font-mono text-text-secondary">{new Date(c.ts * 1000).toLocaleTimeString('zh-CN', { hour12: false })}</td>
                      <td className="py-2 pr-4 font-mono">{c.cache_hit ? '--' : formatDuration(c.duration_ms)}</td>
                      <td className="py-2 pr-4 font-mono text-emerald-400">{c.total_tokens > 0 ? formatTokens(c.total_tokens) : '--'}</td>
                      <td className="py-2 pr-4">{c.cache_hit ? <span className="text-emerald-400">命中</span> : '未命中'}</td>
                      <td className="py-2">{c.success ? <span className="text-emerald-400">成功</span> : <span className="text-red-400" title={c.error || ''}>失败</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function highlightPrompt(raw: string): string {
  const esc = raw.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return esc.split('\n').map((line) => {
    if (/^#{1,4}\s/.test(line)) return `<span class="text-violet-400 font-semibold">${line}</span>`
    if (/^\s*(\/\/|#[^#])/.test(line)) return `<span class="text-zinc-500 italic">${line}</span>`
    return line
      .replace(/(\{[a-zA-Z_][a-zA-Z0-9_]*\})/g, '<span class="text-amber-400 font-semibold">$1</span>')
      .replace(/(&quot;[^&]*?&quot;)\s*:/g, '<span class="text-sky-400">$1</span>:')
      .replace(/:\s*(&quot;[^&]*?&quot;)/g, ': <span class="text-emerald-300">$1</span>')
      .replace(/\b(\d+\.?\d*)\b/g, '<span class="text-orange-400">$1</span>')
      .replace(/\b(true|false|null|none|None|True|False)\b/gi, '<span class="text-pink-400 italic">$1</span>')
  }).join('\n')
}

function StatCell({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-text-tertiary text-xs uppercase">{label}</span>
      <span className={`font-mono font-semibold ${color || 'text-text-secondary'}`}>{value}</span>
    </div>
  )
}
