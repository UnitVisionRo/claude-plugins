<!--
  The Vuetify application root (`<v-app>`) lives in each LAYOUT, not here: the signed-in
  chrome and the bare sign-in screen are different shells, and a page opting out with
  `definePageMeta({ layout: false })` supplies its own `<v-app>` (see app/pages/login.vue).
  Vuetify needs exactly one `<v-app>` per page -- nesting a second one breaks its layout
  calculations for app bars and navigation drawers.

  `<AppUpdatePrompt>` sits here rather than in a layout so that it survives every navigation
  and is present on the layout-less pages too.
-->
<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>

  <AppUpdatePrompt />
</template>
