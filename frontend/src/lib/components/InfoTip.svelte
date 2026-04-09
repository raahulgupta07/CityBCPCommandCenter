<script lang="ts">
  let { title = '', description = '', formula = '', example = '' }: {
    title?: string;
    description?: string;
    formula?: string;
    example?: string;
  } = $props();

  let open = $state(false);
  let el: HTMLDivElement;

  function handleClick(e: MouseEvent) {
    e.stopPropagation();
    open = !open;
  }

  function handleClickOutside(e: MouseEvent) {
    if (el && !el.contains(e.target as Node)) open = false;
  }

  $effect(() => {
    if (open) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  });
</script>

<div class="relative inline-flex items-center" bind:this={el}>
  <button
    class="inline-flex items-center justify-center w-5 h-5 text-xs rounded-full border border-gray-300 text-gray-400 hover:text-gray-700 hover:border-gray-500 cursor-pointer transition-colors"
    onclick={handleClick}
    title="How is this calculated?"
    aria-label="Info"
  >ⓘ</button>

  {#if open}
    <div class="absolute z-50 top-7 right-0 w-80 bg-white border border-gray-200 rounded-lg shadow-xl p-4 text-left" style="min-width: 280px;">
      <button class="absolute top-2 right-2 text-gray-400 hover:text-gray-600 text-sm cursor-pointer" onclick={() => open = false}>✕</button>

      {#if title}
        <div class="font-bold text-sm text-gray-800 mb-2 pr-6">{title}</div>
      {/if}

      {#if description}
        <p class="text-xs text-gray-600 mb-3 leading-relaxed">{description}</p>
      {/if}

      {#if formula}
        <div class="mb-2">
          <span class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Formula</span>
          <div class="mt-1 px-2 py-1.5 bg-gray-50 border border-gray-100 rounded text-xs font-mono text-gray-700 leading-relaxed">{@html formula}</div>
        </div>
      {/if}

      {#if example}
        <div class="mt-2">
          <span class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Example</span>
          <p class="mt-1 text-xs text-gray-500 italic leading-relaxed">{example}</p>
        </div>
      {/if}
    </div>
  {/if}
</div>
