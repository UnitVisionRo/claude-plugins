<!-- Destination: <appSrc>/components/help/HelpButton.vue -->
<template>
    <!-- The component has two root nodes (the button and the dialog), so spacing lives here
         rather than on the caller: a class passed in from outside could not be applied. -->
    <v-btn
        icon="mdi-help-circle-outline"
        variant="text"
        density="comfortable"
        class="mr-1"
        :title="buttonTitle"
        @click="open = true"
    />

    <v-dialog v-model="open" max-width="900" scrollable>
        <v-card>
            <v-card-title class="d-flex align-center ga-2">
                <v-icon icon="mdi-help-circle-outline" size="small" />
                <span class="text-truncate">{{ shownDoc?.title ?? 'Help' }}</span>
                <v-spacer />
                <!-- The search sits in a menu opened from the header: the field does not take up
                     the top of the dialog permanently, and has nothing to sit over when the
                     content scrolls. -->
                <!-- `icon` as a flag, not as a name: the default slot has to carry the menu
                     as well as the icon, and an `icon="..."` name would replace the slot. -->
                <v-btn
                    icon
                    variant="text"
                    density="comfortable"
                    title="Search the documentation"
                >
                    <v-icon icon="mdi-magnify" />
                    <v-menu
                        v-model="searchMenu"
                        activator="parent"
                        :close-on-content-click="false"
                        location="bottom end"
                        offset="5"
                    >
                        <!-- Mounted only while the menu is open: every opening starts from an
                             empty field, not from the previous search. -->
                        <v-card v-if="searchMenu" min-width="480" max-width="620" max-height="60vh" class="d-flex flex-column">
                            <HelpSearch class="help-dialog-search" @select="openDoc">
                                <p class="pa-4 mb-0 text-body-2 text-medium-emphasis">
                                    Type at least two letters to search every topic.
                                </p>
                            </HelpSearch>
                        </v-card>
                    </v-menu>
                </v-btn>
                <v-btn
                    icon="mdi-close"
                    variant="text"
                    density="comfortable"
                    title="Close"
                    @click="open = false"
                />
            </v-card-title>

            <v-card-text class="help-dialog-body">
                <!-- `open` is in the condition so the dialog mounts the content again on every
                     opening: otherwise Vuetify keeps it mounted and scrolling to the active
                     tab's section would happen only once, the first time. -->
                <HelpContent
                    v-if="open && shownDoc"
                    :slug="shownDoc.slug"
                    :section="shownSection"
                    @navigate="open = false"
                />
                <template v-else-if="open">
                    <p class="mb-2">There is no dedicated guide for this page yet. Pick a topic:</p>
                    <HelpTopicList @select="openDoc" />
                </template>
            </v-card-text>

            <v-card-actions>
                <v-spacer />
                <v-btn variant="text" @click="openDoc()">All documentation</v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
import HelpContent from '~/components/help/HelpContent.vue'
import HelpSearch from '~/components/help/HelpSearch.vue'
import HelpTopicList from '~/components/help/HelpTopicList.vue'
import { findHelpDoc, findHelpDocForPath } from '~/utils/helpDocs'

// Contextual help: the app bar button opens the document declared for the current page (through
// `routes` in the frontmatter), without leaving the page. If the page has no dedicated document,
// the topic list is shown instead.
const route = useRoute()
const open = ref(false)
const searchMenu = ref(false)

const contextualDoc = computed(() => findHelpDocForPath(route.path))

// On tabbed pages each tab has its own help, declared in `tabs`: either a section of the page's
// document or a separate document. The active tab is in the address (`?activeTab=`), so the app
// bar button can read it itself, without the page passing it down.
const tabTarget = computed(() => {
    const activeTab = route.query.activeTab
    return typeof activeTab === 'string'
        ? contextualDoc.value?.tabs?.[activeTab]
        : undefined
})

/** The document shown: the active tab's, if it declares one, otherwise the page's. */
const shownDoc = computed(() => {
    const target = tabTarget.value
    return (target ? findHelpDoc(target.slug) : undefined) ?? contextualDoc.value
})

/** The section only applies if the document shown is in fact the tab's target. */
const shownSection = computed(() => {
    const target = tabTarget.value
    return target && shownDoc.value?.slug === target.slug ? target.section : undefined
})

const buttonTitle = computed(() => shownDoc.value ? `Help: ${shownDoc.value.title}` : 'Help')

/**
 * Leaves the dialog for the help page: at a given topic, at a given section (when it comes from
 * a search result), or at the whole documentation.
 */
function openDoc(slug?: string, section?: string) {
    open.value = false
    if (!slug) {
        navigateTo('/help')
        return
    }
    navigateTo(section ? `/help/${slug}?s=${section}` : `/help/${slug}`)
}
</script>

<style scoped>
/* The search menu has a limited height, so the field stays at the top and the results scroll
   beneath it: a flex column parent plus `min-height: 0` all the way down. */
.help-dialog-search {
    flex: 1 1 auto;
    min-height: 0;
}

.help-dialog-body {
    max-height: 70vh;
    /* Wide content (a table with many columns) has to be able to scroll, not be clipped by the
       dialog's edge. */
    overflow-x: auto;
}
</style>
