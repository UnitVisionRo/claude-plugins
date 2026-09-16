<!-- Destination: gui/app/components/AppUpdatePrompt.vue -->
<!--
  Tells an already-open tab that a newer build has been deployed, and lets the user take it.

  How the detection works (Nuxt's own `check-outdated-build.client` plugin, enabled by
  `experimental.appManifest`, which defaults to true): the client polls
  `/_nuxt/builds/latest.json` on a plain `setTimeout` chain and compares its build id against
  the one baked into the running bundle. It is a wall-clock interval and NOTHING else -- a
  route navigation does not trigger a check -- so the interval is the whole story for how
  stale a tab can be. `nuxt.config.ts` sets it to 15 minutes.

  Two consequences of that plugin's implementation this component is built around:
  - The hook fires AT MOST ONCE per tab: on a mismatch Nuxt calls the hook and then clears
    its own timer, so polling stops for good. A prompt the user dismisses is therefore never
    shown again for the life of that tab -- which is why this is a persistent snackbar
    (`:timeout="-1"`, no dismiss action) rather than a dialog with a Cancel button.
  - In dev, restarting `npm run dev` mints a new build id, so an open tab will pop this
    prompt. That is the mechanism working, not a bug.

  `window.location.reload()` rather than `reloadNuxtApp()`: the latter defaults its `path` to
  `window.location.pathname`, which silently drops the query string.
-->
<template>
  <v-snackbar v-model="updateAvailable" :timeout="-1" color="primary" location="bottom">
    A new version of __APP_NAME__ is available.

    <template #actions>
      <v-btn :loading="reloading" variant="text" @click="reload">Reload</v-btn>
    </template>
  </v-snackbar>
</template>

<script setup lang="ts">
const updateAvailable = ref(false)
const reloading = ref(false)

// Client-only hook; on the server it simply never fires.
useRuntimeHook('app:manifest:update', () => {
    updateAvailable.value = true
})

function reload() {
    reloading.value = true
    window.location.reload()
}
</script>
