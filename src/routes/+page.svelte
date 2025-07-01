<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import { writable, derived } from "svelte/store";
  import { cn } from "$lib/utils.js";
  import Button from "$lib/components/ui/Button.svelte";
  import Card from "$lib/components/ui/Card.svelte";
  import { FileText, Play, Settings, CheckCircle, AlertCircle, Loader2, ChevronUp, ChevronDown, ChevronsUpDown, Download, Filter, X } from 'lucide-svelte';

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
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes slideIn {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
  }
  .animate-fade-in { animation: fadeIn 0.5s ease-out; }
  .animate-slide-in { animation: slideIn 0.3s ease-out; }
  .hover-lift:hover { transform: translateY(-2px); box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1); }
  .active-scale:active { transform: scale(0.95); }

  /* 自定义动画 */
  @keyframes bounce-in {
    0% { transform: scale(0.3); opacity: 0; }
    50% { transform: scale(1.05); }
    70% { transform: scale(0.9); }
    100% { transform: scale(1); opacity: 1; }
  }

  @keyframes slide-up {
    from { transform: translateY(20px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
  }

  @keyframes fade-in {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .animate-bounce-in {
    animation: bounce-in 0.6s ease-out;
  }

  .animate-slide-up {
    animation: slide-up 0.5s ease-out;
  }

  .animate-fade-in {
    animation: fade-in 0.4s ease-out forwards;
    opacity: 0;
  }

  .pulse {
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }

  /* 自定义滚动条 */
  .custom-scrollbar {
    scrollbar-width: thin;
    scrollbar-color: rgb(34 197 94) rgb(243 244 246);
  }

  .custom-scrollbar::-webkit-scrollbar {
    width: 6px;
  }

  .custom-scrollbar::-webkit-scrollbar-track {
    background: rgb(243 244 246);
    border-radius: 3px;
  }

  .custom-scrollbar::-webkit-scrollbar-thumb {
    background: rgb(34 197 94);
    border-radius: 3px;
  }

  .custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background: rgb(22 163 74);
  }
</style>

<div class="min-h-screen bg-gradient-to-br from-gray-50 to-blue-100 dark:from-gray-900 dark:to-blue-950 p-6 space-y-8">
  <!-- Toast Notifications -->
  {#if $toasts.length > 0}
    <div class="fixed top-6 right-6 z-50 space-y-3">
      {#each $toasts as toast (toast.id)}
        <div class={cn(
          "animate-slide-in rounded-xl p-4 shadow-lg border transition-all duration-300",
          toast.type === 'success' && "bg-green-100 border-green-300 text-green-800",
          toast.type === 'error' && "bg-red-100 border-red-300 text-red-800",
          toast.type === 'warning' && "bg-yellow-100 border-yellow-300 text-yellow-800"
        )}>
          <div class="flex items-center gap-2">
            {#if toast.type === 'success'}
              <CheckCircle class="h-5 w-5" />
            {:else if toast.type === 'error'}
              <AlertCircle class="h-5 w-5" />
            {:else}
              <AlertCircle class="h-5 w-5" />
            {/if}
            <span class="text-sm font-medium">{toast.message}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Header -->
  <div class="text-center py-10 animate-fade-in">
    <h1 class="text-5xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
      Word List Generator
    </h1>
    <p class="mt-2 text-lg text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
      Analyze word distribution in text files with advanced dispersion metrics.
    </p>
    <div class="mt-4 flex justify-center gap-6 text-sm text-gray-500 dark:text-gray-400">
      <span class="flex items-center gap-2"><span class="w-2 h-2 bg-green-500 rounded-full"></span> ML Powered</span>
      <span class="flex items-center gap-2"><span class="w-2 h-2 bg-blue-500 rounded-full"></span> Real-time</span>
      <span class="flex items-center gap-2"><span class="w-2 h-2 bg-purple-500 rounded-full"></span> Exportable</span>
    </div>
  </div>

  <!-- Operation Card -->
  <Card class="p-8 bg-white/80 dark:bg-gray-800/80 backdrop-blur-md border-2 border-gray-200 dark:border-gray-700 rounded-xl shadow-xl hover-lift transition-all duration-300">
    <div class="space-y-8">
      <div class="text-center">
        <h2 class="text-2xl font-semibold text-gray-800 dark:text-gray-100">Get Started</h2>
        <p class="text-gray-600 dark:text-gray-400">Three simple steps to analyze your files</p>
      </div>
      
      <!-- Progress Bar -->
      <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 mb-8">
        <div 
          class="bg-gradient-to-r from-blue-500 to-purple-600 h-2 rounded-full transition-all duration-700 ease-out"
          style="width: {getProgressWidth()}%"
        ></div>
      </div>
      
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        {#each [
          { 
            step: 1, 
            title: 'Select Files', 
            desc: 'Choose text files', 
            icon: FileText, 
            action: selectFiles, 
            disabled: $analyzing, 
            isCompleted: $filePaths.length > 0,
            isActive: !$filePaths.length && !$analyzing,
            isProcessing: false
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
            isProcessing: $modelStatus && !$modelLoaded
          },
          { 
            step: 3, 
            title: 'Start Analysis', 
            desc: 'Process and extract insights', 
            icon: Play, 
            action: analyze, 
            disabled: $analyzing || $filePaths.length === 0 || !$modelLoaded, 
            isCompleted: $result.length > 0,
            isActive: $modelLoaded && $result.length === 0 && !$analyzing,
            isProcessing: $analyzing
          }
        ] as step}
          <div class={cn(
            "relative p-6 rounded-xl border-2 transition-all duration-500 ease-out transform",
            "hover:scale-105 hover:shadow-lg",
            step.isCompleted 
              ? "border-green-300 bg-gradient-to-br from-green-50 to-green-100 dark:border-green-600 dark:from-green-900/20 dark:to-green-800/30 shadow-green-100 dark:shadow-green-900/20" 
              : step.isActive 
                ? "border-blue-300 bg-gradient-to-br from-blue-50 to-blue-100 dark:border-blue-600 dark:from-blue-900/20 dark:to-blue-800/30 shadow-blue-100 dark:shadow-blue-900/20 ring-2 ring-blue-200 dark:ring-blue-700" 
                : step.isProcessing
                  ? "border-amber-300 bg-gradient-to-br from-amber-50 to-amber-100 dark:border-amber-600 dark:from-amber-900/20 dark:to-amber-800/30 shadow-amber-100 dark:shadow-amber-900/20"
                  : "border-gray-200 bg-gradient-to-br from-gray-50 to-gray-100 dark:border-gray-600 dark:from-gray-700/30 dark:to-gray-600/30"
          )}>
            
            <!-- Step Content -->
            <div class="flex flex-col items-center text-center space-y-4">
              
              <!-- Icon/Progress Circle -->
              <div class="relative">
                <div class={cn(
                  "w-14 h-14 rounded-full flex items-center justify-center text-lg font-bold transition-all duration-500 ease-out",
                  step.isCompleted 
                    ? "bg-gradient-to-br from-green-500 to-green-600 text-white shadow-lg transform scale-110" 
                    : step.isProcessing
                      ? "bg-gradient-to-br from-amber-500 to-orange-500 text-white shadow-lg"
                      : step.isActive 
                        ? "bg-gradient-to-br from-blue-500 to-purple-600 text-white shadow-lg pulse" 
                        : "bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300"
                )}>
                  {#if step.isCompleted}
                    <CheckCircle class="h-7 w-7 animate-bounce-in" />
                  {:else if step.isProcessing}
                    <Loader2 class="h-7 w-7 animate-spin" />
                  {:else}
                    <svelte:component this={step.icon} class="h-7 w-7" />
                  {/if}
                </div>
                
                <!-- Processing Ring -->
                {#if step.isProcessing}
                  <div class="absolute inset-0 rounded-full border-4 border-t-transparent border-amber-300 animate-spin"></div>
                {/if}
                
                <!-- Active Pulse Ring -->
                {#if step.isActive && !step.isProcessing}
                  <div class="absolute inset-0 rounded-full border-2 border-blue-400 animate-ping opacity-75"></div>
                {/if}
              </div>
              
              <!-- Title and Description -->
              <div class="space-y-2">
                <h3 class={cn(
                  "font-semibold text-lg transition-colors duration-300",
                  step.isCompleted ? "text-green-800 dark:text-green-200" 
                  : step.isActive ? "text-blue-800 dark:text-blue-200"
                  : step.isProcessing ? "text-amber-800 dark:text-amber-200"
                  : "text-gray-800 dark:text-gray-100"
                )}>{step.title}</h3>
                <p class={cn(
                  "text-sm transition-colors duration-300",
                  step.isCompleted ? "text-green-600 dark:text-green-400" 
                  : step.isActive ? "text-blue-600 dark:text-blue-400"
                  : step.isProcessing ? "text-amber-600 dark:text-amber-400"
                  : "text-gray-600 dark:text-gray-400"
                )}>{step.desc}</p>
              </div>
              
              <!-- Action Button -->
              <Button 
                on:click={step.action} 
                disabled={step.disabled}
                class={cn(
                  "w-full transition-all duration-300 transform hover:scale-105 active:scale-95",
                  step.isCompleted && "bg-green-600 hover:bg-green-700 shadow-lg",
                  step.isActive && "bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 shadow-lg",
                  step.isProcessing && "bg-amber-500 hover:bg-amber-600"
                )}
                variant={step.isCompleted || step.isActive ? "default" : "outline"}
              >
                <div class="flex items-center justify-center space-x-2">
                  {#if step.isProcessing}
                    <Loader2 class="h-4 w-4 animate-spin" />
                  {:else}
                    <svelte:component this={step.icon} class="h-4 w-4" />
                  {/if}
                  <span>
                    {#if step.step === 1}
                      {step.isCompleted ? `${$filePaths.length} File${$filePaths.length > 1 ? 's' : ''} Selected` : 'Select Files'}
                    {:else if step.step === 2}
                      {#if step.isProcessing}
                        {$modelStatus || 'Loading...'}
                      {:else}
                        {step.isCompleted ? 'Models Ready' : 'Load Models'}
                      {/if}
                    {:else}
                      {#if step.isProcessing}
                        Analyzing...
                      {:else}
                        {step.isCompleted ? 'Analysis Complete' : 'Start Analysis'}
                      {/if}
                    {/if}
                  </span>
                </div>
              </Button>
            </div>
            
            <!-- Completion Badge -->
            {#if step.isCompleted}
              <div class="absolute -top-3 -right-3 w-8 h-8 bg-gradient-to-br from-green-500 to-green-600 rounded-full flex items-center justify-center shadow-lg animate-bounce-in">
                <CheckCircle class="h-5 w-5 text-white" />
              </div>
            {/if}
            
            <!-- Connection Line to Next Step -->
            {#if step.step < 3}
              <div class={cn(
                "hidden md:block absolute top-1/2 -right-3 w-6 h-0.5 transition-all duration-500",
                step.isCompleted ? "bg-green-400" : step.isActive ? "bg-blue-400" : "bg-gray-300"
              )}></div>
            {/if}
          </div>
        {/each}
      </div>
      
      <!-- File List -->
      {#if $filePaths.length > 0}
        <div class="mt-8 p-6 rounded-xl border border-green-200 bg-gradient-to-br from-green-50/50 to-green-100/30 dark:border-green-700 dark:bg-gradient-to-br dark:from-green-900/20 dark:to-green-800/10 animate-slide-up shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <h4 class="font-semibold text-green-800 dark:text-green-200 flex items-center">
              <FileText class="h-5 w-5 mr-2" /> 
              Selected Files ({$filePaths.length})
            </h4>
            <div class="flex items-center space-x-2">
              <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span class="text-xs font-medium text-green-700 bg-green-200 dark:bg-green-800 dark:text-green-200 px-3 py-1 rounded-full">
                Ready
              </span>
            </div>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 max-h-32 overflow-y-auto custom-scrollbar">
            {#each $filePaths as file, index}
              <div class="flex items-center gap-3 p-3 bg-white/80 dark:bg-gray-800/60 rounded-lg border border-green-100 dark:border-green-700 hover:shadow-md transition-all duration-200 animate-fade-in"
                  style="animation-delay: {index * 50}ms">
                <div class="w-3 h-3 bg-gradient-to-br from-green-400 to-green-600 rounded-full flex-shrink-0 animate-pulse"></div>
                <span class="text-sm text-gray-700 dark:text-gray-300 truncate font-medium" title={file}>
                  {file.split(/[\\/]/).pop()}
                </span>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  </Card>

  <!-- Progress Display -->
  {#if $analyzing}
    <Card className="p-8 bg-gradient-to-br from-blue-100 to-indigo-100 dark:from-blue-900/30 dark:to-indigo-900/30 border-2 border-blue-200 dark:border-blue-700 rounded-xl shadow-xl animate-fade-in">
      <div class="space-y-6 text-center">
        <div class="inline-flex items-center justify-center w-16 h-16 bg-blue-200 dark:bg-blue-800 rounded-full mb-4">
          <Loader2 class="h-8 w-8 text-blue-600 dark:text-blue-300 animate-spin" />
        </div>
        <h2 class="text-2xl font-semibold text-blue-800 dark:text-blue-200">Processing...</h2>
        <div class="max-w-md mx-auto space-y-4">
          <div class="flex justify-between text-sm text-blue-700 dark:text-blue-300">
            <span>{$progress.current}/{$progress.total}</span>
            <span>{Math.round(($progress.current / ($progress.total || 1)) * 100)}%</span>
          </div>
          <div class="w-full bg-blue-200 dark:bg-blue-800 rounded-full h-3 overflow-hidden">
            <div class="bg-gradient-to-r from-blue-500 to-indigo-500 h-3 rounded-full transition-all duration-300" style="width: {($progress.current / ($progress.total || 1)) * 100}%"></div>
          </div>
          {#if $progress.file}
            <div class="p-3 bg-white/50 dark:bg-gray-800/50 rounded-lg">
              <p class="text-sm text-gray-600 dark:text-gray-400">Processing:</p>
              <p class="text-sm font-medium text-blue-700 dark:text-blue-300 truncate" title={$progress.file}>{$progress.file.split(/[\\/]/).pop()}</p>
            </div>
          {/if}
        </div>
      </div>
    </Card>
  {/if}

  <!-- Results Display -->
  {#if $result.length > 0}
    <Card className="p-6 bg-white/80 dark:bg-gray-800/80 backdrop-blur-md border-2 border-gray-200 dark:border-gray-700 rounded-xl shadow-xl animate-fade-in">
      <div class="space-y-6">
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg flex items-center justify-center">
              <CheckCircle class="h-6 w-6 text-white" />
            </div>
            <div>
              <h2 class="text-2xl font-semibold text-gray-800 dark:text-gray-100">Analysis Complete</h2>
              <p class="text-sm text-gray-600 dark:text-gray-400">
                Total: {$result.length} | Filtered: {$filteredResult.length} | Page: {$finalPaginatedResult.length}
              </p>
            </div>
          </div>
            <Button
            on:click={downloadCSV}
            variant="outline"
            disabled={$filteredResult.length === 0}
            class="border-2 rounded-lg px-4 py-2 font-semibold text-blue-700 dark:text-blue-200 bg-gradient-to-r from-blue-100 to-indigo-100 dark:from-blue-900/30 dark:to-indigo-900/30 hover:bg-blue-200 dark:hover:bg-blue-800 transition-all duration-200 shadow-md hover-lift active-scale flex items-center gap-2"
            >
            <Download class="h-5 w-5 mr-2" />
            Export CSV
            </Button>
        </div>

        <!-- Filters -->
        <Card className="p-4 bg-gray-50/50 dark:bg-gray-700/50 border-2 rounded-xl">
          <div class="space-y-4">
            <div class="flex items-center gap-2">
              <Filter class="h-4 w-4 text-blue-600 dark:text-blue-400" />
              <h3 class="font-medium text-gray-800 dark:text-gray-100">Filters</h3>
              {#if $filterConfig.wordLength.min || $filterConfig.wordLength.max || $filterConfig.pos.include.length > 0 || $filterConfig.pos.exclude.length > 0 || $filterConfig.metrics.some(m => m.metric && m.value)}
                <Button size="sm" variant="ghost" on:click={clearFilters} class="hover:bg-gray-200 dark:hover:bg-gray-600">
                  <X class="h-3 w-3 mr-1" /> Clear
                </Button>
              {/if}
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="space-y-2">
                <label for="word-length-min" class="text-sm font-medium text-gray-700 dark:text-gray-300">Word Length</label>
                <div class="flex gap-2">
                  <input id="word-length-min" class="h-9 w-20 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2 text-sm focus:ring-2 focus:ring-blue-500" type="number" min="1" placeholder="Min" bind:value={$filterConfig.wordLength.min} on:input={() => currentPage.set(1)} />
                  <span class="self-center text-gray-600 dark:text-gray-400">~</span>
                  <input id="word-length-max" class="h-9 w-20 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2 text-sm focus:ring-2 focus:ring-blue-500" type="number" min="1" placeholder="Max" bind:value={$filterConfig.wordLength.max} on:input={() => currentPage.set(1)} />
                </div>
              </div>
              <div class="space-y-2">
                <label for="pos-list" class="text-sm font-medium text-gray-700 dark:text-gray-300">Part of Speech</label>
                <div id="pos-list" class="max-h-32 overflow-y-auto border border-gray-300 dark:border-gray-600 rounded p-2 bg-white dark:bg-gray-800">
                  {#each $uniquePOS as pos}
                    <div class="flex items-center gap-2 py-1">
                      <input type="checkbox" id={"pos-inc-" + pos} checked={$filterConfig.pos.include.includes(pos)} on:change={e => {
                        filterConfig.update(cfg => {
                          if (e.target.checked) cfg.pos.include = [...cfg.pos.include, pos];
                          else cfg.pos.include = cfg.pos.include.filter(p => p !== pos);
                          return cfg;
                        });
                        currentPage.set(1);
                      }} />
                      <label for={"pos-inc-" + pos} class="text-xs text-gray-700 dark:text-gray-300">{pos}</label>
                      <button class="text-xs px-1 rounded bg-red-100 text-red-600 hover:bg-red-200" on:click={() => {
                        filterConfig.update(cfg => { if (!cfg.pos.exclude.includes(pos)) cfg.pos.exclude = [...cfg.pos.exclude, pos]; return cfg; });
                        currentPage.set(1);
                      }}>Exclude</button>
                      {#if $filterConfig.pos.exclude.includes(pos)}
                        <span class="text-xs text-red-500">Excluded</span>
                        <button class="text-xs px-1 rounded hover:bg-gray-200" on:click={() => {
                          filterConfig.update(cfg => { cfg.pos.exclude = cfg.pos.exclude.filter(p => p !== pos); return cfg; });
                          currentPage.set(1);
                        }}>Cancel</button>
                      {/if}
                    </div>
                  {/each}
                </div>
              </div>
            </div>
            <div class="space-y-3">
              <div class="flex items-center justify-between">
                <label for="add-metric-filter-btn" class="text-sm font-medium text-gray-700 dark:text-gray-300">Metric Filters</label>
                <Button id="add-metric-filter-btn" size="sm" variant="outline" on:click={addMetricFilter}>+ Add</Button>
              </div>
              {#each $filterConfig.metrics as metricFilter, index}
                <div class="flex items-center gap-2 p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800">
                  <select class="h-9 w-32 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm focus:ring-2 focus:ring-blue-500" bind:value={metricFilter.metric} on:change={(e) => updateMetricFilter(index, 'metric', e.target.value)}>
                    <option value="">Select Metric</option>
                    {#each $metricColumns as metric}
                      <option value={metric}>{metric}</option>
                    {/each}
                  </select>
                  <select class="h-9 w-16 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm focus:ring-2 focus:ring-blue-500" bind:value={metricFilter.operator} on:change={(e) => updateMetricFilter(index, 'operator', e.target.value)} disabled={!metricFilter.metric}>
                    <option value="gt">&gt;</option>
                    <option value="gte">&gt;=</option>
                    <option value="lt">&lt;</option>
                    <option value="lte">&lt;=</option>
                    <option value="eq">=</option>
                  </select>
                  <input class="h-9 w-24 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2 text-sm focus:ring-2 focus:ring-blue-500" type="number" step="0.0001" placeholder="Value" bind:value={metricFilter.value} on:input={(e) => updateMetricFilter(index, 'value', e.target.value)} disabled={!metricFilter.metric} />
                  <Button size="sm" variant="ghost" on:click={() => removeMetricFilter(index)} class="text-red-500 hover:text-red-700"><X class="h-4 w-4" /></Button>
                </div>
              {/each}
            </div>
          </div>
        </Card>

        <!-- Results Table -->
        <div class="border-2 border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-gray-100 dark:bg-gray-700">
                <tr class="border-b border-gray-200 dark:border-gray-600">
                  <th class="px-4 py-3 text-left font-medium sticky left-0 bg-gray-100 dark:bg-gray-700 z-10">
                    <button class="flex items-center gap-1 hover:bg-gray-200 dark:hover:bg-gray-600 p-1 rounded w-full text-left" on:click={() => handleSort('word')}>
                      <span>Word</span>
                      <span class="text-xs">{#if $sortConfig.column === 'word'}{#if $sortConfig.direction === 'asc'}↑{:else if $sortConfig.direction === 'desc'}↓{:else}↕{/if}{:else}↕{/if}</span>
                    </button>
                  </th>
                  <th class="px-4 py-3 text-left font-medium sticky left-16 bg-gray-100 dark:bg-gray-700 z-10">
                    <button class="flex items-center gap-1 hover:bg-gray-200 dark:hover:bg-gray-600 p-1 rounded w-full text-left" on:click={() => handleSort('pos')}>
                      <span>POS</span>
                      <span class="text-xs">{#if $sortConfig.column === 'pos'}{#if $sortConfig.direction === 'asc'}↑{:else if $sortConfig.direction === 'desc'}↓{:else}↕{/if}{:else}↕{/if}</span>
                    </button>
                  </th>
                  {#each $metricColumns as column}
                    <th class="px-4 py-3 text-left font-medium">
                      <button class="flex items-center gap-1 hover:bg-gray-200 dark:hover:bg-gray-600 p-1 rounded w-full text-left" on:click={() => handleSort(column)} title={column}>
                        <span class="truncate max-w-[120px]">{column}</span>
                        <span class="text-xs">{#if $sortConfig.column === column}{#if $sortConfig.direction === 'asc'}↑{:else if $sortConfig.direction === 'desc'}↓{:else}↕{/if}{:else}↕{/if}</span>
                      </button>
                    </th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each $finalPaginatedResult as item}
                  <tr class="border-b border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
                    <td class="px-4 py-3 font-medium sticky left-0 bg-white dark:bg-gray-800 z-10">{item.word}</td>
                    <td class="px-4 py-3 text-gray-600 dark:text-gray-400 sticky left-16 bg-white dark:bg-gray-800 z-10">{item.pos}</td>
                    {#each $metricColumns as column}
                      <td class="px-4 py-3" title="{column}: {item.metrics[column] ?? '-'}">
                        {#if item.metrics[column] !== undefined}
                          {#if typeof item.metrics[column] === 'number'}
                            <span class="font-mono text-xs">{item.metrics[column].toFixed(4)}</span>
                          {:else}
                            {item.metrics[column]}
                          {/if}
                        {:else}
                          <span class="text-gray-400 dark:text-gray-500">-</span>
                        {/if}
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>

        <!-- Pagination -->
        {#if totalPages > 1}
          <div class="flex items-center justify-center gap-4 mt-4">
            <Button variant="outline" size="sm" on:click={() => goToPage($currentPage - 1)} disabled={$currentPage === 1} class="hover-lift active-scale">Previous</Button>
            <span class="text-sm text-gray-600 dark:text-gray-400">Page {$currentPage} of {totalPages}</span>
            <Button variant="outline" size="sm" on:click={() => goToPage($currentPage + 1)} disabled={$currentPage === totalPages} class="hover-lift active-scale">Next</Button>
          </div>
        {/if}
      </div>
    </Card>
  {/if}
</div>