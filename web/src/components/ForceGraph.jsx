import { useRef, useEffect, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'

export default function ForceGraph({ selectedSandbox, onNodeClick, selectedNode }) {
  const fgRef = useRef()
  const [graphData, setGraphData] = useState({ nodes: [], links: [] })

  // 获取数据
  useEffect(() => {
    if (!selectedSandbox) {
      setGraphData({ nodes: [], links: [] })
      return
    }

    fetch(`http://127.0.0.1:8888/api/graph?workspace=${selectedSandbox}`)
      .then(res => res.json())
      .then(data => {
        // 终极防线：收集所有真实存在的节点 ID
        const validNodeIds = new Set(data.nodes.map(n => n.id))

        // 把那些指向了“不存在的节点”的幽灵连线全部过滤掉！
        const safeLinks = data.links.filter(link =>
          validNodeIds.has(link.source) && validNodeIds.has(link.target)
        )

        // 只把安全的线交给物理引擎
        setGraphData({ nodes: data.nodes, links: safeLinks })
      })
      .catch(err => console.error("星图获取失败:", err))
  }, [selectedSandbox])

  return (
    <div className="w-full h-full bg-[#020617] relative overflow-hidden">
      {graphData.nodes.length === 0 ? (
        <div className="absolute inset-0 flex items-center justify-center text-slate-500 font-mono text-sm">
          {!selectedSandbox ? "👈 请在左侧选择一个知识沙箱" : "🌌 正在扫描星图数据或沙箱为空..."}
        </div>
      ) : (
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          nodeRelSize={5}

          // 💡 视觉优化 1：为节点添加多彩着色逻辑
          // 如果节点数据里未来有 'group'（组）或 'type'（类型），我们可以动态着色
          // 这里我们假定不同的 group 对应不同颜色，如果没有 group 则用默认颜色
          // 如果想立刻看到效果，可以修改 nodeCanvasObjectMode 为 'replace'，
          // 并自己用 canvas 绘制不同颜色的圆点。
          nodeColor={(node) => {
            // 选定节点：白色
            if (node.id === selectedNode) return '#ffffff';

            // 示例：根据不同 group 分配不同科幻色 (f87171, 60a5fa, c084fc, fb923c, a3e635, 0ea5e9)
            if (node.group === 1) return '#f87171'; // 红色
            if (node.group === 2) return '#60a5fa'; // 蓝色
            if (node.group === 3) return '#c084fc'; // 紫色
            if (node.group === 4) return '#fb923c'; // 橙色
            if (node.group === 5) return '#a3e635'; // 绿色

            // 默认颜色：青色
            return '#0ea5e9';
          }}

          // 💡 视觉优化 2：更改连线颜色和透明度
          linkColor={() => 'rgba(203, 213, 225, 0.15)'} // 极轻柔的暗青色连线
          linkWidth={1}

          nodeCanvasObjectMode={() => 'after'}
          nodeCanvasObject={(node, ctx, globalScale) => {
            if (globalScale >= 2) {
              const label = node.id
              const fontSize = 12 / globalScale
              ctx.font = `${fontSize}px "Fira Code", monospace`
              ctx.textAlign = 'center'
              ctx.textBaseline = 'middle'
              ctx.fillStyle = '#cbd5e1'
              ctx.fillText(label, node.x, node.y + 6 + fontSize)
            }
          }}

          onNodeClick={node => {
            fgRef.current.centerAt(node.x, node.y, 1000)
            fgRef.current.zoom(4, 1000)
            if (onNodeClick) onNodeClick(node.id)
          }}
          enableNodeDrag={true}
        />
      )}
    </div>
  )
}