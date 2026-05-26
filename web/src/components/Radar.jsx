import { mockRadarItems } from '../data/mockData'

export default function Radar() {
  return (
    <div className="p-3 space-y-2">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/40 border border-slate-700/40">
        <span className="text-slate-400">📡</span>
        <div>
          <p className="text-xs text-slate-300 font-medium">需求雷达</p>
          <p className="text-[10px] text-slate-500">用户搜索落空记录 · 待补全的概念</p>
        </div>
      </div>

      {/* Items */}
      {mockRadarItems.map(item => {
        const pct = Math.round((item.count / item.total) * 100)
        const isCritical = item.count >= item.total
        const color = isCritical ? 'red' : item.color
        const borderColor = color === 'red' ? 'border-red-500/30' : 'border-yellow-500/20'
        const dotColor = color === 'red' ? 'bg-red-400' : 'bg-yellow-400'
        const textColor = color === 'red' ? 'text-red-300' : 'text-yellow-300'

        return (
          <div
            key={item.id}
            className={`glass rounded-lg p-3 border-l-2 ${borderColor} hover:bg-slate-800/40 transition-all cursor-pointer group`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${dotColor} ${isCritical ? 'animate-pulse' : ''}`} />
                <span className={`text-sm font-mono font-medium ${textColor}`}>
                  [{item.term}]
                </span>
              </div>
              <span className="text-[10px] text-slate-500 font-mono">{item.count}/{item.total}</span>
            </div>

            {/* Progress bar */}
            <div className="mt-2 w-full h-1 bg-slate-700/50 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  isCritical ? 'bg-red-500/60' : 'bg-yellow-500/40'
                }`}
                style={{ width: `${pct}%` }}
              />
            </div>

            {/* Action hint */}
            <div className="mt-1.5 text-[10px] text-slate-600 group-hover:text-slate-400 transition-colors">
              {isCritical ? '🔴 已达阈值 · 建议立即补全' : '🟡 持续出现 · 考虑创建页面'}
            </div>
          </div>
        )
      })}

      {/* Summary */}
      <div className="mt-3 px-3 py-2 rounded-lg bg-slate-800/30 border border-slate-700/30">
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-slate-500">总监控词数</span>
          <span className="text-slate-300 font-mono">{mockRadarItems.length}</span>
        </div>
        <div className="flex items-center justify-between text-[10px] mt-1">
          <span className="text-slate-500">已达阈值</span>
          <span className="text-red-400 font-mono">
            {mockRadarItems.filter(i => i.count >= i.total).length}
          </span>
        </div>
      </div>
    </div>
  )
}
