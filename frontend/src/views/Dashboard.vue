<template>
  <div class="dashboard">
    <HistorySidebar :activeProjectId="String(currentProjectId || '')" @select="onSelectProject" />

    <main class="main-pane">
      <header class="dash-header">
        <div class="header-left">
          <div class="proj-title">{{ projectData?.name || (currentProjectId === 'new' ? '新项目初始化中…' : '加载中…') }}</div>
          <div class="proj-sub">{{ currentProjectId !== 'new' ? currentProjectId : '' }}</div>
        </div>
        <div class="header-right">
          <span class="badge" :class="step1Class">
            <span class="dot"></span>Step1: {{ step1Text }}
          </span>
          <span class="badge" :class="step2Class">
            <span class="dot"></span>Step2: {{ step2Text }}
          </span>
        </div>
      </header>

      <section class="graph-section">
        <GraphPanel
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="currentPhase"
          @refresh="refreshGraph"
        />
      </section>

      <section class="personas-section">
        <div class="section-bar">
          <div class="section-title">
            <span class="diamond">◇</span>
            Generated Personas <span class="count">{{ personas.length }} / {{ expectedCount || '?' }}</span>
          </div>
          <div class="section-actions">
            <span v-if="taskMessage" class="task-msg">{{ taskMessage }}</span>
            <div v-if="step2Active" class="progress-wrap">
              <div class="progress-bar" :style="{ width: progressPercent + '%' }"></div>
            </div>
            <button
              v-if="canStartStep2"
              class="action-btn"
              :disabled="step2Active"
              @click="startPersonaGenerate"
            >
              {{ personas.length ? '重新生成人设' : '开始生成人设' }} →
            </button>
          </div>
        </div>

        <div v-if="error" class="error-banner">{{ error }}</div>

        <div class="personas-grid">
          <PersonaCard
            v-for="p in personas"
            :key="p.user_id"
            :persona="p"
            :streaming="streamingIds.has(p.user_id)"
            @select="selectedPersona = $event"
          />
          <template v-if="step2Active">
            <div v-for="i in placeholderCount" :key="'ph-' + i" class="persona-card placeholder">
              <div class="placeholder-line w70"></div>
              <div class="placeholder-line w90"></div>
              <div class="placeholder-line w50"></div>
            </div>
          </template>
          <div v-if="!step2Active && personas.length === 0 && currentPhase >= 2" class="empty-state">
            <div class="empty-icon">◯</div>
            <p>尚未生成人设,点击右上角"开始生成人设"</p>
          </div>
          <div v-if="!step2Active && personas.length === 0 && currentPhase < 2" class="empty-state">
            <div class="empty-icon">◯</div>
            <p>等待 Step1 图谱构建完成…</p>
          </div>
        </div>
      </section>
    </main>

    <!-- Persona detail overlay -->
    <div v-if="selectedPersona" class="overlay" @click.self="selectedPersona = null">
      <div class="overlay-card">
        <div class="overlay-header">
          <div class="avatar lg" :style="{ background: avatarColor(selectedPersona) }">
            {{ (selectedPersona.name || '?').slice(0, 1) }}
          </div>
          <div>
            <div class="overlay-name">{{ selectedPersona.name }}</div>
            <div class="overlay-username">@{{ selectedPersona.user_name }}</div>
          </div>
          <button class="close-btn" @click="selectedPersona = null">×</button>
        </div>
        <div class="overlay-body">
          <div class="overlay-section">
            <span class="section-label">BIO</span>
            <p>{{ selectedPersona.bio }}</p>
          </div>
          <div class="overlay-section">
            <span class="section-label">PERSONA</span>
            <p class="persona-text">{{ selectedPersona.persona }}</p>
          </div>
          <div class="overlay-section">
            <span class="section-label">META</span>
            <div class="meta-grid">
              <div><span class="meta-key">年龄</span><span>{{ selectedPersona.age }}</span></div>
              <div><span class="meta-key">性别</span><span>{{ selectedPersona.gender }}</span></div>
              <div><span class="meta-key">MBTI</span><span>{{ selectedPersona.mbti }}</span></div>
              <div><span class="meta-key">国家</span><span>{{ selectedPersona.country }}</span></div>
              <div><span class="meta-key">职业</span><span>{{ selectedPersona.profession }}</span></div>
              <div><span class="meta-key">来源类型</span><span>{{ selectedPersona.source_entity_type }}</span></div>
            </div>
          </div>
          <div v-if="selectedPersona.interested_topics?.length" class="overlay-section">
            <span class="section-label">INTERESTED TOPICS</span>
            <div class="topics">
              <span v-for="t in selectedPersona.interested_topics" :key="t" class="topic-tag">#{{ t }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '../components/GraphPanel.vue'
