<script lang="ts">
	import { api } from '$lib/api';
	import { onMount } from 'svelte';

	let { type = 'executive', data = {}, title = 'AI EXECUTIVE BRIEFING', autoLoad = true }: { type?: string; data?: any; title?: string; autoLoad?: boolean } = $props();

	let content = $state('');
	let loading = $state(false);
	let error = $state('');
	let timestamp = $state('');
	let copied = $state(false);

	// Cache key for localStorage
	const cacheKey = `ai_insight_${type}_${data?.tab || 'default'}`;

	onMount(() => {
		// Load from localStorage cache first
		const cached = localStorage.getItem(cacheKey);
		if (cached) {
			try {
				const parsed = JSON.parse(cached);
				content = parsed.content || '';
				timestamp = parsed.timestamp || '';
				return; // Don't auto-generate if cached
			} catch {}
		}
		// Auto-trigger if no cache and autoLoad enabled
		if (autoLoad) {
			setTimeout(() => generate(false), 500);
		}
	});

	async function generate(forceRefresh = false) {
		loading = true;
		error = '';
		try {
			const res = await api.post('/insights', { type, data, force_refresh: forceRefresh });
			content = res.content || '';
			timestamp = new Date().toLocaleString();
			// Save to localStorage
			localStorage.setItem(cacheKey, JSON.stringify({ content, timestamp }));
		} catch (e: any) {
			error = e.message || 'Failed to generate insight';
		}
		loading = false;
	}

	function copyToClipboard() {
		navigator.clipboard.writeText(content.replace(/[🔴🟠🟡🟢⚪■━]/g, '').trim());
		copied = true;
		setTimeout(() => copied = false, 2000);
	}

	function formatContent(text: string): string {
		return text
			.replace(/■\s*([A-Z][A-Z\s&]+)/g, '<div class="mt-4 mb-2 font-black uppercase text-[11px] tracking-wider" style="color: #383832; border-bottom: 2px solid #383832; padding-bottom: 4px;">$1</div>')
			.replace(/🔴\s*(\d+)\.\s*(.+)/g, '<div class="flex items-start gap-2 mt-2"><span class="shrink-0 px-1.5 py-0.5 text-[9px] font-black" style="background: #be2d06; color: white;">CRITICAL</span><span class="font-bold" style="color: #be2d06;">$2</span></div>')
			.replace(/🟠\s*(\d+)\.\s*(.+)/g, '<div class="flex items-start gap-2 mt-2"><span class="shrink-0 px-1.5 py-0.5 text-[9px] font-black" style="background: #ff9d00; color: white;">WARNING</span><span class="font-bold" style="color: #ff9d00;">$2</span></div>')
			.replace(/🟡\s*(\d+)\.\s*(.+)/g, '<div class="flex items-start gap-2 mt-2"><span class="shrink-0 px-1.5 py-0.5 text-[9px] font-black" style="background: #ff9d00; color: white;">WATCH</span><span class="font-bold" style="color: #65655e;">$2</span></div>')
			.replace(/(\d+)\.\s*\[🔴\s*([A-Z]+)\]/g, '<span class="inline-block px-1.5 py-0.5 text-[9px] font-black mr-1" style="background: #be2d06; color: white;">$2</span>')
			.replace(/(\d+)\.\s*\[🟠\s*([A-Z\s]+)\]/g, '<span class="inline-block px-1.5 py-0.5 text-[9px] font-black mr-1" style="background: #ff9d00; color: white;">$2</span>')
			.replace(/(\d+)\.\s*\[🟡\s*([A-Z\s]+)\]/g, '<span class="inline-block px-1.5 py-0.5 text-[9px] font-black mr-1" style="background: #ff9d00; color: white;">$2</span>')
			.replace(/(\d+)\.\s*\[⚪\s*([A-Z]+)\]/g, '<span class="inline-block px-1.5 py-0.5 text-[9px] font-black mr-1" style="background: #65655e; color: white;">$2</span>')
			.replace(/🟢/g, '<span style="color: #007518;">●</span>')
			.replace(/🔴/g, '<span style="color: #be2d06;">●</span>')
			.replace(/🟠/g, '<span style="color: #ff9d00;">●</span>')
			.replace(/⚪/g, '<span style="color: #9d9d91;">○</span>')
			.replace(/▼(\d+%)/g, '<span class="font-bold" style="color: #be2d06;">▼$1</span>')
			.replace(/▲(\d+%)/g, '<span class="font-bold" style="color: #007518;">▲$1</span>')
			.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
			.replace(/\n/g, '<br/>');
	}
