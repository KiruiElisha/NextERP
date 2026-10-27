<template>
  <div v-if="!session.ready" class="flex h-full items-center justify-center text-sm text-slate-400">Opening…</div>
  <SignIn v-else-if="!session.signedIn" />
  <div v-else class="flex h-full">
    <Sidebar />
    <div class="flex min-w-0 flex-1 flex-col">
      <TopBar @search="palette = true" />
      <main class="min-h-0 flex-1 overflow-y-auto">
        <router-view />
      </main>
    </div>
    <CommandPalette v-model="palette" />
  </div>
  <Toasts />
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import Sidebar from './components/Sidebar.vue'
import TopBar from './components/TopBar.vue'
import CommandPalette from './components/CommandPalette.vue'
import Toasts from './components/Toasts.vue'
import SignIn from './pages/SignIn.vue'
import { call, on, openDesk } from './lib/backend'
import { session, signOut, start } from './lib/session'

const router = useRouter()
const palette = ref(false)

// The native menu's items: the window owns them, this screen decides what they do.
const MENU = {
  'new-invoice': () => router.push('/new/sales-invoice'),
  search: () => (palette.value = true),
  sync: () => call('sync_now'),
  desk: () => openDesk('/app'),
  'sign-out': () => signOut(),
  reload: () => window.location.reload(),
}

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
