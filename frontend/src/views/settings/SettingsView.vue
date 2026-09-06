<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { KeyRound, Save, Info, HardDrive } from 'lucide-vue-next'
import { getJson, requestJson } from '@/api/http'

// 修改密码
const passwordForm = ref({
  current_password: '',
  new_password: '',
  confirm_password: '',
})
const passwordError = ref('')
const passwordSuccess = ref('')
const changingPassword = ref(false)

// 系统信息
interface SystemInfo {
  python_version: string
  django_version: string
  database_type: string
  celery_status: string
  debug: boolean
}
const systemInfo = ref<SystemInfo | null>(null)
const sysInfoError = ref('')

// 存储使用情况
interface StorageUsage {
  upload: string
  results: string
  keyframes: string
}
const storageUsage = ref<StorageUsage | null>(null)
const storageError = ref('')

async function changePassword() {
  passwordError.value = ''
  passwordSuccess.value = ''
  if (!passwordForm.value.current_password) {
    passwordError.value = '请输入当前密码'
    return
  }
  if (!passwordForm.value.new_password) {
    passwordError.value = '请输入新密码'
    return
  }
  if (passwordForm.value.new_password.length < 6) {
    passwordError.value = '新密码至少 6 个字符'
    return
  }
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    passwordError.value = '两次密码输入不一致'
    return
  }
  changingPassword.value = true
  try {
    await requestJson('/auth/change-password/', {
      method: 'POST',
      body: JSON.stringify({
        current_password: passwordForm.value.current_password,
        new_password: passwordForm.value.new_password,
      }),
    })
    passwordSuccess.value = '密码修改成功'
    passwordForm.value = { current_password: '', new_password: '', confirm_password: '' }
  } catch (reason) {
    passwordError.value = reason instanceof Error ? reason.message : '修改密码失败'
  } finally {
    changingPassword.value = false
  }
}

async function fetchSystemInfo() {
  try {
    systemInfo.value = await getJson<SystemInfo>('/system/info/')
  } catch (reason) {
    sysInfoError.value = reason instanceof Error ? reason.message : '获取系统信息失败'
  }
}

async function fetchStorageUsage() {
  try {
    storageUsage.value = await getJson<StorageUsage>('/system/storage/')
  } catch (reason) {
    storageError.value = reason instanceof Error ? reason.message : '获取存储信息失败'
  }
}

onMounted(() => {
  fetchSystemInfo()
  fetchStorageUsage()
})
</script>

