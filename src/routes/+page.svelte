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

  // Toast notification store (简化版)
  const toasts = writable<Array<{id: number, message: string, type: string}>>([]);
  let toastId = 0;

  function showToast(message: string, type: 'success' | 'error' | 'warning' = 'success') {
    const id = toastId++;
    toasts.update(current => [...current, { id, message, type }]);
    setTimeout(() => {
      toasts.update(current => current.filter(t => t.id !== id));
    }, 5000);
  }

  // 固定的模型文件名
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
      // @ts-ignore
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
      await invoke("load_models", {
        cwsPath: cwsModel,
        posPath: posModel,
      });
      modelLoaded.set(true);
      modelStatus.set("");
      showToast('Model loaded!', 'success');
    } catch (e) {
      modelLoaded.set(false);
      modelStatus.set("");
      showToast(`Fail to load models: ${e}`, 'error');
    }
  }

  // 处理分析结果，展开JSON指标
  const processedResult = derived([result], ([$result]) => {
    return $result.map(([word, pos, metrics]) => {
      // 展开metrics对象为扁平结构
      const flatMetrics: Record<string, any> = {};
      
      // 递归展开嵌套对象
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

      if (metrics && typeof metrics === 'object') {
        flattenObject(metrics);
      }

      return {
        word,
        pos,
        metrics: flatMetrics
      };
    });
  });

  // 分页处理后的结果
  const paginatedProcessedResult = derived(
    [processedResult, currentPage],
    ([$processedResult, $currentPage]) => {
      const start = ($currentPage - 1) * itemsPerPage;
      const end = start + itemsPerPage;
      return $processedResult.slice(start, end);
    }
  );

  // 获取所有可用的指标列名
  const metricColumns = derived([processedResult], ([$processedResult]) => {
    const columns = new Set<string>();
    $processedResult.forEach(item => {
      Object.keys(item.metrics).forEach(key => columns.add(key));
    });
    return Array.from(columns).sort();
  });

  // 排序状态
  const sortConfig = writable({ column: '', direction: 'none' });

  // 排序后的结果
  const sortedResult = derived([processedResult, sortConfig], ([$processedResult, $sortConfig]) => {
    if ($sortConfig.column === '' || $sortConfig.direction === 'none') {
      return $processedResult;
    }

    const sorted = [...$processedResult].sort((a, b) => {
      let aVal, bVal;
      
      if ($sortConfig.column === 'word') {
        aVal = a.word;
        bVal = b.word;
      } else if ($sortConfig.column === 'pos') {
        aVal = a.pos;
        bVal = b.pos;
      } else {
        aVal = a.metrics[$sortConfig.column];
        bVal = b.metrics[$sortConfig.column];
        
        // 处理数值排序
        if (typeof aVal === 'number' && typeof bVal === 'number') {
          return $sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal;
        }
      }
      
      // 字符串排序
      if (aVal == null) aVal = '';
      if (bVal == null) bVal = '';
      
      const comparison = String(aVal).localeCompare(String(bVal));
      return $sortConfig.direction === 'asc' ? comparison : -comparison;
    });

    return sorted;
  });

  // 重新定义分页结果使用排序后的数据
  const paginatedSortedResult = derived(
    [sortedResult, currentPage],
    ([$sortedResult, $currentPage]) => {
      const start = ($currentPage - 1) * itemsPerPage;
      const end = start + itemsPerPage;
      return $sortedResult.slice(start, end);
    }
  );

  // 筛选状态
  // 筛选配置：词长范围、词性多选（包含/排除）、多个指标筛选
  const filterConfig = writable({
    wordLength: { min: '', max: '' }, // 支持范围
    pos: { include: [], exclude: [] }, // 支持包含/排除
    metrics: [] // 支持多个指标筛选: [{metric: '', operator: 'gt', value: ''}]
  });

  // 筛选后的结果
  const filteredResult = derived([sortedResult, filterConfig], ([$sortedResult, $filterConfig]) => {
    return $sortedResult.filter(item => {
      // 词汇长度范围筛选
      const minLen = parseInt($filterConfig.wordLength.min) || 0;
      const maxLen = parseInt($filterConfig.wordLength.max) || 99;
      if ($filterConfig.wordLength.min !== '' || $filterConfig.wordLength.max !== '') {
        if (item.word.length < minLen || item.word.length > maxLen) return false;
      }

      // 词性多选筛选（包含/排除）
      if (
        ($filterConfig.pos.include.length > 0 && !$filterConfig.pos.include.includes(item.pos)) ||
        ($filterConfig.pos.exclude.length > 0 && $filterConfig.pos.exclude.includes(item.pos))
      ) {
        return false;
      }

      // 多个指标筛选
      for (const metricFilter of $filterConfig.metrics) {
        if (metricFilter.metric && metricFilter.value && metricFilter.value !== '') {
          const metricValue = item.metrics[metricFilter.metric];
          const targetValue = parseFloat(metricFilter.value);

          if (metricValue === undefined || metricValue === null) return false;
          if (typeof metricValue !== 'number') return false;

          switch (metricFilter.operator) {
            case 'gt': if (!(metricValue > targetValue)) return false; break;
            case 'lt': if (!(metricValue < targetValue)) return false; break;
            case 'gte': if (!(metricValue >= targetValue)) return false; break;
            case 'lte': if (!(metricValue <= targetValue)) return false; break;
            case 'eq': if (!(Math.abs(metricValue - targetValue) < 0.0001)) return false; break;
            default: break;
          }
        }
      }

      return true;
    });
  });

  // 更新分页结果使用筛选后的数据
  const finalPaginatedResult = derived(
    [filteredResult, currentPage],
    ([$filteredResult, $currentPage]) => {
      const start = ($currentPage - 1) * itemsPerPage;
      const end = start + itemsPerPage;
      return $filteredResult.slice(start, end);
    }
  );

  // 获取唯一的词性列表
  const uniquePOS = derived([processedResult], ([$processedResult]) => {
    const posSet = new Set<string>();
    $processedResult.forEach(item => posSet.add(item.pos));
    return Array.from(posSet).sort();
  });

  // 排序函数
  function handleSort(column: string) {
    sortConfig.update(current => {
      if (current.column === column) {
        // 循环：无排序 -> 升序 -> 降序 -> 无排序
        const directions = ['none', 'asc', 'desc', 'none'];
        const currentIndex = directions.indexOf(current.direction);
        const nextDirection = directions[(currentIndex + 1) % directions.length];
        return { column: nextDirection === 'none' ? '' : column, direction: nextDirection };
      } else {
        return { column, direction: 'asc' };
      }
    });
    
    // 排序后重置到第一页
    currentPage.set(1);
  }

  // 清除筛选
  function clearFilters() {
    filterConfig.set({
      wordLength: { min: '', max: '' },
      pos: { include: [], exclude: [] },
      metrics: []
    });
    currentPage.set(1);
  }

  // 添加指标筛选条件
  function addMetricFilter() {
    filterConfig.update(cfg => {
      cfg.metrics = [...cfg.metrics, { metric: '', operator: 'gt', value: '' }];
      return cfg;
    });
  }

  // 删除指标筛选条件
  function removeMetricFilter(index) {
    filterConfig.update(cfg => {
      cfg.metrics = cfg.metrics.filter((_, i) => i !== index);
      return cfg;
    });
    currentPage.set(1);
  }

  // 更新指标筛选条件
  function updateMetricFilter(index, field, value) {
    filterConfig.update(cfg => {
      cfg.metrics[index][field] = value;
      return cfg;
    });
    currentPage.set(1);
  }

  // 下载CSV功能
  async function downloadCSV() {
    try {
      // 生成CSV内容
      const headers = ['Word', 'POS', ...$metricColumns];
      const csvRows = [headers.join(',')];
      
      // 使用筛选后的完整数据，不仅仅是当前页
      $filteredResult.forEach(item => {
        const row = [
          `"${item.word}"`,
          `"${item.pos}"`,
          ...$metricColumns.map(col => {
            const value = item.metrics[col];
            return value !== undefined && value !== null ? value : '';
          })
        ];
        csvRows.push(row.join(','));
      });
      
      const csvContent = csvRows.join('\n');
      
      // 生成文件名
      const now = new Date();
      const timestamp = now.toISOString().replace(/[:\.]/g, '-').slice(0, 19);
      const filename = `wordlist_results_${timestamp}.csv`;
      
      // 使用Tauri的save API
      const { save } = await import("@tauri-apps/plugin-dialog");
      const filePath = await save({
        defaultPath: filename,
        filters: [{ name: 'CSV Files', extensions: ['csv'] }]
      });
      
      if (filePath) {
        // 写入文件
        const { writeTextFile } = await import("@tauri-apps/plugin-fs");
        await writeTextFile(filePath, csvContent);
        showToast(`Results saved to: ${filePath}`, 'success');
      }
    } catch (error) {
      showToast(`Fail to save: ${error}`, 'error');
    }
  }

  async function analyze() {
    if (!$modelLoaded) {
      showToast('Please load the NLP model first', 'warning');
      return;
    }
    if ($filePaths.length === 0) {
      showToast('Please select files to analyze first', 'warning');
      return;
    }
    analyzing.set(true);
    result.set([]);
    currentPage.set(1);
    await startProgressListener();
    try {
      const analysisResult: Array<[string, string, any]> = await invoke("start_analysis", {
        filePaths: $filePaths
      });
      result.set(analysisResult);
      if (analysisResult.length === 0) {
        showToast('Analysis complete, but no results were extracted.', 'warning');
      } else {
        showToast('Analysis complete!', 'success');
      }
    } catch (e) {
      showToast(`Analysis failed: ${e}`, 'error');
    }
    analyzing.set(false);
    if (unlisten) {
      await unlisten();
      unlisten = null;
    }
  }

  // 分页函数
  function goToPage(page: number) {
    currentPage.set(page);
  }

  $: totalPages = Math.ceil($filteredResult.length / itemsPerPage);
