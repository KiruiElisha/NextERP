import { createRouter, createWebHashHistory } from 'vue-router'

// Hash history: the app is files in the bundle, there is no server to route paths.
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/home' },
    { path: '/home', component: () => import('./pages/Home.vue') },
    { path: '/list/:slug', component: () => import('./pages/ListPage.vue'), props: true },
    { path: '/doc/:slug/:name', component: () => import('./pages/DocPage.vue'), props: true },
    { path: '/new/sales-invoice', component: () => import('./pages/NewInvoice.vue') },
    { path: '/esg', component: () => import('./pages/Esg.vue') },
    { path: '/settings', component: () => import('./pages/Settings.vue') },
  ],
})
