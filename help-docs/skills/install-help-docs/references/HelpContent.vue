<!-- Destination: <appSrc>/components/help/HelpContent.vue -->
<template>
    <div>
        <v-progress-linear v-if="loading" indeterminate color="primary" />
        <v-alert v-else-if="errorMessage" type="warning" variant="tonal" density="comfortable">
            {{ errorMessage }}
        </v-alert>
        <!-- The content is generated at build time from docs/help/*.md, with raw HTML disabled
             in the parser. It is our own content, reviewed in a PR -- it does not come from
             users and is not fetched at runtime. -->
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div v-else ref="bodyEl" class="help-body" @click="onBodyClick" v-html="visibleHtml" />
    </div>
</template>

<script setup lang="ts">
import { filterHelpModuleBlocks, loadHelpDocHtml } from '~/utils/helpDocs'

const props = defineProps<{
    /** The document shown (the file name in docs/help, without its extension). */
    slug: string
    /** The id of the section to scroll to once loaded. */
    section?: string
}>()

const emit = defineEmits<{
    /** The user followed an internal link in the document. */
    navigate: []
}>()

const html = ref('')
const loading = ref(false)
const errorMessage = ref<string | null>(null)
const bodyEl = ref<HTMLElement | null>(null)

/**
 * The body with the `:::module` blocks of switched-off modules removed. A computed, not a
 * one-off transform of `html`, so the content follows the module flags: if what a flag reads is
 * reactive, turning a module on reveals its passages without reloading the document.
 */
const visibleHtml = computed(() => filterHelpModuleBlocks(html.value))

async function scrollToSection() {
    if (!props.section) {
        return
    }
    // Let the layout settle: right after the content is inserted the scrolling area does not yet
    // have its final height, so there would be nowhere to scroll to. A timer, not a render
    // frame, so it also works in a background tab.
    await new Promise(resolve => setTimeout(resolve, 50))
    const target = bodyEl.value?.querySelector(`#${CSS.escape(props.section)}`)
    // A direct jump, not a smooth one: an animation depends on rendering and would not start in
    // a tab opened in the background.
    target?.scrollIntoView({ block: 'start' })
}

/**
 * Internal links are rewritten by the generator into plain application paths, so the browser
 * would follow them as a full page load. The router has to handle them instead -- and the caller
 * has to be told, because the contextual help dialog must close, or it would stay open over the
 * newly loaded page.
 *
 * External links (`target="_blank"`) and modified clicks (ctrl/cmd/shift, middle button) are
 * left alone: opening in a new tab is the user's decision, not ours.
 */
function onBodyClick(event: MouseEvent) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return
    }
    const link = (event.target as HTMLElement | null)?.closest('a')
    const href = link?.getAttribute('href')
    if (!href || !href.startsWith('/') || link?.target === '_blank') {
        return
    }
    event.preventDefault()
    emit('navigate')
    navigateTo(href)
}

async function load() {
    loading.value = true
    errorMessage.value = null
    try {
        html.value = await loadHelpDocHtml(props.slug)
        // Scrolling only happens once the content is rendered.
        loading.value = false
        await nextTick()
        await scrollToSection()
    } catch {
        html.value = ''
        errorMessage.value = 'This help topic is not available.'
    } finally {
        loading.value = false
    }
}

watch(() => props.slug, load, { immediate: true })
watch(() => props.section, async () => {
    await nextTick()
    await scrollToSection()
})
</script>

<style scoped>
/* The body is HTML generated from Markdown, so it carries no Vuetify classes -- the plain
   elements are styled here, once. `:deep()` is required: `v-html` content is not compiled by
   Vue, so it never receives the scope attribute.

   Only default-theme tokens are used (`primary`, `on-surface`), with alpha for borders and
   shading, so this works against `createVuetify()` without a custom palette. */
