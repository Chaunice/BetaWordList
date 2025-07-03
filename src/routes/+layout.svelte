<script>
  // 导入全局样式
  import '../app.css';
  // 导入图标
  import { Github } from 'lucide-svelte';

  let isDark = false;
  
  // 彩蛋相关状态
  let isEasterEggActive = false;
  let currentTextIndex = 0;
  let easterEggTexts = [
    "BetaWordList",
    "βWordList 🚀", 
    "词表生成器 🔍",
    "Word Wizard ✨",
    "词表挖掘机 ⛏️",
    "BetaWordList"
  ];

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

  // 彩蛋功能
  function triggerEasterEgg() {
    if (isEasterEggActive) return;
    
    // 添加触觉反馈（如果支持）
    if (navigator.vibrate) {
      navigator.vibrate([100, 50, 100]);
    }
    
    isEasterEggActive = true;
    currentTextIndex = 0;
    
    // 创建粒子效果
    createParticles();
    
    const interval = setInterval(() => {
      currentTextIndex = (currentTextIndex + 1) % easterEggTexts.length;
      
      // 当回到原始文本时停止
      if (currentTextIndex === easterEggTexts.length - 1) {
        setTimeout(() => {
          isEasterEggActive = false;
          clearInterval(interval);
        }, 1000);
      }
    }, 600);
  }
  
  // 创建粒子效果
  function createParticles() {
    const colors = ['#3b82f6', '#8b5cf6', '#ec4899', '#10b981', '#f59e0b'];
    
    for (let i = 0; i < 8; i++) {
      setTimeout(() => {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.cssText = `
          position: fixed;
          top: 20px;
          left: 200px;
          width: 6px;
          height: 6px;
          background: ${colors[Math.floor(Math.random() * colors.length)]};
          border-radius: 50%;
          pointer-events: none;
          z-index: 9999;
          animation: particleFloat ${0.8 + Math.random() * 0.4}s ease-out forwards;
        `;
        
        // 随机方向
        const angle = (Math.PI * 2 * i) / 8 + (Math.random() - 0.5) * 0.5;
        const distance = 50 + Math.random() * 30;
        const endX = Math.cos(angle) * distance;
        const endY = Math.sin(angle) * distance;
        
        particle.style.setProperty('--endX', endX + 'px');
        particle.style.setProperty('--endY', endY + 'px');
        
        document.body.appendChild(particle);
        
        // 清理粒子
        setTimeout(() => {
          if (particle.parentNode) {
            particle.parentNode.removeChild(particle);
          }
        }, 1200);
      }, i * 50);
    }
  }
</script>

<style>
  /* 彩蛋动画效果 */
  @keyframes textBounce {
    0%, 20%, 50%, 80%, 100% {
      transform: translateY(0) scale(1);
    }
    40% {
      transform: translateY(-10px) scale(1.05);
    }
    60% {
      transform: translateY(-5px) scale(1.02);
    }
  }
  
  @keyframes rainbowShift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
  }
  
  @keyframes particleFloat {
    0% {
      transform: translate(0, 0) scale(1);
      opacity: 1;
    }
    100% {
      transform: translate(var(--endX, 0), var(--endY, 0)) scale(0);
      opacity: 0;
    }
  }
  
  .easter-egg-active {
    animation: textBounce 0.6s ease-in-out, rainbowShift 2s ease-in-out infinite;
    background-size: 200% 200%;
    text-shadow: 0 0 10px rgba(168, 85, 247, 0.4);
  }
  
  :global(.particle) {
    box-shadow: 0 0 6px currentColor;
  }
</style>

<!-- 现代化的应用布局 -->
<div class="min-h-screen bg-gradient-to-br from-gray-50 to-white dark:from-gray-900 dark:to-gray-800 text-foreground">
  <!-- 顶部导航栏 -->
  <header class="sticky top-0 z-50 w-full border-b bg-white/80 dark:bg-gray-900/80 backdrop-blur-md supports-[backdrop-filter]:bg-white/60 dark:supports-[backdrop-filter]:bg-gray-900/60 shadow-sm">
    <div class="container max-w-full mx-auto px-4 flex h-16 items-center">
      <!-- 左侧品牌 -->
      <div class="mr-4 flex">
        <a class="mr-6 flex items-center space-x-2" href="/">
          <!-- <div class="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <span class="text-white font-bold text-sm">NLP</span>
          </div> -->
          <button 
            class="font-semibold text-lg tracking-tight hidden sm:block cursor-pointer select-none transition-all duration-300 hover:scale-105 active:scale-95 {isEasterEggActive ? 'easter-egg-active text-transparent bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 bg-clip-text' : 'hover:text-primary'}"
            on:click={triggerEasterEgg}
            title="🎉 Click me for a surprise!"
          >
            {easterEggTexts[currentTextIndex]}
          </button>
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
    <div class="container max-w-full mx-auto px-4 py-8 lg:py-12 md:px-4">
      <slot />
    </div>
  </main>
</div>


