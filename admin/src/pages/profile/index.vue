<template>
  <div class="profile-page">
    <el-card>
      <template #header>
        <span>个人中心</span>
      </template>

      <el-form ref="formRef" :model="form" label-width="100px">
        <el-form-item label="用户名">
          <el-input :value="authStore.adminInfo?.username" disabled />
        </el-form-item>
        <el-form-item label="真实姓名">
          <el-input v-model="form.realName" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input :model-value="maskPhone(authStore.adminInfo?.phone)" disabled />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input :model-value="maskEmail(authStore.adminInfo?.email)" disabled />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="margin-top: 20px;">
      <template #header>
        <span>修改密码</span>
      </template>

      <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-width="100px">
        <el-form-item label="旧密码" prop="oldPassword">
          <el-input v-model="passwordForm.oldPassword" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="passwordForm.newPassword" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="passwordForm.confirmPassword" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="changingPassword" @click="handleChangePassword">修改密码</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/store/modules/auth'
import { changePassword } from '@/api/auth'
import { ElMessage } from 'element-plus'
import { maskPhone, maskEmail } from '@/utils/mask'

const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const passwordFormRef = ref<FormInstance>()
const saving = ref(false)
const changingPassword = ref(false)

const form = reactive({
  realName: '',
})

const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const validateConfirmPassword = (_rule: any, value: string, callback: any) => {
  if (value !== passwordForm.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const passwordRules: FormRules = {
  oldPassword: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码长度不能少于8位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

onMounted(() => {
  if (authStore.adminInfo) {
    form.realName = authStore.adminInfo.realName || ''
  }
})

const handleSave = async () => {
  saving.value = true
  try {
    // TODO: 调用更新个人信息接口
    ElMessage.success('保存成功')
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleChangePassword = async () => {
  if (!passwordFormRef.value) return
  
  await passwordFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    changingPassword.value = true
    try {
      await changePassword({
        oldPassword: passwordForm.oldPassword,
        newPassword: passwordForm.newPassword,
      })
      ElMessage.success('密码修改成功')
      passwordForm.oldPassword = ''
      passwordForm.newPassword = ''
      passwordForm.confirmPassword = ''
    } catch (error) {
      ElMessage.error('密码修改失败')
    } finally {
      changingPassword.value = false
    }
  })
}
</script>

<style scoped>
.profile-page {
  max-width: 600px;
}
</style>
