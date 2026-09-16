<!-- Destination: gui/app/pages/password-reset/[token].vue -->
<template>
  <v-app>
    <v-main class="d-flex align-center">
      <v-container>
        <v-row justify="center">
          <v-col cols="12" md="6" lg="5">
            <v-card :loading="checking">
              <template v-if="tokenError">
                <v-card-title>Link no longer valid</v-card-title>
                <v-card-text>
                  <v-alert type="error" variant="tonal">{{ tokenError }}</v-alert>
                </v-card-text>
                <v-card-actions class="px-4 pb-4">
                  <v-btn block to="/login" variant="tonal">Back to sign in</v-btn>
                </v-card-actions>
              </template>

              <template v-else-if="done">
                <v-card-title>Password changed</v-card-title>
                <v-card-text>
                  <v-alert type="success" variant="tonal">
                    You can sign in with your new password<template v-if="target">
                      as <strong>{{ target.username ?? target.email }}</strong></template>.
                    Any other browsers you were signed in on have been signed out.
                  </v-alert>
                </v-card-text>
                <v-card-actions class="px-4 pb-4">
                  <v-btn block color="primary" to="/login" variant="flat">Sign in</v-btn>
                </v-card-actions>
              </template>

              <template v-else>
                <v-card-title>Choose a new password</v-card-title>
                <v-card-subtitle v-if="target" class="text-wrap">
                  For <strong>{{ target.username ?? target.email }}</strong>
                  <template v-if="target.username"> ({{ target.email }})</template>
                </v-card-subtitle>
                <v-form @submit.prevent="submit">
                  <v-card-text>
                    <v-alert v-if="error" class="mb-4" density="compact" type="error" variant="tonal">{{ error }}</v-alert>
                    <v-text-field
                      v-model="newPassword"
                      autocomplete="new-password"
                      class="mb-2"
                      hint="At least 8 characters, with a lowercase and an uppercase letter, a digit and a symbol."
                      label="New password"
                      persistent-hint
                      :rules="[required]"
                      type="password"
                    />
                    <v-text-field
                      v-model="confirmPassword"
                      autocomplete="new-password"
                      label="Repeat password"
                      :rules="[required, matches]"
                      type="password"
                    />
                  </v-card-text>
                  <v-card-actions class="px-4 pb-4">
                    <v-btn block color="primary" :loading="busy" type="submit" variant="flat">
                      Change password
                    </v-btn>
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
import { checkRecoveryToken, resetPassword } from '~/generated/rest'
import type { RecoveryTarget } from '~/generated/rest'

definePageMeta({ layout: false })

const route = useRoute()
const token = computed(() => String(route.params.token ?? ''))

const checking = ref(true)
const tokenError = ref('')
const target = ref<RecoveryTarget | null>(null)
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const busy = ref(false)
const done = ref(false)

const required = (value: string) => !!value || 'Required'
const matches = (value: string) => value === newPassword.value || 'Passwords do not match'

// Check the link before showing the form, so an expired one says so immediately instead of
// after the user has picked and typed a password twice.
onMounted(async () => {
    try {
        target.value = await checkRecoveryToken({ path: { token: token.value } })
    } catch (requestError) {
        tokenError.value = apiErrorMessage(
            requestError,
            'This reset link is invalid, expired, or has already been used.',
        )
    } finally {
        checking.value = false
    }
})

async function submit() {
    if (!newPassword.value || newPassword.value !== confirmPassword.value) return
    error.value = ''
    busy.value = true
    try {
        await resetPassword({
            body: {
                recoveryToken: token.value,
                newPassword: newPassword.value,
                confirmPassword: confirmPassword.value,
            },
        })
        done.value = true
    } catch (requestError) {
        // The complexity rule lives in `schemas/rest.py`; its message arrives here as a 422.
        error.value = apiErrorMessage(requestError)
    } finally {
        busy.value = false
    }
}
</script>
