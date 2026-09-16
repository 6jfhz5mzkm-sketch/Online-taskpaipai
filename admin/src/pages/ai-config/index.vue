<template>
  <div v-loading="loading" class="ai-config-page">
    <el-alert
      class="ai-config-page__intro"
      type="info"
      :closable="false"
      show-icon
      :title="AI_CONFIG_PAGE_INTRO_TEXT"
    />

    <el-empty v-if="!loading && items.length === 0" :description="AI_CONFIG_EMPTY_TEXT" />

    <el-card v-for="item in items" :key="item.entry" class="ai-config-card" shadow="never">
      <template #header>
        <div class="ai-config-card__header">
          <span class="ai-config-card__title">{{ AI_CONFIG_ENTRY_LABELS[item.entry] }}</span>
          <el-tag v-if="item.apiKeyStatus === 'ok'" type="success">{{ AI_CONFIG_KEY_STATUS_OK_TEXT }}</el-tag>
          <el-tag v-else-if="item.apiKeyStatus === 'none'" type="info">
            {{ AI_CONFIG_KEY_STATUS_NONE_TEXT }}
          </el-tag>
          <el-tag v-else type="danger" effect="dark">
            {{ AI_CONFIG_KEY_STATUS_DECRYPT_FAILED_TEXT }}
          </el-tag>
          <span class="ai-config-card__meta">{{ fingerprintText(item) }}</span>
          <span class="ai-config-card__meta">{{ updatedText(item) }}</span>
        </div>
      </template>

      <el-form label-width="220px" class="ai-config-form">
        <div class="ai-config-fields">
          <div class="ai-config-field">
            <el-form-item>
              <template #label>
                <span>{{ AI_CONFIG_FIELD_LABELS.apiKey }}</span>
                <el-tag class="ai-config-field__source" size="small" type="info" effect="plain">
                  {{ sourceLabel(item.effectiveSource.apiKey) }}
                </el-tag>
              </template>
              <el-input
                v-model="forms[item.entry].apiKey"
                type="password"
                show-password
                :placeholder="secretPlaceholder(item)"
              />
            </el-form-item>
          </div>
          <div class="ai-config-field">
            <el-form-item>
              <template #label>
                <span>{{ AI_CONFIG_FIELD_LABELS.baseUrl }}</span>
                <el-tag class="ai-config-field__source" size="small" type="info" effect="plain">
                  {{ sourceLabel(item.effectiveSource.baseUrl) }}
                </el-tag>
              </template>
              <el-input v-model="forms[item.entry].baseUrl" />
            </el-form-item>
          </div>
          <div class="ai-config-field">
            <el-form-item>
              <template #label>
                <span>{{ AI_CONFIG_FIELD_LABELS.model }}</span>
                <el-tag class="ai-config-field__source" size="small" type="info" effect="plain">
                  {{ sourceLabel(item.effectiveSource.model) }}
                </el-tag>
              </template>
              <el-input v-model="forms[item.entry].model" />
            </el-form-item>
          </div>
          <div class="ai-config-field">
            <el-form-item>
              <template #label>
                <span>{{ AI_CONFIG_FIELD_LABELS.timeoutMs }}</span>
                <el-tag class="ai-config-field__source" size="small" type="info" effect="plain">
                  {{ sourceLabel(item.effectiveSource.timeoutMs) }}
                </el-tag>
              </template>
              <el-input-number
                v-model="forms[item.entry].timeoutMs"
                class="ai-config-field__number"
                :min="AI_CONFIG_LIMITS.timeoutMs.min"
                :max="AI_CONFIG_LIMITS.timeoutMs.max"
                :step="1000"
                controls-position="right"
              />
            </el-form-item>
          </div>
          <div class="ai-config-field">
            <el-form-item>
              <template #label>
                <span>{{ AI_CONFIG_FIELD_LABELS.maxTokens }}</span>
                <el-tag class="ai-config-field__source" size="small" type="info" effect="plain">
                  {{ sourceLabel(item.effectiveSource.maxTokens) }}
                </el-tag>
              </template>
              <el-input-number
                v-model="forms[item.entry].maxTokens"
                class="ai-config-field__number"
                :min="AI_CONFIG_LIMITS.maxTokens.min"
                :max="AI_CONFIG_LIMITS.maxTokens.max"
                controls-position="right"
              />
            </el-form-item>
          </div>
          <div class="ai-config-field">
            <el-form-item>
              <template #label>
                <span>{{ AI_CONFIG_FIELD_LABELS.dailyLimit }}</span>
                <el-tag class="ai-config-field__source" size="small" type="info" effect="plain">
                  {{ sourceLabel(item.effectiveSource.dailyLimit) }}
                </el-tag>
              </template>
              <el-input-number
                v-model="forms[item.entry].dailyLimit"
                class="ai-config-field__number"
                :min="AI_CONFIG_LIMITS.dailyLimit.min"
                :max="AI_CONFIG_LIMITS.dailyLimit.max"
                controls-position="right"
              />
            </el-form-item>
          </div>
          <div class="ai-config-field">
            <el-form-item :label="AI_CONFIG_FIELD_LABELS.enabled">
              <el-switch v-model="forms[item.entry].enabled" />
              <span class="ai-config-card__meta ai-config-card__hint">
                {{ AI_CONFIG_ENABLED_HINT_TEXT }}
              </span>
            </el-form-item>
          </div>
        </div>
      </el-form>

      <div class="ai-config-card__actions">
        <el-button type="primary" :loading="savingEntry === item.entry" @click="handleSave(item)">
          {{ AI_CONFIG_SAVE_TEXT }}
        </el-button>
        <el-button :loading="verifyingEntry === item.entry" @click="handleVerify(item)">
          {{ AI_CONFIG_VERIFY_TEXT }}
        </el-button>
        <el-button
          type="warning"
          plain
          :loading="clearingEntry === item.entry"
          @click="handleClearKey(item)"
        >
          {{ AI_CONFIG_CLEAR_KEY_TEXT }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAiConfigList, updateAiConfig, verifyAiConfig } from '@/api/ai-config'