</script>

<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832; background: white; margin-top: 1rem;">
	<div class="px-4 py-2 flex items-center justify-between" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-2">
			<span class="material-symbols-outlined text-lg" style="color: #00fc40;">psychology</span>
			<span class="text-[11px] font-black uppercase">{title}</span>
			{#if timestamp}
				<span class="text-[9px] opacity-50 ml-2">{timestamp}</span>
			{/if}
		</div>
		<div class="flex items-center gap-2">
			{#if content}
				<button onclick={copyToClipboard}
					class="px-2 py-1 text-[9px] font-black uppercase flex items-center gap-1 transition-colors"
					style="background: {copied ? '#007518' : 'transparent'}; color: {copied ? 'white' : '#feffd6'}; border: 1px solid #feffd6;">
					<span class="material-symbols-outlined text-xs">{copied ? 'check' : 'content_copy'}</span>
					{copied ? 'COPIED' : 'COPY'}
				</button>
				<button onclick={() => generate(true)}
					class="px-2 py-1 text-[9px] font-black uppercase flex items-center gap-1"
					style="color: #feffd6; border: 1px solid #feffd6;"
					disabled={loading}>
					<span class="material-symbols-outlined text-xs">refresh</span> REFRESH
				</button>
			{/if}
			{#if !content && !loading}
				<button onclick={() => generate(false)}
					class="px-3 py-1.5 text-[10px] font-black uppercase flex items-center gap-1 transition-colors hover:opacity-90"
					style="background: #00fc40; color: #383832;">
					<span class="material-symbols-outlined text-sm">psychology</span> ASK AI
				</button>
			{/if}
		</div>
	</div>

	{#if loading}
		<div class="px-4 py-6 text-center">
			<div class="inline-flex items-center gap-3">
				<div class="animate-spin h-5 w-5 border-2 border-t-transparent rounded-full" style="border-color: #383832; border-top-color: transparent;"></div>
				<span class="text-sm font-bold uppercase" style="color: #383832;">Generating AI Analysis...</span>
			</div>
			<p class="text-[10px] mt-2" style="color: #65655e;">Analyzing your data. This takes 5-10 seconds on first load.</p>
		</div>
	{:else if error}
		<div class="px-4 py-4 text-center">
			<span class="material-symbols-outlined text-xl" style="color: #be2d06;">error</span>
			<p class="text-xs font-bold mt-1" style="color: #be2d06;">{error}</p>
			<button onclick={() => generate(false)} class="mt-2 px-3 py-1 text-[10px] font-black uppercase" style="background: #383832; color: #feffd6;">RETRY</button>
		</div>
	{:else if content}
		<div class="px-4 py-4 text-xs leading-relaxed" style="color: #383832;">
			{@html formatContent(content)}
		</div>
		<div class="px-4 py-1.5 flex items-center justify-between text-[9px]" style="background: #f6f4e9; border-top: 1px solid #ebe8dd; color: #9d9d91;">
			<span>Cached locally | Click REFRESH for new analysis</span>
			<span>{timestamp}</span>
		</div>
	{:else}
		<div class="px-4 py-4 text-center">
			<span class="material-symbols-outlined text-2xl" style="color: #ebe8dd;">psychology</span>
			<p class="text-[10px] mt-1" style="color: #9d9d91;">Click ASK AI to generate analysis</p>
		</div>
	{/if}
</div>
