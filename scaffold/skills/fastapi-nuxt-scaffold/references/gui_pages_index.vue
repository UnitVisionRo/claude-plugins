<!-- Destination: gui/app/pages/index.vue -->
<template>
  <v-row justify="center">
    <v-col cols="12" md="8">
      <v-card>
        <v-card-title>Signed in</v-card-title>
        <v-card-text>
          <v-table density="comfortable">
            <tbody>
              <tr><td class="text-medium-emphasis">Name</td><td>{{ user?.name }}</td></tr>
              <tr><td class="text-medium-emphasis">Username</td><td>{{ user?.username }}</td></tr>
              <tr><td class="text-medium-emphasis">Email</td><td>{{ user?.email }}</td></tr>
              <tr>
                <td class="text-medium-emphasis">Role</td>
                <td><v-chip :color="user?.role === 'ADMIN' ? 'primary' : undefined" size="small">{{ user?.role }}</v-chip></td>
              </tr>
            </tbody>
          </v-table>
        </v-card-text>
        <v-card-actions>
          <v-btn to="/account" variant="tonal">Security settings</v-btn>
          <v-btn v-if="auth.isAdmin" to="/users" variant="tonal">Manage users</v-btn>
        </v-card-actions>
      </v-card>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'

const auth = useAuthStore()
const user = computed(() => auth.currentUser)
</script>