import type { AiConfigEntry, AiConfigItem, AiConfigPatch } from '@/api/ai-config'
import {
  AI_CONFIG_API_KEY_LENGTH_TEXT,
  AI_CONFIG_API_KEY_MASK_REJECT_TEXT,
  AI_CONFIG_BASE_URL_FORMAT_TEXT,
  AI_CONFIG_CLEAR_CONFIRM_CANCEL_TEXT,
  AI_CONFIG_CLEAR_CONFIRM_MESSAGE,
  AI_CONFIG_CLEAR_CONFIRM_OK_TEXT,
  AI_CONFIG_CLEAR_CONFIRM_TITLE,
  AI_CONFIG_CLEAR_KEY_TEXT,
  AI_CONFIG_CLEAR_OK_TEXT,
  AI_CONFIG_EMPTY_TEXT,
  AI_CONFIG_ENABLED_HINT_TEXT,
  AI_CONFIG_ENTRY_LABELS,
  AI_CONFIG_FIELD_LABELS,
  AI_CONFIG_FINGERPRINT_EMPTY_TEXT,
  AI_CONFIG_FINGERPRINT_PREFIX,
  AI_CONFIG_KEY_STATUS_DECRYPT_FAILED_TEXT,
  AI_CONFIG_KEY_STATUS_NONE_TEXT,
  AI_CONFIG_KEY_STATUS_OK_TEXT,
  AI_CONFIG_LIMITS,
  AI_CONFIG_MASK_PATTERN,
  AI_CONFIG_NO_DIRTY_TEXT,
  AI_CONFIG_PAGE_INTRO_TEXT,
  AI_CONFIG_SAVE_OK_TEXT,
  AI_CONFIG_SAVE_TEXT,
  AI_CONFIG_SECRET_PLACEHOLDER_CONFIGURED_PREFIX,
  AI_CONFIG_SECRET_PLACEHOLDER_EMPTY,
  AI_CONFIG_SECRET_PLACEHOLDER_SUFFIX,
  AI_CONFIG_SOURCE_LABELS,
  AI_CONFIG_UPDATED_EMPTY_TEXT,
  AI_CONFIG_UPDATED_PREFIX,
  AI_CONFIG_VERIFY_TEXT,
} from '@/constants/ai-config'

