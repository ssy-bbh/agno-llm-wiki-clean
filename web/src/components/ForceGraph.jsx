import { useRef, useCallback, useEffect, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { mockGraphNodes, mockGraphLinks } from '../data/mockData'

const NODE_COLORS = {
  core: '#10b981',      // emerald
  model: '#06b6d4',     // cyan
  training: '#f59e0b',  // amber
  architecture: '#a855f7', // purple
}

const GROUP_LABELS = {
  core: '核心概念',
  model: '模型',
  training: '训练方法',
  architecture: '架构',
}

export default function ForceGraph({ onNodeClick, selectedNode }) {
  const fgRef = useRef()
  const [graphData, setGraphData] = useState({ nodes: mockGraphNodes, links: mockGraphLinks })
  const [hoveredNode, setHoveredNode] = useState(null)

  // Highlight selected node
  useEffect(() => {
    if (!fgRef.current || !selectedNode) return
    const node = graphData.nodes.find(n => n.id === selectedNode)
    if (node) {
      fgRef.current.centerAt(node.x, node.y, 500)
      fgRef.current.zoom(3, 500)
    }
  }, [selectedNode])

  const handleNodeClick = useCallback((node) => {
    onNodeClick?.(node.id)
  }, [onNodeClick])

  const handleNodeHover = useCallback((node) => {
    setHoveredNode(node?.id || null)
    const canvas = fgRef.current?.canvas()
    if (canvas) {
      canvas.style.cursor = node ? 'pointer' : 'default'
    }
  }, [])

  const paintNode = useCallback((node, ctx) => {
    const color = NODE_COLORS[node.group] || '#94a3b8'
    const isHighlighted = node.id === selectedNode || node.id === hoveredNode
    const radius = isHighlighted ? node.val * 0.8 + 4 : node.val * 0.7

    // Glow effect
    if (isHighlighted) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, radius + 8, 0, 2 * Math.PI, false)
      ctx.fillStyle = color + '20'
      ctx.fill()
    }

    // Node circle
    ctx.beginPath()
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false)
    ctx.fillStyle = color + (isHighlighted ? 'dd' : 'aa')
    ctx.fill()

    // Border
    ctx.strokeStyle = color
    ctx.lineWidth = isHighlighted ? 2 : 1
    ctx.stroke()

    // Label
    ctx.fillStyle = isHighlighted ? '#f1f5f9' : '#94a3b8'
    ctx.font = `${isHighlighted ? '600' : '400'} ${isHighlighted ? 13 : 11}px Inter, sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(node.label, node.x, node.y + radius + 14)
  }, [selectedNode, hoveredNode])

  return (
    <div className="w-full h-full bg-slate-950 relative">
      {/* Grid background */}
      <div className="absolute inset-0 opacity-[0.04]" style={{
        backgroundImage: 'radial-gradient(circle, rgba(148,163,184,0.4) 1px, transparent 1px)',
        backgroundSize: '30px 30px'
      }} />

      {/* Legend */}
      <div className="absolute bottom-4 left-4 glass rounded-lg px-3 py-2 z-10">
        <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1.5">图例</div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {Object.entries(GROUP_LABELS).map(([key, label]) => (
            <div key={key} className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: NODE_COLORS[key] }} />
              <span className="text-[10px] text-slate-400">{label}</span>
            </div>
          ))}
        </div>
      </div>

      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        nodeRelSize={0.6}
        nodeColor={node => NODE_COLORS[node.group] || '#94a3b8'}
        nodeCanvasObject={paintNode}
        nodeCanvasObjectMode={() => 'after'}
        linkColor={() => 'rgba(71, 85, 105, 0.3)'}
        linkWidth={1}
        linkDirectionalParticles={2}
        linkDirectionalParticleWidth={1.5}
        linkDirectionalParticleColor={() => 'rgba(34, 211, 238, 0.4)'}
        backgroundColor="transparent"
        onNodeClick={handleNodeClick}
        onNodeHover={handleNodeHover}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.4}
        cooldownTicks={100}
      />
    </div>
  )
}