import HistorySidebar from '../components/HistorySidebar.vue'
import PersonaCard from '../components/PersonaCard.vue'
import { generateOntology, getProject, buildGraph, getTaskStatus, getGraphData } from '../api/graph'
import { generatePersonas, getPersonasTask, getPersonas } from '../api/personas'
import { getPendingUpload, clearPendingUpload } from '../store/pendingUpload'

const route = useRoute()
const router = useRouter()

const currentProjectId = ref(route.params.projectId)
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const error = ref('')

// Step1
const buildTaskId = ref(null)
const buildProgress = ref(0)
const buildStatus = ref('')
const currentPhase = ref(-1) // -1 init, 0 ontology, 1 build, 2 done

// Step2
const personasTaskId = ref(null)
const personas = ref([])
const expectedCount = ref(0)
const taskMessage = ref('')
const taskProgress = ref({ current: 0, total: 0 })
const personasStatus = ref('')
const streamingIds = ref(new Set())
const selectedPersona = ref(null)

let buildTaskTimer = null
let graphDataTimer = null
let personasTaskTimer = null
let personasListTimer = null

// ---------- 状态徽章 ----------
const step1Class = computed(() => {
  if (buildStatus.value === 'failed') return 'failed'
  if (buildStatus.value === 'completed') return 'completed'
  if (buildStatus.value === 'processing' || buildStatus.value === 'pending') return 'processing'
  if (currentPhase.value >= 2) return 'completed'
  return 'idle'
})
const step1Text = computed(() => {
  if (buildStatus.value === 'failed') return '失败'
  if (buildStatus.value === 'completed' || currentPhase.value >= 2) return '完成'
  if (buildStatus.value === 'processing') return `${buildProgress.value || 0}%`
  if (buildStatus.value === 'pending') return '排队'
  if (currentPhase.value === 0) return '本体生成中'
  return '待开始'
})

const step1Done = computed(() =>
  buildStatus.value === 'completed' ||
  ['graph_completed', 'personas_generating', 'personas_completed'].includes(projectData.value?.status)
)

const step2Active = computed(() => personasStatus.value === 'processing' || personasStatus.value === 'pending')
const step2Done = computed(() => personasStatus.value === 'completed' || projectData.value?.status === 'personas_completed')

const step2Class = computed(() => {
  if (personasStatus.value === 'failed') return 'failed'
  if (step2Done.value) return 'completed'
  if (step2Active.value) return 'processing'
  return 'idle'
})
const step2Text = computed(() => {
  if (personasStatus.value === 'failed') return '失败'
  if (step2Done.value) return `完成 ${personas.value.length}`
  if (step2Active.value) return `${progressPercent.value}%`
  if (step1Done.value) return '待启动'
  return '等待 Step1'
})

const canStartStep2 = computed(() => step1Done.value && projectData.value?.graph_id)

const progressPercent = computed(() => {
  const total = taskProgress.value.total || expectedCount.value
  if (!total) return 0
  return Math.min(100, Math.round((taskProgress.value.current / total) * 100))
})

const placeholderCount = computed(() => {
  const total = expectedCount.value || taskProgress.value.total
  if (!total) return 0
  return Math.max(0, Math.min(5, total - personas.value.length))
})

const COLORS = ['#FF6B35', '#004E89', '#7B2D8E', '#1A936F', '#C5283D', '#E9724C', '#3498db', '#9b59b6', '#27ae60', '#f39c12']
const avatarColor = (p) => COLORS[(p?.user_id || 0) % COLORS.length]

// ---------- 路由切换 ----------
const onSelectProject = (pid) => {
  if (pid === currentProjectId.value) return
  router.push(`/dashboard/${pid}`)
}

watch(() => route.params.projectId, (v) => {
  if (!v || v === currentProjectId.value) return
  resetState()
  currentProjectId.value = v
  init()
})

