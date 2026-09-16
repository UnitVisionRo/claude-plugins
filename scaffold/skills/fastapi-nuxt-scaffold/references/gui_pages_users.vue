<!-- Destination: gui/app/pages/users.vue -->
<template>
  <v-row justify="center">
    <v-col cols="12" lg="10">
      <v-card class="mb-6">
        <v-card-title>Invite a user</v-card-title>
        <v-form @submit.prevent="submitInvite">
          <v-card-text>
            <v-alert v-if="error" class="mb-4" density="compact" type="error" variant="tonal">{{ error }}</v-alert>

            <!-- The link is shown as well as emailed: delivery is best-effort, and before SMTP
                 is configured this is the only way to hand an invitation over. -->
            <v-alert v-if="lastInviteUrl" class="mb-4" type="success" variant="tonal">
              <div class="mb-2">Invitation sent. You can also share the link directly:</div>
              <code class="d-block pa-2 rounded bg-surface" style="word-break: break-all;">{{ lastInviteUrl }}</code>
            </v-alert>

            <v-row density="compact">
              <v-col cols="12" md="5">
                <v-text-field v-model="form.email" label="Email" :rules="[required]" type="email" />
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field v-model="form.name" label="Name (optional)" />
              </v-col>
              <v-col cols="12" md="3">
                <v-select v-model="form.role" :items="['USER', 'ADMIN']" label="Role" />
              </v-col>
            </v-row>
          </v-card-text>
          <v-card-actions class="px-4 pb-4">
            <v-btn color="primary" :loading="inviting" type="submit" variant="flat">Send invitation</v-btn>
          </v-card-actions>
        </v-form>
      </v-card>

      <v-card :loading="loading">
        <v-card-title>Users</v-card-title>
        <v-table>
          <thead>
            <tr>
              <th>Email</th><th>Username</th><th>Name</th><th>Role</th><th>Status</th><th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.uuid">
              <td>{{ user.email }}</td>
              <td>{{ user.username ?? '—' }}</td>
              <td>{{ user.name ?? '—' }}</td>
              <td><v-chip size="small">{{ user.role }}</v-chip></td>
              <td>
                <v-chip :color="user.isPending ? 'warning' : 'success'" size="small" variant="tonal">
                  {{ user.isPending ? 'Invited' : 'Active' }}
                </v-chip>
              </td>
              <td class="text-right">
                <v-btn
                  v-if="user.isPending"
                  :loading="resendingFor === user.uuid"
                  size="small"
                  variant="text"
                  @click="resend(user.uuid)"
                >
                  Resend
                </v-btn>
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-card>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
import { inviteUser, listUsers, resendInvite } from '~/generated/rest'
import type { Role, UserListItem } from '~/generated/rest'

// The middleware reads this; the API enforces it for real (`require_admin`).
definePageMeta({ requiresAdmin: true })

const users = ref<UserListItem[]>([])
const loading = ref(false)
const inviting = ref(false)
const resendingFor = ref<string | null>(null)
const error = ref('')
const lastInviteUrl = ref('')

const form = reactive({ email: '', name: '', role: 'USER' as Role })

const required = (value: string) => !!value || 'Required'

async function load() {
    loading.value = true
    try {
        users.value = await listUsers()
    } catch (requestError) {
        error.value = apiErrorMessage(requestError)
    } finally {
        loading.value = false
    }
}

onMounted(load)

async function submitInvite() {
    if (!form.email) return
    error.value = ''
    lastInviteUrl.value = ''
    inviting.value = true
    try {
        const result = await inviteUser({
            body: { email: form.email, role: form.role, name: form.name || null },
        })
        lastInviteUrl.value = result.inviteUrl
        form.email = ''
        form.name = ''
        await load()
    } catch (requestError) {
        error.value = apiErrorMessage(requestError)
    } finally {
        inviting.value = false
    }
}

async function resend(userUuid: string) {
    error.value = ''
    lastInviteUrl.value = ''
    resendingFor.value = userUuid
    try {
        // A fresh token each time, so the previous link stops working.
        const result = await resendInvite({ path: { user_uuid: userUuid } })
        lastInviteUrl.value = result.inviteUrl
    } catch (requestError) {
        error.value = apiErrorMessage(requestError)
    } finally {
        resendingFor.value = null
    }
}
</script>
