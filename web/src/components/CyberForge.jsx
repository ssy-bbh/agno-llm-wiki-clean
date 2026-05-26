import { useState, useCallback } from 'react'

export default function CyberForge() {
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)

  const simulateUpload = useCallback(() => {
    setUploading(true)
    setProgress(0)
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval)
          setUploading(false)
          return 100
        }
        return prev + Math.random() * 15
      })
    }, 300)
  }, [])

  return (
    <div className="p-4 space-y-4">
      {/* Upload Zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); simulateUpload() }}
        className={`border-2 border-dashed rounded-xl p-6 text-center transition-all duration-300 cursor-pointer ${
          dragOver
            ? 'border-cyan-400/60 bg-cyan-500/10'
            : 'border-slate-700/50 hover:border-slate-600/50 bg-slate-800/20'
        }`}
        onClick={simulateUpload}
      >
        {uploading ? (
          <div className="space-y-3">
            <div className="text-2xl animate-pulse">⚡</div>
            <div className="text-sm text-cyan-300 font-medium">正在摄入知识...</div>
            <div className="w-full h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-cyan-400 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(progress, 100)}%` }}
              />
            </div>
            <div className="text-[10px] text-slate-500 font-mono">{Math.min(Math.round(progress), 100)}%</div>
          </div>
        ) : (
          <>
            <div className="text-3xl mb-2 opacity-60">🕸️</div>
            <div className="text-sm text-slate-400 font-medium">拖拽文件至此处</div>
            <div className="text-[10px] text-slate-600 mt-1">或点击选择 · PDF / Markdown / TXT</div>
          </>
        )}
      </div>

      {/* Action Buttons */}
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => {}}
          className="py-2.5 px-3 rounded-lg bg-slate-800/50 border border-slate-700/40 text-xs text-slate-300 hover:border-red-500/40 hover:text-red-400 transition-all font-medium flex items-center justify-center gap-1.5 group"
        >
          <span className="group-hover:animate-pulse">🕷️</span>
          重织死链
        </button>
        <button
          onClick={() => {}}
          className="py-2.5 px-3 rounded-lg bg-slate-800/50 border border-slate-700/40 text-xs text-slate-300 hover:border-purple-500/40 hover:text-purple-400 transition-all font-medium flex items-center justify-center gap-1.5 group"
        >
          <span className="group-hover:animate-pulse">🪄</span>
          填补黑洞
        </button>
      </div>

      {/* Status */}
      <div className="glass rounded-lg p-3">
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-slate-500">最近摄入</span>
          <span className="text-slate-400 font-mono">2026-05-26 09:42</span>
        </div>
        <div className="flex items-center justify-between text-[10px] mt-1.5">
          <span className="text-slate-500">提取概念</span>
          <span className="text-emerald-400 font-mono">12 个</span>
        </div>
        <div className="flex items-center justify-between text-[10px] mt-1.5">
          <span className="text-slate-500">合并同义词</span>
          <span className="text-amber-400 font-mono">3 对</span>
        </div>
      </div>
    </div>
  )
}
