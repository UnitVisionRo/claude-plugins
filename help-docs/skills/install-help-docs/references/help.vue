<!-- Destination: <appSrc>/pages/help.vue -->
<template>
    <v-row>
        <!-- The topic list lives in the parent page, so it stays mounted when the topic changes:
             only the content reloads, through `NuxtPage`, and the list keeps its scroll
             position. The comment sits inside the root element, not above it: a comment beside
             the root counts as a second root node and `vue/no-multiple-template-root` rejects it. -->
        <v-col cols="12" md="4" lg="3">
            <!-- The card is not itself the scrolling area: the title stays put and the search
                 field with the list below it scrolls, inside `HelpSearch`. -->
            <v-card class="help-topics-card d-flex flex-column">
                <v-card-title class="text-subtitle-1">Topics</v-card-title>
                <HelpSearch class="help-topics-search" @select="select">
                    <HelpTopicList :active-slug="activeSlug" @select="select" />
                </HelpSearch>
            </v-card>
        </v-col>
        <v-col cols="12" md="8" lg="9">
            <NuxtPage />
        </v-col>
    </v-row>
</template>

<script setup lang="ts">
import HelpSearch from '~/components/help/HelpSearch.vue'
import HelpTopicList from '~/components/help/HelpTopicList.vue'
import { resolveHelpSlug } from '~/utils/helpDocs'

const route = useRoute()
const router = useRouter()

const activeSlug = computed(() => resolveHelpSlug(route.params.slug))

// A search result carries the section it was found in; a topic from the list does not, so it
// opens at the top.
function select(slug: string, section?: string) {
    router.push(section ? `/help/${slug}?s=${section}` : `/help/${slug}`)
}
</script>

<style scoped>
/* The list is capped rather than stretched to fill the viewport: this page renders inside the
   layout's ordinary `v-container`, which is not a full-height flex column, so there is no
   remaining height for a `flex: 1 1 0` chain to claim. The cap is what gives `HelpSearch`
   something to scroll within; `min-height: 0` lets it shrink below its content. */
.help-topics-card {
    max-height: calc(100vh - 180px);
    min-height: 320px;
}

.help-topics-search {
    flex: 1 1 auto;
    min-height: 0;
}
</style>
