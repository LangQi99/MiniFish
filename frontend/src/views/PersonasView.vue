<template>
  <div class="personas-view">
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">MINIFISH</div>
      </div>
      <div class="header-center">
        <span class="back-link" @click="router.push({ name: 'Process', params: { projectId } })">← 返回 Step 01</span>
      </div>
      <div class="header-right">
        <div class="workflow-step">
          <span class="step-num">Step 02/02</span>
          <span class="step-name">生成 Agent 人设</span>
        </div>
        <div class="step-divider"></div>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
      </div>
    </header>

    <main class="content-area">
      <aside class="control-panel">
        <div class="panel-section">
          <div class="panel-header">
            <span class="diamond">◇</span>
            <span class="panel-title">02 / 人设并行生成</span>
          </div>
          <p class="panel-desc">
            基于 Step 01 构建的图谱节点，对每个实体并行调用 LLM 生成详细 Agent 人设：
            个人实体生成具体人物设定，机构实体生成代表性账号设定。
          </p>

          <div class="config-row">
            <label class="config-label">并行数</label>
            <input type="number" v-model.number="parallel" min="1" max="20" class="num-input" :disabled="taskRunning" />
          </div>
          <div class="config-row">
            <label class="config-label">使用 LLM</label>
            <input type="checkbox" v-model="useLlm" :disabled="taskRunning" />
          </div>

          <button class="action-btn" @click="startGenerate" :disabled="!canStart || taskRunning">
            <span v-if="!taskRunning">{{ existingPersonas.length ? '重新生成' : '启动生成' }}</span>
            <span v-else>生成中...</span>
            <span class="btn-arrow">→</span>
          </button>
        </div>

        <div class="panel-section stats-section">
          <div class="stat-row">
            <div class="stat-card">
              <span class="stat-value">{{ taskProgress.current }}</span>
              <span class="stat-label">已生成</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ taskProgress.total || expectedCount || '?' }}</span>
              <span class="stat-label">目标数</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ progressPercent }}%</span>
              <span class="stat-label">进度</span>
            </div>
          </div>
          <div class="progress-bar-wrapper">
            <div class="progress-bar" :style="{ width: progressPercent + '%' }"></div>
          </div>
          <p class="progress-message">{{ taskMessage || '等待启动...' }}</p>
        </div>

        <div class="panel-section logs-section">
          <div class="panel-header">
            <span class="diamond">◇</span>
            <span class="panel-title">SYSTEM LOGS</span>
          </div>
          <div class="logs">
            <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
              <span class="log-time">{{ log.time }}</span>
              <span class="log-msg">{{ log.msg }}</span>
            </div>
          </div>
        </div>
      </aside>

      <section class="personas-grid-area">
        <div class="grid-header">
          <span class="grid-title">Generated Personas</span>
          <span class="grid-count">{{ personas.length }} / {{ expectedCount || '?' }}</span>
        </div>

        <div class="personas-grid">
          <div
            v-for="p in personas"
            :key="p.user_id"
            class="persona-card"
            :class="{ pulse: streamingIds.has(p.user_id) }"
            @click="selectedPersona = p"
          >
            <div class="card-top">
              <div class="avatar" :style="{ background: avatarColor(p) }">
                {{ (p.name || '?').slice(0, 1) }}
              </div>
              <div class="card-meta">
                <div class="card-name">{{ p.name }}</div>
                <div class="card-username">@{{ p.user_name }}</div>
              </div>
              <span class="entity-badge">{{ p.source_entity_type || 'Entity' }}</span>
            </div>
            <div class="card-bio">{{ p.bio }}</div>
            <div class="card-attrs">
              <span v-if="p.age" class="attr">{{ p.age }}岁</span>
              <span v-if="p.gender" class="attr">{{ p.gender }}</span>
              <span v-if="p.mbti" class="attr">{{ p.mbti }}</span>
              <span v-if="p.country" class="attr">{{ p.country }}</span>
              <span v-if="p.profession" class="attr">{{ p.profession }}</span>
            </div>
            <div v-if="p.interested_topics?.length" class="topics">
              <span v-for="t in p.interested_topics.slice(0, 5)" :key="t" class="topic-tag">#{{ t }}</span>
            </div>
          </div>

          <div v-if="taskRunning" v-for="i in placeholderCount" :key="'placeholder-' + i" class="persona-card placeholder">
            <div class="placeholder-line w70"></div>
            <div class="placeholder-line w90"></div>
            <div class="placeholder-line w50"></div>
          </div>

          <div v-if="!taskRunning && personas.length === 0" class="empty-state">
            <div class="empty-icon">◯</div>
            <p>尚未生成人设，点击左侧"启动生成"开始</p>
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
import { generatePersonas, getPersonasTask, getPersonas } from '../api/personas'
import { getProject } from '../api/graph'

