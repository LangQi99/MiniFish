<template>
  <div class="home-container">
    <nav class="navbar">
      <div class="nav-brand">MINIFISH</div>
      <div class="nav-links">
        <span class="nav-link" @click="goDashboard">仪表盘 / 历史</span>
      </div>
    </nav>

    <div class="main-content">
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row">
            <span class="orange-tag">长文本 → GraphRAG → Agent 人设</span>
            <span class="version-text">/ MiniFish V0.1</span>
          </div>

          <h1 class="main-title">
            两步精简版<br />
            <span class="gradient-text">长文本到 Agent 群</span>
          </h1>

          <div class="hero-desc">
            <p>
              <span class="highlight-bold">Step 01</span> 上传长文本与一段模拟需求,并行构建知识图谱并实时绘制;
              <span class="highlight-bold">Step 02</span> 基于图谱节点并行生成详细 Agent 人设。
              全流程并行加速,告别串行等待<span class="blinking-cursor">_</span>
            </p>
          </div>
        </div>
      </section>

      <section class="dashboard-section">
        <div class="left-panel">
          <div class="panel-header"><span class="status-dot">■</span> 工作流</div>
          <div class="workflow-list">
            <div class="workflow-item">
              <span class="step-num">01</span>
              <div class="step-info">
                <div class="step-title">模拟实例初始化</div>
                <div class="step-desc">本体生成 → 并行抽取实体/关系 → 实时绘制 GraphRAG</div>
              </div>
            </div>
            <div class="workflow-item">
              <span class="step-num">02</span>
              <div class="step-info">
                <div class="step-title">生成 Agent 人设</div>
                <div class="step-desc">基于图谱节点并行调用 LLM 生成详细人设(个人 / 群体两套模板)</div>
              </div>
            </div>
          </div>
        </div>

        <div class="right-panel">
          <div class="console-box">
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">01 / 长文本</span>
                <span class="console-meta">支持: PDF, MD, TXT</span>
              </div>

              <div
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="isDragOver = false"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input ref="fileInput" type="file" multiple accept=".pdf,.md,.txt" @change="handleFileSelect" style="display:none" :disabled="loading" />
                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">拖拽文件上传</div>
                  <div class="upload-hint">或点击浏览文件系统</div>
                </div>
                <div v-else class="file-list">
                  <div v-for="(f, idx) in files" :key="idx" class="file-item">
                    <span class="file-icon">📄</span>
                    <span class="file-name">{{ f.name }}</span>
                    <button @click.stop="removeFile(idx)" class="remove-btn">×</button>
                  </div>
                </div>
              </div>
            </div>

            <div class="console-divider"><span>输入参数</span></div>

            <div class="console-section">
              <div class="console-header">
                <span class="console-label">>_ 02 / 模拟需求</span>
              </div>
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  placeholder="// 用一段话描述你想模拟/预测的场景"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">引擎: MiniFish-V0.1</div>
              </div>
            </div>

            <div class="console-section btn-section">
              <button class="start-engine-btn" @click="startSimulation" :disabled="!canSubmit || loading">
                <span v-if="!loading">启动 Step 01</span>
                <span v-else>初始化中...</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { setPendingUpload } from '../store/pendingUpload'

const router = useRouter()

const formData = ref({ simulationRequirement: '' })
const files = ref([])
const loading = ref(false)
const isDragOver = ref(false)
const fileInput = ref(null)

const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
})

const triggerFileInput = () => { if (!loading.value) fileInput.value?.click() }

const handleFileSelect = (event) => {
  addFiles(Array.from(event.target.files))
}

const handleDragOver = () => { if (!loading.value) isDragOver.value = true }

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  addFiles(Array.from(e.dataTransfer.files))
}

