<!-- Destination: <nuxtDir>/<srcDir>/components/help/HelpTopicList.vue -->
<template>
    <v-list density="compact" nav>
        <template v-for="(group, index) in groups" :key="group.group ?? index">
            <v-list-subheader v-if="group.group">{{ group.group }}</v-list-subheader>
            <v-list-item
                v-for="doc in group.docs"
                :key="doc.slug"
                :active="doc.slug === activeSlug"
                color="primary"
                @click="emit('select', doc.slug)"
            >
                <v-list-item-title>{{ doc.title }}</v-list-item-title>
                <v-list-item-subtitle v-if="doc.summary">{{ doc.summary }}</v-list-item-subtitle>
            </v-list-item>
        </template>
    </v-list>
</template>

<script setup lang="ts">
import { groupedHelpDocs } from '~/utils/helpDocs'

// The list of help topics. It does not navigate by itself -- the caller decides what happens to
// the chosen topic (the help page changes route, the contextual dialog opens the page).
defineProps<{
    activeSlug?: string
}>()

const emit = defineEmits<{
    select: [slug: string]
}>()

const groups = groupedHelpDocs()
</script>
