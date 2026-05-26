import { useState } from 'react'
import { mockInboxItems } from '../data/mockData'

export default function Inbox() {
  const [items, setItems] = useState(mockInboxItems)
  const [previewing, setPreviewing] = useState(null)

  const handleAction = (id, action) => {
    setItems(prev => prev.filter(item => item.id !== id))
  }

  if (items.length === 0) {
    return (
      <div className="p-6 text-center">
        <div className="text-3xl mb-2 opacity-40">✅</div>
        <p className="text-sm text-slate-500">所有草稿已处理完毕</p>
        <p className="text-[10px] text-slate-600 mt-1">系统将在有新草稿时通知您</p>
      </div>
    )
  }

  return (
    <div className="p-3 space-y-2">
      {/* Warning Header */}
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
        <span className="text-amber-400 animate-pulse">⚠️</span>
        <span className="text-xs text-amber-300 font-medium">{items.length} 项待确认</span>
      </div>

      {/* Items */}
      {items.map(item => (
        <div
          key={item.id}
          className="glass rounded-lg p-3 animate-slide-up transition-all hover:border-slate-600/60"
        >
          {/* Header */}
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
                <span className="text-sm font-medium text-slate-200 font-mono">{item.title}</span>
              </div>
              <p className="text-[10px] text-slate-500 mt-0.5 ml-4">{item.source}</p>
            </div>
          </div>

          {/* Preview panel */}
          {previewing === item.id && (
            <div className="mt-2 p-3 bg-black/40 rounded-lg border border-slate-700/40 text-xs text-slate-400 font-mono leading-relaxed">
              <div className="text-slate-500 text-[10px] mb-1">— 内容预览 —</div>
              <p># {item.title.replace('.md', '')}</p>
              <p className="text-slate-600 mt-1">Abstract: 本文档由系统自动生成，描述核心概念...</p>
              <p className="text-slate-600 mt-0.5">## Key Concepts</p>
              <p className="text-slate-600 ml-2">- 概念 A</p>
              <p className="text-slate-600 ml-2">- 概念 B</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-1.5 mt-3 pt-2 border-t border-slate-700/30">
            <button
              onClick={() => setPreviewing(previewing === item.id ? null : item.id)}
              className="flex-1 py-1.5 rounded-md bg-slate-800/60 border border-slate-700/40 text-[10px] text-slate-400 hover:text-cyan-400 hover:border-cyan-500/30 transition-all font-medium"
            >
              👀 预览
            </button>
            <button
              onClick={() => handleAction(item.id, 'approve')}
              className="flex-1 py-1.5 rounded-md bg-slate-800/60 border border-slate-700/40 text-[10px] text-slate-400 hover:text-emerald-400 hover:border-emerald-500/30 transition-all font-medium"
            >
              ✔️ 入库
            </button>
            <button
              onClick={() => handleAction(item.id, 'reject')}
              className="flex-1 py-1.5 rounded-md bg-slate-800/60 border border-slate-700/40 text-[10px] text-slate-400 hover:text-red-400 hover:border-red-500/30 transition-all font-medium"
            >
              ❌ 废弃
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
