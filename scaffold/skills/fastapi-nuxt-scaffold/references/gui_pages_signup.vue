<!-- Destination: gui/app/pages/signup/[token].vue -->
<template>
  <v-app>
    <v-main class="d-flex align-center">
      <v-container>
        <v-row justify="center">
          <v-col cols="12" md="6" lg="5">
            <v-card :loading="loadingInvite">
              <template v-if="inviteError">
                <v-card-title>Invitation unavailable</v-card-title>
                <v-card-text>
                  <v-alert type="error" variant="tonal">{{ inviteError }}</v-alert>
                </v-card-text>
                <v-card-actions class="px-4 pb-4">
                  <v-btn block to="/login" variant="tonal">Go to sign in</v-btn>
                </v-card-actions>
              </template>

              <template v-else-if="done">
                <v-card-title>Account created</v-card-title>
                <v-card-text>
                  <v-alert type="success" variant="tonal">
                    You can now sign in with the username and password you chose.
                  </v-alert>
                </v-card-text>
                <v-card-actions class="px-4 pb-4">
                  <v-btn block color="primary" to="/login" variant="flat">Sign in</v-btn>
                </v-card-actions>
              </template>

              <template v-else>
                <v-card-title>Accept your invitation</v-card-title>
                <v-card-subtitle class="text-wrap">
                  Choose a username and password for <strong>{{ invite?.email }}</strong>.
                </v-card-subtitle>
                <v-form @submit.prevent="submit">
                  <v-card-text>
                    <v-alert v-if="error" class="mb-4" density="compact" type="error" variant="tonal">{{ error }}</v-alert>
                    <v-text-field
                      v-model="form.name"
                      class="mb-2"
                      :error-messages="issues.name ? [issues.name] : []"
                      label="Full name"
                      :rules="[required(), fieldRule(vSignupRequest, 'name')]"
                    />
                    <v-text-field
                      v-model="form.username"
                      autocomplete="username"
                      class="mb-2"
                      :error-messages="usernameErrors"
                      label="Username"
                      :loading="checkingUsername"
                      :rules="[required(), fieldRule(vSignupRequest, 'username', MESSAGES.username)]"
                    />
                    <v-text-field
                      v-model="form.password"
                      autocomplete="new-password"
                      class="mb-2"
                      :error-messages="issues.password ? [issues.password] : []"
                      :hint="MESSAGES.password"
                      label="Password"
                      persistent-hint
                      :rules="[required(), fieldRule(vSignupRequest, 'password', MESSAGES.password)]"
                      type="password"
                    />
                    <v-text-field
                      v-model="form.confirmPassword"
                      autocomplete="new-password"
                      label="Repeat password"
                      :rules="[required(), matches(() => form.password)]"
                      type="password"
                    />
                  </v-card-text>
                  <v-card-actions class="px-4 pb-4">
                    <v-btn block color="primary" :loading="busy" type="submit" variant="flat">Create account</v-btn>
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
import { checkUsername, getInvite, signup } from '~/generated/rest'
import type { InvitedUserResult, SignupRequest } from '~/generated/rest'
import { vSignupRequest } from '~/generated/rest/valibot.gen'
import type { FieldIssues } from '~/utils/validation'
import { MESSAGES, fieldRule, matches, required, validatePayload } from '~/utils/validation'

definePageMeta({ layout: false })

const route = useRoute()
const token = computed(() => String(route.params.token ?? ''))

const invite = ref<InvitedUserResult | null>(null)
const inviteError = ref('')
const loadingInvite = ref(true)

const form = reactive({ name: '', username: '', password: '', confirmPassword: '' })
const error = ref('')
const busy = ref(false)
const done = ref(false)

const usernameTaken = ref(false)
const checkingUsername = ref(false)
let usernameTimer: ReturnType<typeof setTimeout> | null = null

const issues = ref<FieldIssues<SignupRequest>>({})

const usernameErrors = computed(() => {
    if (usernameTaken.value) return ['That username is already taken']
    return issues.value.username ? [issues.value.username] : []
})

// The token identifies the invitation, so this is a public lookup -- resolving it is what
// tells us whether the link in the email is still good, and gives the invitee's email to
// show them which account they are accepting.
onMounted(async () => {
    try {
        invite.value = await getInvite({ path: { token: token.value } })
        form.name = invite.value.name ?? ''
    } catch (requestError) {
        inviteError.value = apiErrorMessage(requestError, 'This invitation is invalid or has already been used.')
    } finally {
        loadingInvite.value = false
    }
})

// Debounced so typing a name doesn't fire a request per keystroke.
watch(() => form.username, (value) => {
    usernameTaken.value = false
    if (usernameTimer) clearTimeout(usernameTimer)
    if (!value || value.length < 3) return

    usernameTimer = setTimeout(async () => {
        checkingUsername.value = true
        try {
            usernameTaken.value = !(await checkUsername({ query: { username: value } }))
        } catch {
            // Availability is a hint; the signup call is what actually decides.
            usernameTaken.value = false
        } finally {
            checkingUsername.value = false
        }
    }, 400)
})

onBeforeUnmount(() => {
    if (usernameTimer) clearTimeout(usernameTimer)
})

async function submit() {
    error.value = ''
    const payload: SignupRequest = { ...form, inviteToken: token.value }

    // One parse against the generated schema decides whether to send. The rules come from the
    // backend, so this cannot disagree with what the server will accept -- except for the
    // confirmation match, which no schema can express and which is checked alongside.
    const { ok, issues: found } = validatePayload(vSignupRequest, payload)
    issues.value = found
    if (!ok) return
    if (form.password !== form.confirmPassword) {
        issues.value = { confirmPassword: 'Passwords do not match' }
        return
    }

    busy.value = true
    try {
        await signup({ body: payload })
        done.value = true
    } catch (requestError) {
        // The password-complexity rule lives in `schemas/rest.py`, so its message arrives here
        // as a 422 rather than being duplicated (and left to drift) in this form.
        error.value = apiErrorMessage(requestError)
    } finally {
        busy.value = false
    }
}
</script>