const addFiles = (newFiles) => {
  const valid = newFiles.filter((f) => {
    const ext = f.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...valid)
}

const removeFile = (idx) => { files.value.splice(idx, 1) }

const startSimulation = () => {
  if (!canSubmit.value || loading.value) return
  setPendingUpload(files.value, formData.value.simulationRequirement)
  router.push('/dashboard/new')
}

const goDashboard = () => router.push('/dashboard/new')
</script>

<style scoped>
.home-container { min-height: 100vh; background: #FFF; font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif; color: #000; }
.navbar { height: 60px; background: #000; color: #FFF; display: flex; justify-content: space-between; align-items: center; padding: 0 40px; }
.nav-brand { font-family: 'JetBrains Mono', monospace; font-weight: 800; letter-spacing: 1px; font-size: 1.2rem; }
.nav-links { display: flex; align-items: center; gap: 18px; }
.nav-link { color: #FFF; cursor: pointer; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 500; }
.nav-link:hover { opacity: 0.8; }

.main-content { max-width: 1400px; margin: 0 auto; padding: 60px 40px; }

.hero-section { display: flex; justify-content: space-between; margin-bottom: 80px; }
.hero-left { flex: 1; }
.tag-row { display: flex; align-items: center; gap: 15px; margin-bottom: 25px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }
.orange-tag { background: #FF4500; color: #FFF; padding: 4px 10px; font-weight: 700; letter-spacing: 1px; font-size: 0.75rem; }
.version-text { color: #999; font-weight: 500; letter-spacing: 0.5px; }
.main-title { font-size: 4.5rem; line-height: 1.2; font-weight: 500; margin: 0 0 40px 0; letter-spacing: -2px; color: #000; }
.gradient-text { background: linear-gradient(90deg, #000 0%, #444 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.hero-desc { font-size: 1.05rem; line-height: 1.8; color: #666; max-width: 640px; }
.highlight-bold { color: #000; font-weight: 700; }
.blinking-cursor { color: #FF4500; animation: blink 1s step-end infinite; font-weight: 700; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

.dashboard-section { display: flex; gap: 60px; border-top: 1px solid #E5E5E5; padding-top: 60px; align-items: flex-start; }
.left-panel { flex: 0.8; }
.panel-header { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #999; display: flex; align-items: center; gap: 8px; margin-bottom: 20px; }
.status-dot { color: #FF4500; }
.workflow-list { display: flex; flex-direction: column; gap: 20px; padding: 24px; border: 1px solid #E5E5E5; }
.workflow-item { display: flex; gap: 18px; align-items: flex-start; }
.step-num { font-family: 'JetBrains Mono', monospace; font-weight: 700; opacity: 0.4; }
.step-title { font-weight: 600; margin-bottom: 4px; }
.step-desc { font-size: 0.85rem; color: #666; }

.right-panel { flex: 1.2; }
.console-box { border: 1px solid #CCC; padding: 8px; }
.console-section { padding: 20px; }
.console-section.btn-section { padding-top: 0; }
.console-header { display: flex; justify-content: space-between; margin-bottom: 15px; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #666; }
.upload-zone { border: 1px dashed #CCC; height: 200px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.3s; background: #FAFAFA; }
.upload-zone:hover { background: #F0F0F0; border-color: #999; }
.upload-placeholder { text-align: center; }
.upload-icon { width: 40px; height: 40px; border: 1px solid #DDD; display: flex; align-items: center; justify-content: center; margin: 0 auto 15px; color: #999; }
.upload-title { font-weight: 500; font-size: 0.9rem; margin-bottom: 5px; }
.upload-hint { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #999; }
.file-list { width: 100%; padding: 15px; display: flex; flex-direction: column; gap: 10px; }
.file-item { display: flex; align-items: center; background: #FFF; padding: 8px 12px; border: 1px solid #EEE; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
.file-name { flex: 1; margin: 0 10px; }
.remove-btn { background: none; border: none; cursor: pointer; font-size: 1.2rem; color: #999; }
.console-divider { display: flex; align-items: center; margin: 10px 0; }
.console-divider::before, .console-divider::after { content: ''; flex: 1; height: 1px; background: #EEE; }
.console-divider span { padding: 0 15px; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #BBB; letter-spacing: 1px; }
.input-wrapper { position: relative; border: 1px solid #DDD; background: #FAFAFA; }
.code-input { width: 100%; border: none; background: transparent; padding: 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; line-height: 1.6; resize: vertical; outline: none; min-height: 150px; }
.model-badge { position: absolute; bottom: 10px; right: 15px; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #AAA; }
.start-engine-btn { width: 100%; background: #000; color: #FFF; border: none; padding: 20px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 1.1rem; display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: all 0.3s ease; letter-spacing: 1px; }
.start-engine-btn:not(:disabled):hover { background: #FF4500; }
.start-engine-btn:disabled { background: #E5E5E5; color: #999; cursor: not-allowed; }
</style>
