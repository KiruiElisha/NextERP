import { createRouter, createWebHashHistory } from 'vue-router'
import { bySlug } from './lib/doctypes'

// Hash history: the app is files in the bundle, there is no server to route paths.
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/home' },
    { path: '/home', component: () => import('./pages/Home.vue') },
    { path: '/list/:slug', component: () => import('./pages/ListPage.vue'), props: true },
    { path: '/form/:doctype/:name', component: () => import('./pages/FormPage.vue'), props: true },
    { path: '/l/:doctype', component: () => import('./pages/GenericList.vue'), props: true },
    // Older addresses: a cached document and the quick invoice now open in the full form.
    { path: '/doc/:slug/:name', redirect: (to) => `/form/${encodeURIComponent(bySlug(to.params.slug) || to.params.slug)}/${encodeURIComponent(to.params.name)}` },
    { path: '/new/sales-invoice', redirect: '/form/Sales%20Invoice/new' },
    { path: '/esg', component: () => import('./pages/Esg.vue') },
    { path: '/reports', component: () => import('./pages/Reports.vue') },
    { path: '/reports/:dept', component: () => import('./pages/Reports.vue'), props: true },
    { path: '/pos', component: () => import('./pages/Pos.vue'), meta: { bare: true } },
    { path: '/stock-take', component: () => import('./pages/StockTake.vue') },
    { path: '/stock-take/:name', component: () => import('./pages/StockTake.vue'), props: true },
    { path: '/report/:name', component: () => import('./pages/ReportRunner.vue'), props: true },
    { path: '/settings', component: () => import('./pages/Settings.vue') },
  ],
})