<template>
  <section class="workspace">
    <div class="page-heading">
      <div>
        <span class="eyebrow">SETTINGS / SYSTEM</span>
        <h2>系统设置</h2>
        <p>管理系统配置和个人账户</p>
      </div>
    </div>

    <!-- 修改密码 -->
    <div class="settings-section">
      <div class="section-header">
        <KeyRound :size="16" />
        <h3>修改密码</h3>
      </div>
      <div class="section-body">
        <div v-if="passwordError" class="form-error">{{ passwordError }}</div>
        <div v-if="passwordSuccess" class="form-success">{{ passwordSuccess }}</div>
        <div class="password-form">
          <label class="form-field">
            <span>当前密码</span>
            <input
              v-model="passwordForm.current_password"
              type="password"
              placeholder="输入当前密码"
            />
          </label>
          <label class="form-field">
            <span>新密码</span>
            <input
              v-model="passwordForm.new_password"
              type="password"
              placeholder="输入新密码（至少 6 位）"
            />
          </label>
          <label class="form-field">
            <span>确认新密码</span>
            <input
              v-model="passwordForm.confirm_password"
              type="password"
              placeholder="再次输入新密码"
            />
          </label>
          <button
            class="primary-button"
            :disabled="changingPassword"
            @click="changePassword"
          >
            <Save :size="14" /> {{ changingPassword ? '修改中…' : '修改密码' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 系统信息 -->
    <div class="settings-section">
      <div class="section-header">
        <Info :size="16" />
        <h3>系统信息</h3>
      </div>
      <div class="section-body">
        <div v-if="sysInfoError" class="form-error">{{ sysInfoError }}</div>
        <div v-else-if="systemInfo" class="info-grid">
          <div class="info-row">
            <span class="info-label">Python 版本</span>
            <span class="info-value">{{ systemInfo.python_version }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Django 版本</span>
            <span class="info-value">{{ systemInfo.django_version }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">数据库类型</span>
            <span class="info-value">{{ systemInfo.database_type }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Celery 状态</span>
            <span
              class="info-value"
              :style="{ color: systemInfo.celery_status === 'running' ? '#22C55E' : '#EF4444' }"
            >
              {{ systemInfo.celery_status === 'running' ? '运行中' : '未运行' }}
            </span>
          </div>
          <div class="info-row">
            <span class="info-label">Debug 模式</span>
            <span class="info-value">{{ systemInfo.debug ? '开启' : '关闭' }}</span>
          </div>
        </div>
        <div v-else class="placeholder-text">加载中…</div>
      </div>
    </div>

    <!-- 存储使用情况 -->
    <div class="settings-section">
      <div class="section-header">
        <HardDrive :size="16" />
        <h3>存储使用情况</h3>
      </div>
      <div class="section-body">
        <div v-if="storageError" class="form-error">{{ storageError }}</div>
        <div v-else-if="storageUsage" class="info-grid">
          <div class="info-row">
            <span class="info-label">Upload 目录</span>
            <span class="info-value">{{ storageUsage.upload }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Results 目录</span>
            <span class="info-value">{{ storageUsage.results }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Keyframes 目录</span>
            <span class="info-value">{{ storageUsage.keyframes }}</span>
          </div>
        </div>
        <div v-else class="placeholder-text">加载中…</div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.page-heading {
  display: flex; align-items: flex-end; justify-content: space-between;
  padding-bottom: 20px; border-bottom: 1px solid #1E2A45; margin-bottom: 20px;
}
.page-heading h2 { margin: 8px 0 5px; font-size: 27px; }
.page-heading p { margin: 0; color: #789084; font-size: 12px; }

.settings-section {
  margin-bottom: 20px; background: #111A2E; border: 1px solid #1E2A45;
  border-radius: 6px; overflow: hidden;
}
.section-header {
  display: flex; align-items: center; gap: 8px;
  padding: 14px 18px; border-bottom: 1px solid #1E2A45;
  color: #E2E8F0;
}
.section-header h3 { margin: 0; font-size: 14px; font-weight: 500; }
.section-body { padding: 18px; }

.form-error {
  padding: 8px 12px; margin-bottom: 12px; color: #EF4444;
  background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3);
  border-radius: 4px; font-size: 12px;
}
.form-success {
  padding: 8px 12px; margin-bottom: 12px; color: #22C55E;
  background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.3);
  border-radius: 4px; font-size: 12px;
}

.password-form { display: grid; gap: 14px; max-width: 400px; }
.form-field { display: grid; gap: 6px; }
.form-field span { color: #94A3B8; font-size: 12px; }
.form-field input {
  width: 100%; height: 40px; padding: 0 12px; color: #E2E8F0;
  background: #0F172A; border: 1px solid #1E2A45; border-radius: 4px;
  outline: none; font-size: 13px;
}
.form-field input:focus { border-color: #3B82F6; }

.primary-button {
  display: flex; align-items: center; gap: 6px; min-height: 38px;
  padding: 0 16px; color: #06170f; background: #39e58c; border: 0;
  border-radius: 4px; font-size: 12px; font-weight: 700; cursor: pointer; width: fit-content;
}
.primary-button:hover { background: #63eea5; }
.primary-button:disabled { opacity: 0.55; cursor: not-allowed; }

.info-grid { display: grid; gap: 10px; }
.info-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #1E2A45; }
.info-row:last-child { border-bottom: 0; }
.info-label { color: #64748B; font-size: 12px; }
.info-value { color: #E2E8F0; font-size: 12px; font-family: ui-monospace, monospace; }

.placeholder-text { color: #64748B; font-size: 12px; }
</style>