const resetState = () => {
  stopAll()
  projectData.value = null
  graphData.value = null
  error.value = ''
  buildTaskId.value = null
  buildProgress.value = 0
  buildStatus.value = ''
  currentPhase.value = -1
  personasTaskId.value = null
  personas.value = []
  expectedCount.value = 0
  taskMessage.value = ''
  taskProgress.value = { current: 0, total: 0 }
  personasStatus.value = ''
  streamingIds.value = new Set()
  selectedPersona.value = null
}

// ---------- 初始化 ----------
const init = async () => {
  if (currentProjectId.value === 'new') {
    await handleNewProject()
  } else {
    await loadExisting()
  }
}

const handleNewProject = async () => {
  const pending = getPendingUpload()
  if (!pending.isPending || !pending.files.length) {
    error.value = '没有待上传文件,请回首页重新提交。'
    return
  }
  try {
    currentPhase.value = 0
    const fd = new FormData()
    pending.files.forEach((f) => fd.append('files', f))
    fd.append('simulation_requirement', pending.simulationRequirement)
    const res = await generateOntology(fd)
    if (!res.success) throw new Error(res.error || 'ontology failed')
    clearPendingUpload()
    const pid = res.data.project_id
    currentProjectId.value = pid
    projectData.value = res.data
    router.replace(`/dashboard/${pid}`)
    await startBuildGraph()
  } catch (e) {
    error.value = e.message
  }
}

const loadExisting = async () => {
  try {
    const res = await getProject(currentProjectId.value)
    if (!res.success) {
      error.value = res.error
      return
    }
    projectData.value = res.data
    inferPhase(res.data.status)

    // Step1 进行中 → 续接轮询
    if (res.data.status === 'graph_building' && res.data.graph_build_task_id) {
      buildTaskId.value = res.data.graph_build_task_id
      startBuildPolling()
    } else if (res.data.status === 'ontology_generated' && !res.data.graph_id) {
      // 本体已生成但还没构建 → 自动启动 Step1
      await startBuildGraph()
    } else if (res.data.graph_id) {
      // 图谱已存在 → 直接拉数据
      await refreshGraph()
    }

    // Step2 进行中 → 续接轮询
    if (res.data.status === 'personas_generating' && res.data.personas_task_id) {
      personasTaskId.value = res.data.personas_task_id
      startPersonasPolling()
    }

    await fetchPersonasOnce()
  } catch (e) {
    error.value = e.message
  }
}

const inferPhase = (status) => {
  switch (status) {
    case 'created':
    case 'ontology_generated':
      currentPhase.value = 0; break
    case 'graph_building':
      currentPhase.value = 1; break
    case 'graph_completed':
    case 'personas_generating':
    case 'personas_completed':
      currentPhase.value = 2; break
    case 'failed':
      error.value = projectData.value?.error || '项目失败'; break
  }
}

// ---------- Step1 ----------
const startBuildGraph = async () => {
  try {
    currentPhase.value = 1
    const res = await buildGraph({ project_id: currentProjectId.value })
    if (!res.success) throw new Error(res.error)
    buildTaskId.value = res.data.task_id
    startBuildPolling()
  } catch (e) {
    error.value = e.message
  }
}

const startBuildPolling = () => {
  pollBuildTask()
  buildTaskTimer = setInterval(pollBuildTask, 2000)
  graphDataTimer = setInterval(fetchGraphData, 3000)
  fetchGraphData()
}

const pollBuildTask = async () => {
  if (!buildTaskId.value) return
  try {
    const res = await getTaskStatus(buildTaskId.value)
    if (!res.success) return
    const t = res.data
    buildStatus.value = t.status
    buildProgress.value = t.progress || 0
    if (t.status === 'completed') {
      stopBuildPolling()
      currentPhase.value = 2
      const proj = await getProject(currentProjectId.value)
      if (proj.success) projectData.value = proj.data
      await refreshGraph()
    } else if (t.status === 'failed') {
      stopBuildPolling()
      error.value = t.error || '图谱构建失败'
    }
  } catch (e) { /* 静默 */ }
}

