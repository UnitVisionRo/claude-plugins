<!-- Destination: gui/app/pages/account.vue -->
<template>
  <v-row justify="center">
    <v-col cols="12" md="8">
      <v-card :loading="loading">
        <v-card-title>Two-step verification</v-card-title>
        <v-card-text>
          <v-alert v-if="error" class="mb-4" density="compact" type="error" variant="tonal">{{ error }}</v-alert>
          <v-alert v-if="notice" class="mb-4" density="compact" type="success" variant="tonal">{{ notice }}</v-alert>

          <!-- Current state -->
          <template v-if="step === 'status'">
            <v-alert v-if="status.method" type="success" variant="tonal">
              Two-step verification is on. Method: <strong>{{ methodLabel(status.method) }}</strong>.
            </v-alert>
            <p v-else class="text-body-2">
              Add a second step to signing in: as well as your password, we ask for a one-time code.
              You can receive it by email, or generate it with an authenticator app.
            </p>
          </template>

          <!-- Step 1: choose a method, confirm with the current password -->
          <v-form v-else-if="step === 'choose'" @submit.prevent="startSetup">
            <v-select
              v-model="setupMethod"
              class="mb-2"
              :items="methodItems"
              label="Method"
            />
            <v-text-field
              v-model="currentPassword"
              autocomplete="current-password"
              hint="Confirm it is really you making this change."
              label="Current password"
              persistent-hint
              type="password"
            />
          </v-form>

          <!-- Step 2: enrol and confirm a code -->
          <v-form v-else-if="step === 'confirm'" @submit.prevent="confirmSetup">
            <template v-if="setupResult.otpauthUri">
              <p class="mb-3 text-body-2">
                Scan this with Microsoft Authenticator, Google Authenticator or any compatible app.
              </p>
              <div class="d-flex justify-center pa-4 mb-3 bg-white rounded border">
                <QrcodeVue :size="180" :value="setupResult.otpauthUri" />
              </div>
              <div class="text-caption text-medium-emphasis">Can't scan? Enter this key manually:</div>
              <div class="mb-4 pa-2 rounded border" style="word-break: break-all; user-select: all; font-family: monospace;">
                {{ setupResult.secret }}
              </div>
            </template>
            <p v-else class="mb-3 text-body-2">We emailed you a code. Enter it below to finish.</p>

            <v-text-field
              v-model="code"
              autocomplete="one-time-code"
              inputmode="numeric"
              label="Verification code"
              maxlength="6"
            />
          </v-form>

          <!-- Turning it off -->
          <v-form v-else @submit.prevent="disable">
            <v-alert class="mb-4" type="warning" variant="tonal">
              With two-step verification off, your password is the only thing protecting this account.
            </v-alert>
            <v-text-field
              v-model="currentPassword"
              autocomplete="current-password"
              label="Current password"
              type="password"
            />
          </v-form>
        </v-card-text>

        <v-card-actions class="px-4 pb-4">
          <template v-if="step === 'status'">
            <v-btn color="primary" variant="flat" @click="openSetup">
              {{ status.method ? 'Change method' : 'Turn on' }}
            </v-btn>
            <v-btn v-if="status.method" color="error" variant="text" @click="openDisable">Turn off</v-btn>
          </template>
          <template v-else-if="step === 'choose'">
            <v-btn color="primary" :loading="busy" variant="flat" @click="startSetup">Continue</v-btn>
            <v-btn variant="text" @click="reset">Cancel</v-btn>
          </template>
          <template v-else-if="step === 'confirm'">
            <v-btn color="primary" :loading="busy" variant="flat" @click="confirmSetup">Confirm</v-btn>
            <v-btn variant="text" @click="reset">Cancel</v-btn>
          </template>
          <template v-else>
            <v-btn color="error" :loading="busy" variant="flat" @click="disable">Turn off</v-btn>
            <v-btn variant="text" @click="reset">Cancel</v-btn>
          </template>
        </v-card-actions>
      </v-card>

      <v-card class="mt-6" :loading="loadingSessions">
        <v-card-title>Where you are signed in</v-card-title>
        <v-card-subtitle class="text-wrap">
          One entry per browser. Signing one out immediately stops it renewing its session.
        </v-card-subtitle>
        <v-card-text>
          <v-alert v-if="sessionsError" class="mb-4" density="compact" type="error" variant="tonal">
            {{ sessionsError }}
          </v-alert>
          <v-table>
            <thead>
              <tr><th>Browser</th><th>IP</th><th>Last used</th><th /></tr>
            </thead>
            <tbody>
              <tr v-for="session in sessions" :key="session.deviceId">
                <td>
                  {{ describeBrowser(session.userAgent) }}
                  <v-chip v-if="session.isCurrent" class="ml-2" color="primary" size="x-small" variant="tonal">
                    This browser
                  </v-chip>
                </td>
                <td>{{ session.ip ?? '—' }}</td>
                <td>{{ formatWhen(session.lastUsedAt) }}</td>
                <td class="text-right">
                  <v-btn
                    v-if="!session.isCurrent"
                    color="error"
                    :loading="revoking === session.deviceId"
                    size="small"
                    variant="text"
                    @click="revoke(session.deviceId)"
                  >
                    Sign out
                  </v-btn>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-card-text>
        <v-card-actions class="px-4 pb-4">
          <v-btn
            color="error"
            :disabled="sessions.length < 2"
            :loading="revoking === 'all'"
            variant="tonal"
            @click="revoke('all')"
          >
            Sign out everywhere else
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
import QrcodeVue from 'qrcode.vue'

