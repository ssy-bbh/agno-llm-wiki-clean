import { useState, useCallback, useEffect, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'

// ── Phase definitions ──
const PHASES = {
  idle:       { label: '空闲',     icon: '💤', color: 'slate' },
  stopping:   { label: '已停止',   icon: '🛑', color: 'red' },
  parsing:    { label: '解析文档', icon: '📄', color: 'blue' },
  extracting: { label: '提取概念', icon: '⚡', color: 'cyan' },
  clustering: { label: '聚类归并', icon: '🔀', color: 'purple' },
  merging:    { label: '融合落盘', icon: '🧠', color: 'emerald' },
  done:       { label: '提炼完成', icon: '✅', color: 'emerald' },
}

const PHASE_ORDER = ['idle', 'stopping', 'parsing', 'extracting', 'clustering', 'merging', 'done']

// Calculate overall percentage from structured progress
function calcPercent(p) {
  if (!p || p.phase === 'idle') return 0
  if (p.phase === 'done') return 100
  if (p.phase === 'stopping') return 0  // 已停止，不显示进度条

  const phaseIdx = PHASE_ORDER.indexOf(p.phase)
  // Phase base percentages: parsing=5, extracting=5-45, clustering=45-55, merging=55-95
  const phaseRanges = {
    parsing:    [2, 8],
    extracting: [8, 45],
    clustering: [45, 55],
    merging:    [55, 95],
  }

  const range = phaseRanges[p.phase]
  if (!range) return 0

  let subProgress = 0
  if (p.phase === 'extracting' && p.total_chunks > 0) {
    subProgress = p.map_done / p.total_chunks
  } else if (p.phase === 'merging' && p.total_concepts > 0) {
    subProgress = p.reduce_done / p.total_concepts
  } else {
    subProgress = 0.5 // indeterminate midpoint
  }

  return Math.min(100, Math.round(range[0] + (range[1] - range[0]) * subProgress))
}

export default function CyberForge({ selectedSandbox, setForgeLogs }) {
  const { apiFetch, token } = useAuth()
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [isForging, setIsForging] = useState(false)
  const [terminating, setTerminating] = useState(false)
  const [resuming, setResuming] = useState(false)
  const [sseKey, setSseKey] = useState(0)  // 强制 SSE 重连

  // ── Ingest progress state ──
  const [ingestStatus, setIngestStatus] = useState('idle')
  const [progress, setProgress] = useState(null) // structured progress from backend
  const [elapsed, setElapsed] = useState(0)
  const [checkpoint, setCheckpoint] = useState(null) // { concepts, files_done, has_checkpoint }

  const sseRef = useRef(null)
  const timerRef = useRef(null)
  // Prevent poll from overwriting optimistic 'ingesting' before backend thread writes status file
  const optimisticUntilRef = useRef(0)
  // Ref to track current ingestStatus for SSE callback (closure captures stale state)
  const ingestStatusRef = useRef('idle')
  // Keep ref in sync with state
  useEffect(() => { ingestStatusRef.current = ingestStatus }, [ingestStatus])

  // ── 切换沙箱时清空所有状态，防止跨沙箱数据串扰 ──
  useEffect(() => {
    setForgeLogs([])
    setIngestStatus('idle')
    setProgress(null)
    setElapsed(0)
    setCheckpoint(null)
    optimisticUntilRef.current = 0
  }, [selectedSandbox])

  // ── Poll status (includes structured progress) ──
  useEffect(() => {
    if (!selectedSandbox) return
    let alive = true

    const poll = async () => {
      try {
        const res = await apiFetch(`/api/task-logs/${encodeURIComponent(selectedSandbox)}/status`)
        if (!alive) return
        const data = await res.json()

        // Stopping state: always accept stopping/idle transitions (bypass optimistic window)
        if (ingestStatus === 'stopping') {
          if (data.status === 'idle') {
            setIngestStatus('idle')
            setProgress(null)  // 清除残留的 phase=done，防止完成卡片遮住暂停卡片
          }
          return
        }

        // Don't let server overwrite optimistic status within the lock window
        if (Date.now() < optimisticUntilRef.current) return
        setIngestStatus(data.status)
        if (data.progress) {
          setProgress(data.progress)
          if (data.progress.started) {
            setElapsed(Math.floor(Date.now() / 1000 - data.progress.started))
          }
        }
        if (data.status !== 'ingesting') {
          setElapsed(0)
        }
      } catch {}
    }

    poll()
    const iv = setInterval(poll, 1500)
    return () => { alive = false; clearInterval(iv) }
  }, [selectedSandbox])

  // ── Poll checkpoint status ──
  useEffect(() => {
    if (!selectedSandbox) return
    let alive = true

    const pollCp = async () => {
      try {
        const res = await apiFetch(`/api/ingest/checkpoint?workspace=${encodeURIComponent(selectedSandbox)}`)
        if (!alive) return
        if (res.ok) {
          const data = await res.json()
          setCheckpoint(data)
        }
      } catch {}
    }

    pollCp()
    const iv = setInterval(pollCp, 5000)
    return () => { alive = false; clearInterval(iv) }
  }, [selectedSandbox])

  // ── Terminate ingest ──
  const handleTerminate = async () => {
    if (!selectedSandbox || terminating) return
    setTerminating(true)
    // 立即切换到 stopping 状态，不等 API 返回
    setIngestStatus('stopping')
    setProgress(null)  // 直接清除进度，进度条立即消失
    optimisticUntilRef.current = Date.now() + 300000  // 5分钟内忽略服务器旧状态
    // 立即关闭 SSE，防止后台线程推送进度事件覆盖 stopping
    if (sseRef.current) {
      sseRef.current.close()
      sseRef.current = null
    }
    try {
      const formData = new FormData()
      formData.append('workspace', selectedSandbox)
      const res = await apiFetch('/api/ingest/terminate', { method: 'POST', body: formData })
      if (res.ok) {
        setForgeLogs(prev => [...prev, { text: '🛑 已停止摄入，已保存检查点', level: 'warning' }])
      } else {
        const err = await res.json().catch(() => ({}))
        setForgeLogs(prev => [...prev, { text: `❌ 终止失败: ${err.detail || res.status}`, level: 'error' }])
      }
    } catch (e) {
      setForgeLogs(prev => [...prev, { text: `❌ 终止请求失败: ${e.message}`, level: 'error' }])
    } finally {
      setTimeout(() => setTerminating(false), 2000)
    }
  }

  // ── Resume ingest (non-blocking: click once, poll in background) ──
  const handleResume = async () => {
    if (!selectedSandbox || resuming) return
    setResuming(true)  // 立即显示"等待停止中..."
    setForgeLogs(prev => [...prev, { text: '⏳ 正在等待后台任务完全停止...', level: 'info' }])

    // 后台轮询，不阻塞 UI
    (async () => {
      try {
        let serverIdle = false
        for (let attempt = 0; attempt < 12; attempt++) {
          const statusRes = await apiFetch(`/api/task-logs/${encodeURIComponent(selectedSandbox)}/status`)
          if (statusRes.ok) {
            const statusData = await statusRes.json()
            if (statusData.status === 'idle') {
              serverIdle = true
              break
            }
          }
          await new Promise(r => setTimeout(r, 5000))
        }

        if (!serverIdle) {
          setForgeLogs(prev => [...prev, { text: '⏳ 后台任务尚未完全停止（可能正在处理长 LLM 调用），请稍后再试', level: 'warning' }])
          setResuming(false)
          return
        }

        const formData = new FormData()
        formData.append('workspace', selectedSandbox)
        const res = await apiFetch('/api/ingest/resume', { method: 'POST', body: formData })
        if (res.ok) {
          const data = await res.json()
          setForgeLogs(prev => [...prev, {
            text: `🔄 继续摄入已启动：${data.files.length} 个文件，${data.checkpoint_concepts} 个概念将从检查点跳过`,
            level: 'info'
          }])
          setIngestStatus('ingesting')
          setProgress({
            phase: 'parsing',
            current_file: 0, total_files: data.files.length,
            current_file_name: '', total_chunks: 0, map_done: 0,
            total_concepts: data.checkpoint_concepts || 0,
            reduce_done: data.checkpoint_concepts || 0,
          })
          setElapsed(0)
          optimisticUntilRef.current = Date.now() + 30000
          setSseKey(k => k + 1)
        } else {
          const err = await res.json().catch(() => ({}))
          setForgeLogs(prev => [...prev, { text: `❌ 继续失败: ${err.detail || res.status}`, level: 'error' }])
        }
      } catch (e) {
        setForgeLogs(prev => [...prev, { text: `❌ 继续请求失败: ${e.message}`, level: 'error' }])
      } finally {
        setResuming(false)
      }
    })()
  }

  // ── Elapsed timer ──
  useEffect(() => {
    if (ingestStatus !== 'ingesting') {
      if (timerRef.current) clearInterval(timerRef.current)
      return
    }
    timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    return () => clearInterval(timerRef.current)
  }, [ingestStatus])

  // ── Auto-dismiss done card after 3s so checkpoint card can show ──
  useEffect(() => {
    if (ingestStatus === 'idle' && progress?.phase === 'done') {
      const timer = setTimeout(() => setProgress(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [ingestStatus, progress?.phase])

  // ── SSE: real-time log + progress events ──
  useEffect(() => {
    if (!selectedSandbox || !token) return

    if (sseRef.current) {
      sseRef.current.close()
      sseRef.current = null
    }

    const url = `/api/task-logs/${encodeURIComponent(selectedSandbox)}/stream?token=${token}`
    const fullUrl = url.startsWith('http') ? url : `${window.location.origin}${url}`
    const es = new EventSource(fullUrl)
    sseRef.current = es

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)

        // Structured progress update
        if (data.type === 'progress') {
          // Stopping 状态：忽略所有进度更新，防止旧线程的 done 事件覆盖停止卡片
          if (ingestStatusRef.current === 'stopping') return
          setProgress({ ...data })
          if (data.started) setElapsed(Math.floor(Date.now() / 1000 - data.started))
          return
        }

        // Regular log entry
        if (data.message && data.message !== '── 实时推送中 ──') {
          const level = data.level || 'info'
          const prefix = level === 'success' ? '✅' : level === 'error' ? '❌' : level === 'warning' ? '⚠️' : ''
          setForgeLogs(prev => [...prev, {
            text: `${data.time ? `[${data.time}] ` : ''}${prefix}${data.message}`,
            level,
          }])

          if (data.message.includes('提炼完成') || data.message.includes('全部完成') || data.message.includes('摄入完毕')) {
            window.dispatchEvent(new CustomEvent('KB_PHYSICAL_UPDATE'))
          }
        }
      } catch {}
    }

    es.onerror = () => {}

    return () => {
      es.close()
      sseRef.current = null
    }
  }, [selectedSandbox, token, sseKey])

  // ── Upload files ──
  const uploadFiles = async (files) => {
    if (!selectedSandbox) {
      setForgeLogs(prev => [...prev, { text: "❌ 请先在左侧选择或新建一个目标沙箱！" }])
      return
    }

    const fileArray = Array.from(files)
    if (fileArray.length === 0) return

    setUploading(true)
    setUploadProgress(10)
    setForgeLogs(prev => [...prev, { text: `📥 收到 ${fileArray.length} 个文件，正在上传至 [${selectedSandbox}]...` }])

    const formData = new FormData()
    formData.append("workspace", selectedSandbox)
    fileArray.forEach(file => formData.append("files", file))

    try {
      setUploadProgress(40)
      const response = await apiFetch("/api/upload", {
        method: "POST",
        body: formData
      })

      if (!response.ok) throw new Error(`上传异常: ${response.status}`)

      setUploadProgress(100)
      setForgeLogs(prev => [...prev, { text: `✅ 文件已落盘，AI 提炼引擎已启动` }])
      // Optimistic: show progress card immediately, protect from poll for 10s
      setIngestStatus('ingesting')
      setElapsed(0)
      optimisticUntilRef.current = Date.now() + 10000
    } catch (err) {
      setForgeLogs(prev => [...prev, { text: `❌ 上传失败: ${err.message}` }])
    } finally {
      setTimeout(() => {
        setUploading(false)
        setUploadProgress(0)
      }, 800)
    }
  }

  // ── Forge actions ──
  const handleForgeAction = async (actionType) => {
    if (isForging) return
    if (!selectedSandbox) {
      setForgeLogs(prev => [...prev, { text: "❌ 请先在左侧选择目标沙箱！" }])
      return
    }

    setIsForging(true)
    setForgeLogs(prev => [...prev, { text: `🔥 正在执行 [${actionType}]...` }])

    try {
      const response = await apiFetch('/api/forge', {
        method: 'POST',
        body: JSON.stringify({ action: actionType, workspace: selectedSandbox })
      })

      if (!response.ok) throw new Error(`后端无响应: ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (value) buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        if (!done) buffer = parts.pop() || ''

        for (const line of parts) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '')
            if (!dataStr.trim()) continue
            try {
              const data = JSON.parse(dataStr)
              if (data.type === 'log') {
                setForgeLogs(prev => [...prev, { text: data.content }])
              }
            } catch {}
          }
        }
        if (done) break
      }

      window.dispatchEvent(new CustomEvent('KB_PHYSICAL_UPDATE'))

    } catch (err) {
      setForgeLogs(prev => [...prev, { text: `💥 操作失败: ${err.message}` }])
    } finally {
      setIsForging(false)
    }
  }

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      uploadFiles(e.target.files)
    }
  }

  const formatTime = (s) => {
    if (s < 60) return `${s}s`
    return `${Math.floor(s / 60)}m ${s % 60}s`
  }

  const isIng = ingestStatus === 'ingesting'
  const phase = progress?.phase || (isIng ? 'parsing' : 'idle')
  const phaseInfo = PHASES[phase] || PHASES.idle
  const percent = calcPercent(progress)

  return (
    <div className="p-2 space-y-4">
      {/* ══════════════════════════════════════════
          🔥 提炼进度可视化卡片
          ══════════════════════════════════════════ */}
      {isIng && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden">
          {/* ── 顶部：阶段 + 计时 ── */}
          <div className="px-4 pt-3 pb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl">{phaseInfo.icon}</span>
              <div>
                <div className="text-sm font-bold text-slate-200">
                  {phaseInfo.label}
                  {phase === 'done' ? '' : ' 中...'}
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  {progress?.current_file_name && (
                    <span className="text-cyan-400/80">📄 {progress.current_file_name}</span>
                  )}
                  {!progress?.current_file_name && progress?.current_file > 0 && (
                    <span>文件 {progress.current_file}/{progress.total_files}</span>
                  )}
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-lg font-mono font-bold text-cyan-400">{percent}%</div>
              <div className="text-[10px] text-slate-500 font-mono">{formatTime(elapsed)}</div>
            </div>
          </div>

          {/* ── 进度条 ── */}
          <div className="px-4 pb-2">
            <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ease-out ${
                  phase === 'done'
                    ? 'bg-gradient-to-r from-emerald-500 to-green-400'
                    : 'bg-gradient-to-r from-cyan-500 via-blue-500 to-purple-500'
                }`}
                style={{ width: `${percent}%` }}
              />
            </div>
          </div>

          {/* ── 阶段指示器 ── */}
          <div className="px-4 pb-3">
            <div className="flex items-center justify-between">
              {PHASE_ORDER.filter(p => p !== 'idle' && p !== 'stopping' && p !== 'done').map((p, i) => {
                const info = PHASES[p]
                const phaseIdx = PHASE_ORDER.indexOf(p)
                const currentIdx = PHASE_ORDER.indexOf(phase)
                const isPast = phaseIdx < currentIdx || phase === 'done'
                const isCurrent = p === phase
                const isFuture = phaseIdx > currentIdx && phase !== 'done'

                return (
                  <div key={p} className="flex items-center flex-1 last:flex-none">
                    <div className="flex flex-col items-center">
                      <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs transition-all duration-300 ${
                        isPast ? 'bg-emerald-500/20 border border-emerald-500/50 text-emerald-400' :
                        isCurrent ? 'bg-cyan-500/20 border border-cyan-400/60 text-cyan-300 shadow-[0_0_8px_rgba(34,211,238,0.3)]' :
                        'bg-slate-800/50 border border-slate-700/40 text-slate-600'
                      }`}>
                        {isPast ? '✓' : info.icon}
                      </div>
                      <span className={`text-[9px] mt-0.5 font-mono ${
                        isCurrent ? 'text-cyan-400' : isPast ? 'text-emerald-500/70' : 'text-slate-600'
                      }`}>{info.label}</span>
                    </div>
                    {i < 3 && (
                      <div className={`flex-1 h-px mx-1 mt-[-10px] ${
                        isPast ? 'bg-emerald-500/40' : 'bg-slate-800'
                      }`} />
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* ── 统计行 ── */}
          <div className="px-4 pb-3 grid grid-cols-3 gap-2 text-center">
            <div className="bg-slate-950/50 rounded-lg py-1.5 px-2">
              <div className="text-[9px] text-slate-500 font-mono">文件</div>
              <div className="text-xs font-mono text-slate-300">
                <span className="text-cyan-400">{progress?.current_file || 0}</span>
                <span className="text-slate-600">/{progress?.total_files || 0}</span>
              </div>
            </div>
            <div className="bg-slate-950/50 rounded-lg py-1.5 px-2">
              <div className="text-[9px] text-slate-500 font-mono">概念</div>
              <div className="text-xs font-mono text-slate-300">
                <span className="text-purple-400">{progress?.reduce_done || 0}</span>
                <span className="text-slate-600">/{progress?.total_concepts || 0}</span>
              </div>
            </div>
            <div className="bg-slate-950/50 rounded-lg py-1.5 px-2">
              <div className="text-[9px] text-slate-500 font-mono">耗时</div>
              <div className="text-xs font-mono text-amber-400">{formatTime(elapsed)}</div>
            </div>
          </div>

          {/* ── 终止按钮 ── */}
          <div className="px-4 pb-3">
            <button
              onClick={handleTerminate}
              disabled={terminating}
              className={`w-full py-2 rounded-lg border text-xs font-mono font-medium flex items-center justify-center gap-2 transition-all duration-200 ${
                terminating
                  ? 'bg-red-900/30 border-red-800/50 text-red-500/60 cursor-wait'
                  : 'bg-red-950/40 border-red-800/40 text-red-400 hover:bg-red-900/40 hover:border-red-600/60 hover:shadow-[0_0_12px_rgba(239,68,68,0.15)]'
              }`}
            >
              {terminating ? (
                <><span className="animate-spin">⏳</span> 正在终止...</>
              ) : (
                <><span>⏹</span> 终止摄入</>
              )}
            </button>
          </div>

        </div>
      )}

      {/* ── 已停止状态卡片（后台可能仍在运行）── */}
      {ingestStatus === 'stopping' && (
        <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">🛑</span>
            <div className="flex-1">
              <div className="text-xs font-bold text-red-400">
                {resuming ? '等待后台完全停止...' : '摄入已停止'}
              </div>
              <div className="text-[10px] text-red-300/60 font-mono">
                已处理的概念已保存检查点，可点击继续
              </div>
            </div>
          </div>
          <button
            onClick={handleResume}
            disabled={resuming}
            className={`w-full py-1.5 rounded-lg border text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-all duration-200 ${
              resuming
                ? 'bg-emerald-900/30 border-emerald-800/50 text-emerald-500/60 cursor-wait'
                : 'bg-emerald-950/40 border-emerald-700/40 text-emerald-400 hover:bg-emerald-900/40 hover:border-emerald-600/60'
            }`}
          >
            {resuming ? (
              <><span className="animate-spin">⏳</span> 等待停止中...</>
            ) : (
              <><span>▶</span> 继续摄入</>
            )}
          </button>
        </div>
      )}

      {/* ── 完成状态卡片（有 checkpoint 时不显示，避免打架）── */}
      {ingestStatus === 'idle' && progress?.phase === 'done' && !checkpoint?.has_checkpoint && (
        <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3">
          <div className="flex items-center gap-2">
            <span className="text-lg">✅</span>
            <div className="flex-1">
              <div className="text-xs font-bold text-emerald-400">提炼完成</div>
              <div className="text-[10px] text-emerald-300/60 font-mono">
                {progress.total_concepts} 个概念已落盘 · 耗时 {formatTime(elapsed)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── 检查点继续摄入卡片（概念级断点）── */}
      {ingestStatus === 'idle' && checkpoint?.has_checkpoint && (
        <div className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">📌</span>
            <div className="flex-1">
              <div className="text-xs font-bold text-amber-400">上次摄入未完成</div>
              <div className="text-[10px] text-amber-300/60 font-mono">
                已融合 {checkpoint.concepts} 个概念（REDUCE 断点，继续时将跳过）
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleResume}
              disabled={resuming}
              className={`flex-1 py-1.5 rounded-lg border text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-all duration-200 ${
                resuming
                  ? 'bg-emerald-900/30 border-emerald-800/50 text-emerald-500/60 cursor-wait'
                  : 'bg-emerald-950/40 border-emerald-700/40 text-emerald-400 hover:bg-emerald-900/40 hover:border-emerald-600/60'
              }`}
            >
              {resuming ? (
                <><span className="animate-spin">⏳</span> 等待停止中...</>
              ) : (
                <><span>▶</span> 继续摄入</>
              )}
            </button>
            <button
              onClick={async () => {
                if (!selectedSandbox) return
                try {
                  const formData = new FormData()
                  formData.append('workspace', selectedSandbox)
                  await apiFetch('/api/ingest/clear-checkpoint', { method: 'POST', body: formData })
                  setCheckpoint(null)
                  setForgeLogs(prev => [...prev, { text: '🗑️ 检查点已清除，下次摄入将从头开始', level: 'info' }])
                } catch {}
              }}
              className="py-1.5 px-3 rounded-lg border text-xs font-mono border-slate-800 text-slate-500 hover:border-slate-700 hover:text-slate-400 transition-all"
              title="清除检查点，下次从头开始"
            >
              🗑️
            </button>
          </div>
        </div>
      )}

      {/* Upload Zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if(e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            uploadFiles(e.dataTransfer.files)
          }
        }}
        onClick={() => document.getElementById('forge-file-picker').click()}
        className={`border-2 border-dashed rounded-xl p-5 text-center transition-all duration-300 cursor-pointer ${
          dragOver
            ? 'border-cyan-400 bg-cyan-500/10 shadow-[0_0_12px_rgba(34,211,238,0.15)]'
            : 'border-slate-800 hover:border-slate-700 bg-slate-950/20'
        } ${isIng ? 'opacity-50 pointer-events-none' : ''}`}
      >
        <input
          type="file"
          id="forge-file-picker"
          className="hidden"
          multiple
          onChange={handleFileChange}
          accept=".md,.txt,.pdf"
        />
        {uploading ? (
          <div className="space-y-3">
            <div className="text-xl animate-bounce text-cyan-400">⚡</div>
            <div className="text-xs text-cyan-300 font-medium font-mono">UPLOADING...</div>
            <div className="w-full h-1 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-cyan-400 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(uploadProgress, 100)}%` }}
              />
            </div>
            <div className="text-[9px] text-slate-500 font-mono">{Math.round(uploadProgress)}%</div>
          </div>
        ) : (
          <>
            <div className="text-2xl mb-1 opacity-70">🕸️</div>
            <div className="text-xs text-slate-400 font-medium">拖拽或点击投入物理知识资产</div>
            <div className="text-[9px] text-slate-600 mt-0.5 font-mono">SUPPORT BATCH: PDF / Markdown / TXT</div>
          </>
        )}
      </div>

      {/* Action Buttons */}
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => handleForgeAction('reweave')}
          disabled={isForging || uploading || isIng}
          className={`py-2 px-2 rounded-lg border text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-all duration-200 ${
            isForging || isIng ? 'bg-slate-900 border-slate-800 text-slate-600 cursor-wait' : 'bg-slate-800/40 border-slate-800 text-slate-300 hover:border-red-500/40 hover:text-red-400 shadow-sm'
          }`}
        >
          <span>🕷️</span>
          重织死链
        </button>
        <button
          onClick={() => handleForgeAction('fill_blackhole')}
          disabled={isForging || uploading || isIng}
          className={`py-2 px-2 rounded-lg border text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-all duration-200 ${
            isForging || isIng ? 'bg-slate-900 border-slate-800 text-slate-600 cursor-wait' : 'bg-slate-800/40 border-slate-800 text-slate-300 hover:border-purple-500/40 hover:text-purple-400 shadow-sm'
          }`}
        >
          <span>🪄</span>
          填补黑洞
        </button>
      </div>

      {/* Status */}
      <div className="bg-slate-950/60 border border-slate-900 rounded-lg p-2.5 font-mono text-[10px] space-y-1 text-slate-400">
        <div className="flex items-center justify-between">
          <span className="text-slate-500">沙箱:</span>
          <span className="text-cyan-400">{selectedSandbox ? `[${selectedSandbox}]` : "未选定"}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-500">提炼引擎:</span>
          <span className={isIng ? 'text-amber-400 animate-pulse' : 'text-emerald-400'}>
            {isIng ? `⚡ ${phaseInfo.label}中` : '✅ 空闲'}
          </span>
        </div>
      </div>
    </div>
  )
}
