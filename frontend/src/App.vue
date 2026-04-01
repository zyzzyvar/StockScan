<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <el-container style="min-height: 100vh">
    <el-header style="background: #001529; display: flex; align-items: center; padding: 0 24px">
      <span style="color: #fff; font-size: 20px; font-weight: 600; margin-right: 40px">
        StockScan 选股系统
      </span>
      <el-menu
        mode="horizontal"
        :ellipsis="false"
        background-color="#001529"
        text-color="#ccc"
        active-text-color="#409eff"
        router
        style="border: none; flex: 1"
      >
        <el-menu-item index="/">选股运行</el-menu-item>
        <el-menu-item index="/schemes">方案管理</el-menu-item>
        <el-menu-item index="/history">历史记录</el-menu-item>
        <el-menu-item index="/backtest">个股回测</el-menu-item>
        <el-menu-item index="/portfolio-backtest">方案回测</el-menu-item>
      </el-menu>
    </el-header>

    <el-main style="background: #f5f5f5; padding: 24px">
      <RouterView />
    </el-main>
  </el-container>
</template>

<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
.el-header { height: 56px !important; }
</style>