import {
    confirmTwoFactor,
    disableTwoFactor,
    getTwoFactorStatus,
    listSessions,
    revokeSession,
    setupTwoFactor,
} from '~/generated/rest'
import type { ActiveSession, TwoFactorMethod, TwoFactorSetupResult, TwoFactorStatus } from '~/generated/rest' 

type Step = 'status' | 'choose' | 'confirm' | 'disable'

const step = ref<Step>('status')
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')

const status = ref<TwoFactorStatus>({})
const setupResult = ref<TwoFactorSetupResult>({})
const setupMethod = ref<TwoFactorMethod>('TOTP')
const currentPassword = ref('')
const code = ref('')

const methodItems = [
    { title: 'Authenticator app', value: 'TOTP' },
    { title: 'Email', value: 'EMAIL' },
]

const methodLabel = (method?: TwoFactorMethod | null) =>
    methodItems.find(item => item.value === method)?.title ?? String(method)

async function loadStatus() {
    loading.value = true
    try {
        status.value = await getTwoFactorStatus()
    } catch (requestError) {
        error.value = apiErrorMessage(requestError)
    } finally {
        loading.value = false
    }
}

// --- active sessions -------------------------------------------------------------------

const sessions = ref<ActiveSession[]>([])
const loadingSessions = ref(false)
const sessionsError = ref('')
const revoking = ref<string | null>(null)

async function loadSessions() {
    loadingSessions.value = true
    try {
        sessions.value = await listSessions()
    } catch (requestError) {
        sessionsError.value = apiErrorMessage(requestError)
    } finally {
        loadingSessions.value = false
    }
}

async function revoke(deviceId: string) {
    sessionsError.value = ''
    revoking.value = deviceId
    try {
        await revokeSession({ path: { device_id: deviceId } })
        await loadSessions()
    } catch (requestError) {
        sessionsError.value = apiErrorMessage(requestError)
    } finally {
        revoking.value = null
    }
}

/**
 * A readable name for a raw User-Agent string.
 *
 * Deliberately crude, and deliberately not a UA-parsing library: this is a hint that helps
 * someone recognise their own devices in a list, not analytics. Anything it fails to match
 * falls back to the raw string, which is still more useful than "Unknown".
 */
function describeBrowser(userAgent?: string | null): string {
    if (!userAgent) return 'Unknown browser'
    const browser = /Edg\//.test(userAgent) ? 'Edge'
        : /OPR\//.test(userAgent) ? 'Opera'
            : /Firefox\//.test(userAgent) ? 'Firefox'
                : /Chrome\//.test(userAgent) ? 'Chrome'
                    : /Safari\//.test(userAgent) ? 'Safari'
                        : null
    const platform = /Android/.test(userAgent) ? 'Android'
        : /iPhone|iPad/.test(userAgent) ? 'iOS'
            : /Mac OS X/.test(userAgent) ? 'macOS'
                : /Windows/.test(userAgent) ? 'Windows'
                    : /Linux/.test(userAgent) ? 'Linux'
                        : null
    if (!browser && !platform) return userAgent
    return [browser, platform].filter(Boolean).join(' on ')
}

function formatWhen(value: string): string {
    return new Date(value).toLocaleString()
}

onMounted(() => {
    loadStatus()
    loadSessions()
})

function reset() {
    step.value = 'status'
    currentPassword.value = ''
    code.value = ''
    setupResult.value = {}
    error.value = ''
}

function openSetup() {
    reset()
    setupMethod.value = status.value.method ?? 'TOTP'
    step.value = 'choose'
}

function openDisable() {
    reset()
    step.value = 'disable'
}

async function startSetup() {
    error.value = ''
    notice.value = ''
    busy.value = true
    try {
        // The ACTIVE method is untouched until the code below is confirmed, so cancelling here
        // leaves the account exactly as protected as it was.
        setupResult.value = await setupTwoFactor({
            body: { method: setupMethod.value, currentPassword: currentPassword.value },
        })
        code.value = ''
        step.value = 'confirm'
    } catch (requestError) {
        error.value = apiErrorMessage(requestError)
    } finally {
        busy.value = false
    }
}

async function confirmSetup() {
    error.value = ''
    busy.value = true
    try {
        await confirmTwoFactor({ body: { code: code.value } })
        notice.value = 'Two-step verification is on.'
        reset()
        await loadStatus()
    } catch (requestError) {
        error.value = apiErrorMessage(requestError)
        code.value = ''
    } finally {
        busy.value = false
    }
}

async function disable() {
    error.value = ''
    busy.value = true
    try {
        await disableTwoFactor({ body: { currentPassword: currentPassword.value } })
        notice.value = 'Two-step verification is off.'
        reset()
        await loadStatus()
    } catch (requestError) {
        error.value = apiErrorMessage(requestError)
    } finally {
        busy.value = false
    }
}
</script>
