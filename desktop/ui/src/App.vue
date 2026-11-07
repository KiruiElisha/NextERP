<template>
  <div v-if="!session.ready" class="flex h-full items-center justify-center text-sm text-slate-400">Opening…</div>
  <SignIn v-else-if="!session.signedIn" />
  <div v-else-if="route.meta.bare" class="h-full">
    <router-view />
    <AppPicker v-if="picker.open" />
  </div>
  <div v-else class="flex h-full">
    <Sidebar />
    <div class="flex min-w-0 flex-1 flex-col">
      <TopBar @search="palette = true" />
      <main class="min-h-0 flex-1 overflow-y-auto">
        <router-view />
      </main>
    </div>
    <CommandPalette v-model="palette" />
    <AppPicker v-if="picker.open" />
  </div>
  <Toasts />
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Sidebar from './components/Sidebar.vue'
import TopBar from './components/TopBar.vue'
import CommandPalette from './components/CommandPalette.vue'
import Toasts from './components/Toasts.vue'
import SignIn from './pages/SignIn.vue'
import AppPicker from './components/AppPicker.vue'
import { onSignedIn, picker } from './lib/apps'
import { call, on, openDesk } from './lib/backend'
import { session, signOut, start } from './lib/session'

const router = useRouter()
const route = useRoute()
const palette = ref(false)

// The native menu's items: the window owns them, this screen decides what they do.
const MENU = {
  'new-invoice': () => router.push('/form/Sales%20Invoice/new'),
  search: () => (palette.value = true),
  sync: () => call('sync_now'),
  desk: () => openDesk('/app'),
  switch: () => (picker.open = true),
  'sign-out': () => signOut(),
  reload: () => window.location.reload(),
}

// Once a site is signed in (on launch or from the sign-in screen), the app picker for that site.
// The boot remembered from the last launch may predate the site's app list; the refreshed one has it.
watch(
  () => (session.signedIn ? `${session.site}|${(session.boot?.apps || []).length}` : ''),
  (key) => key && onSignedIn(router),
)

onMounted(async () => {
  await start()
  on('menu', (id) => session.signedIn && MENU[id]?.())
  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault()
      palette.value = true
    }
  })
})
</script>
