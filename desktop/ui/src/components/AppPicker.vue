<template>
  <!-- Which app this computer opens on the site, as the JEMKAS launcher asks: ERPNext here, any
       other installed app in its own window. Asked once per site; File → Switch App… asks again. -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-6 backdrop-blur-sm">
    <div class="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl">
      <div class="flex items-center gap-3">
        <img src="/icon.png" class="size-10 rounded-xl" alt="" />
        <div class="flex-1">
          <h1 class="text-lg font-semibold text-slate-900">{{ __('Choose the app this computer is for') }}</h1>
          <p class="text-sm text-slate-500">The apps installed on {{ site }}.</p>
        </div>
        <button v-if="chosenApp()" class="btn-ghost" @click="picker.open = false">{{ __('Cancel') }}</button>
      </div>
      <div class="mt-5 grid grid-cols-2 gap-3" role="radiogroup" :aria-label="__('App')">
        <label v-for="a in apps" :key="a.name" class="flex cursor-pointer items-center gap-3 rounded-xl border p-4 transition-colors"
          :class="selected === a.name ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-100' : 'border-slate-200 hover:border-slate-300'">
          <input v-model="selected" type="radio" name="app" :value="a.name" class="sr-only" />
          <img v-if="a.logo" :src="logo(a)" class="size-9 rounded-lg object-contain" alt="" @error="(e) => (e.target.style.visibility = 'hidden')" />
          <span class="min-w-0 flex-1">
            <span class="block truncate font-medium text-slate-900">{{ a.title }}</span>
            <span class="block truncate text-xs text-slate-500">{{ a.native ? __('Fast, works offline, in this window') : `Opens ${a.route} in its own window` }}</span>
          </span>
        </label>
      </div>
      <label class="mt-4 flex items-center gap-2 text-sm text-slate-600">
        <input v-model="remember" type="checkbox" class="rounded border-slate-300" /> {{ __('Open this app automatically next time') }}
      </label>
      <div class="mt-5 flex items-center justify-between">
        <p class="text-xs text-slate-400">{{ __('Switch later from') }} <b>{{ __('File → Switch App…') }}</b> {{ __('or the ERPNext menu at the top left.') }}</p>
        <button class="btn-primary" :disabled="!selected" @click="open">{{ __('Open') }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { choose, chosenApp, opensAutomatically, picker, siteApps } from '@/lib/apps'
import { session } from '@/lib/session'

const router = useRouter()
const apps = computed(() => siteApps())
const site = computed(() => (session.site || '').replace(/^https?:\/\//, ''))
const selected = ref(chosenApp() || apps.value[0]?.name)
const remember = ref(opensAutomatically())
const logo = (a) => (a.logo?.startsWith('/') ? `${session.site}${a.logo}` : a.logo)

function open() {
  const app = apps.value.find((a) => a.name === selected.value)
  if (app) choose(app, remember.value, router)
}
</script>