/** 可编辑表单（apiKey 始终初始为空：不预填掩码，留空 = 不修改） */
interface AiConfigForm {
  apiKey: string
  baseUrl: string
  model: string
  timeoutMs: number | null
  maxTokens: number | null
  dailyLimit: number | null
  enabled: boolean
}

type AiConfigBaseline = Omit<AiConfigForm, 'apiKey'>

const loading = ref(false)
const savingEntry = ref<AiConfigEntry | ''>('')
const verifyingEntry = ref<AiConfigEntry | ''>('')
const clearingEntry = ref<AiConfigEntry | ''>('')

const items = ref<AiConfigItem[]>([])
const forms = reactive<Record<string, AiConfigForm>>({})
const baselines = reactive<Record<string, AiConfigBaseline>>({})

const sourceLabel = (source: 'db' | 'env') => AI_CONFIG_SOURCE_LABELS[source] ?? source

const secretPlaceholder = (item: AiConfigItem) =>
  item.apiKeyMasked
    ? `${AI_CONFIG_SECRET_PLACEHOLDER_CONFIGURED_PREFIX}${item.apiKeyMasked}${AI_CONFIG_SECRET_PLACEHOLDER_SUFFIX}`
    : AI_CONFIG_SECRET_PLACEHOLDER_EMPTY

const fingerprintText = (item: AiConfigItem) =>
  item.apiKeyFingerprint
    ? `${AI_CONFIG_FINGERPRINT_PREFIX}${item.apiKeyFingerprint}`
    : AI_CONFIG_FINGERPRINT_EMPTY_TEXT

const updatedText = (item: AiConfigItem) =>
  item.updatedBy || item.updatedAt
    ? `${AI_CONFIG_UPDATED_PREFIX}${item.updatedBy ?? '—'} @ ${item.updatedAt ?? '—'}`
    : AI_CONFIG_UPDATED_EMPTY_TEXT

/** 服务端投影 → 表单 + 基线（基线用于 dirty 比对） */
const syncEntry = (item: AiConfigItem) => {
  forms[item.entry] = {
    apiKey: '',
    baseUrl: item.baseUrl ?? '',
    model: item.model ?? '',
    timeoutMs: item.timeoutMs,
    maxTokens: item.maxTokens,
    dailyLimit: item.dailyLimit,
    enabled: item.enabled,
  }
  baselines[item.entry] = {
    baseUrl: item.baseUrl ?? '',
    model: item.model ?? '',
    timeoutMs: item.timeoutMs,
    maxTokens: item.maxTokens,
    dailyLimit: item.dailyLimit,
    enabled: item.enabled,
  }
}

const replaceItem = (item: AiConfigItem) => {
  const index = items.value.findIndex((row) => row.entry === item.entry)
  if (index >= 0) items.value[index] = item
  else items.value.push(item)
  syncEntry(item)
}

const fetchList = async () => {
  loading.value = true
  try {
    const res = await getAiConfigList()
    items.value = res.data
    items.value.forEach(syncEntry)
  } catch (error) {
    // 错误提示由 request 拦截器按后端 message 统一展示，这里只记日志
    console.error('获取 AI 配置失败', error)
  } finally {
    loading.value = false
  }
}

/**
 * 组装 dirty 补丁（P7 §5.3）：
 * - 未改动的字段不进 payload（省略 = 不修改）；
 * - 文本/数字字段被清空 → 显式 null（清除自定义值、回落 env）；
 * - api_key 仅在用户实际填写时提交，且提交前拦截掩码/长度非法值。
 */
