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
  ai: { provider: string; model: string; fallback_providers: string[]; has_api_key: boolean }
  video_analysis: { level: string }
  output: { format: string }
  export: { google_docs: { enabled: boolean; folder_name: string; has_credentials: boolean; has_token: boolean } }
  timeouts: { pipeline: number; ffmpeg: number; transcribe: number }
  paths: { data: string; output: string; model_cache: string }
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

// ── 主页面 ──

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthInfo | null>(null)
  const [config, setConfig] = useState<ConfigInfo | null>(null)
  const [status, setStatus] = useState<StatusMap | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchAll = useCallback(async () => {
    try {
      const [h, c, s] = await Promise.all([
        fetch(`${API_URL}/health`).then(r => r.json()),
        fetch(`${API_URL}/api/config`).then(r => r.json()),
        fetch(`${API_URL}/api/status`).then(r => r.json()),
      ])
      setHealth(h); setConfig(c); setStatus(s); setError('')
    } catch { setError('无法连接后端服务') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    fetchAll()
    const iv = setInterval(fetchAll, 10000)
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
              {/* 链路 */}
              <div className="mt-4 flex items-center gap-3 text-sm sm:text-base text-text-tertiary flex-wrap">
                <span>调用链路</span>
                {[config?.ai.provider, ...(config?.ai.fallback_providers || [])].filter((v, i, a) => a.indexOf(v) === i).map((p, i, arr) => (
                  <span key={p} className="flex items-center gap-2">
                    <span className={`font-semibold ${i === 0 ? 'text-emerald-400' : 'text-text-secondary'}`}>{p}</span>
                    {i < arr.length - 1 && <span className="text-text-tertiary/50">→</span>}
                  </span>
                ))}
              </div>
            </section>

            {/* ── 处理引擎 ── */}
            <section>
              <SectionHeader title="处理引擎" subtitle="语音识别 · 文字识别 · 视频分析 · 图像生成" />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
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
                <ModelCard
                  name="Stable Diffusion"
                  subtitle="图像生成"
                  model="SD WebUI"
                  status={status?.stable_diffusion}
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
  name, subtitle, model, status, isPrimary, badge, extra, location,
}: {
  name: string; subtitle: string; model: string; status?: ServiceStatus
  isPrimary?: boolean; badge?: string; extra?: string; location?: 'local' | 'cloud'
}) {
  const s = status?.status || 'offline'
  const theme = STATUS_THEME[s] || STATUS_THEME.offline

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
