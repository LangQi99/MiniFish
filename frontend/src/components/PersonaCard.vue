<template>
  <div class="persona-card" :class="{ pulse: streaming }" @click="$emit('select', persona)">
    <div class="card-top">
      <div class="avatar" :style="{ background: avatarColor }">
        {{ (persona.name || '?').slice(0, 1) }}
      </div>
      <div class="card-meta">
        <div class="card-name">{{ persona.name }}</div>
        <div class="card-username">@{{ persona.user_name }}</div>
      </div>
      <span class="entity-badge">{{ persona.source_entity_type || 'Entity' }}</span>
    </div>
    <div class="card-bio">{{ persona.bio }}</div>
    <div class="card-attrs">
      <span v-if="persona.age" class="attr">{{ persona.age }}岁</span>
      <span v-if="persona.gender" class="attr">{{ persona.gender }}</span>
      <span v-if="persona.mbti" class="attr">{{ persona.mbti }}</span>
      <span v-if="persona.country" class="attr">{{ persona.country }}</span>
      <span v-if="persona.profession" class="attr">{{ persona.profession }}</span>
    </div>
    <div v-if="persona.interested_topics?.length" class="topics">
      <span v-for="t in persona.interested_topics.slice(0, 5)" :key="t" class="topic-tag">#{{ t }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  persona: { type: Object, required: true },
  streaming: { type: Boolean, default: false },
})

defineEmits(['select'])

const COLORS = ['#FF6B35', '#004E89', '#7B2D8E', '#1A936F', '#C5283D', '#E9724C', '#3498db', '#9b59b6', '#27ae60', '#f39c12']

const avatarColor = computed(() => COLORS[(props.persona.user_id || 0) % COLORS.length])
</script>

<style scoped>
.persona-card { background: #FFF; border: 1px solid #EAEAEA; border-radius: 8px; padding: 16px; cursor: pointer; transition: all 0.2s; display: flex; flex-direction: column; gap: 10px; }
.persona-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); transform: translateY(-2px); }
.persona-card.pulse { animation: cardPulse 1.5s ease-out; }
@keyframes cardPulse {
  0% { box-shadow: 0 0 0 0 rgba(255, 87, 34, 0.55); transform: scale(1.02); }
  100% { box-shadow: 0 0 0 12px rgba(255, 87, 34, 0); transform: scale(1); }
}
.card-top { display: flex; align-items: center; gap: 12px; }
.avatar { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 700; font-size: 16px; flex-shrink: 0; }
.card-meta { flex: 1; min-width: 0; }
.card-name { font-weight: 700; font-size: 13px; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-username { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #999; }
.entity-badge { font-size: 9px; padding: 3px 8px; background: #F5F5F5; color: #666; border-radius: 3px; font-family: 'JetBrains Mono', monospace; }
.card-bio { font-size: 12px; color: #555; line-height: 1.5; max-height: 60px; overflow: hidden; }
.card-attrs { display: flex; flex-wrap: wrap; gap: 6px; }
.attr { font-size: 10px; padding: 2px 8px; background: #FAFAFA; border: 1px solid #EEE; border-radius: 10px; color: #666; }
.topics { display: flex; flex-wrap: wrap; gap: 4px; }
.topic-tag { font-size: 10px; color: #FF5722; }
</style>
