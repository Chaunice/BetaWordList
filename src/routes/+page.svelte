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

  const filterConfig = writable<{
    wordLength: { min: string; max: string };
    pos: { include: string[]; exclude: string[] };
    metrics: Array<{ metric: string; operator: string; value: string }>;
  }>({
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

  // POS filter search
  const posSearchInclude = writable('');
  const posSearchExclude = writable('');
  
  const filteredPOSInclude = derived([uniquePOS, posSearchInclude], ([$uniquePOS, $search]) => {
    if (!$search) return $uniquePOS;
    return $uniquePOS.filter(pos => pos.toLowerCase().includes($search.toLowerCase()));
  });
  
  const filteredPOSExclude = derived([uniquePOS, posSearchExclude], ([$uniquePOS, $search]) => {
    if (!$search) return $uniquePOS;
    return $uniquePOS.filter(pos => pos.toLowerCase().includes($search.toLowerCase()));
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

  function removeMetricFilter(index: number) {
    filterConfig.update(cfg => {
      cfg.metrics = cfg.metrics.filter((_, i) => i !== index);
      return cfg;
    });
    currentPage.set(1);
  }

  function updateMetricFilter(index: number, field: string, value: string) {
    filterConfig.update(cfg => {
      (cfg.metrics[index] as any)[field] = value;
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
    
    /* Dynamic theme variables */
    --bg-primary: theme('colors.slate.900');
    --bg-secondary: theme('colors.slate.800');
    --bg-accent: theme('colors.purple.900');
    --text-primary: theme('colors.white');
    --text-secondary: theme('colors.gray.300');
    --text-muted: theme('colors.gray.400');
    --border-color: theme('colors.gray.700');
    --glass-bg: rgba(255, 255, 255, 0.1);
    --glass-border: rgba(255, 255, 255, 0.15);
    --glass-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
  }

  /* Dark mode (default) */
  :root {
    --bg-primary: #0f172a;
    --bg-secondary: #1e293b;
    --bg-accent: #581c87;
    --text-primary: #ffffff;
    --text-secondary: #d1d5db;
    --text-muted: #9ca3af;
    --border-color: #374151;
    --glass-bg: rgba(255, 255, 255, 0.1);
    --glass-border: rgba(255, 255, 255, 0.15);
  }

  /* Light mode */
  :root:not(.dark) {
    --bg-primary: #f9fafb;
    --bg-secondary: #ffffff;
    --bg-accent: #dbeafe;
    --text-primary: #111827;
    --text-secondary: #374151;
    --text-muted: #6b7280;
    --border-color: #e5e7eb;
    --glass-bg: rgba(255, 255, 255, 0.8);
    --glass-border: rgba(0, 0, 0, 0.1);
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
    color: var(--text-primary);
  }

  .glass-button {
    background: var(--glass-bg);
    backdrop-filter: blur(10px);
    border: 1px solid var(--glass-border);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    color: var(--text-primary);
  }

  .glass-button:hover {
    background: rgba(255, 255, 255, 0.15);
    transform: translateY(-2px);
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
  }

  :root:not(.dark) .glass-button:hover {
    background: rgba(0, 0, 0, 0.05);
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
    color: var(--text-primary);
  }

  .table-row:hover {
    background: linear-gradient(90deg, rgba(56, 189, 248, 0.05), rgba(147, 51, 234, 0.05));
    transform: translateX(4px);
  }

  .stats-card {
    background: var(--glass-bg);
    backdrop-filter: blur(10px);
    border: 1px solid var(--glass-border);
    transition: all 0.3s ease;
    color: var(--text-primary);
  }

  .stats-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  }

  /* Update input and select styles for theme support */
  input, select {
    transition: all 0.2s ease;
  }

  input:focus, select:focus {
    outline: none;
    border-color: var(--primary-400) !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
  }

  :root:not(.dark) input,
  :root:not(.dark) select {
    background: rgba(255, 255, 255, 0.8) !important;
    color: var(--text-primary) !important;
    border-color: var(--border-color) !important;
  }

  :root:not(.dark) input::placeholder {
    color: var(--text-muted) !important;
  }

  /* Option elements styling for better theme support */
  select option {
    background: var(--card-bg);
    color: var(--text-primary);
    padding: 8px 12px;
  }

  /* Light mode option styling */
  :root:not(.dark) select option {
    background: #ffffff;
    color: #1f2937;
  }

  /* Dark mode option styling for better contrast */
  :global(.dark) select option {
    background: #1f2937;
    color: #f9fafb;
  }

  :root:not(.dark) .table-row:hover {
    background: linear-gradient(90deg, rgba(59, 130, 246, 0.05), rgba(168, 85, 247, 0.05));
  }

  /* ...existing code... */
</style>

<div class="min-h-screen relative overflow-hidden transition-colors duration-300" style="background: linear-gradient(135deg, var(--bg-primary), var(--bg-accent), var(--bg-primary));">
  <!-- Floating Background Elements -->
  <div class="floating-element floating-circle top-20 left-10 animate-float"></div>
  <div class="floating-element floating-square top-40 right-20" style="animation-delay: -2s;"></div>
  <div class="floating-element floating-circle bottom-20 right-10" style="animation-delay: -4s;"></div>
  
  <!-- Gradient Overlay -->
  <div class="absolute inset-0 opacity-50" style="background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(168, 85, 247, 0.1), rgba(236, 72, 153, 0.1));"></div>
  
  <div class="relative z-10 p-6 space-y-8">
    <!-- Toast Notifications -->
    {#if $toasts.length > 0}
      <div class="fixed top-6 right-6 z-50 space-y-3">
        {#each $toasts as toast (toast.id)}
          <div class={cn(
            "animate-slide-down glass-card rounded-2xl p-4 border-l-4 transition-all duration-300",
            toast.type === 'success' && "border-l-green-400 bg-green-900/20",
            toast.type === 'error' && "border-l-red-400 bg-red-900/20", 
            toast.type === 'warning' && "border-l-yellow-400 bg-yellow-900/20"
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
              <span class="text-sm font-medium" style="color: var(--text-primary);">{toast.message}</span>
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
      <p class="mt-4 text-xl max-w-3xl mx-auto leading-relaxed" style="color: var(--text-secondary);">
        Generating word lists with advanced dispersion analysis across text files.
      </p>
      <div class="mt-8 flex justify-center gap-8 text-sm">
        {#each [
          { icon: Brain, label: 'AI Powered', color: 'text-blue-400' },
          { icon: Zap, label: 'Real-time', color: 'text-yellow-400' },
          { icon: Sparkles, label: 'Insights', color: 'text-purple-400' }
        ] as feature}
          <div class="flex items-center gap-2 glass-card px-4 py-2 rounded-full">
            <svelte:component this={feature.icon} class="h-4 w-4 {feature.color}" />
            <span class="font-medium" style="color: var(--text-secondary);">{feature.label}</span>
          </div>
        {/each}
      </div>
    </div>

    <!-- Main Operation Card -->
    <div class="glass-card rounded-3xl p-8 shadow-2xl animate-scale-in">
      <div class="space-y-10">
        <!-- Progress Header -->
        <div class="text-center space-y-4">
          <h2 class="text-3xl font-bold" style="color: var(--text-primary);">Get Started</h2>
          <p style="color: var(--text-muted);">Three simple steps to unlock linguistic insights</p>
          
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
            <div class="flex justify-between text-xs mt-2" style="color: var(--text-muted);">
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
              desc: 'Initialize NLP models', 
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
                  <h3 class="text-xl font-bold" style="color: var(--text-primary);">{step.title}</h3>
                  <p class="text-sm leading-relaxed" style="color: var(--text-muted);">{step.desc}</p>
                  
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
            <h2 class="text-2xl font-bold" style="color: var(--text-primary);">Analysis in Progress</h2>
          </div>
          
          <div class="max-w-2xl mx-auto space-y-4">
            <div class="flex justify-between items-center text-sm">
              <span style="color: var(--text-muted);">Processing files...</span>
              <span class="font-medium" style="color: var(--text-primary);">{$progress.current} / {$progress.total}</span>
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
                <p class="text-sm" style="color: var(--text-muted);">Currently processing:</p>
                <p class="font-medium truncate max-w-md mx-auto" style="color: var(--text-primary);">{$progress.file}</p>
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
              <h2 class="text-3xl font-bold mb-2" style="color: var(--text-primary);">Analysis Results</h2>
              <p style="color: var(--text-muted);">Comprehensive linguistic analysis completed</p>
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
                  <div class="text-2xl font-bold" style="color: var(--text-primary);">{stat.value.toLocaleString()}</div>
                  <div class="text-xs" style="color: var(--text-muted);">{stat.label}</div>
                </div>
              {/each}
            </div>
          </div>
        </div>

        <!-- Filters Section -->
        <div class="glass-card rounded-3xl p-8">
          <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6 mb-8">
            <h3 class="text-xl font-bold flex items-center gap-2" style="color: var(--text-primary);">
              <Filter class="h-5 w-5 text-blue-400" />
              Advanced Filters
            </h3>
            <div class="flex gap-3">
              <Button
                on:click={clearFilters}
                class="glass-button text-red-400 px-4 py-2 rounded-lg hover:bg-red-500/20 transition-all duration-300"
              >
                <X class="h-4 w-4 mr-2" />
                Clear All
              </Button>
              <Button
                on:click={downloadCSV}
                class="glass-button text-green-400 px-4 py-2 rounded-lg hover:bg-green-500/20 transition-all duration-300"
              >
                <Download class="h-4 w-4 mr-2" />
                Export CSV ({$filteredResult.length})
              </Button>
            </div>
          </div>
          
          <!-- Filter Controls - Improved Layout -->
          <div class="space-y-8">
            
            <!-- Word Length Filter -->
            <div class="space-y-4">
              <h4 class="text-lg font-semibold flex items-center gap-2" style="color: var(--text-primary);">
                <span class="w-2 h-2 bg-blue-400 rounded-full"></span>
                Word Length Range
              </h4>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-md">
                <div>
                  <label for="word-length-min" class="block text-sm font-medium mb-2" style="color: var(--text-secondary);">Minimum Length</label>
                  <input
                    id="word-length-min"
                    type="number"
                    min="1"
                    placeholder="e.g., 2"
                    bind:value={$filterConfig.wordLength.min}
                    on:input={() => currentPage.set(1)}
                    class="w-full bg-gray-800/50 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20 transition-all duration-200"
                    style="background: var(--glass-bg); color: var(--text-primary); border-color: var(--border-color);"
                  />
                </div>
                <div>
                  <label for="word-length-max" class="block text-sm font-medium mb-2" style="color: var(--text-secondary);">Maximum Length</label>
                  <input
                    id="word-length-max"
                    type="number"
                    min="1"
                    placeholder="e.g., 10"
                    bind:value={$filterConfig.wordLength.max}
                    on:input={() => currentPage.set(1)}
                    class="w-full bg-gray-800/50 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20 transition-all duration-200"
                    style="background: var(--glass-bg); color: var(--text-primary); border-color: var(--border-color);"
                  />
                </div>
              </div>
            </div>
            
            <!-- POS Filter - Improved with Tag-based UI -->
            <div class="space-y-4">
              <h4 class="text-lg font-semibold flex items-center gap-2" style="color: var(--text-primary);">
                <span class="w-2 h-2 bg-purple-400 rounded-full"></span>
                Part-of-Speech Tags
              </h4>
              
              <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- Include POS -->
                <div class="space-y-3">
                  <div class="block text-sm font-medium" style="color: var(--text-secondary);">
                    Include Only These Tags
                    <span class="text-xs opacity-75">(leave empty to include all)</span>
                  </div>
                  <!-- Search box for POS include -->
                  <div class="relative">
                    <input
                      type="text"
                      bind:value={$posSearchInclude}
                      placeholder="Search POS tags..."
                      class="w-full bg-gray-800/50 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20"
                      style="background: var(--glass-bg); color: var(--text-primary); border-color: var(--border-color);"
                    />
                    {#if $posSearchInclude}
                      <button
                        on:click={() => posSearchInclude.set('')}
                        class="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-200 transition-colors"
                        title="Clear search"
                      >
                        <X class="h-5 w-5" />
                      </button>
                    {/if}
                  </div>
                  <div class="min-h-[120px] max-h-40 overflow-y-auto p-4 rounded-lg border custom-scrollbar" 
                       style="background: var(--glass-bg); border-color: var(--border-color);">
                    <div class="flex flex-wrap gap-2">
                      {#each $filteredPOSInclude as pos}
                        <button
                          class={cn(
                            "px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200 border",
                            $filterConfig.pos.include.includes(pos)
                              ? "bg-green-500/20 text-green-300 border-green-400/50 shadow-sm"
                              : "bg-gray-700/30 text-gray-400 border-gray-600/50 hover:bg-gray-600/30 hover:text-gray-300"
                          )}
                          on:click={() => {
                            const currentInclude = $filterConfig.pos.include;
                            if (currentInclude.includes(pos)) {
                              filterConfig.update(cfg => ({
                                ...cfg,
                                pos: { ...cfg.pos, include: currentInclude.filter(p => p !== pos) }
                              }));
                            } else {
                              filterConfig.update(cfg => ({
                                ...cfg,
                                pos: { ...cfg.pos, include: [...currentInclude, pos] }
                              }));
                            }
                            currentPage.set(1);
                          }}
                        >
                          {pos}
                          {#if $filterConfig.pos.include.includes(pos)}
                            <CheckCircle class="h-3 w-3 ml-1 inline" />
                          {/if}
                        </button>
                      {/each}
                    </div>
                  </div>
                </div>
                
                <!-- Exclude POS -->
                <div class="space-y-3">
                  <div class="block text-sm font-medium" style="color: var(--text-secondary);">
                    Exclude These Tags
                    <span class="text-xs opacity-75">(click to exclude)</span>
                  </div>
                  <!-- Search box for POS exclude -->
                  <div class="relative">
                    <input
                      type="text"
                      bind:value={$posSearchExclude}
                      placeholder="Search POS tags..."
                      class="w-full bg-gray-800/50 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20"
                      style="background: var(--glass-bg); color: var(--text-primary); border-color: var(--border-color);"
                    />
                    {#if $posSearchExclude}
                      <button
                        on:click={() => posSearchExclude.set('')}
                        class="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-200 transition-colors"
                        title="Clear search"
                      >
                        <X class="h-5 w-5" />
                      </button>
                    {/if}
                  </div>
                  <div class="min-h-[120px] max-h-40 overflow-y-auto p-4 rounded-lg border custom-scrollbar" 
                       style="background: var(--glass-bg); border-color: var(--border-color);">
                    <div class="flex flex-wrap gap-2">
                      {#each $filteredPOSExclude as pos}
                        <button
                          class={cn(
                            "px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200 border",
                            $filterConfig.pos.exclude.includes(pos)
                              ? "bg-red-500/20 text-red-300 border-red-400/50 shadow-sm"
                              : "bg-gray-700/30 text-gray-400 border-gray-600/50 hover:bg-gray-600/30 hover:text-gray-300"
                          )}
                          on:click={() => {
                            const currentExclude = $filterConfig.pos.exclude;
                            if (currentExclude.includes(pos)) {
                              filterConfig.update(cfg => ({
                                ...cfg,
                                pos: { ...cfg.pos, exclude: currentExclude.filter(p => p !== pos) }
                              }));
                            } else {
                              filterConfig.update(cfg => ({
                                ...cfg,
                                pos: { ...cfg.pos, exclude: [...currentExclude, pos] }
                              }));
                            }
                            currentPage.set(1);
                          }}
                        >
                          {pos}
                          {#if $filterConfig.pos.exclude.includes(pos)}
                            <X class="h-3 w-3 ml-1 inline" />
                          {/if}
                        </button>
                      {/each}
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Metric Filters -->
            <div class="space-y-4">
              <div class="flex items-center justify-between">
                <h4 class="text-lg font-semibold flex items-center gap-2" style="color: var(--text-primary);">
                  <span class="w-2 h-2 bg-orange-400 rounded-full"></span>
                  Metric Filters
                </h4>
                <Button
                  on:click={addMetricFilter}
                  class="glass-button text-blue-400 px-4 py-2 rounded-lg text-sm hover:bg-blue-500/20 transition-all duration-300"
                >
                  <span class="mr-2">+</span>
                  Add Filter
                </Button>
              </div>
              
              {#if $filterConfig.metrics.length === 0}
                <div class="text-center py-8 rounded-lg border border-dashed" style="border-color: var(--border-color);">
                  <SlidersHorizontal class="h-8 w-8 mx-auto mb-2 opacity-50" style="color: var(--text-muted);" />
                  <p class="text-sm" style="color: var(--text-muted);">No metric filters added yet</p>
                  <p class="text-xs mt-1" style="color: var(--text-muted);">Click "Add Filter" to start filtering by metrics</p>
                </div>
              {:else}
                <div class="space-y-4">
                  {#each $filterConfig.metrics as filter, index}
                    <div class="p-6 rounded-xl border" style="background: var(--glass-bg); border-color: var(--border-color);">
                      <div class="flex items-center justify-between mb-4">
                        <span class="text-sm font-medium" style="color: var(--text-secondary);">Filter #{index + 1}</span>
                        <Button
                          on:click={() => removeMetricFilter(index)}
                          class="glass-button text-red-400 p-2 rounded-lg hover:bg-red-500/20 transition-all duration-300"
                        >
                          <X class="h-4 w-4" />
                        </Button>
                      </div>
                      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                          <label for={`metric-select-${index}`} class="block text-sm font-medium mb-2" style="color: var(--text-secondary);">Metric</label>
                          <select
                            id={`metric-select-${index}`}
                            bind:value={filter.metric}
                            on:change={(e) => updateMetricFilter(index, 'metric', (e.target as HTMLSelectElement).value)}
                            class="w-full bg-gray-800/50 border border-gray-600 rounded-lg px-3 py-2 text-white focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20"
                            style="background: var(--glass-bg); color: var(--text-primary); border-color: var(--border-color);"
                          >
                            <option value="">Select a metric...</option>
                            {#each $metricColumns as col}
                              <option value={col}>{col}</option>
                            {/each}
                          </select>
                        </div>
                        
                        <div>
                          <label for={`condition-select-${index}`} class="block text-sm font-medium mb-2" style="color: var(--text-secondary);">Condition</label>
                          <select
                            id={`condition-select-${index}`}
                            bind:value={filter.operator}
                            on:change={(e) => updateMetricFilter(index, 'operator', (e.target as HTMLSelectElement).value)}
                            class="w-full bg-gray-800/50 border border-gray-600 rounded-lg px-3 py-2 text-white focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20"
                            style="background: var(--glass-bg); color: var(--text-primary); border-color: var(--border-color);"
                          >
                            <option value="gt">Greater than (&gt;)</option>
                            <option value="gte">Greater or equal (≥)</option>
                            <option value="lt">Less than (&lt;)</option>
                            <option value="lte">Less or equal (≤)</option>
                            <option value="eq">Equal to (=)</option>
                          </select>
                        </div>
                        
                        <div>
                          <label for={`value-input-${index}`} class="block text-sm font-medium mb-2" style="color: var(--text-secondary);">Value</label>
                          <input
                            id={`value-input-${index}`}
                            type="number"
                            step="any"
                            placeholder="Enter number..."
                            bind:value={filter.value}
                            on:input={(e) => updateMetricFilter(index, 'value', (e.target as HTMLInputElement).value)}
                            class="w-full bg-gray-800/50 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20"
                            style="background: var(--glass-bg); color: var(--text-primary); border-color: var(--border-color);"
                          />
                        </div>
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          </div>
        </div>

        <!-- Results Table -->
        <div class="glass-card rounded-3xl overflow-hidden">
          <div class="p-6 border-b" style="border-color: var(--border-color);">
            <h3 class="text-xl font-bold" style="color: var(--text-primary);">Word Analysis Data</h3>
            <p class="text-sm mt-1" style="color: var(--text-secondary);">
              Showing {($currentPage - 1) * itemsPerPage + 1} - {Math.min($currentPage * itemsPerPage, $filteredResult.length)} of {$filteredResult.length} results
            </p>
          </div>
          
          <div class="overflow-x-auto custom-scrollbar">
            <table class="w-full">
              <thead style="background: var(--glass-bg);">
                <tr>
                  {#each [
                    { key: 'word', label: 'Word' },
                    { key: 'pos', label: 'POS' },
                    ...$metricColumns.map(col => ({ key: col, label: col.replace(/\./g, ' ').replace(/([A-Z])/g, ' $1').trim() }))
                  ] as column}
                    <th class="text-left p-4 font-semibold" style="color: var(--text-secondary);">
                      <button
                        on:click={() => handleSort(column.key)}
                        class="flex items-center gap-2 hover:text-white transition-colors group w-full text-left"
                        style="color: var(--text-secondary);"
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
                  <tr class="table-row border-b transition-all duration-200" style="border-color: var(--border-color);">
                    <td class="p-4 font-medium" style="color: var(--text-primary);">{item.word}</td>
                    <td class="p-4">
                      <span class="inline-flex px-2 py-1 text-xs font-medium bg-blue-500/20 text-blue-300 rounded-full">
                        {item.pos}
                      </span>
                    </td>
                    {#each $metricColumns as col}
                      <td class="p-4" style="color: var(--text-secondary);">
                        {#if typeof item.metrics[col] === 'number'}
                          <span class="font-mono">
                            {item.metrics[col].toFixed(4)}
                          </span>
                        {:else}
                          <span style="color: var(--text-muted);">
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
            <div class="p-6 border-t" style="border-color: var(--border-color);">
              <div class="flex items-center justify-between">
                <div class="text-sm" style="color: var(--text-muted);">
                  Page {$currentPage} of {totalPages}
                </div>
                
                <div class="flex items-center gap-2">
                  <Button
                    on:click={() => goToPage(Math.max(1, $currentPage - 1))}
                    disabled={$currentPage === 1}
                    class="glass-button px-3 py-2 rounded-lg disabled:opacity-50 transition-all duration-300"
                    style="color: var(--text-primary);"
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
                        "px-3 py-2 rounded-lg font-medium transition-all duration-300",
                        page === $currentPage 
                          ? "bg-blue-500 text-white shadow-lg" 
                          : "glass-button hover:scale-105"
                      )}
                      style={page !== $currentPage ? "color: var(--text-secondary);" : ""}
                    >
                      {page}
                    </Button>
                  {/each}
                  
                  <Button
                    on:click={() => goToPage(Math.min(totalPages, $currentPage + 1))}
                    disabled={$currentPage === totalPages}
                    class="glass-button px-3 py-2 rounded-lg disabled:opacity-50 transition-all duration-300"
                    style="color: var(--text-primary);"
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
          <h3 class="text-xl font-bold" style="color: var(--text-primary);">Advanced Dispersion Analysis</h3>
        </div>
        <p class="leading-relaxed" style="color: var(--text-secondary);">
          Powered by state-of-the-art machine learning models for Chinese word segmentation, 
          part-of-speech tagging, and comprehensive dispersion analysis. 
          Built with Tauri, Svelte, and Rust for optimal performance.
        </p>
        <div class="mt-6 flex justify-center gap-6 text-sm">
          {#each [
            { label: 'Fast Processing', icon: Zap },
            { label: 'Accurate Results', icon: CheckCircle },
            { label: 'Export Ready', icon: Download }
          ] as feature}
            <div class="flex items-center gap-2" style="color: var(--text-muted);">
              <svelte:component this={feature.icon} class="h-4 w-4 text-blue-400" />
              <span>{feature.label}</span>
            </div>
          {/each}
        </div>
      </div>
    </div>
  </div>
</div>