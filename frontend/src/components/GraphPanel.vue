<template>
  <div class="graph-panel">
    <div class="panel-header">
      <span class="panel-title">Graph Relationship Visualization</span>
      <div class="header-tools">
        <button class="tool-btn" @click="$emit('refresh')" :disabled="loading" title="刷新图谱">
          <span class="icon-refresh" :class="{ spinning: loading }">↻</span>
          <span class="btn-text">Refresh</span>
        </button>
      </div>
    </div>

    <div class="graph-container" ref="graphContainer">
      <div v-if="graphData" class="graph-view">
        <svg ref="graphSvg" class="graph-svg"></svg>
        <div v-if="currentPhase === 1" class="graph-building-hint">
          <div class="memory-icon-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="memory-icon">
              <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-4.04z" />
              <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-4.04z" />
            </svg>
          </div>
          实时更新中...
        </div>

        <div v-if="selectedItem" class="detail-panel">
          <div class="detail-panel-header">
            <span class="detail-title">{{ selectedItem.type === 'node' ? 'Node Details' : 'Relationship' }}</span>
            <span v-if="selectedItem.type === 'node'" class="detail-type-badge" :style="{ background: selectedItem.color, color: '#fff' }">
              {{ selectedItem.entityType }}
            </span>
            <button class="detail-close" @click="closeDetailPanel">×</button>
          </div>
          <div v-if="selectedItem.type === 'node'" class="detail-content">
            <div class="detail-row"><span class="detail-label">Name:</span><span class="detail-value">{{ selectedItem.data.name }}</span></div>
            <div class="detail-row"><span class="detail-label">UUID:</span><span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span></div>
            <div class="detail-section" v-if="selectedItem.data.attributes && Object.keys(selectedItem.data.attributes).length > 0">
              <div class="section-title">Properties:</div>
              <div class="properties-list">
                <div v-for="(value, key) in selectedItem.data.attributes" :key="key" class="property-item">
                  <span class="property-key">{{ key }}:</span>
                  <span class="property-value">{{ value || 'None' }}</span>
                </div>
              </div>
            </div>
            <div class="detail-section" v-if="selectedItem.data.summary">
              <div class="section-title">Summary:</div>
              <div class="summary-text">{{ selectedItem.data.summary }}</div>
            </div>
          </div>
          <div v-else class="detail-content">
            <div class="edge-relation-header">
              {{ selectedItem.data.source_name }} → {{ selectedItem.data.name || 'RELATED' }} → {{ selectedItem.data.target_name }}
            </div>
            <div class="detail-row"><span class="detail-label">UUID:</span><span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span></div>
            <div class="detail-row" v-if="selectedItem.data.fact"><span class="detail-label">Fact:</span><span class="detail-value fact-text">{{ selectedItem.data.fact }}</span></div>
          </div>
        </div>
      </div>

      <div v-else-if="loading" class="graph-state">
        <div class="loading-spinner"></div>
        <p>图谱数据加载中...</p>
      </div>
      <div v-else class="graph-state">
        <div class="empty-icon">❖</div>
        <p class="empty-text">等待图谱构建...</p>
      </div>
    </div>

    <div v-if="graphData && entityTypes.length" class="graph-legend">
      <span class="legend-title">Entity Types</span>
      <div class="legend-items">
        <div class="legend-item" v-for="type in entityTypes" :key="type.name">
          <span class="legend-dot" :style="{ background: type.color }"></span>
          <span class="legend-label">{{ type.name }}</span>
        </div>
      </div>
    </div>

    <div v-if="graphData" class="edge-labels-toggle">
      <label class="toggle-switch">
        <input type="checkbox" v-model="showEdgeLabels" />
        <span class="slider"></span>
      </label>
      <span class="toggle-label">Show Edge Labels</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  graphData: Object,
  loading: Boolean,
  currentPhase: Number,
})

defineEmits(['refresh'])

const graphContainer = ref(null)
const graphSvg = ref(null)
const selectedItem = ref(null)
const showEdgeLabels = ref(true)

const entityTypes = computed(() => {
  if (!props.graphData?.nodes) return []
  const typeMap = {}
  const colors = ['#FF6B35', '#004E89', '#7B2D8E', '#1A936F', '#C5283D', '#E9724C', '#3498db', '#9b59b6', '#27ae60', '#f39c12']
  props.graphData.nodes.forEach((node) => {
    const type = node.labels?.find((l) => l !== 'Entity') || 'Entity'
    if (!typeMap[type]) {
      typeMap[type] = { name: type, count: 0, color: colors[Object.keys(typeMap).length % colors.length] }
    }
    typeMap[type].count++
  })
  return Object.values(typeMap)
})

const closeDetailPanel = () => { selectedItem.value = null }