const fetchGraphData = async () => {
  try {
    const proj = await getProject(currentProjectId.value)
    if (proj.success && proj.data.graph_id) {
      const g = await getGraphData(proj.data.graph_id)
      if (g.success) graphData.value = g.data
    }
  } catch (e) { /* 静默 */ }
}

const refreshGraph = async () => {
  if (!projectData.value?.graph_id) return
  graphLoading.value = true
  try {
    const res = await getGraphData(projectData.value.graph_id)
    if (res.success) graphData.value = res.data
  } finally {
    graphLoading.value = false
  }
}

const stopBuildPolling = () => {
  if (buildTaskTimer) { clearInterval(buildTaskTimer); buildTaskTimer = null }
  if (graphDataTimer) { clearInterval(graphDataTimer); graphDataTimer = null }
}

// ---------- Step2 ----------
const startPersonaGenerate = async () => {
  if (!canStartStep2.value || step2Active.value) return
  try {
    error.value = ''
    personas.value = []
    streamingIds.value = new Set()
    taskProgress.value = { current: 0, total: 0 }
    taskMessage.value = '启动任务...'
    personasStatus.value = 'pending'

    const res = await generatePersonas({
      project_id: currentProjectId.value,
      parallel: 5,
      use_llm: true,
      force: true,
    })
    if (!res.success) throw new Error(res.error)
    personasTaskId.value = res.data.task_id
    expectedCount.value = res.data.expected_count || 0
    taskProgress.value.total = expectedCount.value
    startPersonasPolling()
  } catch (e) {
    error.value = e.message
    personasStatus.value = 'failed'
  }
}

const startPersonasPolling = () => {
  pollPersonasTask()
  personasTaskTimer = setInterval(pollPersonasTask, 2000)
  pollPersonasList()
  personasListTimer = setInterval(pollPersonasList, 1500)
}

const pollPersonasTask = async () => {
  if (!personasTaskId.value) return
  try {
    const res = await getPersonasTask(personasTaskId.value)
    if (!res.success) return
    const t = res.data
    personasStatus.value = t.status
    taskMessage.value = t.message || ''
    if (t.progress_detail?.total) {
      taskProgress.value = {
        current: t.progress_detail.current || 0,
        total: t.progress_detail.total,
      }
    }
    if (t.status === 'completed') {
      stopPersonasPolling()
      await pollPersonasList()
    } else if (t.status === 'failed') {
      stopPersonasPolling()
      error.value = t.error || '人设生成失败'
    }
  } catch (e) { /* 静默 */ }
}

const pollPersonasList = async () => {
  try {
    const res = await getPersonas(currentProjectId.value)
    if (!res.success) return
    const incoming = res.data.personas || []
    const oldIds = new Set(personas.value.map((p) => p.user_id))
    const newOnes = incoming.filter((p) => !oldIds.has(p.user_id))
    newOnes.forEach((p) => streamingIds.value.add(p.user_id))
    personas.value = incoming
    setTimeout(() => newOnes.forEach((p) => streamingIds.value.delete(p.user_id)), 1500)
  } catch (e) { /* 静默 */ }
}

const fetchPersonasOnce = async () => {
  try {
    const res = await getPersonas(currentProjectId.value)
    if (res.success) personas.value = res.data.personas || []
  } catch (e) { /* 静默 */ }
}

const stopPersonasPolling = () => {
  if (personasTaskTimer) { clearInterval(personasTaskTimer); personasTaskTimer = null }
  if (personasListTimer) { clearInterval(personasListTimer); personasListTimer = null }
}

const stopAll = () => {
  stopBuildPolling()
  stopPersonasPolling()
}

onMounted(init)
onUnmounted(stopAll)
</script>

