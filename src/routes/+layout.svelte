<script>
  // 导入全局样式
  import '../app.css';
  // 导入图标
  import { Github } from 'lucide-svelte';

  let isDark = false;

  // 初始化时检测本地存储或系统主题
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('theme');
    if (stored) {
      isDark = stored === 'dark';
    } else {
      // 如果没有存储的主题，使用系统偏好设置
      isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      // 保存初始的系统偏好设置
      localStorage.setItem('theme', isDark ? 'dark' : 'light');
    }
    updateTheme();
  }

  function toggleDark() {
    isDark = !isDark;
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    updateTheme();
  }

  function updateTheme() {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }
</script>

<!-- 现代化的应用布局 -->
<div class="min-h-screen bg-gradient-to-br from-gray-50 to-white dark:from-gray-900 dark:to-gray-800 text-foreground">
  <!-- 顶部导航栏 -->
  <header class="sticky top-0 z-50 w-full border-b bg-white/80 dark:bg-gray-900/80 backdrop-blur-md supports-[backdrop-filter]:bg-white/60 dark:supports-[backdrop-filter]:bg-gray-900/60 shadow-sm">
    <div class="container flex h-16 items-center">
      <!-- 左侧品牌 -->
      <div class="mr-4 flex">
        <a class="mr-6 flex items-center space-x-2" href="/">
          <div class="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <span class="text-white font-bold text-sm">NLP</span>
          </div>
          <span class="font-semibold text-lg tracking-tight hidden sm:block">BetaWordList</span>
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
          <button
            class="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring hover:bg-accent hover:text-accent-foreground h-9 px-3"
            on:click={toggleDark}
            aria-label="Toggle dark mode"
            type="button"
          >
            {#if isDark}
              🌙 Dark
            {:else}
              ☀️ Light
            {/if}
          </button>
        </nav>
      </div>
    </div>
  </header>

  <!-- 主要内容区域 -->
  <main class="flex-1">
    <div class="container py-8 lg:py-12">
      <slot />
    </div>
  </main>
</div>

<style>
  .container {
    @apply max-w-screen-2xl mx-auto px-4 md:px-6;
  }
</style>