let currentSimulation = null
let linkLabelsRef = null
let linkLabelBgRef = null

const renderGraph = () => {
  if (!graphSvg.value || !props.graphData) return
  if (currentSimulation) currentSimulation.stop()

  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight

  const svg = d3
    .select(graphSvg.value)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
  svg.selectAll('*').remove()

  const nodesData = props.graphData.nodes || []
  const edgesData = props.graphData.edges || []
  if (nodesData.length === 0) return

  const nodeMap = {}
  nodesData.forEach((n) => (nodeMap[n.uuid] = n))

  const nodes = nodesData.map((n) => ({
    id: n.uuid,
    name: n.name || 'Unnamed',
    type: n.labels?.find((l) => l !== 'Entity') || 'Entity',
    rawData: n,
  }))

  const nodeIds = new Set(nodes.map((n) => n.id))
  const tempEdges = edgesData.filter((e) => nodeIds.has(e.source_node_uuid) && nodeIds.has(e.target_node_uuid))
  const edgePairCount = {}
  tempEdges.forEach((e) => {
    if (e.source_node_uuid !== e.target_node_uuid) {
      const key = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
      edgePairCount[key] = (edgePairCount[key] || 0) + 1
    }
  })
  const edgePairIndex = {}
  const processedSelfLoopNodes = new Set()
  const edges = []
  tempEdges.forEach((e) => {
    const isSelfLoop = e.source_node_uuid === e.target_node_uuid
    if (isSelfLoop) {
      if (processedSelfLoopNodes.has(e.source_node_uuid)) return
      processedSelfLoopNodes.add(e.source_node_uuid)
      edges.push({
        source: e.source_node_uuid,
        target: e.target_node_uuid,
        name: 'Self Relations',
        curvature: 0,
        isSelfLoop: true,
        rawData: { ...e, source_name: nodeMap[e.source_node_uuid]?.name, target_name: nodeMap[e.source_node_uuid]?.name },
      })
      return
    }
    const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
    const totalCount = edgePairCount[pairKey]
    const currentIndex = edgePairIndex[pairKey] || 0
    edgePairIndex[pairKey] = currentIndex + 1
    const isReversed = e.source_node_uuid > e.target_node_uuid
    let curvature = 0
    if (totalCount > 1) {
      const range = Math.min(1.2, 0.6 + totalCount * 0.15)
      curvature = (currentIndex / (totalCount - 1) - 0.5) * range * 2
      if (isReversed) curvature = -curvature
    }
    edges.push({
      source: e.source_node_uuid,
      target: e.target_node_uuid,
      name: e.name || e.fact_type || 'RELATED',
      curvature,
      isSelfLoop: false,
      pairTotal: totalCount,
      rawData: { ...e, source_name: nodeMap[e.source_node_uuid]?.name, target_name: nodeMap[e.target_node_uuid]?.name },
    })
  })

  const colorMap = {}
  entityTypes.value.forEach((t) => (colorMap[t.name] = t.color))
  const getColor = (type) => colorMap[type] || '#999'

  const simulation = d3
    .forceSimulation(nodes)
    .force(
      'link',
      d3.forceLink(edges).id((d) => d.id).distance((d) => 150 + ((d.pairTotal || 1) - 1) * 50)
    )
    .force('charge', d3.forceManyBody().strength(-400))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(50))
    .force('x', d3.forceX(width / 2).strength(0.04))
    .force('y', d3.forceY(height / 2).strength(0.04))
  currentSimulation = simulation

  const g = svg.append('g')
  svg.call(
    d3
      .zoom()
      .extent([[0, 0], [width, height]])
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => g.attr('transform', event.transform))
  )

  const linkGroup = g.append('g').attr('class', 'links')

  const getLinkPath = (d) => {
    const sx = d.source.x, sy = d.source.y, tx = d.target.x, ty = d.target.y
    if (d.isSelfLoop) {
      const r = 30
      return `M${sx + 8},${sy - 4} A${r},${r} 0 1,1 ${sx + 8},${sy + 4}`
    }
    if (d.curvature === 0) return `M${sx},${sy} L${tx},${ty}`
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    const ratio = 0.25 + (d.pairTotal || 1) * 0.05
    const baseOffset = Math.max(35, dist * ratio)
    const offsetX = (-dy / dist) * d.curvature * baseOffset
    const offsetY = (dx / dist) * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`
  }

  const getLinkMidpoint = (d) => {
    const sx = d.source.x, sy = d.source.y, tx = d.target.x, ty = d.target.y
    if (d.isSelfLoop) return { x: sx + 70, y: sy }
    if (d.curvature === 0) return { x: (sx + tx) / 2, y: (sy + ty) / 2 }
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    const ratio = 0.25 + (d.pairTotal || 1) * 0.05
    const baseOffset = Math.max(35, dist * ratio)
    const offsetX = (-dy / dist) * d.curvature * baseOffset
    const offsetY = (dx / dist) * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    const midX = 0.25 * sx + 0.5 * cx + 0.25 * tx
    const midY = 0.25 * sy + 0.5 * cy + 0.25 * ty
    return { x: midX, y: midY }
  }

  const link = linkGroup
    .selectAll('path')
    .data(edges)
    .enter()
    .append('path')
    .attr('stroke', '#C0C0C0')
    .attr('stroke-width', 1.5)
    .attr('fill', 'none')
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      d3.select(event.target).attr('stroke', '#3498db').attr('stroke-width', 3)
      selectedItem.value = { type: 'edge', data: d.rawData }
    })

  const linkLabelBg = linkGroup
    .selectAll('rect')
    .data(edges)
    .enter()
    .append('rect')
    .attr('fill', 'rgba(255,255,255,0.95)')
    .attr('rx', 3)
    .attr('ry', 3)
    .style('display', showEdgeLabels.value ? 'block' : 'none')

  const linkLabels = linkGroup
    .selectAll('text')
    .data(edges)
    .enter()
    .append('text')
    .text((d) => d.name)
    .attr('font-size', '9px')
    .attr('fill', '#666')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .style('font-family', 'system-ui, sans-serif')
    .style('display', showEdgeLabels.value ? 'block' : 'none')

  linkLabelsRef = linkLabels
  linkLabelBgRef = linkLabelBg

  const nodeGroup = g.append('g').attr('class', 'nodes')
  const node = nodeGroup
    .selectAll('circle')
    .data(nodes)
    .enter()
    .append('circle')
    .attr('r', 10)
    .attr('fill', (d) => getColor(d.type))
    .attr('stroke', '#fff')
    .attr('stroke-width', 2.5)
    .style('cursor', 'pointer')
    .call(
      d3
        .drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
    )
    .on('click', (event, d) => {
      event.stopPropagation()
      node.attr('stroke', '#fff').attr('stroke-width', 2.5)
      d3.select(event.target).attr('stroke', '#E91E63').attr('stroke-width', 4)
      selectedItem.value = { type: 'node', data: d.rawData, entityType: d.type, color: getColor(d.type) }
    })

  const nodeLabels = nodeGroup
    .selectAll('text')
    .data(nodes)
    .enter()
    .append('text')
    .text((d) => (d.name.length > 8 ? d.name.substring(0, 8) + '…' : d.name))
    .attr('font-size', '11px')
    .attr('fill', '#333')
    .attr('font-weight', '500')
    .attr('dx', 14)
    .attr('dy', 4)
    .style('pointer-events', 'none')
    .style('font-family', 'system-ui, sans-serif')

  simulation.on('tick', () => {
    link.attr('d', (d) => getLinkPath(d))
    linkLabels.each(function (d) {
      const mid = getLinkMidpoint(d)
      d3.select(this).attr('x', mid.x).attr('y', mid.y)
    })
    linkLabelBg.each(function (d, i) {
      const mid = getLinkMidpoint(d)
      const textEl = linkLabels.nodes()[i]
      const bbox = textEl.getBBox()
      d3.select(this)
        .attr('x', mid.x - bbox.width / 2 - 4)
        .attr('y', mid.y - bbox.height / 2 - 2)
        .attr('width', bbox.width + 8)
        .attr('height', bbox.height + 4)
    })
    node.attr('cx', (d) => d.x).attr('cy', (d) => d.y)
    nodeLabels.attr('x', (d) => d.x).attr('y', (d) => d.y)
  })

  svg.on('click', () => {
    selectedItem.value = null
    node.attr('stroke', '#fff').attr('stroke-width', 2.5)
    linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
  })
}

watch(() => props.graphData, () => { nextTick(renderGraph) }, { deep: true })

watch(showEdgeLabels, (v) => {
  if (linkLabelsRef) linkLabelsRef.style('display', v ? 'block' : 'none')
  if (linkLabelBgRef) linkLabelBgRef.style('display', v ? 'block' : 'none')
})

const handleResize = () => { nextTick(renderGraph) }

onMounted(() => { window.addEventListener('resize', handleResize) })
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (currentSimulation) currentSimulation.stop()
})
</script>

<style scoped>
.graph-panel {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #FAFAFA;
  background-image: radial-gradient(#D0D0D0 1.5px, transparent 1.5px);
  background-size: 24px 24px;
  overflow: hidden;
}
.panel-header {
  position: absolute;
  top: 0; left: 0; right: 0;
  padding: 16px 20px;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(to bottom, rgba(255,255,255,0.95), rgba(255,255,255,0));
  pointer-events: none;
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  pointer-events: auto;
}
.header-tools { pointer-events: auto; display: flex; gap: 10px; align-items: center; }
.tool-btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid #E0E0E0;
  background: #FFF;
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  gap: 6px;
  cursor: pointer;
  color: #666;
  font-size: 13px;
}
.tool-btn:hover { background: #F5F5F5; color: #000; border-color: #CCC; }
.tool-btn .btn-text { font-size: 12px; }
.icon-refresh.spinning { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg);} to { transform: rotate(360deg);} }

.graph-container { width: 100%; height: 100%; }
.graph-view, .graph-svg { width: 100%; height: 100%; display: block; }
.graph-state { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; color: #999; }
.empty-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.2; }

.graph-legend {
  position: absolute; bottom: 24px; left: 24px;
  background: rgba(255,255,255,0.95);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #EAEAEA;
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  z-index: 10;
}
.legend-title { display: block; font-size: 11px; font-weight: 600; color: #E91E63; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }
.legend-items { display: flex; flex-wrap: wrap; gap: 10px 16px; max-width: 320px; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #555; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }

.edge-labels-toggle {
  position: absolute;
  top: 60px; right: 20px;
  display: flex; align-items: center; gap: 10px;
  background: #FFF;
  padding: 8px 14px;
  border-radius: 20px;
  border: 1px solid #E0E0E0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  z-index: 10;
}
.toggle-switch { position: relative; display: inline-block; width: 40px; height: 22px; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #E0E0E0; border-radius: 22px; transition: 0.3s; }
.slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: white; border-radius: 50%; transition: 0.3s; }
input:checked + .slider { background-color: #7B2D8E; }
input:checked + .slider:before { transform: translateX(18px); }
.toggle-label { font-size: 12px; color: #666; }

.detail-panel {
  position: absolute;
  top: 60px; right: 20px;
  width: 320px;
  max-height: calc(100% - 100px);
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.1);
  overflow: hidden;
  font-family: 'Noto Sans SC', system-ui, sans-serif;
  font-size: 13px;
  z-index: 20;
  display: flex; flex-direction: column;
}
.detail-panel-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; background: #FAFAFA; border-bottom: 1px solid #EEE; flex-shrink: 0; }
.detail-title { font-weight: 600; color: #333; font-size: 14px; }
.detail-type-badge { padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; margin-left: auto; margin-right: 12px; }
.detail-close { background: none; border: none; font-size: 20px; cursor: pointer; color: #999; line-height: 1; padding: 0; }
.detail-content { padding: 16px; overflow-y: auto; flex: 1; }
.detail-row { margin-bottom: 12px; display: flex; flex-wrap: wrap; gap: 4px; }
.detail-label { color: #888; font-size: 12px; font-weight: 500; min-width: 80px; }
.detail-value { color: #333; flex: 1; word-break: break-word; }
.detail-value.uuid-text { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #666; }
.detail-value.fact-text { line-height: 1.5; color: #444; }
.detail-section { margin-top: 16px; padding-top: 14px; border-top: 1px solid #F0F0F0; }
.section-title { font-size: 12px; font-weight: 600; color: #666; margin-bottom: 10px; }
.properties-list { display: flex; flex-direction: column; gap: 8px; }
.property-item { display: flex; gap: 8px; }
.property-key { color: #888; font-weight: 500; min-width: 90px; }
.property-value { color: #333; flex: 1; }
.summary-text { line-height: 1.6; color: #444; font-size: 12px; }
.edge-relation-header { background: #F8F8F8; padding: 12px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; font-weight: 500; color: #333; line-height: 1.5; word-break: break-word; }

.graph-building-hint {
  position: absolute; bottom: 100px; left: 50%; transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(8px);
  color: #fff;
  padding: 10px 20px;
  border-radius: 30px;
  font-size: 13px;
  display: flex; align-items: center; gap: 10px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-weight: 500; letter-spacing: 0.5px;
  z-index: 100;
}
.memory-icon-wrapper { display: flex; align-items: center; justify-content: center; animation: breathe 2s ease-in-out infinite; }
.memory-icon { width: 18px; height: 18px; color: #4CAF50; }
@keyframes breathe {
  0%, 100% { opacity: 0.7; transform: scale(1); filter: drop-shadow(0 0 2px rgba(76, 175, 80, 0.3)); }
  50% { opacity: 1; transform: scale(1.15); filter: drop-shadow(0 0 8px rgba(76, 175, 80, 0.6)); }
}
.loading-spinner { width: 40px; height: 40px; border: 3px solid #E0E0E0; border-top-color: #7B2D8E; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 16px; }
</style>
