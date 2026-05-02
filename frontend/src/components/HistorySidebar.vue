<template>
  <aside class="history-sidebar">
    <div class="sidebar-header">
      <div class="brand" @click="goHome">MINIFISH</div>
      <button class="new-btn" @click="goHome" title="新建项目">+ 新建</button>
    </div>

    <div class="sidebar-section">
      <div class="section-label">历史项目 / 任务</div>
      <div v-if="!projects.length" class="empty">暂无项目</div>
      <div
        v-for="p in projects"
        :key="p.project_id"
        class="proj-row"
        :class="{ active: p.project_id === activeProjectId }"
        @click="$emit('select', p.project_id)"
      >
        <div class="proj-name">{{ p.name }}</div>
        <div class="proj-meta">{{ shortId(p.project_id) }} · {{ formatTime(p.updated_at) }}</div>
        <div class="badge-row">
          <span class="badge" :class="badgeClass(taskOf(p, 'graph_build'))">
            <span class="dot"></span>Step1 {{ badgeText(taskOf(p, 'graph_build')) }}
          </span>
          <span class="badge" :class="badgeClass(taskOf(p, 'personas_generate'))">
            <span class="dot"></span>Step2 {{ badgeText(taskOf(p, 'personas_generate')) }}
          </span>
        </div>
        <div v-if="activeTask(p)" class="mini-progress">
          <div class="mini-bar" :style="{ width: (activeTask(p).progress || 0) + '%' }"></div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { listProjects } from '../api/graph'
import { listAllTasks } from '../api/tasks'

defineProps({
  activeProjectId: { type: String, default: '' },
})

defineEmits(['select'])

const router = useRouter()

const projects = ref([])
const tasksByProject = ref({}) // { project_id: { graph_build: task, personas_generate: task } }

let timer = null

const fetchAll = async () => {
  try {
    const [pjRes, tkRes] = await Promise.all([listProjects(50), listAllTasks()])
    if (pjRes.success) projects.value = pjRes.data
    if (tkRes.success) {
      const map = {}
      // 已经按 updated_at desc 排序,同 project+type 取首条 (最新)
      for (const t of tkRes.data) {
        const pid = t.metadata?.project_id
        if (!pid) continue
        if (!map[pid]) map[pid] = {}
        if (!map[pid][t.task_type]) map[pid][t.task_type] = t
      }
      tasksByProject.value = map
    }
  } catch (e) {
    console.warn('sidebar fetch error:', e)
  }
}

const taskOf = (project, type) => tasksByProject.value[project.project_id]?.[type]

const activeTask = (project) => {
  const g = taskOf(project, 'graph_build')
  const p = taskOf(project, 'personas_generate')
  for (const t of [p, g]) {
    if (t && (t.status === 'processing' || t.status === 'pending')) return t
  }
  return null
}

const badgeClass = (task) => {
  if (!task) return 'idle'
  return task.status
}

const badgeText = (task) => {
  if (!task) return '—'
  if (task.status === 'processing') return `${task.progress || 0}%`
  if (task.status === 'pending') return '待开始'
  if (task.status === 'completed') return '完成'
  if (task.status === 'failed') return '失败'
  return task.status
}

const shortId = (id) => (id || '').replace('proj_', '').slice(0, 8)

const formatTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now - d
  if (diffMs < 60_000) return '刚刚'
  if (diffMs < 3_600_000) return `${Math.floor(diffMs / 60_000)}分钟前`
  if (diffMs < 86_400_000) return `${Math.floor(diffMs / 3_600_000)}小时前`
  return d.toLocaleDateString()
}

const goHome = () => router.push('/')

onMounted(() => {
  fetchAll()
  timer = setInterval(fetchAll, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

defineExpose({ refresh: fetchAll })
</script>

<style scoped>
.history-sidebar { width: 260px; background: #FAFAFA; border-right: 1px solid #EAEAEA; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
.sidebar-header { padding: 16px 20px; border-bottom: 1px solid #EAEAEA; display: flex; justify-content: space-between; align-items: center; background: #FFF; }
.brand { font-family: 'JetBrains Mono', monospace; font-weight: 800; font-size: 16px; letter-spacing: 1px; cursor: pointer; }
.new-btn { background: #000; color: #FFF; border: none; padding: 6px 10px; font-family: 'JetBrains Mono', monospace; font-size: 11px; cursor: pointer; }
.new-btn:hover { background: #FF5722; }

.sidebar-section { flex: 1; overflow-y: auto; padding: 16px; }
.section-label { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #999; letter-spacing: 1px; margin-bottom: 12px; }
.empty { color: #999; font-size: 12px; padding: 20px 0; text-align: center; }

.proj-row { padding: 12px; background: #FFF; border: 1px solid #EEE; border-radius: 6px; margin-bottom: 8px; cursor: pointer; transition: all 0.15s; }
.proj-row:hover { border-color: #FF5722; }
.proj-row.active { border-color: #000; background: #FFF; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.proj-name { font-weight: 600; font-size: 13px; color: #222; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.proj-meta { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #999; margin-top: 2px; }

.badge-row { display: flex; gap: 6px; margin-top: 8px; }
.badge { display: flex; align-items: center; gap: 4px; font-family: 'JetBrains Mono', monospace; font-size: 10px; padding: 2px 6px; border-radius: 3px; background: #F5F5F5; color: #666; }
.badge .dot { width: 6px; height: 6px; border-radius: 50%; background: #BBB; }
.badge.processing { background: #FFF3E0; color: #E65100; }
.badge.processing .dot { background: #FF5722; animation: pulse 1s infinite; }
.badge.pending { background: #FFFDE7; color: #F57F17; }
.badge.pending .dot { background: #FBC02D; }
.badge.completed { background: #E8F5E9; color: #2E7D32; }
.badge.completed .dot { background: #4CAF50; }
.badge.failed { background: #FFEBEE; color: #C62828; }
.badge.failed .dot { background: #F44336; }
@keyframes pulse { 50% { opacity: 0.5; } }

.mini-progress { height: 3px; background: #F0F0F0; border-radius: 2px; margin-top: 8px; overflow: hidden; }
.mini-bar { height: 100%; background: linear-gradient(90deg, #FF5722, #FF8A65); transition: width 0.4s ease; }
</style>
