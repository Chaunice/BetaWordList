<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import { writable, derived } from "svelte/store";
  // import { cn } from "$lib/utils.js";
  import * as Button from "$lib/components/ui/button";
  import * as Card from "$lib/components/ui/card";
  // import Input from "$lib/components/ui/input/input.svelte";
  import * as Alert from "$lib/components/ui/alert";
  import * as Progress from "$lib/components/ui/progress";
  import * as Table from "$lib/components/ui/table";
  import { Badge } from "$lib/components/ui/badge";
  import X from 'lucide-svelte/icons/x';
  import CheckCircle from 'lucide-svelte/icons/check-circle';
  import AlertCircle from 'lucide-svelte/icons/alert-circle';
  // import Loader2 from 'lucide-svelte/icons/loader-2';
  import File from 'lucide-svelte/icons/file';
  import Play from 'lucide-svelte/icons/play';
  import Settings from 'lucide-svelte/icons/settings';
  import Sparkles from 'lucide-svelte/icons/sparkles';
  import Brain from 'lucide-svelte/icons/brain';
  import Zap from 'lucide-svelte/icons/zap';
  // import Filter from 'lucide-svelte/icons/filter';
  import Download from 'lucide-svelte/icons/download';
  import FilterPanel from "$lib/components/FilterPanel.svelte";

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

  function closeToast(id: number) {
    toasts.update(current => current.filter(t => t.id !== id));
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
        showToast(`Selected ${selected.length} file(s) for analysis`, 'success');
      } else if (typeof selected === 'string' && selected) {
        filePaths.set([selected]);
        showToast('File selected successfully', 'success');
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
    clearFilters();
    showToast('Starting analysis...', 'success');
    
    await startProgressListener();
    try {
      const analysisResult: Array<[string, string, any]> = await invoke("start_analysis", { filePaths: $filePaths });
      result.set(analysisResult);
      
      showToast(analysisResult.length === 0 ? 'Analysis complete, but no results were extracted.' : `Analysis complete! Found ${analysisResult.length} words.`, analysisResult.length === 0 ? 'warning' : 'success');
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

  // StepCard 组件
  $: steps = [
    {
      key: 'select',
      title: 'Select Files',
      desc: 'Choose your text files for analysis',
      icon: File,
      action: selectFiles,
      disabled: false,
      status: () => $filePaths.length > 0 ? `${$filePaths.length} file(s) selected` : '',
      statusClass: 'text-green-600 dark:text-green-400',
    },
    {
      key: 'model',
      title: 'Load Models',
      desc: 'Initialize NLP models',
      icon: Settings,
      action: loadModel,
      disabled: $analyzing || $modelLoaded || $filePaths.length === 0,
      status: () => $modelStatus ? $modelStatus : ($modelLoaded ? 'Model loaded' : ''),
      statusClass: () => $modelStatus ? 'text-amber-600 dark:text-amber-400 animate-pulse' : ($modelLoaded ? 'text-green-600 dark:text-green-400' : ''),
    },
    {
      key: 'analyze',
      title: 'Start Analysis',
      desc: 'Advanced dispersion analysis',
      icon: Play,
      action: analyze,
      disabled: $analyzing || $filePaths.length === 0 || !$modelLoaded,
      status: () => $analyzing ? 'Analyzing...' : '',
      statusClass: 'text-blue-600 dark:text-blue-400 flex items-center',
    }
  ];
</script>

<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
  /* toast 动画 */
  @keyframes fade-in {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .animate-fade-in {
    animation: fade-in 0.3s cubic-bezier(0.4,0,0.2,1);
  }
</style>

<!-- Header -->
<div class="text-center py-12">
  <h1 class="text-5xl font-black mb-2">Word List Generator</h1>
  <p class="text-lg text-muted-foreground mb-4">Generating word lists with advanced dispersion analysis across text files.</p>
  <div class="flex justify-center gap-4 mb-6">
    <Badge variant="secondary" class="text-blue-600 bg-blue-100 dark:text-blue-400 dark:bg-blue-900/30"><Brain class="h-4 w-4 mr-1" />Perceptron</Badge>
    <Badge variant="secondary" class="text-amber-600 bg-amber-100 dark:text-amber-400 dark:bg-amber-900/30"><Zap class="h-4 w-4 mr-1" />Real-time</Badge>
    <Badge variant="secondary" class="text-purple-600 bg-purple-100 dark:text-purple-400 dark:bg-purple-900/30"><Sparkles class="h-4 w-4 mr-1" />Insights</Badge>
  </div>
</div>

<!-- Main Steps -->
<div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
  {#each steps as step, i (step.key)}
    <Card.Root>
      <Card.Header>{step.title}</Card.Header>
      <Card.Content>
        <p class="mb-2 text-sm text-muted-foreground">{step.desc}</p>
        <!-- 优化主流程按钮样式，适配 dark/light mode，提升对比度 -->
        <button
          class="w-full inline-flex items-center justify-center rounded-md text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 dark:bg-primary dark:text-primary-foreground dark:hover:bg-primary/80 ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary h-9 px-3 mb-2 disabled:opacity-50 disabled:pointer-events-none shadow-sm"
          on:click={step.action}
          disabled={step.disabled}
          type="button"
        >
          <svelte:component this={step.icon} class="h-4 w-4 mr-2" />{step.title}
        </button>
        {#if step.status()}
          <div class={`mt-2 text-xs text-center px-2 py-1 rounded-md bg-muted/30 ${typeof step.statusClass === 'function' ? step.statusClass() : step.statusClass}`}>
            {step.status()}
          </div>
        {/if}
      </Card.Content>
    </Card.Root>
  {/each}
</div>

<!-- Progress Bar -->
<div class="mb-8">
  <Progress.Root value={$progress.total > 0 ? ($progress.current / $progress.total) * 100 : 0} max={100} class="h-3 bg-muted rounded-full overflow-hidden" />
  {#if $analyzing}
    <div class="mt-2 text-center">
      <div class="text-sm font-medium text-foreground">{$progress.file}</div>
      <div class="text-xs text-muted-foreground">Progress: {$progress.current}/{$progress.total}</div>
    </div>
  {/if}
</div>

<!-- Results Section -->
{#if $result.length > 0}
  <Card.Root class="mb-8">
    <Card.Header>Analysis Results</Card.Header>
    <Card.Content>
      <div class="flex flex-wrap gap-4 mb-4">
        <Badge variant="outline" class="text-blue-600 border-blue-200 dark:text-blue-400 dark:border-blue-800">Total Words: {$processedResult.length}</Badge>
        <Badge variant="outline" class="text-purple-600 border-purple-200 dark:text-purple-400 dark:border-purple-800">Unique POS: {$uniquePOS.length}</Badge>
        <Badge variant="outline" class="text-green-600 border-green-200 dark:text-green-400 dark:border-green-800">Filtered: {$filteredResult.length}</Badge>
        <Badge variant="outline" class="text-orange-600 border-orange-200 dark:text-orange-400 dark:border-orange-800">Pages: {totalPages}</Badge>
      </div>
      <div class="flex gap-2 mb-4">
        <!-- @ts-expect-error Svelte slot event type limitation -->
        <button on:click={clearFilters} class="inline-flex items-center rounded-md border border-destructive text-destructive px-3 py-1 hover:bg-destructive/10 dark:hover:bg-destructive/20 transition"><X class="h-4 w-4 mr-1" />Clear Filters</button>
        <!-- @ts-expect-error Svelte slot event type limitation -->
        <button on:click={downloadCSV} class="inline-flex items-center rounded-md border border-green-600 text-green-600 px-3 py-1 hover:bg-green-50 dark:hover:bg-green-900/20 transition"><Download class="h-4 w-4 mr-1" />Export CSV</button>
      </div>
      <FilterPanel
        {filterConfig}
        metricColumns={$metricColumns}
        posSearchInclude={posSearchInclude}
        posSearchExclude={posSearchExclude}
        filteredPOSInclude={$filteredPOSInclude}
        filteredPOSExclude={$filteredPOSExclude}
        {addMetricFilter}
        {removeMetricFilter}
        {updateMetricFilter}
        currentPage={currentPage}
      />
      <div class="overflow-x-auto border rounded-lg">
        <Table.Root class="mt-0">
          <Table.Header>
            <Table.Row class="border-b bg-muted/50">
              <!-- @ts-expect-error Svelte slot event type limitation -->
              <Table.Head class="cursor-pointer hover:bg-muted w-[200px] font-semibold" on:click={() => handleSort('word')}>
                <div class="flex items-center">
                  <span>Word</span>
                  {#if $sortConfig.column === 'word'}
                    <span class="ml-1 text-primary">{$sortConfig.direction === 'asc' ? '↑' : '↓'}</span>
                  {/if}
                </div>
              </Table.Head>
              <!-- @ts-expect-error Svelte slot event type limitation -->
              <Table.Head class="cursor-pointer hover:bg-muted w-[100px] font-semibold" on:click={() => handleSort('pos')}>
                <div class="flex items-center">
                  <span>POS</span>
                  {#if $sortConfig.column === 'pos'}
                    <span class="ml-1 text-primary">{$sortConfig.direction === 'asc' ? '↑' : '↓'}</span>
                  {/if}
                </div>
              </Table.Head>
              {#each $metricColumns as col}
                <!-- @ts-expect-error Svelte slot event type limitation -->
                <Table.Head class="cursor-pointer hover:bg-muted text-right w-[120px] font-semibold" on:click={() => handleSort(col)}>
                  <div class="flex items-center justify-end">
                    <span class="truncate mr-1" title={col}>{col}</span>
                    {#if $sortConfig.column === col}
                      <span class="text-primary">{$sortConfig.direction === 'asc' ? '↑' : '↓'}</span>
                    {/if}
                  </div>
                </Table.Head>
              {/each}
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {#if $finalPaginatedResult.length === 0}
              <Table.Row><Table.Cell colspan={2 + $metricColumns.length} class="text-center text-muted-foreground py-8">No data</Table.Cell></Table.Row>
            {:else}
              {#each $finalPaginatedResult as item}
                <Table.Row class="hover:bg-muted/30 transition-colors border-b">
                  <Table.Cell class="font-medium w-[200px]">
                    <div class="truncate pr-2" title={item.word}>{item.word}</div>
                  </Table.Cell>
                  <Table.Cell class="text-muted-foreground w-[100px]">
                    <div class="truncate pr-2" title={item.pos}>{item.pos}</div>
                  </Table.Cell>
                  {#each $metricColumns as col}
                    <Table.Cell class="text-right font-mono text-sm w-[120px]">
                      {#if typeof item.metrics[col] === 'number'}
                        <div class="truncate tabular-nums pr-2" title={item.metrics[col].toString()}>
                          {item.metrics[col].toFixed(4)}
                        </div>
                      {:else}
                        <div class="truncate text-muted-foreground pr-2" title={item.metrics[col] ?? '-'}>
                          {item.metrics[col] ?? '-'}
                        </div>
                      {/if}
                    </Table.Cell>
                  {/each}
                </Table.Row>
              {/each}
            {/if}
          </Table.Body>
        </Table.Root>
      </div>
      <!-- 简化分页组件 -->
      <div class="mt-6 flex items-center justify-center gap-2">
        <button
          class="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-10 px-4 py-2 gap-1 pl-2.5"
          disabled={$currentPage === 1}
          on:click={() => goToPage($currentPage - 1)}
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          Previous
        </button>
        
        <!-- 显示页码范围，避免显示太多页码 -->
        {#if totalPages <= 10}
          {#each Array(totalPages).fill(0).map((_, i) => i + 1) as pageNum}
            <button
              class="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 h-10 w-10 {pageNum === $currentPage ? 'border border-input bg-background shadow-sm' : 'hover:bg-accent hover:text-accent-foreground'}"
              on:click={() => goToPage(pageNum)}
            >
              {pageNum}
            </button>
          {/each}
        {:else}
          <!-- 显示首页 -->
          {#if $currentPage > 3}
            <button
              class="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 h-10 w-10 hover:bg-accent hover:text-accent-foreground"
              on:click={() => goToPage(1)}
            >
              1
            </button>
            {#if $currentPage > 4}
              <span class="flex h-9 w-9 items-center justify-center">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h.01M12 12h.01M19 12h.01" />
                </svg>
              </span>
            {/if}
          {/if}
          
          <!-- 显示当前页附近的页码 -->
          {#each Array(Math.min(5, totalPages)).fill(0).map((_, i) => Math.max(1, Math.min(totalPages - 4, $currentPage - 2)) + i).filter(p => p <= totalPages) as pageNum}
            <button
              class="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 h-10 w-10 {pageNum === $currentPage ? 'border border-input bg-background shadow-sm' : 'hover:bg-accent hover:text-accent-foreground'}"
              on:click={() => goToPage(pageNum)}
            >
              {pageNum}
            </button>
          {/each}
          
          <!-- 显示末页 -->
          {#if $currentPage < totalPages - 2}
            {#if $currentPage < totalPages - 3}
              <span class="flex h-9 w-9 items-center justify-center">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h.01M12 12h.01M19 12h.01" />
                </svg>
              </span>
            {/if}
            <button
              class="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 h-10 w-10 hover:bg-accent hover:text-accent-foreground"
              on:click={() => goToPage(totalPages)}
            >
              {totalPages}
            </button>
          {/if}
        {/if}
        
        <button
          class="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-10 px-4 py-2 gap-1 pr-2.5"
          disabled={$currentPage === totalPages}
          on:click={() => goToPage($currentPage + 1)}
        >
          Next
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </Card.Content>
  </Card.Root>
{:else if !$analyzing && $result.length === 0}
  <div class="text-center text-muted-foreground my-8">No analysis results yet.</div>
{/if}

<!-- Footer
<Card.Root class="max-w-2xl mx-auto mt-12">
  <Card.Header>Advanced Dispersion Analysis</Card.Header>
  <Card.Content>
    <div class="flex items-center gap-2 mb-2"><Brain class="h-5 w-5 text-blue-400" /><span class="font-bold">Powered by SOTA models</span></div>
    <p class="text-muted-foreground">Chinese word segmentation, POS tagging, and dispersion analysis. Built with Tauri, Svelte, Rust.</p>
    <div class="mt-4 flex gap-4">
      <Badge color="yellow"><Zap class="h-4 w-4 mr-1" />Fast</Badge>
      <Badge color="green"><CheckCircle class="h-4 w-4 mr-1" />Accurate</Badge>
      <Badge color="blue"><Download class="h-4 w-4 mr-1" />Export Ready</Badge>
    </div>
  </Card.Content>
</Card.Root> -->

<!-- Toasts -->
{#if $toasts.length > 0}
  <div class="fixed top-4 left-1/2 transform -translate-x-1/2 z-50 space-y-2 w-96">
    {#each $toasts as toast (toast.id)}
      <Alert.Root variant={toast.type as any} class="relative rounded-lg shadow-lg border bg-background/95 dark:bg-background/90 backdrop-blur-sm transition-all animate-fade-in">
        <Alert.Title class="flex items-center justify-between font-medium pr-8">
          <div class="flex items-center gap-2">
            {#if toast.type === 'success'}<CheckCircle class="h-4 w-4 text-green-500" />{/if}
            {#if toast.type === 'error'}<AlertCircle class="h-4 w-4 text-destructive" />{/if}
            {#if toast.type === 'warning'}<AlertCircle class="h-4 w-4 text-yellow-500" />{/if}
            <span class="text-sm">{toast.message}</span>
          </div>
          <button
            on:click={() => closeToast(toast.id)}
            class="absolute top-2 right-2 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
          >
            <X class="h-4 w-4" />
          </button>
        </Alert.Title>
      </Alert.Root>
    {/each}
  </div>
{/if}