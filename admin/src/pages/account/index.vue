<template>
  <div class="account-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>账号管理</span>
          <div class="header-right" v-if="isSuperAdmin">
            <el-button type="success" @click="handleGenerateOpen">
              <el-icon><Key /></el-icon>
              创建账号-生成随机密码
            </el-button>
            <el-button type="primary" @click="handleAdd">
              <el-icon><Plus /></el-icon>
              新增管理员
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="accounts" v-loading="loading" stripe>
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="realName" label="真实姓名" width="120" />
        <el-table-column label="手机号" width="120">
          <template #default="{ row }">{{ maskPhone(row.phone) }}</template>
        </el-table-column>
        <el-table-column label="邮箱">
          <template #default="{ row }">{{ maskEmail(row.email) }}</template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="getRoleTag(row.role)">{{ getRoleLabel(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" v-if="isSuperAdmin">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="warning" link @click="handleResetPassword(row)">重置密码</el-button>
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 生成账号弹窗（仅 super_admin；无需输入密码，系统随机生成） -->
    <el-dialog
      v-model="generateVisible"
      title="创建账号（生成随机密码）"
      width="500px"
      :close-on-click-modal="false"
      @closed="generateFormRef?.clearValidate()"
    >
      <el-form ref="generateFormRef" :model="generateForm" :rules="generateRules" label-width="100px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="generateForm.username" placeholder="登录用户名（2-20 字符）" />
        </el-form-item>
        <el-form-item label="真实姓名">
          <el-input v-model="generateForm.realName" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="generateForm.phone" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="generateForm.email" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="generateForm.role">
            <el-option label="超级管理员" value="super_admin" />
            <el-option label="管理员" value="admin" />
            <el-option label="查看者" value="viewer" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateVisible = false">取消</el-button>
        <el-button type="primary" :loading="generateLoading" @click="handleGenerateSubmit">生成</el-button>
      </template>
    </el-dialog>

    <!-- 一次性密码展示弹窗（提示仅此一次） -->
    <el-dialog v-model="passwordVisible" title="账号创建成功" width="460px" :close-on-click-modal="false">
      <el-alert type="warning" :closable="false" show-icon title="密码仅显示一次，请立即复制保存，关闭后将无法再次查看" />
      <div class="password-box">
        <div class="password-label">用户名：{{ generatedResult?.username }}</div>
        <div class="password-label">角色：{{ getRoleLabel(generatedResult?.role || '') }}</div>
        <div class="password-row">
          <el-input :model-value="generatedResult?.password" readonly>
            <template #append>
              <el-button @click="copyPassword">复制</el-button>
            </template>
          </el-input>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="passwordVisible = false">我已保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑管理员' : '新增管理员'"
      width="500px"
      :close-on-click-modal="false"
      @closed="formRef?.clearValidate()"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="isEdit" />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
        <el-form-item label="真实姓名">
          <el-input v-model="form.realName" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role">
            <el-option label="超级管理员" value="super_admin" />
            <el-option label="管理员" value="admin" />
            <el-option label="查看者" value="viewer" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码弹窗 -->
    <el-dialog v-model="resetPasswordVisible" title="重置密码" width="400px" :close-on-click-modal="false">
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-width="80px">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="resetForm.password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPasswordVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetLoading" @click="handleResetPasswordSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { Plus, Key } from '@element-plus/icons-vue'
import { getAccountList, createAccount, updateAccount, deleteAccount, resetPassword, generateAccount } from '@/api/account'
import type { AdminAccount, GenerateAccountResult } from '@/api/account'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/store/modules/auth'
import { maskPhone, maskEmail } from '@/utils/mask'

const authStore = useAuthStore()

// 当前登录管理员角色：写操作（建账号/改角色/删除/重置）仅 super_admin 可用
const isSuperAdmin = computed(() => authStore.adminInfo?.role === 'super_admin')

const accounts = ref<AdminAccount[]>([])
const loading = ref(false)
const formRef = ref<FormInstance>()
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const editId = ref<number>(0)

// 生成账号
const generateFormRef = ref<FormInstance>()
const generateVisible = ref(false)
const generateLoading = ref(false)
const passwordVisible = ref(false)
const generatedResult = ref<GenerateAccountResult | null>(null)

const resetPasswordVisible = ref(false)
const resetFormRef = ref<FormInstance>()
const resetLoading = ref(false)
const resetId = ref<number>(0)