const buildPatch = (entry: AiConfigEntry): AiConfigPatch | null => {
  const form = forms[entry]
  const base = baselines[entry]
  const patch: AiConfigPatch = {}

  const apiKey = form.apiKey.trim()
  if (apiKey) {
    if (AI_CONFIG_MASK_PATTERN.test(apiKey)) {
      ElMessage.warning(AI_CONFIG_API_KEY_MASK_REJECT_TEXT)
      return null
    }
    if (apiKey.length < AI_CONFIG_LIMITS.apiKey.min || apiKey.length > AI_CONFIG_LIMITS.apiKey.max) {
      ElMessage.warning(AI_CONFIG_API_KEY_LENGTH_TEXT)
      return null
    }
    patch.api_key = apiKey
  }

  const baseUrl = form.baseUrl.trim()
  if (baseUrl !== base.baseUrl) {
    if (baseUrl && !/^https?:\/\//.test(baseUrl)) {
      ElMessage.warning(AI_CONFIG_BASE_URL_FORMAT_TEXT)
      return null
    }
    patch.base_url = baseUrl === '' ? null : baseUrl
  }

  const model = form.model.trim()
  if (model !== base.model) patch.model = model === '' ? null : model
  if (form.timeoutMs !== base.timeoutMs) patch.timeout_ms = form.timeoutMs ?? null
  if (form.maxTokens !== base.maxTokens) patch.max_tokens = form.maxTokens ?? null
  if (form.dailyLimit !== base.dailyLimit) patch.daily_limit = form.dailyLimit ?? null
  if (form.enabled !== base.enabled) patch.enabled = form.enabled

  if (Object.keys(patch).length === 0) {
    ElMessage.warning(AI_CONFIG_NO_DIRTY_TEXT)
    return null
  }
  return patch
}

const handleSave = async (item: AiConfigItem) => {
  const patch = buildPatch(item.entry)
  if (!patch) return
  savingEntry.value = item.entry
  try {
    const res = await updateAiConfig(item.entry, patch)
    replaceItem(res.data)
    ElMessage.success(AI_CONFIG_SAVE_OK_TEXT)
  } catch (error) {
    console.error('保存 AI 配置失败', error)
  } finally {
    savingEntry.value = ''
  }
}

const handleVerify = async (item: AiConfigItem) => {
  verifyingEntry.value = item.entry
  try {
    const res = await verifyAiConfig(item.entry)
    ElMessage.success(res.data.message)
  } catch (error) {
    // 失败恒 502：后端 message（尾部含错误码）由 request 拦截器展示，不自造同义文案
    console.error('AI 配置连通性自检失败', error)
  } finally {
    verifyingEntry.value = ''
  }
}

const handleClearKey = async (item: AiConfigItem) => {
  try {
    await ElMessageBox.confirm(AI_CONFIG_CLEAR_CONFIRM_MESSAGE, AI_CONFIG_CLEAR_CONFIRM_TITLE, {
      confirmButtonText: AI_CONFIG_CLEAR_CONFIRM_OK_TEXT,
      cancelButtonText: AI_CONFIG_CLEAR_CONFIRM_CANCEL_TEXT,
      type: 'warning',
    })
  } catch {
    return
  }
  clearingEntry.value = item.entry
  try {
    const res = await updateAiConfig(item.entry, { api_key: null })
    replaceItem(res.data)
    ElMessage.success(AI_CONFIG_CLEAR_OK_TEXT)
  } catch (error) {
    console.error('清除自定义密钥失败', error)
  } finally {
    clearingEntry.value = ''
  }
}

onMounted(fetchList)
</script>

<style scoped>
.ai-config-page__intro {
  margin-bottom: 16px;
}

/* 字段标签单行（原 150px 时最长标签「接口地址（base_url）+ 来源标签」余量为 0，字体/缩放差异即换行） */
.ai-config-form :deep(.el-form-item__label) {
  white-space: nowrap;
  align-items: center;
}

/* 两列等宽字段栅格：minmax(0, 1fr) 让子项可收缩，输入控件不会被挤出容器而裁切 */
.ai-config-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
}

.ai-config-field :deep(.el-form-item__content) {
  min-width: 0;
}

/* 窄视口（≤1280，任务单 §2.4）单列堆叠，避免为保两列而挤压标签 */
@media (max-width: 1280px) {
  .ai-config-fields {
    grid-template-columns: minmax(0, 1fr);
  }
}

.ai-config-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-config-card__title {
  font-size: 16px;
  color: var(--el-text-color-primary);
}

.ai-config-card__meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.ai-config-card__hint {
  margin-left: 8px;
}

.ai-config-field__source {
  margin-left: 8px;
}

.ai-config-field__number {
  width: 100%;
}

.ai-config-card__actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
</style>
