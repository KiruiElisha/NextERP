import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { __ } from './lib/i18n'
import { watchTheme } from './lib/theme'
import './style.css'

watchTheme()

const app = createApp(App).use(router)
// __('…') in every template, as in Frappe
app.config.globalProperties.__ = __
app.mount('#app')