const route = useRoute()
const router = useRouter()

const projectId = ref(route.params.projectId)

const project = ref(null)
const personas = ref([])
const existingPersonas = ref([])
const expectedCount = ref(0)
const parallel = ref(5)
const useLlm = ref(true)

const taskId = ref(null)
const taskRunning = ref(false)
const taskProgress = ref({ current: 0, total: 0 })
const taskMessage = ref('')
const error = ref('')
const systemLogs = ref([])
const selectedPersona = ref(null)

const streamingIds = ref(new Set())

let personaPollTimer = null
let taskPollTimer = null

const addLog = (msg) => {
  const now = new Date()
  const time =
    now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) +
    '.' + now.getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 100) systemLogs.value.shift()
}

const canStart = computed(() => !!project.value?.graph_id)

const statusClass = computed(() => {
  if (error.value) return 'error'
  if (taskRunning.value) return 'processing'
  if (personas.value.length > 0) return 'completed'
  return ''
})

const statusText = computed(() => {
  if (error.value) return 'Error'
  if (taskRunning.value) return 'Generating'
  if (personas.value.length > 0) return 'Ready'
  return 'Idle'
})

const progressPercent = computed(() => {
  const total = taskProgress.value.total || expectedCount.value
  if (!total) return 0
  return Math.min(100, Math.round((taskProgress.value.current / total) * 100))
})

const placeholderCount = computed(() => {
  const total = expectedCount.value || taskProgress.value.total
  if (!total) return 0
  return Math.max(0, Math.min(parallel.value, total - personas.value.length))
})

const avatarColor = (p) => {
  const colors = ['#FF6B35', '#004E89', '#7B2D8E', '#1A936F', '#C5283D', '#E9724C', '#3498db', '#9b59b6', '#27ae60', '#f39c12']
  return colors[(p.user_id || 0) % colors.length]
}

const fetchProject = async () => {
  try {
    const res = await getProject(projectId.value)
    if (res.success) {
      project.value = res.data
      // 推断已存在的人设
      if (res.data.personas_count) expectedCount.value = res.data.personas_count
      if (res.data.personas_task_id && res.data.status === 'personas_generating') {
        taskId.value = res.data.personas_task_id
        taskRunning.value = true
        startTaskPoll()
        startPersonaPoll()
        addLog(`恢复任务: ${res.data.personas_task_id}`)
      }
    }
  } catch (e) {
    error.value = e.message
  }
}

const fetchExistingPersonas = async () => {
  try {
    const res = await getPersonas(projectId.value)
    if (res.success) {
      existingPersonas.value = res.data.personas || []
      personas.value = existingPersonas.value
    }
  } catch (e) {
    console.warn(e)
  }
}

