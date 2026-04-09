<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import Chart from '$lib/components/Chart.svelte';
	import { lineChart, barChart, pieChart } from '$lib/charts';

	interface ToolCall { tool: string; preview: string }
	interface Message { role: 'user' | 'assistant'; content: string; tools?: ToolCall[]; thinking?: boolean }

	let messages: Message[] = $state([]);
	let input = $state('');
	let loading = $state(false);
	let ws: WebSocket | null = $state(null);
	let connected = $state(false);
	let chatEnd: HTMLDivElement;
	let expandedTools: Set<number> = $state(new Set());
	let thinkingDots = $state('');
	let thinkingTools: string[] = $state([]);

	const suggestions = [
		{ icon: '⛽', text: 'Which sites have less than 3 days of fuel left?' },
		{ icon: '📊', text: 'What is the BCP score for the CMHL sector?' },
		{ icon: '🔧', text: 'Are there any generator efficiency anomalies?' },
		{ icon: '💰', text: 'What is the fuel price forecast for next week?' },
		{ icon: '🚚', text: 'Show delivery queue for critical sites' },
		{ icon: '📈', text: 'Compare diesel cost vs sales across sectors' },
	];

	let thinkingInterval: any;

	onMount(async () => {
		try {
			const history = await api.get('/chat/history');
			if (Array.isArray(history) && history.length > 0) {
				messages = history.map((m: any) => ({
					role: m.role,
					content: m.content,
					tools: m.tools || [],
				}));
			}
		} catch {}
		connect();
		return () => { ws?.close(); clearInterval(thinkingInterval); };
	});

	function startThinking() {
		let dots = 0;
		const phrases = ['Analyzing data', 'Querying database', 'Running models', 'Generating insights', 'Preparing response'];
		let phraseIdx = 0;
		thinkingDots = phrases[0];
		thinkingInterval = setInterval(() => {
			dots = (dots + 1) % 4;
			if (dots === 0) phraseIdx = (phraseIdx + 1) % phrases.length;
			thinkingDots = phrases[phraseIdx] + '.'.repeat(dots + 1);
		}, 500);
	}

	function stopThinking() {
		clearInterval(thinkingInterval);
		thinkingDots = '';
		thinkingTools = [];
	}

	function connect() {
		const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
		const host = window.location.host;
		const apiBase = import.meta.env.VITE_API_BASE;
		const wsUrl = apiBase ? apiBase.replace(/^http/, 'ws') + '/ws/chat' : `${proto}//${host}/api/ws/chat`;
		const token = localStorage.getItem('token');
		const separator = wsUrl.includes('?') ? '&' : '?';
		ws = new WebSocket(token ? `${wsUrl}${separator}token=${token}` : wsUrl);
		ws.onopen = () => { connected = true; };
		ws.onmessage = (e) => {
			const data = JSON.parse(e.data);
			if (data.type === 'thinking') {
				// Real-time progress from backend
				if (data.step === 'tool') {
					thinkingDots = `Calling ${data.tool}...`;
					thinkingTools = [...thinkingTools, data.tool];
				} else if (data.step === 'llm') {
					thinkingDots = data.turn > 1 ? `Analyzing results (step ${data.turn})...` : 'Thinking...';
				}
				setTimeout(() => chatEnd?.scrollIntoView({ behavior: 'smooth' }), 50);
			} else if (data.type === 'message') {
				messages = [...messages, {
					role: 'assistant',
					content: data.content,
					tools: data.tools || [],
				}];
				loading = false;
				stopThinking();
				setTimeout(() => chatEnd?.scrollIntoView({ behavior: 'smooth' }), 50);
			} else if (data.type === 'error') {
				messages = [...messages, { role: 'assistant', content: `Error: ${data.content}` }];
				loading = false;
				stopThinking();
				setTimeout(() => chatEnd?.scrollIntoView({ behavior: 'smooth' }), 50);
			}
		};
		ws.onclose = () => { connected = false; stopThinking(); };
		ws.onerror = () => { connected = false; loading = false; stopThinking(); };
	}

	function send(text?: string) {
		const msg = text || input.trim();
		if (!msg || !ws || ws.readyState !== WebSocket.OPEN) return;
		messages = [...messages, { role: 'user', content: msg }];
		ws.send(msg);
		input = '';
		loading = true;
		startThinking();
		setTimeout(() => chatEnd?.scrollIntoView({ behavior: 'smooth' }), 50);
	}

	async function clearChat() {
		try { await api.delete('/chat/history'); } catch {}
		messages = [];
		expandedTools = new Set();
		ws?.close();
		setTimeout(connect, 300);
	}

	function toggleTools(idx: number) {
		const next = new Set(expandedTools);
		if (next.has(idx)) next.delete(idx); else next.add(idx);
		expandedTools = next;
	}

	function handleKey(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
	}

	interface ChatChart {
		title: string;
		xAxis: string[];
		series: { name: string; data: number[]; type?: string; color?: string }[];
	}

	function parseCharts(text: string): { segments: { type: 'text' | 'chart'; content: string; chart?: any }[] } {
		const segments: { type: 'text' | 'chart'; content: string; chart?: any }[] = [];
		const chartRegex = /```chart\s*\n([\s\S]*?)\n```/g;
		let lastIndex = 0;
		let match;

		while ((match = chartRegex.exec(text)) !== null) {
			// Text before chart
			if (match.index > lastIndex) {
				segments.push({ type: 'text', content: text.slice(lastIndex, match.index) });
			}
			// Chart block
			try {
				const chartData: ChatChart = JSON.parse(match[1].trim());
				const colors = ['#007518', '#006f7c', '#be2d06', '#ff9d00', '#383832', '#9C27B0'];
				const seriesWithColors = chartData.series.map((s, i) => ({
					...s,
					color: s.color || colors[i % colors.length]
				}));

				let option: any;
				const chartType = chartData.series[0]?.type || 'line';
				if (chartType === 'bar') {
					option = barChart(chartData.xAxis, seriesWithColors.map(s => s.data[0] || 0), { title: chartData.title, colors: seriesWithColors.map(s => s.color || '#383832') });
					// Override for grouped bar if multiple series
					if (seriesWithColors.length > 1) {
						option = {
							title: { text: chartData.title, left: 'center', textStyle: { fontFamily: 'Space Grotesk, monospace', fontWeight: 900, fontSize: 13, color: '#383832' } },
							tooltip: { trigger: 'axis' },
							legend: { bottom: 0, textStyle: { fontFamily: 'Space Grotesk', fontSize: 10 } },
							grid: { top: 40, right: 20, bottom: 40, left: 50 },
							xAxis: { type: 'category', data: chartData.xAxis, axisLabel: { fontFamily: 'Space Grotesk', fontSize: 10 } },
							yAxis: { type: 'value', axisLabel: { fontFamily: 'Space Grotesk', fontSize: 10 } },
							series: seriesWithColors.map(s => ({ name: s.name, type: 'bar', data: s.data, itemStyle: { color: s.color } }))
						};
					}
				} else if (chartType === 'pie') {
					option = {
						title: { text: chartData.title, left: 'center', textStyle: { fontFamily: 'Space Grotesk, monospace', fontWeight: 900, fontSize: 13, color: '#383832' } },
						tooltip: { trigger: 'item' },
						series: [{ type: 'pie', radius: ['40%', '70%'], data: chartData.xAxis.map((label, i) => ({ name: label, value: seriesWithColors[0]?.data[i] || 0 })), itemStyle: { borderColor: '#fff', borderWidth: 2 } }]
					};
				} else {
					// Line chart
					option = lineChart(
						chartData.xAxis,
						seriesWithColors.map(s => ({ name: s.name, data: s.data, color: s.color || '#383832' })),
						{ title: chartData.title }
					);
				}

				segments.push({ type: 'chart', content: '', chart: option });
			} catch {
				// If JSON parse fails, treat as text
				segments.push({ type: 'text', content: match[0] });
			}
			lastIndex = match.index + match[0].length;
		}

		// Remaining text after last chart
		if (lastIndex < text.length) {
			segments.push({ type: 'text', content: text.slice(lastIndex) });
		}

		// If no charts found, return whole text as single segment
		if (segments.length === 0) {
			segments.push({ type: 'text', content: text });
		}

		return { segments };
	}

	function renderMarkdown(text: string): string {
		// First, extract and convert markdown tables
		const lines = text.split('\n');
		const result: string[] = [];
		let i = 0;
		while (i < lines.length) {
			// Detect table: line with | and next line is separator |---|
			if (lines[i].trim().startsWith('|') && i + 1 < lines.length && /^\|[\s:*-]+\|/.test(lines[i + 1].trim())) {
				// Parse header
				const headers = lines[i].split('|').filter(c => c.trim()).map(c => c.trim());
				i += 2; // skip header + separator
				const rows: string[][] = [];
				while (i < lines.length && lines[i].trim().startsWith('|')) {
					rows.push(lines[i].split('|').filter(c => c.trim()).map(c => c.trim()));
					i++;
				}
				// Build HTML table
				let table = '<div class="overflow-x-auto my-3"><table class="w-full text-xs" style="border: 2px solid #383832; border-collapse: collapse;">';
				table += '<thead><tr style="background: #383832;">';
				for (const h of headers) {
					table += `<th class="px-3 py-2 text-left font-black uppercase tracking-wider" style="color: #feffd6; border: 1px solid #383832;">${h}</th>`;
				}
				table += '</tr></thead><tbody>';
				for (let ri = 0; ri < rows.length; ri++) {
					const bg = ri % 2 === 0 ? '#feffd6' : '#f6f4e0';
					table += `<tr style="background: ${bg};">`;
					for (const cell of rows[ri]) {
						// Color code numbers that look like buffer days
						let cellHtml = cell;
						table += `<td class="px-3 py-1.5" style="color: #383832; border: 1px solid #ebe8dd;">${cellHtml}</td>`;
					}
					table += '</tr>';
				}
				table += '</tbody></table></div>';
				result.push(table);
			} else {
				result.push(lines[i]);
				i++;
			}
		}

		// Now apply inline formatting
		return result.join('\n')
			.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
			.replace(/\*(.+?)\*/g, '<em>$1</em>')
			.replace(/`(.+?)`/g, '<code class="px-1 py-0.5 text-[11px]" style="background: #ebe8dd; color: #383832; border-radius: 3px;">$1</code>')
			.replace(/^#{3}\s+(.+)$/gm, '<div class="font-black text-sm mt-3 mb-1" style="color: #383832;">$1</div>')
			.replace(/^#{2}\s+(.+)$/gm, '<div class="font-black text-base mt-4 mb-2" style="color: #383832; border-bottom: 2px solid #383832; padding-bottom: 4px;">$1</div>')
			.replace(/^#{1}\s+(.+)$/gm, '<div class="font-black text-lg mt-4 mb-2" style="color: #383832;">$1</div>')
			.replace(/^[•●]\s*/gm, '<span style="color: #007518; font-weight: bold;">▸ </span>')
			.replace(/^- /gm, '<span style="color: #007518; font-weight: bold;">▸ </span>')
			.replace(/^(\d+)\.\s/gm, '<span class="font-bold" style="color: #383832;">$1.</span> ')
			.replace(/🔴/g, '<span style="color: #be2d06;">●</span>')
			.replace(/🟠/g, '<span style="color: #ff9d00;">●</span>')
			.replace(/🟡/g, '<span style="color: #ff9d00;">●</span>')
			.replace(/🟢/g, '<span style="color: #007518;">●</span>')
			.replace(/\n/g, '<br/>');
	}
</script>

<div class="flex flex-col h-[calc(100vh-120px)]">
	<!-- Header -->
	<div class="flex items-center justify-between px-6 py-3" style="background: #383832; border-bottom: 2px solid #383832;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-xl" style="color: #00fc40;">psychology</span>
			<div>
				<span class="text-sm font-black uppercase" style="color: #feffd6;">BCP AI ASSISTANT</span>
				<span class="text-[9px] ml-2 px-2 py-0.5 font-bold uppercase" style="background: {connected ? '#007518' : '#be2d06'}; color: white;">{connected ? 'ONLINE' : 'OFFLINE'}</span>
			</div>
		</div>
		{#if messages.length > 0}
			<button onclick={clearChat}
				class="text-[10px] font-black uppercase px-3 py-1 flex items-center gap-1 transition-colors hover:opacity-80"
				style="background: transparent; color: #feffd6; border: 1px solid #65655e;">
				<span class="material-symbols-outlined text-xs">delete</span> CLEAR
			</button>
		{/if}
	</div>

	<!-- Messages -->
	<div class="flex-1 overflow-y-auto px-4 py-4 space-y-4" style="background: #f6f4e9;">
		{#if messages.length === 0}
			<div class="flex flex-col items-center justify-center py-12">
				<div class="w-16 h-16 flex items-center justify-center mb-4" style="background: #383832; border-radius: 50%; box-shadow: 3px 3px 0px 0px #383832;">
					<span class="material-symbols-outlined text-3xl" style="color: #00fc40;">psychology</span>
				</div>
				<h2 class="text-xl font-black uppercase mb-1" style="color: #383832;">BCP AI ASSISTANT</h2>
				<p class="text-xs mb-8" style="color: #65655e;">Ask about fuel, generators, costs, predictions, and more</p>

				<div class="w-full max-w-2xl">
					<div class="text-[10px] font-black uppercase mb-3 px-1" style="color: #65655e;">TRY ASKING</div>
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
						{#each suggestions as chip}
							<button
								class="text-left px-4 py-3 text-xs transition-all hover:scale-[1.02]"
								style="background: #feffd6; border: 2px solid #383832; box-shadow: 2px 2px 0px 0px #383832; color: #383832; cursor: pointer;"
								onclick={() => send(chip.text)}
							>
								<span class="text-base mr-2">{chip.icon}</span>
								<span class="font-bold">{chip.text}</span>
							</button>
						{/each}
					</div>
				</div>
			</div>
		{/if}

		{#each messages as msg, idx}
			{#if msg.role === 'user'}
				<!-- User message -->
				<div class="flex justify-end">
					<div class="max-w-[70%] flex items-start gap-2">
						<div class="px-4 py-2.5 text-sm" style="background: #383832; color: #feffd6; border-radius: 12px 12px 0 12px;">
							{msg.content}
						</div>
					</div>
				</div>
			{:else}
				<!-- Assistant message -->
				<div class="flex justify-start">
					<div class="max-w-[80%] flex items-start gap-2">
						<div class="w-7 h-7 flex items-center justify-center shrink-0 mt-1" style="background: #007518; border-radius: 50%;">
							<span class="material-symbols-outlined text-sm" style="color: white;">psychology</span>
						</div>
						<div>
							<div class="px-4 py-3 text-sm leading-relaxed" style="background: white; color: #383832; border: 1px solid #ebe8dd; border-radius: 0 12px 12px 12px;">
								{#each parseCharts(msg.content).segments as seg}
									{#if seg.type === 'chart' && seg.chart}
										<div class="my-3" style="border: 2px solid #383832; border-radius: 8px; overflow: hidden;">
											<Chart option={seg.chart} height="280px" />
										</div>
									{:else}
										{@html renderMarkdown(seg.content)}
									{/if}
								{/each}
							</div>

							{#if msg.tools && msg.tools.length > 0}
								<button onclick={() => toggleTools(idx)}
									class="mt-1.5 text-[9px] font-bold uppercase flex items-center gap-1 px-2 py-0.5 transition-colors"
									style="color: #006f7c; background: {expandedTools.has(idx) ? '#ebe8dd' : 'transparent'}; border-radius: 4px;">
									<span class="material-symbols-outlined text-xs">build</span>
									{msg.tools.length} tool{msg.tools.length > 1 ? 's' : ''} used
									<span class="text-[8px]">{expandedTools.has(idx) ? '▲' : '▼'}</span>
								</button>

								{#if expandedTools.has(idx)}
									<div class="mt-1 px-3 py-2 space-y-1.5" style="background: #ebe8dd; border-radius: 8px;">
										{#each msg.tools as t}
											<div class="text-[10px] flex items-center gap-2">
												<span class="material-symbols-outlined text-xs" style="color: #006f7c;">terminal</span>
												<span class="font-bold" style="color: #006f7c;">{t.tool}</span>
												{#if t.preview}
													<span class="font-mono opacity-50 truncate" style="color: #383832;">{t.preview}</span>
												{/if}
											</div>
										{/each}
									</div>
								{/if}
							{/if}
						</div>
					</div>
				</div>
			{/if}
		{/each}

		<!-- Thinking animation -->
		{#if loading}
			<div class="flex justify-start">
				<div class="max-w-[80%] flex items-start gap-2">
					<div class="w-7 h-7 flex items-center justify-center shrink-0 mt-1 animate-pulse" style="background: #007518; border-radius: 50%;">
						<span class="material-symbols-outlined text-sm" style="color: white;">psychology</span>
					</div>
					<div class="px-4 py-3" style="background: white; border: 1px solid #ebe8dd; border-radius: 0 12px 12px 12px;">
						<div class="flex items-center gap-3">
							<div class="flex gap-1">
								<div class="w-2 h-2 rounded-full animate-bounce" style="background: #007518; animation-delay: 0ms;"></div>
								<div class="w-2 h-2 rounded-full animate-bounce" style="background: #ff9d00; animation-delay: 150ms;"></div>
								<div class="w-2 h-2 rounded-full animate-bounce" style="background: #be2d06; animation-delay: 300ms;"></div>
							</div>
							<span class="text-xs font-medium" style="color: #65655e;">{thinkingDots}</span>
						</div>
						{#if thinkingTools.length > 0}
							<div class="mt-2 pt-2 space-y-1" style="border-top: 1px solid #ebe8dd;">
								{#each thinkingTools as t, i}
									<div class="flex items-center gap-1.5 text-[10px]">
										<span class="material-symbols-outlined text-xs" style="color: {i === thinkingTools.length - 1 ? '#ff9d00' : '#007518'};">{i === thinkingTools.length - 1 ? 'pending' : 'check_circle'}</span>
										<span class="font-bold" style="color: #006f7c;">{t}</span>
										<span style="color: {i === thinkingTools.length - 1 ? '#ff9d00' : '#007518'}; font-weight: bold;">{i === thinkingTools.length - 1 ? 'running...' : 'done'}</span>
									</div>
								{/each}
							</div>
						{/if}
					</div>
				</div>
			</div>
		{/if}

		<div bind:this={chatEnd}></div>
	</div>

	<!-- Input area -->
	<div class="px-4 py-3" style="background: white; border-top: 2px solid #383832;">
		<div class="flex gap-2 max-w-4xl mx-auto items-end">
			<div class="flex-1 relative">
				<textarea
					bind:value={input}
					onkeydown={handleKey}
					rows="1"
					placeholder={connected ? "Ask about fuel, blackouts, costs, predictions..." : "Reconnecting..."}
					disabled={!connected}
					class="w-full px-4 py-3 pr-12 text-sm resize-none focus:outline-none disabled:opacity-50"
					style="background: #f6f4e9; border: 2px solid #383832; color: #383832; border-radius: 8px; min-height: 44px; max-height: 120px;"
				/>
			</div>
			<button
				onclick={() => send()}
				disabled={loading || !input.trim() || !connected}
				class="px-4 py-3 font-black uppercase text-sm transition-all disabled:opacity-30 flex items-center gap-1"
				style="background: #007518; color: white; border: 2px solid #383832; border-radius: 8px;"
			>
				<span class="material-symbols-outlined text-sm">send</span>
			</button>
		</div>
	</div>
</div>

<style>
	@keyframes bounce {
		0%, 100% { transform: translateY(0); }
		50% { transform: translateY(-6px); }
	}
	.animate-bounce {
		animation: bounce 0.6s ease-in-out infinite;
	}
</style>
