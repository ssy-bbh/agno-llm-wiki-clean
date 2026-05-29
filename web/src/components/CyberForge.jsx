import { useState, useCallback, useEffect, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'

export default function CyberForge({ selectedSandbox, setForgeLogs }) {
  const { apiFetch, token } = useAuth()
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [isForging, setIsForging] = useState(false)
  const [ingestStatus, setIngestStatus] = useState('idle') // idle | ingesting
  const [ingestFileCount, setIngestFileCount] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const sseRef = useRef(null)
  const timerRef = useRef(null)

  // ── 轮询摄入状态 ──
  useEffect(() => {
    if (!selectedSandbox) return
    let alive = true

    const poll = async () => {
      try {
        const res = await apiFetch(`/api/task-logs/${encodeURIComponent(selectedSandbox)}/status`)
        if (!alive) return
        const data = await res.json()
        setIngestStatus(data.status)
        setIngestFileCount(data.files || 0)
        if (data.status === 'ingesting' && data.started) {
          setElapsed(Math.floor(Date.now() / 1000 - data.started))
        } else {
          setElapsed(0)
        }
      } catch {}
    }

    poll()
    const iv = setInterval(poll, 2000)
    return () => { alive = false; clearInterval(iv) }
  }, [selectedSandbox])

  // ── 计时器（摄入中时每秒更新） ──
  useEffect(() => {
    if (ingestStatus !== 'ingesting') {
      if (timerRef.current) clearInterval(timerRef.current)
      return
    }
    timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    return () => clearInterval(timerRef.current)
  }, [ingestStatus])

  // ── SSE 订阅实时日志 ──
  useEffect(() => {
    if (!selectedSandbox || !token) return

    // 关闭旧连接
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
        const entry = JSON.parse(e.data)
        if (entry.message && entry.message !== '── 实时推送中 ──') {
          const level = entry.level || 'info'
          const prefix = level === 'success' ? '✅' : level === 'error' ? '❌' : level === 'warning' ? '⚠️' : ''
          setForgeLogs(prev => [...prev, {
            text: `${entry.time ? `[${entry.time}] ` : ''}${prefix}${entry.message}`,
            level,
          }])

          // 提炼完成时通知图谱刷新
          if (entry.message.includes('提炼完成') || entry.message.includes('全部完成')) {
            window.dispatchEvent(new CustomEvent('KB_PHYSICAL_UPDATE'))
          }
        }
      } catch {}
    }

    es.onerror = () => {
      // EventSource auto-reconnects
    }

    return () => {
      es.close()
      sseRef.current = null
    }
  }, [selectedSandbox, token])

  // ── 上传文件 ──
  const uploadFiles = async (files) => {
    if (!selectedSandbox) {
      setForgeLogs(prev => [...prev, { text: "❌ 请先在左侧选择或新建一个目标沙箱！" }])
      return
    }

    const fileArray = Array.from(files)
    if (fileArray.length === 0) return

    setUploading(true)
    setProgress(10)
    setForgeLogs(prev => [...prev, { text: `📥 收到 ${fileArray.length} 个文件，正在上传至 [${selectedSandbox}]...` }])

    const formData = new FormData()
    formData.append("workspace", selectedSandbox)
    fileArray.forEach(file => formData.append("files", file))

    try {
      setProgress(40)
      const response = await apiFetch("/api/upload", {
        method: "POST",
        body: formData
      })

      if (!response.ok) throw new Error(`上传异常: ${response.status}`)

      setProgress(100)
      setForgeLogs(prev => [...prev, { text: `✅ 文件已落盘，AI 提炼引擎已启动` }])
      setForgeLogs(prev => [...prev, { text: `⏳ 提炼过程在后台运行，下方会实时显示进度。提炼完成后图谱会自动刷新。` }])
      setIngestStatus('ingesting')
      setIngestFileCount(fileArray.length)
      setElapsed(0)
    } catch (err) {
      setForgeLogs(prev => [...prev, { text: `❌ 上传失败: ${err.message}` }])
    } finally {
      setTimeout(() => {
        setUploading(false)
        setProgress(0)
      }, 800)
    }
  }

  // ── 织网操作 ──
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

  return (
    <div className="p-2 space-y-4">
      {/* ── 提炼状态横幅 ── */}
      {ingestStatus === 'ingesting' && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 animate-pulse">
          <div className="flex items-center gap-2">
            <span className="text-lg">⚡</span>
            <div className="flex-1">
              <div className="text-xs font-bold text-amber-400">AI 正在提炼中...</div>
              <div className="text-[10px] text-amber-300/70 font-mono">
                {ingestFileCount} 个文件 · 已耗时 {formatTime(elapsed)} · 可正常使用其他功能
              </div>
            </div>
            <div className="flex gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce" style={{animationDelay: '0ms'}} />
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce" style={{animationDelay: '150ms'}} />
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce" style={{animationDelay: '300ms'}} />
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
        }`}
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
            <div className="text-xs text-cyan-300 font-medium font-mono">INGESTING PHYSICAL KNOWLEDGE...</div>
            <div className="w-full h-1 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-cyan-400 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(progress, 100)}%` }}
              />
            </div>
            <div className="text-[9px] text-slate-500 font-mono">{Math.round(progress)}%</div>
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
          disabled={isForging || uploading}
          className={`py-2 px-2 rounded-lg border text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-all duration-200 ${
            isForging ? 'bg-slate-900 border-slate-800 text-slate-600 cursor-wait' : 'bg-slate-800/40 border-slate-800 text-slate-300 hover:border-red-500/40 hover:text-red-400 shadow-sm'
          }`}
        >
          <span>🕷️</span>
          重织死链
        </button>
        <button
          onClick={() => handleForgeAction('fill_blackhole')}
          disabled={isForging || uploading}
          className={`py-2 px-2 rounded-lg border text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-all duration-200 ${
            isForging ? 'bg-slate-900 border-slate-800 text-slate-600 cursor-wait' : 'bg-slate-800/40 border-slate-800 text-slate-300 hover:border-purple-500/40 hover:text-purple-400 shadow-sm'
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
          <span className={ingestStatus === 'ingesting' ? 'text-amber-400 animate-pulse' : 'text-emerald-400'}>
            {ingestStatus === 'ingesting' ? `⚡ 运行中 (${formatTime(elapsed)})` : '✅ 空闲'}
          </span>
        </div>
      </div>
    </div>
  )
}