</script>

<!-- Toast 通知组件 -->
{#if $toasts.length > 0}
  <div class="fixed top-4 right-4 z-50 space-y-2">
    {#each $toasts as toast (toast.id)}
      <div 
        class={cn(
          "rounded-lg border p-4 shadow-lg transition-all duration-300",
          toast.type === 'success' && "bg-green-50 border-green-200 text-green-800",
          toast.type === 'error' && "bg-red-50 border-red-200 text-red-800",
          toast.type === 'warning' && "bg-yellow-50 border-yellow-200 text-yellow-800"
        )}
      >
        <div class="flex items-center">
          {#if toast.type === 'success'}
            <CheckCircle class="h-4 w-4 mr-2" />
          {:else if toast.type === 'error'}
            <AlertCircle class="h-4 w-4 mr-2" />
          {:else}
            <AlertCircle class="h-4 w-4 mr-2" />
          {/if}
          <span class="text-sm font-medium">{toast.message}</span>
        </div>
      </div>
    {/each}
  </div>
{/if}

<div class="space-y-8">
  <!-- 页面标题 - 居中设计 -->
  <div class="text-center space-y-4 py-8">
    <div class="space-y-3">
      <h1 class="text-4xl md:text-5xl font-bold tracking-tight bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
        Word List Generator
      </h1>
      <p class="text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed">
        Making word lists by analyzing word distribution in text files using various dispersion metrics.
      </p>
    </div>
    <div class="flex items-center justify-center gap-6 text-sm text-muted-foreground">
      <div class="flex items-center gap-2">
        <div class="w-2 h-2 bg-green-500 rounded-full"></div>
        <span>Machine Learning Powered</span>
      </div>
      <div class="flex items-center gap-2">
        <div class="w-2 h-2 bg-blue-500 rounded-full"></div>
        <span>Real-time Processing</span>
      </div>
      <div class="flex items-center gap-2">
        <div class="w-2 h-2 bg-purple-500 rounded-full"></div>
        <span>Export Ready</span>
      </div>
    </div>
  </div>

  <!-- 操作卡片 - 现代化设计 -->
  <Card className="p-8 bg-gradient-to-br from-white to-gray-50 dark:from-gray-900 dark:to-gray-800 border-2 shadow-lg">
    <div class="space-y-8">
      <div class="text-center">
        <h2 class="text-2xl font-semibold mb-2">Get Started</h2>
        <p class="text-muted-foreground">Follow these three simple steps to analyze your text files</p>
      </div>
      
      <!-- 步骤卡片布局 -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <!-- 步骤 1: 选择文件 -->
        <div class={cn(
          "relative p-6 rounded-xl border-2 transition-all duration-300 group",
          $filePaths.length > 0 
            ? "border-green-200 bg-green-50/50 dark:border-green-800 dark:bg-green-950/20 shadow-md" 
            : "border-gray-200 bg-gray-50/50 dark:border-gray-700 dark:bg-gray-800/50 hover:border-blue-300 hover:bg-blue-50/30 hover:shadow-md"
        )}>
          <div class="flex flex-col items-center text-center space-y-4">
            <div class={cn(
              "w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold transition-all duration-300 group-hover:scale-105",
              $filePaths.length > 0 ? "bg-green-500 text-white shadow-lg" : "bg-gray-200 text-gray-600"
            )}>
              {#if $filePaths.length > 0}
                <CheckCircle class="h-6 w-6" />
              {:else}
                1
              {/if}
            </div>
            <div class="space-y-2">
              <h3 class="font-semibold text-lg">Select Files</h3>
              <p class="text-sm text-muted-foreground">Choose your text files for analysis</p>
            </div>
            <Button 
              on:click={selectFiles} 
              disabled={$analyzing}
              class={cn(
                "w-full transition-all duration-200 font-medium",
                $filePaths.length > 0 && "bg-green-600 hover:bg-green-700 shadow-md"
              )}
              variant={$filePaths.length > 0 ? "default" : "outline"}
            >
              <FileText class="h-4 w-4 mr-2" />
              {$filePaths.length > 0 ? `${$filePaths.length} File${$filePaths.length > 1 ? 's' : ''} Selected` : 'Select Text Files'}
            </Button>
          </div>
          {#if $filePaths.length > 0}
            <div class="absolute -top-2 -right-2 w-6 h-6 bg-green-500 rounded-full flex items-center justify-center shadow-lg animate-pulse">
              <CheckCircle class="h-4 w-4 text-white" />
            </div>
          {/if}
        </div>

        <!-- 步骤 2: 加载模型 -->
        <div class={cn(
          "relative p-6 rounded-xl border-2 transition-all duration-300 group",
          $modelLoaded 
            ? "border-green-200 bg-green-50/50 dark:border-green-800 dark:bg-green-950/20 shadow-md" 
            : "border-gray-200 bg-gray-50/50 dark:border-gray-700 dark:bg-gray-800/50 hover:border-blue-300 hover:bg-blue-50/30 hover:shadow-md"
        )}>
          <div class="flex flex-col items-center text-center space-y-4">
            <div class={cn(
              "w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold transition-all duration-300 group-hover:scale-105",
              $modelLoaded ? "bg-green-500 text-white shadow-lg" : $modelStatus ? "bg-blue-500 text-white" : "bg-gray-200 text-gray-600"
            )}>
              {#if $modelLoaded}
                <CheckCircle class="h-6 w-6" />
              {:else if $modelStatus}
                <Loader2 class="h-6 w-6 animate-spin" />
              {:else}
                2
              {/if}
            </div>
            <div class="space-y-2">
              <h3 class="font-semibold text-lg">Load Models</h3>
              <p class="text-sm text-muted-foreground">Initialize NLP models for processing</p>
            </div>
            <Button 
              on:click={loadModel} 
              disabled={$analyzing || $modelLoaded}
              class={cn(
                "w-full transition-all duration-200 font-medium",
                $modelLoaded && "bg-green-600 hover:bg-green-700 shadow-md"
              )}
              variant={$modelLoaded ? "default" : "outline"}
            >
              {#if $modelStatus}
                <Loader2 class="h-4 w-4 mr-2 animate-spin" />
                {$modelStatus}
              {:else}
                <Settings class="h-4 w-4 mr-2" />
                {$modelLoaded ? 'Models Ready ✓' : 'Load NLP Models'}
              {/if}
            </Button>
          </div>
          {#if $modelLoaded}
            <div class="absolute -top-2 -right-2 w-6 h-6 bg-green-500 rounded-full flex items-center justify-center shadow-lg animate-pulse">
              <CheckCircle class="h-4 w-4 text-white" />
            </div>
          {/if}
        </div>

        <!-- 步骤 3: 开始分析 -->
        <div class={cn(
          "relative p-6 rounded-xl border-2 transition-all duration-300 group md:col-span-2 lg:col-span-1",
          $result.length > 0 
            ? "border-green-200 bg-green-50/50 dark:border-green-800 dark:bg-green-950/20 shadow-md" 
            : "border-gray-200 bg-gray-50/50 dark:border-gray-700 dark:bg-gray-800/50 hover:border-purple-300 hover:bg-purple-50/30 hover:shadow-md"
        )}>
          <div class="flex flex-col items-center text-center space-y-4">
            <div class={cn(
              "w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold transition-all duration-300 group-hover:scale-105",
              $result.length > 0 ? "bg-green-500 text-white shadow-lg" : $analyzing ? "bg-blue-500 text-white" : "bg-gray-200 text-gray-600"
            )}>
              {#if $result.length > 0}
                <CheckCircle class="h-6 w-6" />
              {:else if $analyzing}
                <Loader2 class="h-6 w-6 animate-spin" />
              {:else}
                3
              {/if}
            </div>
            <div class="space-y-2">
              <h3 class="font-semibold text-lg">Start Analysis</h3>
              <p class="text-sm text-muted-foreground">Process your files and extract insights</p>
            </div>
            <Button 
              on:click={analyze} 
              disabled={$analyzing || $filePaths.length === 0 || !$modelLoaded}
              class={cn(
                "w-full transition-all duration-200 font-medium",
                !($analyzing || $filePaths.length === 0 || !$modelLoaded) && !$result.length && "bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white shadow-md",
                $result.length > 0 && "bg-green-600 hover:bg-green-700 shadow-md"
              )}
              variant={$result.length > 0 ? "default" : ($analyzing || $filePaths.length === 0 || !$modelLoaded) ? "outline" : "default"}
            >
              {#if $analyzing}
                <Loader2 class="h-4 w-4 mr-2 animate-spin" />
                Analyzing...
              {:else if $result.length > 0}
                <CheckCircle class="h-4 w-4 mr-2" />
                Analysis Complete
              {:else}
                <Play class="h-4 w-4 mr-2" />
                Start Analysis
              {/if}
            </Button>
          </div>
          {#if $result.length > 0}
            <div class="absolute -top-2 -right-2 w-6 h-6 bg-green-500 rounded-full flex items-center justify-center shadow-lg animate-pulse">
              <CheckCircle class="h-4 w-4 text-white" />
            </div>
          {/if}
        </div>
      </div>

      <!-- 文件列表展示 -->
      {#if $filePaths.length > 0}
        <div class="mt-4 p-4 rounded-lg border border-green-200 bg-green-50/30 dark:border-green-800 dark:bg-green-950/10">
          <div class="flex items-center justify-between mb-3">
            <h4 class="font-medium text-green-800 dark:text-green-200 flex items-center">
              <FileText class="h-4 w-4 mr-2" />
              Selected Files ({$filePaths.length})
            </h4>
            <span class="text-xs text-green-600 bg-green-100 dark:bg-green-900/50 px-2 py-1 rounded-full">
              Ready for Analysis
            </span>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-24 overflow-y-auto">
            {#each $filePaths as file}
              <div class="flex items-center space-x-2 p-2 bg-white/60 dark:bg-gray-800/60 rounded border border-green-100 dark:border-green-800">
                <div class="w-2 h-2 bg-green-500 rounded-full flex-shrink-0"></div>
                <span class="text-xs font-medium truncate" title={file}>
                  {file.split(/[\\/]/).pop()}
                </span>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  </Card>

  <!-- 进度显示 - 现代化设计 -->
  {#if $analyzing}
    <Card className="p-8 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 border-blue-200 dark:border-blue-800">
      <div class="space-y-6">
        <div class="text-center">
          <div class="inline-flex items-center justify-center w-16 h-16 bg-blue-100 dark:bg-blue-900/50 rounded-full mb-4">
            <Loader2 class="h-8 w-8 text-blue-600 animate-spin" />
          </div>
          <h2 class="text-2xl font-semibold text-blue-800 dark:text-blue-200">Analysis in Progress</h2>
          <p class="text-blue-600 dark:text-blue-300 mt-2">Please wait while we process your files...</p>
        </div>
        
        <div class="max-w-md mx-auto space-y-4">
          <div class="flex justify-between text-sm font-medium text-blue-700 dark:text-blue-300">
            <span>Progress: {$progress.current}/{$progress.total}</span>
            <span>{Math.round(($progress.current / ($progress.total || 1)) * 100)}%</span>
          </div>
          <div class="w-full bg-blue-200 dark:bg-blue-800 rounded-full h-3 overflow-hidden">
            <div 
              class="bg-gradient-to-r from-blue-500 to-purple-500 h-3 rounded-full transition-all duration-300 ease-out shadow-sm" 
              style="width: {($progress.current / ($progress.total || 1)) * 100}%"
            ></div>
          </div>
          {#if $progress.file}
            <div class="text-center p-3 bg-white/50 dark:bg-gray-800/50 rounded-lg">
              <p class="text-sm text-muted-foreground">Currently processing:</p>
              <p class="text-sm font-medium text-blue-700 dark:text-blue-300 truncate" title={$progress.file}>
                {$progress.file.split(/[\\/]/).pop()}
              </p>
            </div>
          {/if}
        </div>
      </div>
    </Card>
  {/if}

  <!-- 结果显示 -->
  {#if $result.length > 0}
    <Card className="p-6">
      <div class="space-y-6">
        <!-- 标题和下载按钮 - 优化设计 -->
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div class="space-y-2">
            <div class="flex items-center space-x-3">
              <div class="w-10 h-10 bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg flex items-center justify-center">
                <CheckCircle class="h-6 w-6 text-white" />
              </div>
              <div>
                <h2 class="text-2xl font-semibold">Analysis Complete</h2>
                <p class="text-sm text-muted-foreground">
                  Original: {$result.length} | After filter: {$filteredResult.length} | On this page: {$finalPaginatedResult.length}
                </p>
              </div>
            </div>
          </div>
          <Button 
            on:click={downloadCSV} 
            variant="outline" 
            disabled={$filteredResult.length === 0}
            size="lg"
            class="px-6 py-3 border-2"
          >
            <Download class="h-5 w-5 mr-2" />
            Export CSV
          </Button>
        </div>

        <!-- 筛选控件 -->
        <Card className="p-4 bg-muted/20">
          <div class="space-y-4">
            <div class="flex items-center gap-2">
              <Filter class="h-4 w-4 text-primary" />
                <h3 class="font-medium">Advanced Filters</h3>
              {#if $filterConfig.wordLength.min || $filterConfig.wordLength.max || $filterConfig.pos.include.length > 0 || $filterConfig.pos.exclude.length > 0 || $filterConfig.metrics.some(m => m.metric && m.value)}
                <Button size="sm" variant="ghost" on:click={clearFilters}>
                  <X class="h-3 w-3 mr-1" />
                  Clear
                </Button>
              {/if}
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <!-- 词汇长度筛选 -->
              <div class="space-y-2">
                <label class="text-sm font-medium" for="word-length-filter-min">Word Length Range</label>
                <div class="flex gap-2">
                  <input
                    id="word-length-filter-min"
                    class="flex h-9 w-20 rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    type="number"
                    min="1"
                    placeholder="Minimum"
                    bind:value={$filterConfig.wordLength.min}
                    on:input={() => currentPage.set(1)}
                  />
                  <span class="self-center">~</span>
                  <input
                    id="word-length-filter-max"
                    class="flex h-9 w-20 rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    type="number"
                    min="1"
                    placeholder="Maximum"
                    bind:value={$filterConfig.wordLength.max}
                    on:input={() => currentPage.set(1)}
                  />
                </div>
              </div>

              <!-- 词性筛选 -->
              <div class="space-y-2">
                <label class="text-sm font-medium" for="pos-filter-list">Part of Speech (multi-select/exclude)</label>
                <div id="pos-filter-list" class="flex flex-col gap-1 max-h-32 overflow-y-auto border rounded p-2 bg-background">
                  {#each $uniquePOS as pos}
                    <div class="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id={"pos-inc-" + pos}
                        checked={$filterConfig.pos.include.includes(pos)}
                        on:change={e => {
                          const checked = e.target.checked;
                          filterConfig.update(cfg => {
                            if (checked) {
                              cfg.pos.include = [...cfg.pos.include, pos];
                            } else {
                              cfg.pos.include = cfg.pos.include.filter(p => p !== pos);
                            }
                            return cfg;
                          });
                          currentPage.set(1);
                        }}
                      />
                      <label for={"pos-inc-" + pos} class="text-xs">{pos}</label>
                      <button
                        type="button"
                        class="ml-2 text-xs px-1 rounded bg-red-100 text-red-600 hover:bg-red-200"
                        title="Exclude this part of speech"
                        on:click={() => {
                          filterConfig.update(cfg => {
                            if (!cfg.pos.exclude.includes(pos)) {
                              cfg.pos.exclude = [...cfg.pos.exclude, pos];
                            }
                            return cfg;
                          });
                          currentPage.set(1);
                        }}
                      >Exclude</button>
                      {#if $filterConfig.pos.exclude.includes(pos)}
                        <span class="text-xs text-red-500">Excluded</span>
                        <button
                          type="button"
                          class="ml-1 text-xs px-1 rounded bg-gray-100 text-gray-600 hover:bg-gray-200"
                          title="Cancel Exclusion"
                          on:click={() => {
                            filterConfig.update(cfg => {
                              cfg.pos.exclude = cfg.pos.exclude.filter(p => p !== pos);
                              return cfg;
                            });
                            currentPage.set(1);
                          }}
                        >Cancle</button>
                      {/if}
                    </div>
                  {/each}
                </div>
              </div>
            </div>

            <!-- 指标筛选区域 -->
            <div class="space-y-3">
              <div class="flex items-center justify-between">
                <label class="text-sm font-medium" for="metric-filter-select">Metric Filters</label>
                <Button size="sm" variant="outline" on:click={addMetricFilter}>
                    <span class="text-sm">+ Add Condition</span>
                </Button>
              </div>
              
              {#if $filterConfig.metrics.length === 0}
                <div class="text-sm text-muted-foreground bg-muted/30 p-3 rounded border-2 border-dashed">
                    Click "+ Add Condition" to create a metric filter condition
                </div>
              {/if}

              {#each $filterConfig.metrics as metricFilter, index}
                <div class="flex items-center gap-2 p-3 border rounded-lg bg-background">
                  <div class="flex items-center gap-2 flex-1">
                    <!-- 指标选择 -->
                    <select
                      class="flex h-9 w-32 rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      bind:value={metricFilter.metric}
                      on:change={(e) => updateMetricFilter(index, 'metric', e.target.value)}
                    >
                        <option value="">Select Metric</option>
                      {#each $metricColumns as metric}
                        <option value={metric}>{metric}</option>
                      {/each}
                    </select>

                    <!-- 操作符选择 -->
                    <select
                      class="flex h-9 w-16 rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      bind:value={metricFilter.operator}
                      on:change={(e) => updateMetricFilter(index, 'operator', e.target.value)}
                      disabled={!metricFilter.metric}
                    >
                      <option value="gt">&gt;</option>
                      <option value="gte">&gt;=</option>
                      <option value="lt">&lt;</option>
                      <option value="lte">&lt;=</option>
                      <option value="eq">=</option>
                    </select>

                    <!-- 数值输入 -->
                    <input
                      class="flex h-9 w-24 rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      type="number"
                      step="0.0001"
                      placeholder="Value"
                      bind:value={metricFilter.value}
                      on:input={(e) => updateMetricFilter(index, 'value', e.target.value)}
                      disabled={!metricFilter.metric}
                    />

                    <!-- 条件描述 -->
                    {#if metricFilter.metric && metricFilter.value}
                      <span class="text-sm text-muted-foreground">
                        {metricFilter.metric} 
                        {metricFilter.operator === 'gt' ? '>' : 
                         metricFilter.operator === 'gte' ? '>=' : 
                         metricFilter.operator === 'lt' ? '<' : 
                         metricFilter.operator === 'lte' ? '<=' : '='} 
                        {metricFilter.value}
                      </span>
                    {/if}
                  </div>

                  <!-- 删除按钮 -->
                  <Button 
                    size="sm" 
                    variant="ghost" 
                    on:click={() => removeMetricFilter(index)}
                    class="text-red-500 hover:text-red-700 hover:bg-red-50"
                  >
                    <X class="h-4 w-4" />
                  </Button>
                </div>
              {/each}
            </div>
          </div>
        </Card>
        
        <!-- 结果表格 -->
        <div class="border rounded-lg overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-muted/50">
                <tr class="border-b">
                  <!-- 可排序的词汇列 -->
                  <th class="px-3 py-2 text-left font-medium sticky left-0 bg-muted/50 z-10">
                    <button
                      class="flex items-center space-x-1 hover:bg-muted/20 p-1 rounded transition-colors w-full text-left"
                      on:click={() => handleSort('word')}
                    >
                      <span>Word</span>
                      <span class="text-xs opacity-60">
                        {#if $sortConfig.column === 'word'}
                          {#if $sortConfig.direction === 'asc'}↑{:else if $sortConfig.direction === 'desc'}↓{:else}↕{/if}
                        {:else}
                          ↕
                        {/if}
                      </span>
                    </button>
                  </th>
                  
                  <!-- 可排序的词性列 -->
                  <th class="px-3 py-2 text-left font-medium sticky left-16 bg-muted/50 z-10">
                    <button
                      class="flex items-center space-x-1 hover:bg-muted/20 p-1 rounded transition-colors w-full text-left"
                      on:click={() => handleSort('pos')}
                    >
                      <span>POS</span>
                      <span class="text-xs opacity-60">
                        {#if $sortConfig.column === 'pos'}
                          {#if $sortConfig.direction === 'asc'}↑{:else if $sortConfig.direction === 'desc'}↓{:else}↕{/if}
                        {:else}
                          ↕
                        {/if}
                      </span>
                    </button>
                  </th>
                  
                  <!-- 可排序的指标列 -->
                  {#each $metricColumns as column}
                    <th class="px-3 py-2 text-left font-medium whitespace-nowrap">
                      <button
                        class="flex items-center space-x-1 hover:bg-muted/20 p-1 rounded transition-colors w-full text-left"
                        on:click={() => handleSort(column)}
                        title="Click to sort: {column}"
                      >
                        <span class="truncate max-w-[120px]">{column}</span>
                        <span class="text-xs opacity-60 flex-shrink-0">
                          {#if $sortConfig.column === column}
                            {#if $sortConfig.direction === 'asc'}↑{:else if $sortConfig.direction === 'desc'}↓{:else}↕{/if}
                          {:else}
                            ↕
                          {/if}
                        </span>
                      </button>
                    </th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each $finalPaginatedResult as item}
                  <tr class="border-b hover:bg-muted/25 transition-colors">
                    <td class="px-3 py-2 font-medium sticky left-0 bg-background hover:bg-muted/25 z-10">
                      {item.word}
                    </td>
                    <td class="px-3 py-2 text-muted-foreground sticky left-16 bg-background hover:bg-muted/25 z-10">
                      {item.pos}
                    </td>
                    {#each $metricColumns as column}
                      <td class="px-3 py-2 whitespace-nowrap" title="{column}: {item.metrics[column] ?? '-'}">
                        {#if item.metrics[column] !== undefined}
                          {#if typeof item.metrics[column] === 'number'}
                            <span class="font-mono text-xs">
                              {item.metrics[column].toFixed(4)}
                            </span>
                          {:else}
                            {item.metrics[column]}
                          {/if}
                        {:else}
                          <span class="text-muted-foreground">-</span>
                        {/if}
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>

        <!-- 分页控件 -->
        {#if totalPages > 1}
          <div class="flex items-center justify-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              on:click={() => goToPage(Math.max(1, $currentPage - 1))}
              disabled={$currentPage === 1}
            >
              Previous
            </Button>
            
            <span class="text-sm text-muted-foreground">
                Page {$currentPage} of {totalPages}
            </span>
            
            <Button
              variant="outline"
              size="sm"
              on:click={() => goToPage(Math.min(totalPages, $currentPage + 1))}
              disabled={$currentPage === totalPages}
            >
              Next
            </Button>
          </div>
        {/if}

        <!-- 表格功能说明 -->
        {#if $metricColumns.length > 0}
          <div class="text-xs text-muted-foreground bg-muted/30 p-3 rounded-lg">
            <p class="font-medium mb-1">📊 Interactive Table Features:</p>
            <div class="space-y-1">
              <p>• <strong>Click column headers</strong> to sort (cycles through ascending → descending → none)</p>
              <p>• <strong>Word</strong> and <strong>POS</strong> columns are fixed on the left for easy comparison</p>
              <p>• <strong>Numeric values</strong> are shown with 4 decimal places; '-' means the metric is not applicable</p>
              <p>• <strong>Hover</strong> to see the full column name and value</p>
            </div>
          </div>
        {/if}

        <!-- 排序状态提示 -->
        {#if $sortConfig.column !== '' && $sortConfig.direction !== 'none'}
          <div class="flex items-center gap-2 text-sm text-muted-foreground bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-lg p-2">
            <span class="text-blue-600 dark:text-blue-400">🔄</span>
            <span>
              Currently sorted by <strong>{$sortConfig.column}</strong>
              in {$sortConfig.direction === 'asc' ? 'ascending' : 'descending'} order
            </span>
            <button
              class="ml-auto text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200"
              on:click={() => sortConfig.set({ column: '', direction: 'none' })}
              title="Clear sorting"
            >
              ✕
            </button>
          </div>
        {/if}
      </div>
    </Card>
  {/if}
</div>

