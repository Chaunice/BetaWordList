<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import { writable, derived } from "svelte/store";
  import { cn } from "$lib/utils.js";
  import Button from "$lib/components/ui/Button.svelte";
  import Card from "$lib/components/ui/Card.svelte";
  import { File, Play, Settings, CheckCircle, AlertCircle, Loader2, ChevronUp, ChevronDown, ChevronsUpDown, Download, SlidersHorizontal, X, Sparkles, Brain, Zap, Filter } from 'lucide-svelte';

  // Stores
  const filePaths = writable<string[]>([]);
  const analyzing = writable(false);
  const progress = writable({ current: 0, total: 0, file: "" });
  const result = writable<Array<[string, string, any]>>([]);
  const modelLoaded = writable(false);
  const modelStatus = writable("");

  // Pagination
  const currentPage = writable(1);
  const itemsPerPage = 15;
  const paginatedResult = derived(
    [result, currentPage],
    ([$result, $currentPage]) => {
      const start = ($currentPage - 1) * itemsPerPage;
      const end = start + itemsPerPage;
      return $result.slice(start, end);
    }
  );

  // Toast notification store
  const toasts = writable<Array<{id: number, message: string, type: string}>>([]);
  let toastId = 0;

  function showToast(message: string, type: 'success' | 'error' | 'warning' = 'success') {
    const id = toastId++;
    toasts.update(current => [...current, { id, message, type }]);
    setTimeout(() => {
      toasts.update(current => current.filter(t => t.id !== id));
    }, 5000);
  }

  const cwsModel = "cws_model.bin";
  const posModel = "pos_model.bin";

  let unlisten: (() => void) | null = null;
  async function startProgressListener() {
    if (unlisten) await unlisten();
    unlisten = await listen("progress", (event) => {
      progress.set(event.payload as { current: number; total: number; file: string });
    });
  }

  async function selectFiles() {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({ multiple: true, filters: [{ name: "Text", extensions: ["txt"] }] });
      if (Array.isArray(selected) && selected.length > 0) {
        filePaths.set(selected);
      } else if (typeof selected === 'string' && selected) {
        filePaths.set([selected]);
      }
    } catch (e) {
      showToast(`File selection failed: ${e}`, 'error');
    }
  }

  async function loadModel() {
    modelStatus.set("Loading models...");
    try {
      await invoke("load_models", { cwsPath: cwsModel, posPath: posModel });
      modelLoaded.set(true);
      modelStatus.set("");
      showToast('Model loaded!', 'success');
    } catch (e) {
      modelLoaded.set(false);
      modelStatus.set("");
      showToast(`Fail to load models: ${e}`, 'error');
    }
  }

  const processedResult = derived([result], ([$result]) => {
    return $result.map(([word, pos, metrics]) => {
      const flatMetrics: Record<string, any> = {};
      function flattenObject(obj: any, prefix = '') {
        for (const key in obj) {
          if (obj.hasOwnProperty(key)) {
            const newKey = prefix ? `${prefix}.${key}` : key;
            if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
              flattenObject(obj[key], newKey);
            } else {
              flatMetrics[newKey] = obj[key];
            }
          }
        }
      }
      if (metrics && typeof metrics === 'object') flattenObject(metrics);
      return { word, pos, metrics: flatMetrics };
    });
  });

  const paginatedProcessedResult = derived(
    [processedResult, currentPage],
    ([$processedResult, $currentPage]) => {
      const start = ($currentPage - 1) * itemsPerPage;
      const end = start + itemsPerPage;
      return $processedResult.slice(start, end);
    }
  );

  const metricColumns = derived([processedResult], ([$processedResult]) => {
    const columns = new Set<string>();
    $processedResult.forEach(item => Object.keys(item.metrics).forEach(key => columns.add(key)));
    return Array.from(columns).sort();
  });

  const sortConfig = writable({ column: '', direction: 'none' });
  const sortedResult = derived([processedResult, sortConfig], ([$processedResult, $sortConfig]) => {
    if ($sortConfig.column === '' || $sortConfig.direction === 'none') return $processedResult;
    const sorted = [...$processedResult].sort((a, b) => {
      let aVal, bVal;
      if ($sortConfig.column === 'word') { aVal = a.word; bVal = b.word; }
      else if ($sortConfig.column === 'pos') { aVal = a.pos; bVal = b.pos; }
      else {
        aVal = a.metrics[$sortConfig.column]; bVal = b.metrics[$sortConfig.column];
        if (typeof aVal === 'number' && typeof bVal === 'number') {
          return $sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal;
        }
      }
      aVal = aVal ?? ''; bVal = bVal ?? '';
      const comparison = String(aVal).localeCompare(String(bVal));
      return $sortConfig.direction === 'asc' ? comparison : -comparison;
    });
    return sorted;
  });

  const paginatedSortedResult = derived(
    [sortedResult, currentPage],
    ([$sortedResult, $currentPage]) => {
      const start = ($currentPage - 1) * itemsPerPage;
      const end = start + itemsPerPage;
      return $sortedResult.slice(start, end);
    }
  );

  const filterConfig = writable({
    wordLength: { min: '', max: '' },
    pos: { include: [], exclude: [] },
    metrics: []
  });

  const filteredResult = derived([sortedResult, filterConfig], ([$sortedResult, $filterConfig]) => {
    return $sortedResult.filter(item => {
      const minLen = parseInt($filterConfig.wordLength.min) || 0;
      const maxLen = parseInt($filterConfig.wordLength.max) || 99;
      if ($filterConfig.wordLength.min !== '' || $filterConfig.wordLength.max !== '') {
        if (item.word.length < minLen || item.word.length > maxLen) return false;
      }
      if (
        ($filterConfig.pos.include.length > 0 && !$filterConfig.pos.include.includes(item.pos)) ||
        ($filterConfig.pos.exclude.length > 0 && $filterConfig.pos.exclude.includes(item.pos))
      ) return false;
      for (const metricFilter of $filterConfig.metrics) {
        if (metricFilter.metric && metricFilter.value && metricFilter.value !== '') {
          const metricValue = item.metrics[metricFilter.metric];
          const targetValue = parseFloat(metricFilter.value);
          if (metricValue === undefined || metricValue === null || typeof metricValue !== 'number') return false;
          switch (metricFilter.operator) {
            case 'gt': if (!(metricValue > targetValue)) return false; break;
            case 'lt': if (!(metricValue < targetValue)) return false; break;
            case 'gte': if (!(metricValue >= targetValue)) return false; break;
            case 'lte': if (!(metricValue <= targetValue)) return false; break;
            case 'eq': if (!(Math.abs(metricValue - targetValue) < 0.0001)) return false; break;
          }
        }
      }
      return true;
    });
  });

  const finalPaginatedResult = derived(
    [filteredResult, currentPage],
    ([$filteredResult, $currentPage]) => {
      const start = ($currentPage - 1) * itemsPerPage;
      const end = start + itemsPerPage;
      return $filteredResult.slice(start, end);
    }
  );

  const uniquePOS = derived([processedResult], ([$processedResult]) => {
    const posSet = new Set<string>();
    $processedResult.forEach(item => posSet.add(item.pos));
    return Array.from(posSet).sort();
  });

  function handleSort(column: string) {
    sortConfig.update(current => {
      if (current.column === column) {
        const directions = ['none', 'asc', 'desc', 'none'];
        const currentIndex = directions.indexOf(current.direction);
        const nextDirection = directions[(currentIndex + 1) % directions.length];
        return { column: nextDirection === 'none' ? '' : column, direction: nextDirection };
      } else {
        return { column, direction: 'asc' };
      }
    });
    currentPage.set(1);
  }

  function clearFilters() {
    filterConfig.set({ wordLength: { min: '', max: '' }, pos: { include: [], exclude: [] }, metrics: [] });
    currentPage.set(1);
  }

  function addMetricFilter() {
    filterConfig.update(cfg => {
      cfg.metrics = [...cfg.metrics, { metric: '', operator: 'gt', value: '' }];
      return cfg;
    });
  }

  function removeMetricFilter(index) {
    filterConfig.update(cfg => {
      cfg.metrics = cfg.metrics.filter((_, i) => i !== index);
      return cfg;
    });
    currentPage.set(1);
  }

  function updateMetricFilter(index, field, value) {
    filterConfig.update(cfg => {
      cfg.metrics[index][field] = value;
      return cfg;
    });
    currentPage.set(1);
  }

  async function downloadCSV() {
    try {
      const headers = ['Word', 'POS', ...$metricColumns];
      const csvRows = [headers.join(',')];
      $filteredResult.forEach(item => {
        const row = [
          `"${item.word}"`,
          `"${item.pos}"`,
          ...$metricColumns.map(col => item.metrics[col] ?? '')
        ];
        csvRows.push(row.join(','));
      });
      const csvContent = csvRows.join('\n');
      const now = new Date();
      const timestamp = now.toISOString().replace(/[:\.]/g, '-').slice(0, 19);
      const filename = `wordlist_results_${timestamp}.csv`;
      const { save } = await import("@tauri-apps/plugin-dialog");
      const filePath = await save({ defaultPath: filename, filters: [{ name: 'CSV Files', extensions: ['csv'] }] });
      if (filePath) {
        const { writeTextFile } = await import("@tauri-apps/plugin-fs");
        await writeTextFile(filePath, csvContent);
        showToast(`Results saved to: ${filePath}`, 'success');
      }
    } catch (error) {
      showToast(`Fail to save: ${error}`, 'error');
    }
  }

  async function analyze() {
    if (!$modelLoaded) { showToast('Please load the NLP model first', 'warning'); return; }
    if ($filePaths.length === 0) { showToast('Please select files to analyze first', 'warning'); return; }
    analyzing.set(true);
    result.set([]);
    currentPage.set(1);
    await startProgressListener();
    try {
      const analysisResult: Array<[string, string, any]> = await invoke("start_analysis", { filePaths: $filePaths });
      result.set(analysisResult);
      showToast(analysisResult.length === 0 ? 'Analysis complete, but no results were extracted.' : 'Analysis complete!', analysisResult.length === 0 ? 'warning' : 'success');
    } catch (e) {
      showToast(`Analysis failed: ${e}`, 'error');
    }
    analyzing.set(false);
    if (unlisten) { await unlisten(); unlisten = null; }
  }

  function goToPage(page: number) {
    currentPage.set(page);
  }

  $: totalPages = Math.ceil($filteredResult.length / itemsPerPage);

  // 计算整体进度宽度
  function getProgressWidth() {
    let progress = 0;
    if ($filePaths.length > 0) progress += 33;
    if ($modelLoaded) progress += 33;
    if ($result.length > 0) progress += 34;
    return progress;
  }
