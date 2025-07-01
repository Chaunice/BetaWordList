<script>
  // 导入全局样式
  import '../app.css';
  // 导入图标
  import { Github } from 'lucide-svelte';
</script>

<!-- 现代化的应用布局 -->
<div class="min-h-screen bg-background text-foreground">
  <!-- 顶部导航栏 -->
  <header class="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
    <div class="container flex h-14 items-center">
      <!-- 左侧品牌 -->
      <div class="mr-4 flex">
        <a class="mr-6 flex items-center space-x-2" href="/">
          <span class="font-bold text-xl tracking-tight">BetaWordList</span>
        </a>
      </div>
      
      <!-- 右侧操作 -->
      <div class="flex flex-1 items-center justify-end space-x-2">
        <nav class="flex items-center space-x-2">
          <a
            class="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring hover:bg-accent hover:text-accent-foreground h-9 px-3"
            href="https://github.com/Chaunice/BetaWordList"
            target="_blank"
            rel="noreferrer"
          >
            <Github class="h-4 w-4 mr-2" />
            GitHub
          </a>
        </nav>
      </div>
    </div>
  </header>

  <!-- 主要内容区域 -->
  <main class="flex-1">
    <div class="container py-6">
      <slot />
    </div>
  </main>
</div>

<style>
  .container {
    @apply max-w-screen-2xl mx-auto px-4 md:px-6;
  }
</style>
