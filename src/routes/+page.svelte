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
      showToast(`文件选择失败: ${e}`, 'error');
    }
  }

  async function loadModel() {
    modelStatus.set("正在加载模型...");
    try {
      await invoke("load_models", {
        cwsPath: cwsModel,
        posPath: posModel,
      });
      modelLoaded.set(true);
      modelStatus.set("");
      showToast('模型加载成功!', 'success');
    } catch (e) {
      modelLoaded.set(false);
      modelStatus.set("");
      showToast(`模型加载失败: ${e}`, 'error');
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
  // 筛选配置：词长范围、词性多选（包含/排除）、指标
  const filterConfig = writable({
    wordLength: { min: '', max: '' }, // 支持范围
    pos: { include: [], exclude: [] }, // 支持包含/排除
    metric: '',
    operator: 'gt',
    value: ''
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

      // 指标筛选
      if ($filterConfig.metric && $filterConfig.value && $filterConfig.value !== '') {
        const metricValue = item.metrics[$filterConfig.metric];
        const targetValue = parseFloat($filterConfig.value);

        if (metricValue === undefined || metricValue === null) return false;
        if (typeof metricValue !== 'number') return false;

        switch ($filterConfig.operator) {
          case 'gt': return metricValue > targetValue;
          case 'lt': return metricValue < targetValue;
          case 'gte': return metricValue >= targetValue;
          case 'lte': return metricValue <= targetValue;
          case 'eq': return Math.abs(metricValue - targetValue) < 0.0001;
          default: return true;
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
      metric: '',
      operator: 'gt',
      value: ''
    });
    currentPage.set(1);
  }

  // 下载CSV功能
  async function downloadCSV() {
    try {
      // 生成CSV内容
      const headers = ['词汇', '词性', ...$metricColumns];
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
        showToast(`文件已保存: ${filePath}`, 'success');
      }
    } catch (error) {
      showToast(`下载失败: ${error}`, 'error');
    }
  }

  async function analyze() {
    if (!$modelLoaded) {
      showToast('请先加载NLP模型', 'warning');
      return;
    }
    if ($filePaths.length === 0) {
      showToast('请先选择要分析的文本文件', 'warning');
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
        showToast('分析完成，但未提取到任何结果。', 'warning');
      } else {
        showToast('分析完成!', 'success');
      }
    } catch (e) {
      showToast(`分析出错: ${e}`, 'error');
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
  <!-- 页面标题 -->
  <div class="space-y-2">
    <h1 class="text-3xl font-bold tracking-tight">词汇分析工具</h1>
    <p class="text-muted-foreground">
      使用先进的NLP技术分析文本文件中的词汇分布和特征
    </p>
  </div>

  <!-- 操作卡片 -->
  <Card className="p-6">
    <div class="space-y-6">
      <h2 class="text-xl font-semibold">操作控制</h2>
      
      <div class="flex flex-wrap gap-3">
        <Button on:click={selectFiles} disabled={$analyzing}>
          <FileText class="h-4 w-4 mr-2" />
          选择文件
        </Button>
        
        <Button 
          variant="secondary" 
          on:click={loadModel} 
          disabled={$analyzing || $modelLoaded}
        >
          {#if $modelStatus}
            <Loader2 class="h-4 w-4 mr-2 animate-spin" />
            {$modelStatus}
          {:else}
            <Settings class="h-4 w-4 mr-2" />
            加载模型
          {/if}
        </Button>
        
        <Button 
          on:click={analyze} 
          disabled={$analyzing || $filePaths.length === 0 || !$modelLoaded}
        >
          {#if $analyzing}
            <Loader2 class="h-4 w-4 mr-2 animate-spin" />
            正在分析...
          {:else}
            <Play class="h-4 w-4 mr-2" />
            开始分析
          {/if}
        </Button>
      </div>

      {#if $filePaths.length > 0}
        <div class="rounded-lg border bg-muted/50 p-4">
          <h3 class="font-medium mb-2">已选择 {$filePaths.length} 个文件:</h3>
          <ul class="text-sm text-muted-foreground space-y-1 max-h-32 overflow-y-auto">
            {#each $filePaths as file}
              <li class="truncate">• {file.split(/[\\/]/).pop()}</li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>
  </Card>

  <!-- 进度显示 -->
  {#if $analyzing}
    <Card className="p-6">
      <div class="space-y-4">
        <h2 class="text-xl font-semibold">分析进度</h2>
        <div class="space-y-2">
          <div class="flex justify-between text-sm text-muted-foreground">
            <span>进度: {$progress.current}/{$progress.total}</span>
            <span>{Math.round(($progress.current / ($progress.total || 1)) * 100)}%</span>
          </div>
          <div class="w-full bg-secondary rounded-full h-2">
            <div 
              class="bg-primary h-2 rounded-full transition-all duration-300" 
              style="width: {($progress.current / ($progress.total || 1)) * 100}%"
            ></div>
          </div>
          {#if $progress.file}
            <p class="text-sm text-muted-foreground">当前文件: {$progress.file}</p>
          {/if}
        </div>
      </div>
    </Card>
  {/if}

  <!-- 结果显示 -->
  {#if $result.length > 0}
    <Card className="p-6">
      <div class="space-y-6">
        <!-- 标题和下载按钮 -->
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-xl font-semibold">分析结果</h2>
            <p class="text-sm text-muted-foreground mt-1">
              原始: {$result.length} 个 | 筛选后: {$filteredResult.length} 个 | 当前页: {$finalPaginatedResult.length} 个
            </p>
          </div>
          <Button on:click={downloadCSV} variant="outline" disabled={$filteredResult.length === 0}>
            <Download class="h-4 w-4 mr-2" />
            下载CSV
          </Button>
        </div>

        <!-- 筛选控件 -->
        <Card className="p-4 bg-muted/20">
          <div class="space-y-4">
            <div class="flex items-center gap-2">
              <Filter class="h-4 w-4 text-primary" />
              <h3 class="font-medium">高级筛选</h3>
              {#if $filterConfig.wordLength || $filterConfig.pos || ($filterConfig.metric && $filterConfig.value)}
                <Button size="sm" variant="ghost" on:click={clearFilters}>
                  <X class="h-3 w-3 mr-1" />
                  清除
                </Button>
              {/if}
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
              <!-- 词汇长度筛选 -->
              <div class="space-y-2">
                <label class="text-sm font-medium" for="word-length-filter-min">词汇长度范围</label>
                <div class="flex gap-2">
                  <input
                    id="word-length-filter-min"
                    class="flex h-9 w-20 rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    type="number"
                    min="1"
                    placeholder="最小"
                    bind:value={$filterConfig.wordLength.min}
                    on:input={() => currentPage.set(1)}
                  />
                  <span class="self-center">~</span>
                  <input
                    id="word-length-filter-max"
                    class="flex h-9 w-20 rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    type="number"
                    min="1"
                    placeholder="最大"
                    bind:value={$filterConfig.wordLength.max}
                    on:input={() => currentPage.set(1)}
                  />
                </div>
              </div>

              <!-- 词性筛选 -->
              <div class="space-y-2">
                <label class="text-sm font-medium">词性（多选/排除）</label>
                <div class="flex flex-col gap-1 max-h-32 overflow-y-auto border rounded p-2 bg-background">
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
                        title="排除此词性"
                        on:click={() => {
                          filterConfig.update(cfg => {
                            if (!cfg.pos.exclude.includes(pos)) {
                              cfg.pos.exclude = [...cfg.pos.exclude, pos];
                            }
                            return cfg;
                          });
                          currentPage.set(1);
                        }}
                      >排除</button>
                      {#if $filterConfig.pos.exclude.includes(pos)}
                        <span class="text-xs text-red-500">已排除</span>
                        <button
                          type="button"
                          class="ml-1 text-xs px-1 rounded bg-gray-100 text-gray-600 hover:bg-gray-200"
                          title="取消排除"
                          on:click={() => {
                            filterConfig.update(cfg => {
                              cfg.pos.exclude = cfg.pos.exclude.filter(p => p !== pos);
                              return cfg;
                            });
                            currentPage.set(1);
                          }}
                        >撤销</button>
                      {/if}
                    </div>
                  {/each}
                </div>
              </div>

              <!-- 指标筛选 -->
              <div class="space-y-2">
                <label class="text-sm font-medium">指标</label>
                <select
                  class="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  bind:value={$filterConfig.metric}
                  on:change={() => currentPage.set(1)}
                >
                  <option value="">选择指标</option>
                  {#each $metricColumns as metric}
                    <option value={metric}>{metric}</option>
                  {/each}
                </select>
              </div>

              <!-- 指标条件 -->
              <div class="space-y-2">
                <label class="text-sm font-medium">条件</label>
                <div class="flex gap-1">
                  <select
                    class="flex h-9 w-20 rounded-md border border-input bg-background px-2 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    bind:value={$filterConfig.operator}
                    disabled={!$filterConfig.metric}
                  >
                    <option value="gt">&gt;</option>
                    <option value="gte">&gt;=</option>
                    <option value="lt">&lt;</option>
                    <option value="lte">&lt;=</option>
                    <option value="eq">=</option>
                  </select>
                  <input
                    class="flex h-9 flex-1 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    type="number"
                    step="0.0001"
                    placeholder="数值"
                    bind:value={$filterConfig.value}
                    disabled={!$filterConfig.metric}
                    on:input={() => currentPage.set(1)}
                  />
                </div>
              </div>
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
                      <span>词汇</span>
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
                      <span>词性</span>
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
                        title="点击排序: {column}"
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
              上一页
            </Button>
            
            <span class="text-sm text-muted-foreground">
              第 {$currentPage} 页，共 {totalPages} 页
            </span>
            
            <Button
              variant="outline"
              size="sm"
              on:click={() => goToPage(Math.min(totalPages, $currentPage + 1))}
              disabled={$currentPage === totalPages}
            >
              下一页
            </Button>
          </div>
        {/if}

        <!-- 表格功能说明 -->
        {#if $metricColumns.length > 0}
          <div class="text-xs text-muted-foreground bg-muted/30 p-3 rounded-lg">
            <p class="font-medium mb-1">📊 交互式表格功能：</p>
            <div class="space-y-1">
              <p>• <strong>点击列标题</strong>可排序（升序→降序→无排序循环）</p>
              <p>• <strong>词汇和词性列</strong>固定在左侧，方便对比数据</p>
              <p>• <strong>数值</strong>保留4位小数，'-' 表示该指标不适用</p>
              <p>• <strong>鼠标悬停</strong>可查看完整的列名和数值</p>
            </div>
          </div>
        {/if}

        <!-- 排序状态提示 -->
        {#if $sortConfig.column !== '' && $sortConfig.direction !== 'none'}
          <div class="flex items-center gap-2 text-sm text-muted-foreground bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-lg p-2">
            <span class="text-blue-600 dark:text-blue-400">🔄</span>
            <span>
              当前按 <strong>{$sortConfig.column}</strong>
              {$sortConfig.direction === 'asc' ? '升序' : '降序'} 排列
            </span>
            <button
              class="ml-auto text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200"
              on:click={() => sortConfig.set({ column: '', direction: 'none' })}
              title="清除排序"
            >
              ✕
            </button>
          </div>
        {/if}
      </div>
    </Card>
  {/if}
</div>

