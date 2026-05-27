import { useState, useEffect } from 'react'

export default function Sidebar({ mode, onModeChange, selectedSandbox, onSandboxSelect }) {
  const [sandboxes, setSandboxes] = useState([])

  // 💡 将获取沙箱列表的逻辑剥离出来，方便后续复用
  const fetchWorkspaces = () => {
    fetch('/api/workspaces')
      .then(res => res.json())
      .then(data => {
        const formatted = data.map(name => ({
          id: name,
          name: name,
          status: 'active'
        }))
        setSandboxes(formatted)
      })
      .catch(err => console.error("获取工作区失败:", err))
  }

  // 挂载时初始拉取
  useEffect(() => {
    fetchWorkspaces()
  }, [])

  // 💡 新增：创建沙箱的物理指令
  const handleCreateSandbox = async () => {
    const name = window.prompt("🗂️ 请输入新知识沙箱的名称：\n(建议使用英文或无特殊符号的中文，例如 'AI_Papers')")
    if (!name || !name.trim()) return

    try {
      const response = await fetch("/api/workspaces/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() })
      })

      if (!response.ok) {
          const errorData = await response.text()
          throw new Error(`[HTTP ${response.status}] 详情: ${errorData}`)
      }

      // 创建成功后立刻刷新左侧列表
      fetchWorkspaces()
      alert(`✅ 物理沙箱 [${name.trim()}] 开辟成功！请在列表中选中它以批量导入知识。`)
    } catch (err) {
      alert("❌ 创建沙箱失败: " + err.message)
    }
  }

  return (
    <aside className="w-[260px] min-w-[260px] h-screen bg-slate-950/80 border-r border-slate-700/60 flex flex-col relative scanline overflow-hidden">
      {/* Scanline overlay */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-cyan-500/[0.02] to-transparent h-8 animate-scan" />

      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-700/60">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🧠</span>
          <h1 className="text-lg font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent tracking-wide">
            LLM-Wiki OS
          </h1>
        </div>
        <p className="text-[10px] text-slate-500 mt-1 font-mono tracking-widest uppercase">Knowledge Graph Engine</p>
      </div>

      {/* Mode Toggle */}
      <div className="px-4 py-4 border-b border-slate-700/60">
        <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold">运行模式</p>
        <div className="flex rounded-lg bg-slate-800/60 p-1 border border-slate-700/40">
          <button
            onClick={() => onModeChange('query')}
            className={`flex-1 py-1.5 px-2 text-xs rounded-md transition-all duration-200 font-medium ${
              mode === 'query'
                ? 'bg-emerald-500/20 text-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.3)]'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            🗣️ 探求
          </button>
          <button
            onClick={() => onModeChange('forge')}
            className={`flex-1 py-1.5 px-2 text-xs rounded-md transition-all duration-200 font-medium ${
              mode === 'forge'
                ? 'bg-cyan-500/20 text-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.3)]'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            🕸️ 织网
          </button>
        </div>
      </div>

      {/* Workspace Radar */}
      <div className="flex-1 px-4 py-4 overflow-hidden">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold flex items-center gap-2">
            工作区沙箱
            {/* 💡 新建沙箱按钮 */}
            <button
              onClick={handleCreateSandbox}
              className="text-cyan-400 hover:text-cyan-300 bg-slate-800 hover:bg-slate-700 px-1.5 py-0.5 rounded transition-colors text-[9px] border border-slate-600/50"
            >
              + 新建
            </button>
          </p>
          <span className="text-[9px] text-emerald-500/80 font-mono">{sandboxes.length} active</span>
        </div>
        <div className="space-y-1.5 overflow-y-auto max-h-full scrollbar-thin pb-10">
          {sandboxes.map((sb) => (
            <button
              key={sb.id}
              onClick={() => onSandboxSelect(sb.id === selectedSandbox ? null : sb.id)}
              className={`w-full text-left px-3 py-3 rounded-lg border transition-all duration-200 group ${
                sb.id === selectedSandbox
                  ? 'bg-slate-700/40 border-cyan-500/40 glow-cyan'
                  : 'bg-slate-800/30 border-slate-700/30 hover:border-slate-600/50 hover:bg-slate-800/50'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={`text-xs font-mono font-medium truncate pr-2 ${
                  sb.id === selectedSandbox ? 'text-cyan-300' : 'text-slate-300'
                }`}>
                  {sb.name}
                </span>
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                  sb.id === selectedSandbox ? 'bg-cyan-400 animate-pulse shadow-[0_0_5px_rgba(34,211,238,0.8)]' : 'bg-slate-500'
                }`} />
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-700/60">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[10px] text-slate-500 font-mono">v0.1.0 · Online</span>
        </div>

        <div className="mt-3 pt-3 border-t border-slate-800/60 flex items-center gap-2 text-slate-500 hover:text-slate-300 transition-colors cursor-pointer group text-xs">
          <span className="text-sm group-hover:rotate-45 transition-transform duration-300">⚙️</span>
          <span className="font-mono tracking-wider uppercase">SysConfig</span>
        </div>
      </div>
    </aside>
  )
}