const generateForm = reactive({
  username: '',
  realName: '',
  phone: '',
  email: '',
  role: 'admin',
})

const generateRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度在 2 到 20 个字符', trigger: 'blur' },
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

const form = reactive({
  username: '',
  password: '',
  realName: '',
  phone: '',
  email: '',
  role: 'admin',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码长度不能少于 8 位', trigger: 'blur' },
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

const resetForm = reactive({
  password: '',
})

const resetRules: FormRules = {
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码长度不能少于 8 位', trigger: 'blur' },
  ],
}

onMounted(() => {
  authStore.init()
  fetchAccounts()
})

const fetchAccounts = async () => {
  loading.value = true
  try {
    const res = await getAccountList()
    accounts.value = res.data
  } catch (error) {
    console.error('获取管理员列表失败', error)
  } finally {
    loading.value = false
  }
}

// ---- 生成账号（随机密码） ----
const handleGenerateOpen = () => {
  generateForm.username = ''
  generateForm.realName = ''
  generateForm.phone = ''
  generateForm.email = ''
  generateForm.role = 'admin'
  generateVisible.value = true
}

const handleGenerateSubmit = async () => {
  if (!generateFormRef.value) return

  await generateFormRef.value.validate(async (valid) => {
    if (!valid) return

    generateLoading.value = true
    try {
      const res = await generateAccount({
        username: generateForm.username,
        realName: generateForm.realName,
        phone: generateForm.phone,
        email: generateForm.email,
        role: generateForm.role,
      })
      generatedResult.value = res.data
      generateVisible.value = false
      passwordVisible.value = true
      await fetchAccounts()
    } catch (error) {
      console.error('生成账号失败', error)
    } finally {
      generateLoading.value = false
    }
  })
}

const copyPassword = async () => {
  if (!generatedResult.value?.password) return
  try {
    await navigator.clipboard.writeText(generatedResult.value.password)
    ElMessage.success('密码已复制，请妥善保存')
  } catch (error) {
    ElMessage.error('复制失败，请手动选择复制')
  }
}

// ---- 新增/编辑 ----
const handleAdd = () => {
  isEdit.value = false
  editId.value = 0
  form.username = ''
  form.password = ''
  form.realName = ''
  form.phone = ''
  form.email = ''
  form.role = 'admin'
  dialogVisible.value = true
}

const handleEdit = (row: AdminAccount) => {
  isEdit.value = true
  editId.value = row.id
  form.username = row.username
  form.password = ''
  form.realName = row.realName
  form.phone = row.phone
  form.email = row.email
  form.role = row.role
  dialogVisible.value = true
}

const handleDelete = async (row: AdminAccount) => {
  await ElMessageBox.confirm('确定删除该管理员吗？', '提示', {
    type: 'warning',
  })
  await deleteAccount(row.id)
  ElMessage.success('删除成功')
  await fetchAccounts()
}

const handleResetPassword = (row: AdminAccount) => {
  resetId.value = row.id
  resetForm.password = ''
  resetPasswordVisible.value = true
}

const handleResetPasswordSubmit = async () => {
  if (!resetFormRef.value) return

  await resetFormRef.value.validate(async (valid) => {
    if (!valid) return

    resetLoading.value = true
    try {
      await resetPassword(resetId.value, resetForm.password)
      ElMessage.success('密码重置成功')
      resetPasswordVisible.value = false
    } catch (error) {
      console.error('重置密码失败', error)
    } finally {
      resetLoading.value = false
    }
  })
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (isEdit.value) {
        await updateAccount(editId.value, {
          realName: form.realName,
          phone: form.phone,
          email: form.email,
          role: form.role,
        })
      } else {
        await createAccount(form)
      }
      ElMessage.success('操作成功')
      dialogVisible.value = false
      await fetchAccounts()
    } catch (error) {
      console.error('操作失败', error)
    } finally {
      submitting.value = false
    }
  })
}

const getRoleTag = (role: string) => {
  const map: Record<string, string> = {
    super_admin: 'danger',
    admin: 'primary',
    viewer: 'info',
  }
  return map[role] || 'info'
}

const getRoleLabel = (role: string) => {
  const map: Record<string, string> = {
    super_admin: '超级管理员',
    admin: '管理员',
    viewer: '查看者',
  }
  return map[role] || role
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-right {
  display: flex;
  gap: 16px;
}

.password-box {
  margin-top: 16px;
}

.password-label {
  margin-bottom: 8px;
  color: var(--el-text-color-regular);
}

.password-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
</style>
