import { mockAuditLogs } from '../data/mockData'

export default function AuditLog() {
  return (
    <div className="p-3">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/40 border border-slate-700/40 mb-3">
        <span className="text-slate-400">📜</span>
        <div>
          <p className="text-xs text-slate-300 font-medium">织网档案室</p>
          <p className="text-[10px] text-slate-500">操作审计日志 · 持久化记录</p>
        </div>
      </div>

      {/* Logs */}
      <div className="space-y-1">
        {mockAuditLogs.map(log => (
          <div
            key={log.id}
            className="px-3 py-2 rounded-lg bg-black/30 border border-slate-800/40 font-mono text-[11px] hover:bg-black/40 transition-all"
          >
            <div className="flex items-start gap-2">
              <span className="text-slate-600 shrink-0">{log.time}</span>
              <span className={`shrink-0 ${log.type === 'human' ? 'text-emerald-500/80' : 'text-cyan-500/80'}`}>
                {log.type === 'human' ? '👤' : '🤖'}
              </span>
              <span className="text-slate-300">
                <span className={log.type === 'human' ? 'text-emerald-400/80' : 'text-cyan-400/80'}>
                  {log.user}
                </span>
                {' '}{log.action}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Bottom indicator */}
      <div className="mt-3 flex items-center justify-center gap-2 text-[10px] text-slate-600">
        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/60 animate-pulse" />
        <span>日志实时同步中</span>
      </div>
    </div>
  )
}
