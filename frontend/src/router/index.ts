import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'screening',
      component: () => import('../views/ScreeningView.vue')
    },
    {
      path: '/schemes',
      name: 'schemes',
      component: () => import('../views/SchemesView.vue')
    },
    {
      path: '/schemes/:id/edit',
      name: 'scheme-edit',
      component: () => import('../views/SchemeEditorView.vue')
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('../views/HistoryView.vue')
    },
    {
      path: '/backtest',
      name: 'backtest',
      component: () => import('../views/BacktestView.vue')
    },
    {
      path: '/portfolio-backtest',
      name: 'portfolio-backtest',
      component: () => import('../views/PortfolioBacktestView.vue')
    }
  ]
})

export default router
