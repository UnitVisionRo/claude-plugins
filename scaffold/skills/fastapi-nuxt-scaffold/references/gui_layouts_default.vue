<!-- Destination: gui/app/layouts/default.vue -->
<template>
  <v-app>
    <v-app-bar color="primary" density="comfortable" flat>
      <v-app-bar-title>{{ appTitle }}</v-app-bar-title>

      <v-btn to="/" variant="text">Home</v-btn>
      <v-btn to="/account" variant="text">Account</v-btn>
      <v-btn v-if="auth.isAdmin" to="/users" variant="text">Users</v-btn>

      <v-divider class="mx-2" inset vertical />

      <span class="mr-3 text-body-2">{{ auth.currentUser?.name || auth.currentUser?.username }}</span>
      <v-btn :loading="signingOut" variant="tonal" @click="signOut">Sign out</v-btn>
    </v-app-bar>

    <v-main>
      <v-container class="py-8">
        <slot />
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'

const appTitle = '__APP_NAME__'
const auth = useAuthStore()
const signingOut = ref(false)

async function signOut() {
    signingOut.value = true
    try {
        await auth.signOut()
        await navigateTo('/login')
    } finally {
        signingOut.value = false
    }
}
</script>
