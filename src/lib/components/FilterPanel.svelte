<script lang="ts">
  import type { Writable } from 'svelte/store';
  import Input from "$lib/components/ui/input/input.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import X from 'lucide-svelte/icons/x';
  import SlidersHorizontal from 'lucide-svelte/icons/sliders-horizontal';
  import CheckCircle from 'lucide-svelte/icons/check-circle';
  export let filterConfig: Writable<{
    wordLength: { min: string; max: string };
    pos: { include: string[]; exclude: string[] };
    metrics: Array<{ metric: string; operator: string; value: string }>;
  }>;
  export let metricColumns: string[];
  export let posSearchInclude: Writable<string>;
  export let posSearchExclude: Writable<string>;
  export let filteredPOSInclude: string[];
  export let filteredPOSExclude: string[];
  export let addMetricFilter: () => void;
  export let removeMetricFilter: (index: number) => void;
  export let updateMetricFilter: (index: number, field: string, value: string) => void;
  export let currentPage: Writable<number>;

  // 触发分页重置
  function resetPage() {
    if (currentPage) currentPage.set(1);
  }
</script>

<div class="space-y-8">
  <!-- Word Length Filter -->
  <div class="space-y-4">
    <h4 class="text-lg font-semibold flex items-center gap-2">
      <span class="w-2 h-2 bg-blue-400 rounded-full"></span>
      Word Length Range
    </h4>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-md">
      <div>
        <label for="word-length-min" class="block text-sm font-medium mb-2">Minimum Length</label>
        <!-- @ts-expect-error Svelte slot event type limitation -->
        <Input id="word-length-min" type="number" min="1" placeholder="e.g., 2" bind:value={$filterConfig.wordLength.min} on:input={resetPage} />
      </div>
      <div>
        <label for="word-length-max" class="block text-sm font-medium mb-2">Maximum Length</label>
        <!-- @ts-expect-error Svelte slot event type limitation -->
        <Input id="word-length-max" type="number" min="1" placeholder="e.g., 10" bind:value={$filterConfig.wordLength.max} on:input={resetPage} />
      </div>
    </div>
  </div>

  <!-- POS Filter -->
  <div class="space-y-4">
    <h4 class="text-lg font-semibold flex items-center gap-2">
      <span class="w-2 h-2 bg-purple-400 rounded-full"></span>
      Part-of-Speech Tags
    </h4>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Include POS -->
      <div class="space-y-3">
        <div class="block text-sm font-medium">Include Only These Tags <span class="text-xs opacity-75">(leave empty to include all)</span></div>
        <div class="relative">
          <Input id="pos-include-search" type="text" bind:value={$posSearchInclude} placeholder="Search POS tags..." />
          {#if $posSearchInclude}
            <button on:click={() => posSearchInclude.set('')} class="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-200" title="Clear search">
              <X class="h-5 w-5" />
            </button>
          {/if}
        </div>
        <div class="min-h-[120px] max-h-40 overflow-y-auto p-4 rounded-lg border custom-scrollbar">
          <div class="flex flex-wrap gap-2">
            {#each filteredPOSInclude as pos}
              <button class={$filterConfig.pos.include.includes(pos) ? 
                "px-3 py-1.5 rounded-full text-sm font-medium bg-green-100 text-green-700 border-green-300 border shadow-sm dark:bg-green-900/30 dark:text-green-300 dark:border-green-700" : 
                "px-3 py-1.5 rounded-full text-sm font-medium bg-muted text-muted-foreground border border-border hover:bg-accent hover:text-accent-foreground"
              }
                on:click={() => {
                  const currentInclude = $filterConfig.pos.include;
                  if (currentInclude.includes(pos)) {
                    filterConfig.update(cfg => ({ ...cfg, pos: { ...cfg.pos, include: currentInclude.filter((p: string) => p !== pos) } }));
                  } else {
                    filterConfig.update(cfg => ({ ...cfg, pos: { ...cfg.pos, include: [...currentInclude, pos] } }));
                  }
                  resetPage();
                }}>
                {pos}
                {#if $filterConfig.pos.include.includes(pos)}<CheckCircle class="h-3 w-3 ml-1 inline" />{/if}
              </button>
            {/each}
          </div>
        </div>
      </div>
      <!-- Exclude POS -->
      <div class="space-y-3">
        <div class="block text-sm font-medium">Exclude These Tags <span class="text-xs opacity-75">(click to exclude)</span></div>
        <div class="relative">
          <Input id="pos-exclude-search" type="text" bind:value={$posSearchExclude} placeholder="Search POS tags..." />
          {#if $posSearchExclude}
            <button on:click={() => posSearchExclude.set('')} class="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-200" title="Clear search">
              <X class="h-5 w-5" />
            </button>
          {/if}
        </div>
        <div class="min-h-[120px] max-h-40 overflow-y-auto p-4 rounded-lg border custom-scrollbar">
          <div class="flex flex-wrap gap-2">
            {#each filteredPOSExclude as pos}
              <button class={$filterConfig.pos.exclude.includes(pos) ? 
                "px-3 py-1.5 rounded-full text-sm font-medium bg-red-100 text-red-700 border-red-300 border shadow-sm dark:bg-red-900/30 dark:text-red-300 dark:border-red-700" : 
                "px-3 py-1.5 rounded-full text-sm font-medium bg-muted text-muted-foreground border border-border hover:bg-accent hover:text-accent-foreground"
              }
                on:click={() => {
                  const currentExclude = $filterConfig.pos.exclude;
                  if (currentExclude.includes(pos)) {
                    filterConfig.update(cfg => ({ ...cfg, pos: { ...cfg.pos, exclude: currentExclude.filter((p: string) => p !== pos) } }));
                  } else {
                    filterConfig.update(cfg => ({ ...cfg, pos: { ...cfg.pos, exclude: [...currentExclude, pos] } }));
                  }
                  resetPage();
                }}>
                {pos}
                {#if $filterConfig.pos.exclude.includes(pos)}<X class="h-3 w-3 ml-1 inline" />{/if}
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
      <h4 class="text-lg font-semibold flex items-center gap-2">
        <span class="w-2 h-2 bg-orange-400 rounded-full"></span>
        Metric Filters
      </h4>
      <Button on:click={addMetricFilter} class="text-blue-400 px-4 py-2 rounded-lg text-sm hover:bg-blue-500/20">+ Add Filter</Button>
    </div>
    {#if $filterConfig.metrics.length === 0}
      <div class="text-center py-8 rounded-lg border border-dashed">
        <SlidersHorizontal class="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p class="text-sm">No metric filters added yet</p>
        <p class="text-xs mt-1">Click "Add Filter" to start filtering by metrics</p>
      </div>
    {:else}
      <div class="space-y-4">
        {#each $filterConfig.metrics as filter, index}
          <div class="p-6 rounded-xl border">
            <div class="flex items-center justify-between mb-4">
              <span class="text-sm font-medium">Filter #{index + 1}</span>
              <Button on:click={() => removeMetricFilter(index)} class="text-red-400 p-2 rounded-lg hover:bg-red-500/20"><X class="h-4 w-4" /></Button>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label for={`metric-select-${index}`} class="block text-sm font-medium mb-2">Metric</label>
                <select 
                  id={`metric-select-${index}`} 
                  bind:value={filter.metric} 
                  on:change={(e: Event) => updateMetricFilter(index, 'metric', (e.target as HTMLSelectElement)?.value)}
                  class="w-full px-3 py-2 rounded-md border border-input bg-background text-foreground text-sm ring-offset-background focus:ring-2 focus:ring-ring focus:outline-none dark:bg-gray-800 dark:border-gray-600 dark:text-white"
                >
                  <option value="">Select metric</option>
                  {#each metricColumns as col}
                    <option value={col}>{col}</option>
                  {/each}
                </select>
              </div>
              <div>
                <label for={`condition-select-${index}`} class="block text-sm font-medium mb-2">Condition</label>
                <select 
                  id={`condition-select-${index}`} 
                  bind:value={filter.operator} 
                  on:change={(e: Event) => updateMetricFilter(index, 'operator', (e.target as HTMLSelectElement)?.value)}
                  class="w-full px-3 py-2 rounded-md border border-input bg-background text-foreground text-sm ring-offset-background focus:ring-2 focus:ring-ring focus:outline-none dark:bg-gray-800 dark:border-gray-600 dark:text-white"
                >
                  <option value="gt">&gt;</option>
                  <option value="lt">&lt;</option>
                  <option value="gte">&ge;</option>
                  <option value="lte">&le;</option>
                  <option value="eq">=</option>
                </select>
              </div>
              <div>
                <label for={`value-input-${index}`} class="block text-sm font-medium mb-2">Value</label>
                <!-- @ts-expect-error Svelte slot event type limitation -->
                <Input id={`value-input-${index}`} type="number" bind:value={filter.value} on:input={(e: Event) => updateMetricFilter(index, 'value', (e.target as HTMLInputElement)?.value)} />
              </div>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>
