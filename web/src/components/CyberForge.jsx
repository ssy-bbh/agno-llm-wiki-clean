import { useState, useCallback } from 'react'

export default function CyberForge({ selectedSandbox, setForgeLogs }) {
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [isForging, setIsForging] = useState(false)

  // 💡 升级为支持数组的批量上传函数
  const uploadFiles = async (files) => {
    if (!selectedSandbox) {
      setForgeLogs(prev => [...prev, { text: "❌ 物理摄入失败：请先在左侧选择或新建一个目标沙箱！" }])
      return
    }

    const fileArray = Array.from(files)
    if (fileArray.length === 0) return

    setUploading(true)
    setProgress(10)
    setForgeLogs(prev => [...prev, { text: `📥 [批量摄入流] 收到 ${fileArray.length} 个实体文件，正在注入沙箱 [${selectedSandbox}]...` }])

    const formData = new FormData()
    formData.append("workspace", selectedSandbox)

    // 💡 核心：把多个文件都挂载到 "files" 这个键名下
    fileArray.forEach(file => {
      formData.append("files", file)
    })

    try {
      setProgress(40)
      const response = await fetch("http://127.0.0.1:8888/api/upload", {
        method: "POST",
        body: formData
      })

      if (!response.ok) throw new Error(`落盘响应异常: ${response.status}`)

      setProgress(100)
      setForgeLogs(prev => [...prev, { text: `✅ [落盘成功] ${fileArray.length} 份原始语料已物理归档至 data/raw/${selectedSandbox}/ 目录下。` }])
      setForgeLogs(prev => [...prev, { text: `🔥 [熔炉点火] 后台已自动开启排队队列，大模型正逐个进行降维提取...` }])
      setForgeLogs(prev => [...prev, { text: `⏳ (可前往后端终端查看提炼进度，全部完成后刷新沙箱即可)` }])
    } catch (err) {
      setForgeLogs(prev => [...prev, { text: `❌ [物理阻断] 摄入流强制切断: ${err.message}` }])
    } finally {
      setTimeout(() => {
        setUploading(false)
        setProgress(0)
      }, 800)
    }
  }

  // 💡 真实联动后端流式清洗脚本的动作引擎
  const handleForgeAction = async (actionType) => {
    if (isForging) return
    if (!selectedSandbox) {
      setForgeLogs(prev => [...prev, { text: "❌ 熔炉死锁：必须在左侧指定具体的隔离沙箱环境才能清洗拓扑！" }])
      return
    }

    setIsForging(true)
    setForgeLogs(prev => [...prev, { text: `🔥 [熔炉点火] 正在建立与后端织网任务 [${actionType}] 的数据链...` }])

    try {
      const response = await fetch('http://127.0.0.1:8888/api/forge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: actionType, workspace: selectedSandbox })
      })

      if (!response.ok) throw new Error(`后端网关无响应: ${response.status}`)

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
            } catch (err) {}
          }
        }
        if (done) break
      }

      // 🚀🚀🚀 核心改动：流式任务结束，朝天鸣枪，通知 Radar 和 Inbox 立刻刷新！ 🚀🚀🚀
      window.dispatchEvent(new CustomEvent('KB_PHYSICAL_UPDATE'))

    } catch (err) {
      setForgeLogs(prev => [...prev, { text: `💥 熔炉异常断开: ${err.message}` }])
    } finally {
      setIsForging(false)
    }
  }

  // 触发点击文件框批量上传
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      uploadFiles(e.target.files)
    }
  }

  return (
    <div className="p-2 space-y-4">
      {/* Upload Zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if(e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            uploadFiles(e.dataTransfer.files) // 💡 传入整个文件集合，支持批量拖拽
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
          multiple // 💡 开启多选能力
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

      {/* Real Real-time Status */}
      <div className="bg-slate-950/60 border border-slate-900 rounded-lg p-2.5 font-mono text-[10px] space-y-1 text-slate-400">
        <div className="flex items-center justify-between">
          <span className="text-slate-500">沙箱锚定坐标:</span>
          <span className="text-cyan-400">{selectedSandbox ? `[${selectedSandbox}]` : "未选定"}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-500">落盘物理仓位:</span>
          <span className="text-slate-400">data/raw/.../</span>
        </div>
      </div>
    </div>
  )
}