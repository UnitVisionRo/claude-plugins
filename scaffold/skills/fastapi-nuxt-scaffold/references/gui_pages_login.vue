<!-- Destination: gui/app/pages/login.vue -->
<template>
  <v-app>
    <v-main class="d-flex align-center">
      <v-container>
        <v-row justify="center">
          <v-col cols="12" md="6" lg="4">
            <v-card>
              <!-- Phase two: the password was accepted, a code is still needed. -->
              <template v-if="auth.pendingTwoFactor">
                <v-card-title>Two-step verification</v-card-title>
                <v-card-subtitle class="text-wrap">
                  {{ isEmailMethod ? 'We emailed you a verification code.' : 'Enter the code from your authenticator app.' }}
                </v-card-subtitle>
                <v-form @submit.prevent="submitCode">
                  <v-card-text>
                    <v-alert v-if="error" class="mb-4" density="compact" type="error" variant="tonal">{{ error }}</v-alert>
                    <v-text-field
                      v-model="code"
                      autocomplete="one-time-code"
                      autofocus
                      inputmode="numeric"
                      label="Verification code"
                      maxlength="6"
                      :rules="[required, sixDigits]"
                    />
                  </v-card-text>
                  <v-card-actions class="px-4 pb-4 d-flex flex-column ga-2 align-stretch">
                    <v-btn block color="primary" :loading="busy" type="submit" variant="flat">Verify</v-btn>
                    <v-btn
                      v-if="isEmailMethod"
                      block
                      :disabled="resendIn > 0 || busy"
                      variant="text"
                      @click="resend"
                    >
                      {{ resendIn > 0 ? `Resend code (${resendIn}s)` : 'Resend code' }}
                    </v-btn>
                    <v-btn block variant="text" @click="backToPassword">Back to sign in</v-btn>
                  </v-card-actions>
                </v-form>
              </template>

              <!-- "I forgot my password". -->
              <template v-else-if="forgotPassword">
                <v-card-title>Reset your password</v-card-title>
                <v-card-subtitle class="text-wrap">
                  Enter your username or email and we will send you a link.
                </v-card-subtitle>
                <v-form @submit.prevent="requestReset">
                  <v-card-text>
                    <v-alert v-if="error" class="mb-4" density="compact" type="error" variant="tonal">{{ error }}</v-alert>
                    <v-alert v-if="resetRequested" class="mb-4" type="success" variant="tonal">
                      If that account exists, a reset link is on its way. The link is good for a
                      short time and can be used once.
                    </v-alert>
                    <v-text-field
                      v-if="!resetRequested"
                      v-model="recoveryIdentifier"
                      autocomplete="username"
                      autofocus
                      label="Username or email"
                      :rules="[required]"
                    />
                  </v-card-text>
                  <v-card-actions class="px-4 pb-4 d-flex flex-column ga-2 align-stretch">
                    <v-btn
                      v-if="!resetRequested"
                      block
                      color="primary"
                      :loading="busy"
                      type="submit"
                      variant="flat"
                    >
                      Send reset link
                    </v-btn>
                    <v-btn block variant="text" @click="backToPassword">Back to sign in</v-btn>
                  </v-card-actions>
                </v-form>
              </template>

              <!-- Phase one. -->
              <template v-else>
                <v-card-title>Sign in</v-card-title>
                <v-form @submit.prevent="submitCredentials">
                  <v-card-text>
                    <v-alert v-if="error" class="mb-4" density="compact" type="error" variant="tonal">{{ error }}</v-alert>
                    <v-text-field
                      v-model="username"
                      autocomplete="username"
                      autofocus
                      class="mb-2"
                      label="Username"
                      :rules="[required]"
                    />
                    <v-text-field
                      v-model="password"
                      autocomplete="current-password"
                      label="Password"
                      :rules="[required]"
                      type="password"
                    />
                  </v-card-text>
                  <v-card-actions class="px-4 pb-4 d-flex flex-column ga-2 align-stretch">
                    <v-btn block color="primary" :loading="busy" type="submit" variant="flat">Sign in</v-btn>
                    <v-btn block variant="text" @click="openForgotPassword">Forgot your password?</v-btn>
                  </v-card-actions>
                </v-form>
              </template>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { requestPasswordRecovery, resendTwoFactorCode } from '~/generated/rest'
