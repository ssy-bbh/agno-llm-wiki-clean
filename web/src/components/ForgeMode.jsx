import { useState } from 'react'
import ForceGraph from './ForceGraph'
import CyberForge from './CyberForge'
import Inbox from './Inbox'
import Radar from './Radar'
import AuditLog from './AuditLog'

export default function ForgeMode({ selectedSandbox }) {
  const [selectedNode, setSelectedNode] = useState(null)

  // 💡 核心新增：统一管理织网熔炉的日志通信状态，完成平级兄弟组件之间的高能握手
  const [forgeLogs, setForgeLogs] = useState([
    { text: "🟢 赛博织网系统控制台就绪。等候熔炉指令..." }
  ])

  return (
    <div className="flex h-full bg-slate-900">
      {/* 左侧 70%: 双链拓扑物理星图画布 */}
      <div className="w-[70%] relative border-r border-slate-800">
        <ForceGraph
          selectedSandbox={selectedSandbox}
          onNodeClick={setSelectedNode}
          selectedNode={selectedNode}
        />
        {selectedNode && (
          <div className="absolute top-4 left-4 glass rounded-xl px-4 py-2 animate-fade-in z-20 bg-slate-900/80 border border-slate-700/50 backdrop-blur-md">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span className="text-sm text-cyan-300 font-mono font-medium">{selectedNode}</span>
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

      {/* 右侧 30%: 赛博白盒中控台 (全部运维面板纵向合流) */}
      <div className="w-[30%] h-full flex flex-col bg-slate-950/40 overflow-y-auto p-4 space-y-6 scrollbar-thin">

        {/* 1. 赛博熔炉 / 摄入流卡片 */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 shadow-xl backdrop-blur-md">
          <div className="text-xs font-semibold text-cyan-400 uppercase tracking-wider mb-3 flex items-center gap-2 font-mono">
            <span>☁️</span> CYBER FORGE / INGEST STREAM
          </div>
          {/* 💡 深度打通：下发选中的局部隔离沙箱名与日志分发挂载器 */}
          <CyberForge selectedSandbox={selectedSandbox} setForgeLogs={setForgeLogs} />
        </div>

        {/* 2. 隔离审批区 / Inbox 卡片 */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 shadow-xl backdrop-blur-md">
          <div className="text-xs font-semibold text-yellow-500 uppercase tracking-wider mb-3 flex items-center gap-2 font-mono">
            <span>✅</span> ISOLATION APPROVAL / INBOX
          </div>
          <Inbox />
        </div>

        {/* 3. 需求雷达 / Radar 卡片 */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 shadow-xl backdrop-blur-md">
          <div className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-3 flex items-center gap-2 font-mono">
            <span>📡</span> REQUIREMENT RADAR / RADAR
          </div>
          <Radar />
        </div>

        {/* 4. 织网档案室 / Audit Log 日志显示 */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 shadow-xl backdrop-blur-md flex-1 min-h-[280px] flex flex-col">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2 font-mono">
            <span>📜</span> WEAVING ARCHIVE / AUDIT LOG
          </div>
          <div className="flex-1 bg-slate-950/90 rounded-lg p-3 font-mono text-[11px] border border-slate-800 overflow-y-auto max-h-[350px]">
            {/* 💡 深度打通：将高能数据管道中接收到的实时日志数组下发 */}
            <AuditLog logs={forgeLogs} />
          </div>
        </div>

      </div>
    </div>
  )
}