const startGenerate = async () => {
  try {
    error.value = ''
    personas.value = []
    streamingIds.value = new Set()
    taskProgress.value = { current: 0, total: 0 }
    taskMessage.value = '启动任务...'
    taskRunning.value = true
    addLog('Step 02: 启动 Agent 人设并行生成')

    const res = await generatePersonas({
      project_id: projectId.value,
      parallel: parallel.value,
      use_llm: useLlm.value,
      force: true,
    })

    if (res.success) {
      taskId.value = res.data.task_id
      expectedCount.value = res.data.expected_count || 0
      taskProgress.value.total = expectedCount.value
      addLog(`任务已启动: ${res.data.task_id}（共 ${expectedCount.value} 个实体）`)
      startTaskPoll()
      startPersonaPoll()
    } else {
      error.value = res.error
      taskRunning.value = false
      addLog(`启动失败: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    taskRunning.value = false
    addLog(`异常: ${err.message}`)
  }
}

const startTaskPoll = () => {
  pollTask()
  taskPollTimer = setInterval(pollTask, 2000)
}

const pollTask = async () => {
  if (!taskId.value) return
  try {
    const res = await getPersonasTask(taskId.value)
    if (res.success) {
      const task = res.data
      taskMessage.value = task.message || ''
      if (task.progress_detail?.total) {
        taskProgress.value = {
          current: task.progress_detail.current || 0,
          total: task.progress_detail.total,
        }
      }
      if (task.message) addLog(task.message)
      if (task.status === 'completed') {
        taskRunning.value = false
        addLog('Step 02 完成')
        stopTaskPoll()
        // 最后再拉一次
        await pollPersonas()
        stopPersonaPoll()
      } else if (task.status === 'failed') {
        taskRunning.value = false
        error.value = task.error || '失败'
        addLog(`Step 02 失败: ${task.error}`)
        stopTaskPoll()
        stopPersonaPoll()
      }
    }
  } catch (e) {
    console.warn(e)
  }
}

const startPersonaPoll = () => {
  pollPersonas()
  personaPollTimer = setInterval(pollPersonas, 1500)
}

const pollPersonas = async () => {
  try {
    const res = await getPersonas(projectId.value)
    if (res.success) {
      const incoming = res.data.personas || []
      const oldIds = new Set(personas.value.map((p) => p.user_id))
      const newOnes = incoming.filter((p) => !oldIds.has(p.user_id))
      // 标记新到达的卡片
      newOnes.forEach((p) => streamingIds.value.add(p.user_id))
      personas.value = incoming
      // 1.5 秒后清除高亮
      setTimeout(() => {
        newOnes.forEach((p) => streamingIds.value.delete(p.user_id))
      }, 1500)
    }
  } catch (e) {
    console.warn(e)
  }
}

const stopTaskPoll = () => { if (taskPollTimer) { clearInterval(taskPollTimer); taskPollTimer = null } }
const stopPersonaPoll = () => { if (personaPollTimer) { clearInterval(personaPollTimer); personaPollTimer = null } }

watch(() => route.params.projectId, (v) => { if (v) projectId.value = v })

onMounted(async () => {
  await fetchProject()
  await fetchExistingPersonas()
})

onUnmounted(() => { stopTaskPoll(); stopPersonaPoll() })
</script>

<style scoped>
.personas-view { height: 100vh; display: flex; flex-direction: column; background: #FAFAFA; overflow: hidden; font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif; }
.app-header { height: 60px; border-bottom: 1px solid #EAEAEA; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; background: #FFF; z-index: 100; }
.header-center { position: absolute; left: 50%; transform: translateX(-50%); }
.brand { font-family: 'JetBrains Mono', monospace; font-weight: 800; font-size: 18px; letter-spacing: 1px; cursor: pointer; }
.back-link { color: #666; cursor: pointer; font-size: 13px; font-family: 'JetBrains Mono', monospace; }
.back-link:hover { color: #FF5722; }
.header-right { display: flex; align-items: center; gap: 16px; }
.workflow-step { display: flex; align-items: center; gap: 8px; font-size: 14px; }
.step-num { font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #999; }
.step-name { font-weight: 700; }
.step-divider { width: 1px; height: 14px; background-color: #E0E0E0; }
.status-indicator { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #666; font-weight: 500; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #CCC; }
.status-indicator.processing .dot { background: #FF5722; animation: pulse 1s infinite; }
.status-indicator.completed .dot { background: #4CAF50; }
.status-indicator.error .dot { background: #F44336; }
@keyframes pulse { 50% { opacity: 0.5; } }

.content-area { flex: 1; display: flex; overflow: hidden; }

.control-panel { width: 360px; background: #FFF; border-right: 1px solid #EAEAEA; padding: 24px; display: flex; flex-direction: column; gap: 24px; overflow-y: auto; }
.panel-section { display: flex; flex-direction: column; gap: 12px; }
.panel-header { display: flex; align-items: center; gap: 8px; font-size: 11px; color: #999; font-family: 'JetBrains Mono', monospace; }
.diamond { color: #FF5722; }
.panel-title { font-weight: 600; }
.panel-desc { color: #666; font-size: 12px; line-height: 1.6; }

.config-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.config-label { font-size: 12px; color: #555; }
.num-input { width: 80px; border: 1px solid #DDD; padding: 6px 10px; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
.action-btn { background: #000; color: #FFF; border: none; padding: 14px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 13px; cursor: pointer; transition: all 0.2s; display: flex; justify-content: space-between; align-items: center; }
.action-btn:hover:not(:disabled) { background: #FF5722; }
.action-btn:disabled { background: #CCC; cursor: not-allowed; }
.btn-arrow { font-size: 14px; }

.stats-section { background: #FAFAFA; padding: 16px; border-radius: 6px; }
.stat-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 12px; }
.stat-card { text-align: center; }
.stat-value { display: block; font-size: 20px; font-weight: 700; color: #000; font-family: 'JetBrains Mono', monospace; }
.stat-label { font-size: 9px; color: #999; text-transform: uppercase; }
.progress-bar-wrapper { height: 6px; background: #EEE; border-radius: 3px; overflow: hidden; }
.progress-bar { height: 100%; background: linear-gradient(90deg, #FF5722, #FF8A65); transition: width 0.4s ease; }
.progress-message { font-size: 11px; color: #777; margin-top: 8px; line-height: 1.4; }

.logs-section { flex: 1; min-height: 0; }
.logs { background: #000; color: #DDD; padding: 12px; font-family: 'JetBrains Mono', monospace; font-size: 11px; max-height: 200px; overflow-y: auto; border-radius: 4px; }
.log-line { display: flex; gap: 10px; line-height: 1.5; }
.log-time { color: #666; min-width: 70px; }
.log-msg { color: #CCC; word-break: break-all; }

.personas-grid-area { flex: 1; padding: 24px; overflow-y: auto; }
.grid-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.grid-title { font-size: 14px; font-weight: 600; color: #333; }
.grid-count { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #999; }

.personas-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }

.persona-card { background: #FFF; border: 1px solid #EAEAEA; border-radius: 8px; padding: 16px; cursor: pointer; transition: all 0.2s; display: flex; flex-direction: column; gap: 10px; }
.persona-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); transform: translateY(-2px); }
.persona-card.pulse { animation: cardPulse 1.5s ease-out; }
@keyframes cardPulse {
  0% { box-shadow: 0 0 0 0 rgba(255, 87, 34, 0.55); transform: scale(1.02); }
  100% { box-shadow: 0 0 0 12px rgba(255, 87, 34, 0); transform: scale(1); }
}

.persona-card.placeholder { background: linear-gradient(90deg, #f5f5f5 25%, #ececec 50%, #f5f5f5 75%); background-size: 200% 100%; animation: shimmer 1.5s linear infinite; }
@keyframes shimmer { 0% { background-position: 200% 0;} 100% { background-position: -200% 0;} }
.placeholder-line { height: 12px; background: rgba(255,255,255,0.6); border-radius: 4px; }
.placeholder-line.w70 { width: 70%; }
.placeholder-line.w90 { width: 90%; }
.placeholder-line.w50 { width: 50%; }

.card-top { display: flex; align-items: center; gap: 12px; }
.avatar { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 700; font-size: 16px; flex-shrink: 0; }
.avatar.lg { width: 56px; height: 56px; font-size: 22px; }
.card-meta { flex: 1; min-width: 0; }
.card-name { font-weight: 700; font-size: 13px; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-username { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #999; }
.entity-badge { font-size: 9px; padding: 3px 8px; background: #F5F5F5; color: #666; border-radius: 3px; font-family: 'JetBrains Mono', monospace; }
.card-bio { font-size: 12px; color: #555; line-height: 1.5; max-height: 60px; overflow: hidden; }
.card-attrs { display: flex; flex-wrap: wrap; gap: 6px; }
.attr { font-size: 10px; padding: 2px 8px; background: #FAFAFA; border: 1px solid #EEE; border-radius: 10px; color: #666; }
.topics { display: flex; flex-wrap: wrap; gap: 4px; }
.topic-tag { font-size: 10px; color: #FF5722; }

.empty-state { grid-column: 1 / -1; text-align: center; padding: 60px; color: #999; }
.empty-icon { font-size: 48px; opacity: 0.3; margin-bottom: 12px; }

.overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); z-index: 200; display: flex; align-items: center; justify-content: center; padding: 32px; }
.overlay-card { background: #FFF; border-radius: 10px; max-width: 720px; width: 100%; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
.overlay-header { display: flex; align-items: center; gap: 16px; padding: 20px 24px; border-bottom: 1px solid #EEE; background: #FAFAFA; }
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
</style>
