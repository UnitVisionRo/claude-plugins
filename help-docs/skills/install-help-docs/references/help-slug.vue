<!-- Destination: <nuxtDir>/<srcDir>/pages/help/[[slug]].vue -->
<template>
    <v-card class="help-doc-card">
        <v-card-text>
            <HelpContent v-if="activeSlug" :slug="activeSlug" :section="section" />
            <v-alert v-else type="info" variant="tonal" density="comfortable">
                The documentation has no published topics yet.
            </v-alert>
        </v-card-text>
    </v-card>
</template>

<script setup lang="ts">
import HelpContent from '~/components/help/HelpContent.vue'
import { resolveHelpSlug } from '~/utils/helpDocs'

// No transition: changing topic replaces only the content, and an animation would make it look
// like the whole page had reloaded.
definePageMeta({ pageTransition: false })

const route = useRoute()

// An unknown slug in the address is not an error -- the first topic is shown.
const activeSlug = computed(() => resolveHelpSlug(route.params.slug))

// The section arrives as a query parameter (`?s=...`) rather than an anchor, so that the same
// link works inside the contextual help dialog, where the browser has nothing to jump to.
const section = computed(() => {
    const value = route.query.s
    return typeof value === 'string' ? value : undefined
})
</script>

<style scoped>
/* `.v-card` comes with `overflow: hidden`, so content wider than the card would be clipped.
   Documentation can contain wide tables, which have to be able to scroll. */
.help-doc-card {
    overflow-x: auto;
}
</style>