.help-body {
    color: rgb(var(--v-theme-on-surface));
    line-height: 1.65;
    /* A word that cannot be broken (a long address, a setting name) would otherwise overflow
       its container and be cut off. */
    overflow-wrap: break-word;
}

.help-body :deep(> :first-child) {
    margin-top: 0;
}

.help-body :deep(h1),
.help-body :deep(h2),
.help-body :deep(h3),
.help-body :deep(h4) {
    color: rgb(var(--v-theme-primary));
    font-weight: 500;
    line-height: 1.3;
    margin: 1.5rem 0 0.75rem;
    /* A little room above the heading when scrolling to a section. */
    scroll-margin-top: 12px;
}

.help-body :deep(h1) { font-size: 1.5rem; }

.help-body :deep(h2) {
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.2);
    font-size: 1.25rem;
    padding-bottom: 0.25rem;
}

.help-body :deep(h3) { font-size: 1.1rem; }
.help-body :deep(h4) { font-size: 1rem; }

.help-body :deep(p) { margin: 0 0 0.85rem; }

.help-body :deep(ul),
.help-body :deep(ol) { padding-left: 1.5rem; }

.help-body :deep(li) { margin-bottom: 0.35rem; }

.help-body :deep(a) {
    color: rgb(var(--v-theme-primary));
    text-decoration: none;
}

.help-body :deep(a:hover) { text-decoration: underline; }

.help-body :deep(strong) { font-weight: 600; }

.help-body :deep(code) {
    background-color: rgba(var(--v-theme-on-surface), 0.08);
    border-radius: 4px;
    font-size: 0.875em;
    padding: 0.1rem 0.35rem;
}

.help-body :deep(pre) {
    background-color: rgba(var(--v-theme-on-surface), 0.08);
    border-radius: 6px;
    margin: 0 0 0.85rem;
    overflow-x: auto;
    padding: 0.75rem 1rem;
}

.help-body :deep(pre code) {
    background: none;
    padding: 0;
}

.help-body :deep(blockquote) {
    border-left: 3px solid rgba(var(--v-theme-on-surface), 0.3);
    margin: 0 0 0.85rem;
    opacity: 0.85;
    padding: 0.25rem 0 0.25rem 1rem;
}

.help-body :deep(hr) {
    border: none;
    border-top: 1px solid rgba(var(--v-theme-on-surface), 0.2);
    margin: 1.5rem 0;
}

/* Screenshots, generated as <figure> from the Markdown images. `height: auto` keeps the aspect
   ratio when the width/height attributes are scaled down to the available width. */
.help-body :deep(.help-figure) { margin: 1rem 0 1.25rem; }

.help-body :deep(.help-figure img) {
    border: 1px solid rgba(var(--v-theme-on-surface), 0.2);
    border-radius: 6px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
    display: block;
    height: auto;
    max-width: 100%;
}

.help-body :deep(.help-figure figcaption) {
    font-size: 0.875em;
    margin-top: 0.4rem;
    opacity: 0.75;
    text-align: center;
}

/* Tables can be wider than the text. `display: block` with `overflow-x: auto` makes the table
   scroll rather than the page; `max-width: 100%` keeps it inside the available width, so cells
   wrap instead of pushing the table off screen. */
.help-body :deep(table) {
    border-collapse: collapse;
    display: block;
    margin: 0 0 0.85rem;
    max-width: 100%;
    overflow-x: auto;
    width: max-content;
}

/* Cells do not shrink below a width at which the text becomes unreadable vertically; below
   that, the table scrolls. */
.help-body :deep(td) { min-width: 8rem; }

.help-body :deep(th),
.help-body :deep(td) {
    border: 1px solid rgba(var(--v-theme-on-surface), 0.2);
    padding: 0.4rem 0.6rem;
    text-align: left;
}

.help-body :deep(th) {
    background-color: rgba(var(--v-theme-on-surface), 0.06);
    font-weight: 600;
}
</style>