</script>

<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
  
  :root {
    --primary-50: #f0f9ff;
    --primary-100: #e0f2fe;
    --primary-200: #bae6fd;
    --primary-300: #7dd3fc;
    --primary-400: #38bdf8;
    --primary-500: #0ea5e9;
    --primary-600: #0284c7;
    --primary-700: #0369a1;
    --primary-800: #075985;
    --primary-900: #0c4a6e;
    
    --secondary-50: #fafaf9;
    --secondary-100: #f5f5f4;
    --secondary-200: #e7e5e4;
    --secondary-300: #d6d3d1;
    --secondary-400: #a8a29e;
    --secondary-500: #78716c;
    --secondary-600: #57534e;
    --secondary-700: #44403c;
    --secondary-800: #292524;
    --secondary-900: #1c1917;
    
    --success-500: #10b981;
    --success-600: #059669;
    --warning-500: #f59e0b;
    --warning-600: #d97706;
    --error-500: #ef4444;
    --error-600: #dc2626;
    
    --glass-bg: rgba(255, 255, 255, 0.25);
    --glass-border: rgba(255, 255, 255, 0.18);
    --glass-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
  }

  * {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }

  @keyframes float {
    0%, 100% { transform: translateY(0px); }
    50% { transform: translateY(-20px); }
  }

  @keyframes glow {
    0%, 100% { box-shadow: 0 0 20px rgba(56, 189, 248, 0.3); }
    50% { box-shadow: 0 0 40px rgba(56, 189, 248, 0.6); }
  }

  @keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
  }

  @keyframes slideUp {
    from { opacity: 0; transform: translateY(50px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @keyframes slideDown {
    from { opacity: 0; transform: translateY(-30px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @keyframes scaleIn {
    from { opacity: 0; transform: scale(0.8); }
    to { opacity: 1; transform: scale(1); }
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .animate-float {
    animation: float 6s ease-in-out infinite;
  }

  .animate-glow {
    animation: glow 2s ease-in-out infinite alternate;
  }

  .animate-shimmer {
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
    background-size: 200% 100%;
    animation: shimmer 2s infinite;
  }

  .animate-slide-up {
    animation: slideUp 0.6s ease-out;
  }

  .animate-slide-down {
    animation: slideDown 0.4s ease-out;
  }

  .animate-scale-in {
    animation: scaleIn 0.5s ease-out;
  }

  .animate-pulse {
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }

  .animate-spin {
    animation: spin 1s linear infinite;
  }

  .glass-card {
    background: var(--glass-bg);
    backdrop-filter: blur(25px);
    -webkit-backdrop-filter: blur(25px);
    border: 1px solid var(--glass-border);
    box-shadow: var(--glass-shadow);
  }

  .glass-button {
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .glass-button:hover {
    background: rgba(255, 255, 255, 0.2);
    transform: translateY(-2px);
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
  }

  .gradient-text {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .gradient-bg {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  }

  .step-card {
    position: relative;
    overflow: hidden;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .step-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
    transition: left 0.5s ease;
  }

  .step-card:hover::before {
    left: 100%;
  }

  .custom-scrollbar {
    scrollbar-width: thin;
    scrollbar-color: var(--primary-500) var(--secondary-200);
  }

  .custom-scrollbar::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }

  .custom-scrollbar::-webkit-scrollbar-track {
    background: var(--secondary-100);
    border-radius: 4px;
  }

  .custom-scrollbar::-webkit-scrollbar-thumb {
    background: linear-gradient(135deg, var(--primary-500), var(--primary-600));
    border-radius: 4px;
  }

  .custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background: linear-gradient(135deg, var(--primary-600), var(--primary-700));
  }

  .table-row {
    transition: all 0.2s ease;
  }

  .table-row:hover {
    background: linear-gradient(90deg, rgba(56, 189, 248, 0.05), rgba(147, 51, 234, 0.05));
    transform: translateX(4px);
  }

  .floating-element {
    position: absolute;
    pointer-events: none;
    opacity: 0.1;
  }

  .floating-circle {
    width: 200px;
    height: 200px;
    background: radial-gradient(circle, var(--primary-400), transparent);
    border-radius: 50%;
    animation: float 8s ease-in-out infinite;
  }

  .floating-square {
    width: 150px;
    height: 150px;
    background: linear-gradient(45deg, var(--primary-500), var(--secondary-500));
    transform: rotate(45deg);
    animation: float 10s ease-in-out infinite reverse;
  }

  .stats-card {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.05));
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    transition: all 0.3s ease;
  }

  .stats-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  }
</style>

<div class="min-h-screen relative overflow-hidden bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
  <!-- Floating Background Elements -->
  <div class="floating-element floating-circle top-20 left-10 animate-float"></div>
  <div class="floating-element floating-square top-40 right-20" style="animation-delay: -2s;"></div>
  <div class="floating-element floating-circle bottom-20 right-10" style="animation-delay: -4s;"></div>
  
  <!-- Gradient Overlay -->
  <div class="absolute inset-0 bg-gradient-to-br from-blue-500/10 via-purple-500/10 to-pink-500/10"></div>
  
  <div class="relative z-10 p-6 space-y-8">
    <!-- Toast Notifications -->
    {#if $toasts.length > 0}
      <div class="fixed top-6 right-6 z-50 space-y-3">
        {#each $toasts as toast (toast.id)}
          <div class={cn(
            "animate-slide-down glass-card rounded-2xl p-4 border-l-4 transition-all duration-300",
            toast.type === 'success' && "border-l-green-400 bg-green-900/20 text-green-100",
            toast.type === 'error' && "border-l-red-400 bg-red-900/20 text-red-100",
            toast.type === 'warning' && "border-l-yellow-400 bg-yellow-900/20 text-yellow-100"
          )}>
            <div class="flex items-center gap-3">
              <div class={cn(
                "p-1 rounded-full",
                toast.type === 'success' && "bg-green-500/20",
                toast.type === 'error' && "bg-red-500/20",
                toast.type === 'warning' && "bg-yellow-500/20"
              )}>
                {#if toast.type === 'success'}
                  <CheckCircle class="h-5 w-5 text-green-400" />
                {:else if toast.type === 'error'}
                  <AlertCircle class="h-5 w-5 text-red-400" />
                {:else}
                  <AlertCircle class="h-5 w-5 text-yellow-400" />
                {/if}
              </div>
              <span class="text-sm font-medium">{toast.message}</span>
            </div>
          </div>
        {/each}
      </div>
    {/if}

    <!-- Header -->
    <div class="text-center py-16 animate-slide-up">
      <div class="relative inline-block">
        <h1 class="text-7xl font-black gradient-text mb-4 animate-float">
          Word List Generator
        </h1>
        <div class="absolute -top-4 -right-4 text-yellow-400 animate-pulse">
          <Sparkles class="h-8 w-8" />
        </div>
      </div>
      <p class="mt-4 text-xl text-gray-300 max-w-3xl mx-auto leading-relaxed">
        Advanced linguistic analysis powered by machine learning algorithms
      </p>
      <div class="mt-8 flex justify-center gap-8 text-sm">
        {#each [
          { icon: Brain, label: 'AI Powered', color: 'text-blue-400' },
          { icon: Zap, label: 'Real-time', color: 'text-yellow-400' },
          { icon: Sparkles, label: 'Insights', color: 'text-purple-400' }
        ] as feature}
          <div class="flex items-center gap-2 glass-card px-4 py-2 rounded-full">
            <svelte:component this={feature.icon} class="h-4 w-4 {feature.color}" />
            <span class="text-gray-300 font-medium">{feature.label}</span>
          </div>
        {/each}
      </div>
    </div>

    <!-- Main Operation Card -->
    <div class="glass-card rounded-3xl p-8 shadow-2xl animate-scale-in">
      <div class="space-y-10">
        <!-- Progress Header -->
        <div class="text-center space-y-4">
          <h2 class="text-3xl font-bold text-white">Get Started</h2>
          <p class="text-gray-400">Three simple steps to unlock linguistic insights</p>
          
          <!-- Enhanced Progress Bar -->
          <div class="relative w-full max-w-2xl mx-auto">
            <div class="h-2 bg-gray-800 rounded-full overflow-hidden">
              <div 
                class="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 transition-all duration-1000 ease-out relative"
                style="width: {getProgressWidth()}%"
              >
                <div class="absolute inset-0 animate-shimmer"></div>
              </div>
            </div>
            <div class="flex justify-between text-xs text-gray-500 mt-2">
              <span>Select Files</span>
              <span>Load Models</span>
              <span>Analyze</span>
            </div>
          </div>
        </div>
        
        <!-- Step Cards -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {#each [
            { 
              step: 1, 
              title: 'Select Files', 
              desc: 'Choose your text files for analysis', 
              icon: File, 
              action: selectFiles, 
              disabled: $analyzing, 
              isCompleted: $filePaths.length > 0,
              isActive: !$filePaths.length && !$analyzing,
              isProcessing: false,
              color: 'blue'
            },
            { 
              step: 2, 
              title: 'Load Models', 
              desc: 'Initialize advanced NLP models', 
              icon: Settings, 
              action: loadModel, 
              disabled: $analyzing || $modelLoaded || $filePaths.length === 0, 
              isCompleted: $modelLoaded,
              isActive: $filePaths.length > 0 && !$modelLoaded && !$analyzing,
              isProcessing: $modelStatus && !$modelLoaded,
              color: 'purple'
            },
            { 
              step: 3, 
              title: 'Start Analysis', 
              desc: 'Extract deep linguistic patterns', 
              icon: Play, 
              action: analyze, 
              disabled: $analyzing || $filePaths.length === 0 || !$modelLoaded, 
              isCompleted: $result.length > 0,
              isActive: $modelLoaded && $result.length === 0 && !$analyzing,
              isProcessing: $analyzing,
              color: 'green'
            }
          ] as step, i}
            <div 
              class={cn(
                "step-card relative p-8 rounded-2xl border transition-all duration-500 transform hover:scale-105",
                step.isCompleted 
                  ? "bg-gradient-to-br from-green-500/20 to-emerald-600/20 border-green-400/50 shadow-green-500/25" 
                  : step.isActive 
                    ? `bg-gradient-to-br from-${step.color}-500/20 to-${step.color}-600/20 border-${step.color}-400/50 shadow-${step.color}-500/25 animate-glow` 
                    : step.isProcessing
                      ? "bg-gradient-to-br from-yellow-500/20 to-orange-600/20 border-yellow-400/50 shadow-yellow-500/25"
                      : "bg-gray-800/50 border-gray-700/50"
              )}
              style="animation-delay: {i * 0.2}s"
            >
              
              <!-- Step Content -->
              <div class="flex flex-col items-center text-center space-y-6">
                
                <!-- Icon Circle -->
                <div class="relative">
                  <div class={cn(
                    "w-20 h-20 rounded-2xl flex items-center justify-center text-2xl font-bold transition-all duration-500 relative overflow-hidden",
                    step.isCompleted 
                      ? "bg-gradient-to-br from-green-500 to-emerald-600 text-white shadow-2xl" 
                      : step.isProcessing
                        ? "bg-gradient-to-br from-yellow-500 to-orange-500 text-white shadow-2xl"
                        : step.isActive
                          ? `bg-gradient-to-br from-${step.color}-500 to-${step.color}-600 text-white shadow-2xl`
                          : "bg-gray-700 text-gray-400"
                  )}>
                    {#if step.isCompleted}
                      <CheckCircle class="h-8 w-8" />
                    {:else if step.isProcessing}
                      <Loader2 class="h-8 w-8 animate-spin" />
                    {:else}
                      <svelte:component this={step.icon} class="h-8 w-8" />
                    {/if}
                  </div>
                  
                  <!-- Step Number Badge -->
                  <div class={cn(
                    "absolute -top-2 -right-2 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold",
                    step.isCompleted 
                      ? "bg-green-500 text-white" 
                      : step.isActive 
                        ? `bg-${step.color}-500 text-white` 
                        : "bg-gray-600 text-gray-300"
                  )}>
                    {step.step}
                  </div>
                </div>
                
                <!-- Step Info -->
                <div class="space-y-3">
                  <h3 class="text-xl font-bold text-white">{step.title}</h3>
                  <p class="text-gray-400 text-sm leading-relaxed">{step.desc}</p>
                  
                  <!-- Status Indicators -->
                  {#if step.step === 1 && $filePaths.length > 0}
                    <div class="text-xs text-green-400 font-medium">
                      {$filePaths.length} file{$filePaths.length === 1 ? '' : 's'} selected
                    </div>
                  {/if}
                  
                  {#if step.step === 2 && $modelStatus}
                    <div class="text-xs text-yellow-400 font-medium animate-pulse">
                      {$modelStatus}
                    </div>
                  {/if}
                  
                  {#if step.step === 3 && $analyzing}
                    <div class="text-xs text-blue-400 font-medium">
                      Processing: {$progress.file || 'Initializing...'}
                    </div>
                  {/if}
                </div>
                
                <!-- Action Button -->
                <Button
                  on:click={step.action}
                  disabled={step.disabled}
                  class={cn(
                    "w-full glass-button text-white font-semibold py-3 px-6 rounded-xl transition-all duration-300",
                    step.isCompleted 
                      ? "bg-green-500/80 hover:bg-green-500" 
                      : step.isActive 
                        ? `bg-${step.color}-500/80 hover:bg-${step.color}-500` 
                        : "bg-gray-600/50 hover:bg-gray-600/70",
                    (step.disabled) && "opacity-50 cursor-not-allowed"
                  )}
                >
                  {#if step.isProcessing}
                    <Loader2 class="h-4 w-4 animate-spin mr-2" />
                    Processing...
                  {:else if step.isCompleted}
                    <CheckCircle class="h-4 w-4 mr-2" />
                    Completed
                  {:else}
                    <svelte:component this={step.icon} class="h-4 w-4 mr-2" />
                    {step.title}
                  {/if}
                </Button>
              </div>
            </div>
          {/each}
        </div>
      </div>
    </div>

    <!-- Analysis Progress Section -->
    {#if $analyzing}
      <div class="glass-card rounded-3xl p-8 animate-slide-up">
        <div class="text-center space-y-6">
          <div class="flex items-center justify-center gap-3 mb-6">
            <div class="relative">
              <Loader2 class="h-8 w-8 text-blue-400 animate-spin" />
              <div class="absolute inset-0 bg-blue-400/20 rounded-full animate-ping"></div>
            </div>
            <h2 class="text-2xl font-bold text-white">Analysis in Progress</h2>
          </div>
          
          <div class="max-w-2xl mx-auto space-y-4">
            <div class="flex justify-between items-center text-sm">
              <span class="text-gray-400">Processing files...</span>
              <span class="text-white font-medium">{$progress.current} / {$progress.total}</span>
            </div>
            
            <div class="relative h-3 bg-gray-800 rounded-full overflow-hidden">
              <div 
                class="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-300 ease-out"
                style="width: {$progress.total > 0 ? ($progress.current / $progress.total) * 100 : 0}%"
              >
                <div class="absolute inset-0 bg-white/20 animate-shimmer"></div>
              </div>
            </div>
            
            {#if $progress.file}
              <div class="text-center">
                <p class="text-gray-400 text-sm">Currently processing:</p>
                <p class="text-white font-medium truncate max-w-md mx-auto">{$progress.file}</p>
              </div>
            {/if}
          </div>
        </div>
      </div>
    {/if}

    <!-- Results Section -->
    {#if $result.length > 0}
      <div class="space-y-6 animate-slide-up">
        <!-- Results Header with Stats -->
        <div class="glass-card rounded-3xl p-8">
          <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div>
              <h2 class="text-3xl font-bold text-white mb-2">Analysis Results</h2>
              <p class="text-gray-400">Comprehensive linguistic analysis completed</p>
            </div>
            
            <!-- Statistics Cards -->
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {#each [
                { label: 'Total Words', value: $processedResult.length, icon: File, color: 'blue' },
                { label: 'Unique POS', value: $uniquePOS.length, icon: Settings, color: 'purple' },
                { label: 'Filtered', value: $filteredResult.length, icon: Filter, color: 'green' },
                { label: 'Pages', value: totalPages, icon: ChevronUp, color: 'orange' }
              ] as stat}
                <div class="stats-card p-4 rounded-xl text-center">
                  <div class={`inline-flex p-2 rounded-lg bg-${stat.color}-500/20 mb-2`}>
                    <svelte:component this={stat.icon} class={`h-5 w-5 text-${stat.color}-400`} />
                  </div>
                  <div class="text-2xl font-bold text-white">{stat.value.toLocaleString()}</div>
                  <div class="text-xs text-gray-400">{stat.label}</div>
                </div>
              {/each}
            </div>
          </div>
        </div>

        <!-- Filters Section -->
        <div class="glass-card rounded-3xl p-8">
          <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6 mb-6">
            <h3 class="text-xl font-bold text-white flex items-center gap-2">
              <Filter class="h-5 w-5 text-blue-400" />
              Advanced Filters
            </h3>
            <div class="flex gap-3">
              <Button
                on:click={clearFilters}
                class="glass-button text-white px-4 py-2 rounded-lg hover:bg-red-500/20"
              >
                <X class="h-4 w-4 mr-2" />
                Clear All
              </Button>
              <Button
                on:click={downloadCSV}
                class="glass-button text-white px-4 py-2 rounded-lg hover:bg-green-500/20"
              >
                <Download class="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            </div>
          </div>
          
          <!-- Filter Controls -->
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Word Length Filter -->
            <div class="space-y-3">
              <label for="word-length-min" class="block text-sm font-medium text-gray-300">Word Length</label>
              <div class="flex gap-2">
                <input
                  id="word-length-min"
                  type="number"
                  placeholder="Min"
                  bind:value={$filterConfig.wordLength.min}
                  on:input={() => currentPage.set(1)}
                  class="flex-1 bg-gray-800/50 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-400 focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
                />
                <input
                  id="word-length-max"
                  type="number"
                  placeholder="Max"
                  bind:value={$filterConfig.wordLength.max}
                  on:input={() => currentPage.set(1)}
                  class="flex-1 bg-gray-800/50 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-400 focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
                />
              </div>
            </div>
            
            <!-- POS Include Filter -->
            <div class="space-y-3">
              <label for="include-pos-select" class="block text-sm font-medium text-gray-300">Include POS Tags</label>
              <select
                id="include-pos-select"
                multiple
                bind:value={$filterConfig.pos.include}
                on:change={() => currentPage.set(1)}
                class="w-full bg-gray-800/50 border border-gray-600 rounded-lg px-3 py-2 text-white focus:border-blue-400 focus:ring-1 focus:ring-blue-400 custom-scrollbar"
                size="3"
              >
                {#each $uniquePOS as pos}
                  <option value={pos} class="py-1">{pos}</option>
                {/each}
              </select>
            </div>
            
            <!-- POS Exclude Filter -->
            <div class="space-y-3">
              <label for="exclude-pos-select" class="block text-sm font-medium text-gray-300">Exclude POS Tags</label>
              <select
                id="exclude-pos-select"
                multiple
                bind:value={$filterConfig.pos.exclude}
                on:change={() => currentPage.set(1)}
                class="w-full bg-gray-800/50 border border-gray-600 rounded-lg px-3 py-2 text-white focus:border-blue-400 focus:ring-1 focus:ring-blue-400 custom-scrollbar"
                size="3"
              >
                {#each $uniquePOS as pos}
                  <option value={pos} class="py-1">{pos}</option>
                {/each}
              </select>
            </div>
          </div>
          
          <!-- Metric Filters -->
          <div class="mt-6 space-y-4">
            <div class="flex items-center justify-between">
              <label for="add-metric-filter-btn" class="block text-sm font-medium text-gray-300">Metric Filters</label>
              <Button
                id="add-metric-filter-btn"
                on:click={addMetricFilter}
                class="glass-button text-white px-3 py-1 rounded-lg text-sm hover:bg-blue-500/20"
              >
                Add Filter
              </Button>
            </div>
            
            {#each $filterConfig.metrics as filter, index}
              <div class="grid grid-cols-1 lg:grid-cols-4 gap-3 p-4 bg-gray-800/30 rounded-lg">
                <select
                  bind:value={filter.metric}
                  on:change={(e) => updateMetricFilter(index, 'metric', e.target.value)}
                  class="bg-gray-800/50 border border-gray-600 rounded-lg px-3 py-2 text-white focus:border-blue-400"
                >
                  <option value="">Select Metric</option>
                  {#each $metricColumns as col}
                    <option value={col}>{col}</option>
                  {/each}
                </select>
                
                <select
                  bind:value={filter.operator}
                  on:change={(e) => updateMetricFilter(index, 'operator', e.target.value)}
                  class="bg-gray-800/50 border border-gray-600 rounded-lg px-3 py-2 text-white focus:border-blue-400"
                >
                  <option value="gt">Greater than</option>
                  <option value="lt">Less than</option>
                  <option value="gte">Greater or equal</option>
                  <option value="lte">Less or equal</option>
                  <option value="eq">Equal to</option>
                </select>
                
                <input
                  type="number"
                  step="any"
                  placeholder="Value"
                  bind:value={filter.value}
                  on:input={(e) => updateMetricFilter(index, 'value', e.target.value)}
                  class="bg-gray-800/50 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-400 focus:border-blue-400"
                />
                
                <Button
                  on:click={() => removeMetricFilter(index)}
                  class="glass-button text-red-400 px-3 py-2 rounded-lg hover:bg-red-500/20"
                >
                  <X class="h-4 w-4" />
                </Button>
              </div>
            {/each}
          </div>
        </div>

        <!-- Results Table -->
        <div class="glass-card rounded-3xl overflow-hidden">
          <div class="p-6 border-b border-gray-700/50">
            <h3 class="text-xl font-bold text-white">Word Analysis Data</h3>
            <p class="text-gray-400 text-sm mt-1">
              Showing {($currentPage - 1) * itemsPerPage + 1} - {Math.min($currentPage * itemsPerPage, $filteredResult.length)} of {$filteredResult.length} results
            </p>
          </div>
          
          <div class="overflow-x-auto custom-scrollbar">
            <table class="w-full">
              <thead class="bg-gray-800/50">
                <tr>
                  {#each [
                    { key: 'word', label: 'Word' },
                    { key: 'pos', label: 'POS' },
                    ...$metricColumns.map(col => ({ key: col, label: col.replace(/\./g, ' ').replace(/([A-Z])/g, ' $1').trim() }))
                  ] as column}
                    <th class="text-left p-4 text-gray-300 font-semibold">
                      <button
                        on:click={() => handleSort(column.key)}
                        class="flex items-center gap-2 hover:text-white transition-colors group w-full text-left"
                      >
                        <span class="truncate">{column.label}</span>
                        <div class="flex flex-col">
                          {#if $sortConfig.column === column.key}
                            {#if $sortConfig.direction === 'asc'}
                              <ChevronUp class="h-3 w-3 text-blue-400" />
                            {:else if $sortConfig.direction === 'desc'}
                              <ChevronDown class="h-3 w-3 text-blue-400" />
                            {:else}
                              <ChevronsUpDown class="h-3 w-3 group-hover:text-blue-400" />
                            {/if}
                          {:else}
                            <ChevronsUpDown class="h-3 w-3 group-hover:text-blue-400" />
                          {/if}
                        </div>
                      </button>
                    </th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each $finalPaginatedResult as item, index}
                  <tr class="table-row border-b border-gray-700/30 hover:bg-gradient-to-r hover:from-blue-500/5 hover:to-purple-500/5">
                    <td class="p-4 text-white font-medium">{item.word}</td>
                    <td class="p-4">
                      <span class="inline-flex px-2 py-1 text-xs font-medium bg-blue-500/20 text-blue-300 rounded-full">
                        {item.pos}
                      </span>
                    </td>
                    {#each $metricColumns as col}
                      <td class="p-4 text-gray-300">
                        {#if typeof item.metrics[col] === 'number'}
                          <span class="font-mono">
                            {item.metrics[col].toFixed(4)}
                          </span>
                        {:else}
                          <span class="text-gray-500">
                            {item.metrics[col] ?? 'N/A'}
                          </span>
                        {/if}
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
          
          <!-- Pagination -->
          {#if totalPages > 1}
            <div class="p-6 border-t border-gray-700/50">
              <div class="flex items-center justify-between">
                <div class="text-sm text-gray-400">
                  Page {$currentPage} of {totalPages}
                </div>
                
                <div class="flex items-center gap-2">
                  <Button
                    on:click={() => goToPage(Math.max(1, $currentPage - 1))}
                    disabled={$currentPage === 1}
                    class="glass-button text-white px-3 py-2 rounded-lg disabled:opacity-50"
                  >
                    <ChevronUp class="h-4 w-4 rotate-[-90deg]" />
                  </Button>
                  
                  {#each Array(Math.min(5, totalPages)).fill(0).map((_, i) => {
                    const start = Math.max(1, $currentPage - 2);
                    return start + i;
                  }).filter(page => page <= totalPages) as page}
                    <Button
                      on:click={() => goToPage(page)}
                      class={cn(
                        "px-3 py-2 rounded-lg font-medium transition-all",
                        page === $currentPage 
                          ? "bg-blue-500 text-white shadow-lg" 
                          : "glass-button text-gray-300 hover:text-white"
                      )}
                    >
                      {page}
                    </Button>
                  {/each}
                  
                  <Button
                    on:click={() => goToPage(Math.min(totalPages, $currentPage + 1))}
                    disabled={$currentPage === totalPages}
                    class="glass-button text-white px-3 py-2 rounded-lg disabled:opacity-50"
                  >
                    <ChevronUp class="h-4 w-4 rotate-90" />
                  </Button>
                </div>
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Footer -->
    <div class="text-center py-12 animate-slide-up">
      <div class="glass-card rounded-2xl p-8 max-w-2xl mx-auto">
        <div class="flex items-center justify-center gap-3 mb-4">
          <Brain class="h-6 w-6 text-blue-400" />
          <h3 class="text-xl font-bold text-white">Advanced Linguistic Analysis</h3>
        </div>
        <p class="text-gray-400 leading-relaxed">
          Powered by state-of-the-art machine learning models for Chinese word segmentation, 
          part-of-speech tagging, and comprehensive statistical analysis. 
          Built with Tauri, Svelte, and Rust for optimal performance.
        </p>
        <div class="mt-6 flex justify-center gap-6 text-sm">
          {#each [
            { label: 'Fast Processing', icon: Zap },
            { label: 'Accurate Results', icon: CheckCircle },
            { label: 'Export Ready', icon: Download }
          ] as feature}
            <div class="flex items-center gap-2 text-gray-400">
              <svelte:component this={feature.icon} class="h-4 w-4 text-blue-400" />
              <span>{feature.label}</span>
            </div>
          {/each}
        </div>
      </div>
    </div>
  </div>
</div>