<style scoped>
.dashboard { display: flex; height: 100vh; background: #FFF; font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif; overflow: hidden; }
.main-pane { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; }

.dash-header { height: 60px; padding: 0 24px; border-bottom: 1px solid #EAEAEA; display: flex; justify-content: space-between; align-items: center; background: #FFF; }
.proj-title { font-weight: 700; font-size: 15px; }
.proj-sub { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #999; margin-top: 2px; }
.header-right { display: flex; gap: 10px; }

.badge { display: inline-flex; align-items: center; gap: 6px; font-family: 'JetBrains Mono', monospace; font-size: 11px; padding: 4px 10px; border-radius: 4px; background: #F5F5F5; color: #666; }
.badge .dot { width: 7px; height: 7px; border-radius: 50%; background: #BBB; }
.badge.processing { background: #FFF3E0; color: #E65100; }
.badge.processing .dot { background: #FF5722; animation: pulse 1s infinite; }
.badge.completed { background: #E8F5E9; color: #2E7D32; }
.badge.completed .dot { background: #4CAF50; }
.badge.failed { background: #FFEBEE; color: #C62828; }
.badge.failed .dot { background: #F44336; }
@keyframes pulse { 50% { opacity: 0.5; } }

.graph-section { flex: 1.1; min-height: 0; border-bottom: 1px solid #EAEAEA; }
.personas-section { flex: 1; min-height: 0; display: flex; flex-direction: column; background: #FAFAFA; overflow: hidden; }

.section-bar { padding: 12px 24px; border-bottom: 1px solid #EAEAEA; display: flex; justify-content: space-between; align-items: center; background: #FFF; }
.section-title { font-weight: 600; font-size: 13px; display: flex; align-items: center; gap: 8px; }
.diamond { color: #FF5722; }
.count { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #999; margin-left: 6px; }
.section-actions { display: flex; align-items: center; gap: 10px; }
.task-msg { font-size: 11px; color: #777; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.progress-wrap { width: 120px; height: 4px; background: #EEE; border-radius: 2px; overflow: hidden; }
.progress-bar { height: 100%; background: linear-gradient(90deg, #FF5722, #FF8A65); transition: width 0.4s ease; }
.action-btn { background: #000; color: #FFF; border: none; padding: 8px 14px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 12px; cursor: pointer; transition: all 0.2s; }
.action-btn:hover:not(:disabled) { background: #FF5722; }
.action-btn:disabled { background: #CCC; cursor: not-allowed; }

.error-banner { background: #FFEBEE; color: #C62828; padding: 10px 24px; font-size: 12px; }

.personas-grid { flex: 1; padding: 20px 24px; overflow-y: auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; align-content: start; }
.persona-card.placeholder { background: linear-gradient(90deg, #f5f5f5 25%, #ececec 50%, #f5f5f5 75%); background-size: 200% 100%; animation: shimmer 1.5s linear infinite; min-height: 120px; padding: 16px; border-radius: 8px; }
@keyframes shimmer { 0% { background-position: 200% 0;} 100% { background-position: -200% 0;} }
.placeholder-line { height: 12px; background: rgba(255,255,255,0.6); border-radius: 4px; margin-bottom: 8px; }
.placeholder-line.w70 { width: 70%; }
.placeholder-line.w90 { width: 90%; }
.placeholder-line.w50 { width: 50%; }

.empty-state { grid-column: 1 / -1; text-align: center; padding: 40px; color: #999; }
.empty-icon { font-size: 40px; opacity: 0.3; margin-bottom: 8px; }

.overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); z-index: 200; display: flex; align-items: center; justify-content: center; padding: 32px; }
.overlay-card { background: #FFF; border-radius: 10px; max-width: 720px; width: 100%; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
.overlay-header { display: flex; align-items: center; gap: 16px; padding: 20px 24px; border-bottom: 1px solid #EEE; background: #FAFAFA; }
.avatar { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 700; font-size: 16px; }
.avatar.lg { width: 56px; height: 56px; font-size: 22px; }
.overlay-name { font-size: 18px; font-weight: 700; }
.overlay-username { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #999; }
.close-btn { margin-left: auto; background: none; border: none; font-size: 24px; cursor: pointer; color: #999; }
.overlay-body { padding: 24px; overflow-y: auto; }
.overlay-section { margin-bottom: 24px; }
.section-label { display: block; font-size: 10px; font-weight: 700; color: #AAA; margin-bottom: 8px; letter-spacing: 1px; }
.persona-text { white-space: pre-wrap; line-height: 1.7; color: #444; font-size: 13px; }
.meta-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
.meta-grid > div { display: flex; flex-direction: column; gap: 2px; padding: 8px 12px; background: #FAFAFA; border-radius: 4px; }
.meta-key { font-size: 10px; color: #888; }
.topics { display: flex; flex-wrap: wrap; gap: 4px; }
.topic-tag { font-size: 10px; color: #FF5722; }
</style>
