import { useState, useCallback, useEffect, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'

// ── Phase definitions ──
const PHASES = {
  idle:       { label: '空闲',     icon: '💤', color: 'slate' },
  parsing:    { label: '解析文档', icon: '📄', color: 'blue' },
  extracting: { label: '提取概念', icon: '⚡', color: 'cyan' },
  clustering: { label: '聚类归并', icon: '🔀', color: 'purple' },
  merging:    { label: '融合落盘', icon: '🧠', color: 'emerald' },
  done:       { label: '提炼完成', icon: '✅', color: 'emerald' },
}

const PHASE_ORDER = ['idle', 'parsing', 'extracting', 'clustering', 'merging', 'done']

// Calculate overall percentage from structured progress
function calcPercent(p) {
  if (!p || p.phase === 'idle') return 0
  if (p.phase === 'done') return 100

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

  return Math.round(range[0] + (range[1] - range[0]) * subProgress)
}

export default function CyberForge({ selectedSandbox, setForgeLogs }) {
  const { apiFetch, token } = useAuth()
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [isForging, setIsForging] = useState(false)

  // ── Ingest progress state ──
  const [ingestStatus, setIngestStatus] = useState('idle')
  const [progress, setProgress] = useState(null) // structured progress from backend
  const [elapsed, setElapsed] = useState(0)

  const sseRef = useRef(null)
  const timerRef = useRef(null)

  // ── Poll status (includes structured progress) ──
  useEffect(() => {
    if (!selectedSandbox) return
    let alive = true

    const poll = async () => {
      try {
        const res = await apiFetch(`/api/task-logs/${encodeURIComponent(selectedSandbox)}/status`)
        if (!alive) return
        const data = await res.json()
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

  // ── Elapsed timer ──
  useEffect(() => {
    if (ingestStatus !== 'ingesting') {
      if (timerRef.current) clearInterval(timerRef.current)
      return
    }
    timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    return () => clearInterval(timerRef.current)
  }, [ingestStatus])

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
  }, [selectedSandbox, token])

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
      setIngestStatus('ingesting')
      setElapsed(0)
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
              {PHASE_ORDER.filter(p => p !== 'idle' && p !== 'done').map((p, i) => {
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

        </div>
      )}

      {/* ── 完成状态卡片 ── */}
      {ingestStatus === 'idle' && progress?.phase === 'done' && (
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
