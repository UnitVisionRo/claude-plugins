<!-- Destination: <nuxtDir>/<srcDir>/components/help/HelpSearch.vue -->
<template>
    <!-- The field stays put at the top and only the list below it scrolls: no `position: sticky`
         here, which would let content show through beside the field. -->
    <div class="help-search d-flex flex-column">
        <div class="help-search-field">
            <v-text-field
                v-model="query"
                label="Search the documentation"
                prepend-inner-icon="mdi-magnify"
                autocomplete="off"
                density="compact"
                variant="outlined"
                hide-details
                @keydown.enter="openFirstResult"
                @keydown.esc="clearOnEscape"
            />
        </div>

        <v-progress-linear v-if="loading" indeterminate color="primary" />

        <div class="help-search-body">
            <template v-if="searching">
                <v-list v-if="results.length" density="compact" nav>
                    <v-list-subheader>{{ resultsLabel }}</v-list-subheader>
                    <v-list-item
                        v-for="result in results"
                        :key="`${result.slug}#${result.section}`"
                        color="primary"
                        @click="emit('select', result.slug, result.section)"
                    >
                        <v-list-item-title>{{ result.heading }}</v-list-item-title>
                        <v-list-item-subtitle>{{ result.docTitle }}</v-list-item-subtitle>
                        <!-- The snippet is three pieces of text, not HTML: the matching part is
                             highlighted without inserting markup into the page. -->
                        <div v-if="result.snippet" class="help-search-snippet text-body-2">
                            {{ result.snippet.before }}<mark>{{ result.snippet.match }}</mark>{{ result.snippet.after }}
                        </div>
                    </v-list-item>
                </v-list>
                <div v-else-if="!loading" class="pa-4 text-body-2 text-medium-emphasis">
                    No results for “{{ query.trim() }}”.
                </div>
            </template>

            <!-- While nothing is being searched the caller shows its own content: the topic list
                 on the help page, a short prompt in the dialog's menu. -->
            <slot v-else />
        </div>
    </div>
</template>

<script setup lang="ts">
import type { HelpSearchResult } from '~/utils/helpSearch'
import { HELP_SEARCH_MIN_LENGTH, searchHelpDocs } from '~/utils/helpSearch'

// The documentation search, used both on the help page and in the contextual dialog in the app
// bar. The component owns the field and the results; the caller only decides what happens when a
// result is chosen.

const emit = defineEmits<{
    /** The user chose a result: the document and the section within it. */
    select: [slug: string, section: string]
}>()

/** How long to wait after the last keystroke. Enough that a quickly typed search runs once. */
const DEBOUNCE_MS = 150

const query = ref('')
const results = ref<HelpSearchResult[]>([])
const loading = ref(false)

const searching = computed(() => query.value.trim().length >= HELP_SEARCH_MIN_LENGTH)

const resultsLabel = computed(() => results.value.length === 1
    ? '1 result'
    : `${results.value.length} results`)

let debounce: ReturnType<typeof setTimeout> | undefined

async function run(searched: string) {
    loading.value = true
    try {
        const found = await searchHelpDocs(searched)
        // The first search fetches the index, so it can take longer than the user keeps typing:
        // an answer for text that is no longer in the field is thrown away.
        if (query.value === searched) {
            results.value = found
        }
    } finally {
        if (query.value === searched) {
            loading.value = false
        }
    }
}

watch(query, (searched) => {
    clearTimeout(debounce)
    if (!searching.value) {
        results.value = []
        loading.value = false
        return
    }
    debounce = setTimeout(() => run(searched), DEBOUNCE_MS)
})

/**
 * Escape clears the field, but only when there is something to clear: otherwise the key has to
 * travel on, to the menu or dialog being searched from, so they close as usual.
 */
function clearOnEscape(event: KeyboardEvent) {
    if (query.value) {
        query.value = ''
        event.stopPropagation()
    }
}

/** Enter opens the first result -- most often, the one being looked for. */
function openFirstResult() {
    const first = results.value[0]
    if (first) {
        emit('select', first.slug, first.section)
    }
}
</script>

<style scoped>
/* The caller gives this its height (`flex: 1 1 0; min-height: 0`); `min-height: 0` here lets it
   shrink below its content, so the results area can scroll. */
.help-search {
    min-height: 0;
}

.help-search-field {
    flex: 0 0 auto;
    padding: 8px 8px 4px;
}

.help-search-body {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
}

.help-search-snippet {
    /* The snippet is written over several lines; `v-list-item` limits text to one. */
    white-space: normal;
    opacity: 0.75;
}

.help-search-snippet mark {
    background: rgba(var(--v-theme-primary), 0.2);
    color: inherit;
    font-weight: 600;
}
</style>
