import { useState } from 'react'
import ForceGraph from './ForceGraph'
import CyberForge from './CyberForge'
import Inbox from './Inbox'
import Radar from './Radar'
import AuditLog from './AuditLog'

// 💡 修复 1：在组件参数里接收 selectedSandbox
export default function ForgeMode({ selectedSandbox }) {
  const [selectedNode, setSelectedNode] = useState(null)

  return (
    <div className="flex h-full bg-slate-900">
      <div className="w-[70%] relative border-r border-slate-800">
        {/* 💡 修复 2：把 selectedSandbox 继续传给底层的星图组件 */}
        <ForceGraph
          selectedSandbox={selectedSandbox}
          onNodeClick={setSelectedNode}
          selectedNode={selectedNode}
        />
        {selectedNode && (
          <div className="absolute top-4 left-4 glass rounded-xl px-4 py-2 animate-fade-in z-20">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span className="text-sm text-cyan-300 font-medium">{selectedNode}</span>
              <button
                onClick={() => setSelectedNode(null)}
                className="ml-2 text-slate-500 hover:text-slate-300 text-xs"
              >
                ✕
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 右侧 30%: 赛博白盒中控台 (全部模块同时展现，支持内部纵向滚动) */}
      <div className="w-[30%] h-full flex flex-col bg-slate-950/40 overflow-y-auto p-4 space-y-6 scrollbar-thin">
        {/* 1. 赛博熔炉卡片 */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 shadow-xl backdrop-blur-md">
          <div className="text-xs font-semibold text-cyan-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <span>☁️</span> 赛博熔炉 / 摄入流
          </div>
          <CyberForge />
        </div>

        {/* 2. 隔离审批区 */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 shadow-xl backdrop-blur-md">
          <div className="text-xs font-semibold text-yellow-500 uppercase tracking-wider mb-3 flex items-center gap-2">
            <span>✅</span> 隔离审批区 / Inbox
          </div>
          <Inbox />
        </div>

        {/* 3. 需求雷达 */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 shadow-xl backdrop-blur-md">
          <div className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <span>📡</span> 外部需求雷达 / Radar
          </div>
          <Radar />
        </div>

        {/* 4. 织网档案室 */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 shadow-xl backdrop-blur-md flex-1 min-h-[250px] flex flex-col">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <span>📜</span> 织网档案室 / Audit Log
          </div>
          <div className="flex-1 bg-black/20 rounded-lg p-2 font-mono text-[11px]">
            <AuditLog />
          </div>
        </div>
      </div>
    </div>
  )
}