import { useAuthStore } from '~/stores/auth'

// `layout: false` because the default layout is the signed-in chrome (nav bar, sign-out
// button) and there is no user to put in it yet.
definePageMeta({ layout: false })

const auth = useAuthStore()
const route = useRoute()

const username = ref('')
const password = ref('')
const code = ref('')
const error = ref('')
const busy = ref(false)

const forgotPassword = ref(false)
const recoveryIdentifier = ref('')
const resetRequested = ref(false)

const RESEND_COOLDOWN_SECONDS = 60
const resendIn = ref(0)
let resendTimer: ReturnType<typeof setInterval> | null = null

const isEmailMethod = computed(() => auth.pendingTwoFactor === 'EMAIL')

const required = (value: string) => !!value || 'Required'
const sixDigits = (value: string) => /^\d{6}$/.test((value ?? '').replace(/\s/g, '')) || 'Enter the 6-digit code'

function startResendCountdown() {
    resendIn.value = RESEND_COOLDOWN_SECONDS
    if (resendTimer) clearInterval(resendTimer)
    resendTimer = setInterval(() => {
        resendIn.value -= 1
        if (resendIn.value <= 0 && resendTimer) {
            clearInterval(resendTimer)
            resendTimer = null
        }
    }, 1000)
}

onBeforeUnmount(() => {
    if (resendTimer) clearInterval(resendTimer)
})

async function goToDestination() {
    const redirect = route.query.redirect
    await navigateTo(typeof redirect === 'string' && redirect.startsWith('/') ? redirect : '/')
}

async function submitCredentials() {
    if (!username.value || !password.value) return
    error.value = ''
    busy.value = true
    try {
        const signedIn = await auth.signIn(username.value, password.value)
        if (signedIn) {
            await goToDestination()
            return
        }
        code.value = ''
        if (isEmailMethod.value) startResendCountdown()
    } catch (requestError) {
        error.value = apiErrorMessage(requestError, 'Incorrect username or password')
    } finally {
        busy.value = false
    }
}

async function submitCode() {
    if (!/^\d{6}$/.test(code.value.replace(/\s/g, ''))) return
    error.value = ''
    busy.value = true
    try {
        await auth.submitTwoFactorCode(code.value)
        await goToDestination()
    } catch (requestError) {
        error.value = apiErrorMessage(requestError, 'Invalid or expired code')
        code.value = ''
        // 401 means the 10-minute window closed; the password has to be entered again.
        if ((requestError as { status?: number })?.status === 401) backToPassword()
    } finally {
        busy.value = false
    }
}

async function resend() {
    error.value = ''
    busy.value = true
    try {
        await resendTwoFactorCode()
        startResendCountdown()
    } catch (requestError) {
        error.value = apiErrorMessage(requestError)
    } finally {
        busy.value = false
    }
}

function openForgotPassword() {
    error.value = ''
    resetRequested.value = false
    recoveryIdentifier.value = username.value
    forgotPassword.value = true
}

async function requestReset() {
    if (!recoveryIdentifier.value) return
    error.value = ''
    busy.value = true
    try {
        await requestPasswordRecovery({ body: { usernameOrEmail: recoveryIdentifier.value } })
        // Shown whether or not the account exists -- the endpoint answers the same way either
        // way on purpose, so that this page cannot be used to test whether an account is real.
        resetRequested.value = true
    } catch (requestError) {
        error.value = apiErrorMessage(requestError)
    } finally {
        busy.value = false
    }
}

function backToPassword() {
    auth.cancelTwoFactor()
    password.value = ''
    code.value = ''
    error.value = ''
    forgotPassword.value = false
    resetRequested.value = false
    if (resendTimer) {
        clearInterval(resendTimer)
        resendTimer = null
    }
    resendIn.value = 0
}
</script>
