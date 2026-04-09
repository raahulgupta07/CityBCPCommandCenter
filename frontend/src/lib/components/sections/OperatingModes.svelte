<script lang="ts">
	import { api, downloadExcel } from '$lib/api';
	import { onMount } from 'svelte';
	import InfoTip from '$lib/components/InfoTip.svelte';
	import { KPI } from '$lib/kpi-definitions';

	let { sector = '', company = 'All', siteType = 'All', sites = [] as string[] }: { sector?: string; company?: string; siteType?: string; sites?: string[] } = $props();

	let modes: any[] = $state([]);
	let queue: any[] = $state([]);
	let generators: any[] = $state([]);
	let transfers: any[] = $state([]);
	let loadOpt: any[] = $state([]);
	let anomalies: any[] = $state([]);
	let loading = $state(true);
	let error = $state('');

	const modeSeverity: Record<string, number> = { CLOSE: 0, REDUCE: 1, MONITOR: 2, FULL: 3 };
	const modeColors: Record<string, string> = {
		FULL: '#007518',
		MONITOR: '#ff9d00',
		REDUCE: '#f95630',
		CLOSE: '#be2d06'
	};
	const urgencyColors: Record<string, string> = {
		HIGH: '#be2d06',
		MEDIUM: '#ff9d00',
		MED: '#ff9d00',
		LOW: '#007518'
	};

	let sortedModes = $derived(
		[...modes].sort(
			(a, b) => (modeSeverity[a.mode] ?? 99) - (modeSeverity[b.mode] ?? 99)
		)
	);

	let sortedQueue = $derived(
		[...queue].sort((a, b) => (a.days_left ?? a.days_of_buffer ?? 999) - (b.days_left ?? b.days_of_buffer ?? 999))
	);

	let urgentCount = $derived(
		queue.filter((q) => (q.urgency || '').toUpperCase() === 'HIGH').length
	);

	const riskSeverity: Record<string, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };

	let sortedGenerators = $derived(
		[...generators].sort(
			(a, b) =>
				(riskSeverity[(a.risk_level || '').toUpperCase()] ?? 99) -
				(riskSeverity[(b.risk_level || '').toUpperCase()] ?? 99)
		)
	);

	let highRiskCount = $derived(
		generators.filter((g) => (g.risk_level || '').toUpperCase() === 'HIGH').length
	);

	let fullCount = $derived(modes.filter(m => (m.mode || '').toUpperCase() === 'FULL').length);
	let monitorCount = $derived(modes.filter(m => (m.mode || '').toUpperCase() === 'MONITOR').length);
	let reducedCount = $derived(modes.filter(m => ['REDUCE', 'REDUCED'].includes((m.mode || '').toUpperCase())).length);
	let closeCount = $derived(modes.filter(m => (m.mode || '').toUpperCase() === 'CLOSE').length);
	let noDataCount = $derived(modes.filter(m => !m.mode || (m.mode || '').toUpperCase() === 'NO DATA').length);
	let totalModes = $derived(modes.length || 1);

	let totalLitersNeeded = $derived(queue.reduce((s: number, q: any) => s + (q.liters_needed ?? 0), 0));
	let totalEstCost = $derived(queue.reduce((s: number, q: any) => s + (q.est_cost ?? 0), 0));
	let qCritical = $derived(queue.filter((q: any) => (q.urgency || '').toUpperCase() === 'CRITICAL').length);
	let qHigh = $derived(queue.filter((q: any) => (q.urgency || '').toUpperCase() === 'HIGH').length);
	let qMedium = $derived(queue.filter((q: any) => (q.urgency || '').toUpperCase() === 'MEDIUM').length);
	let qLow = $derived(queue.filter((q: any) => (q.urgency || '').toUpperCase() === 'LOW').length);

	let genLow = $derived(generators.filter((g: any) => (g.risk_level || '').toUpperCase() === 'LOW').length);
	let genMed = $derived(generators.filter((g: any) => (g.risk_level || '').toUpperCase() === 'MEDIUM').length);
	let genHigh = $derived(generators.filter((g: any) => (g.risk_level || '').toUpperCase() === 'HIGH').length);
	let genCrit = $derived(generators.filter((g: any) => (g.risk_level || '').toUpperCase() === 'CRITICAL').length);
	let runningGens = $derived(generators.filter((g: any) => (g.avg_daily_hours ?? 0) > 0).length);

	let avgHoursUntilService = $derived(
		generators.length > 0
			? generators.reduce((s: number, g: any) => s + (g.hours_until_service ?? 0), 0) / generators.length
			: 0
	);

	let top15LoadOpt = $derived([...loadOpt].sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999)).slice(0, 15));

	let anomalyCount = $derived(anomalies.length);

	let highAnomalies = $derived(
		anomalies.filter((a) => (a.pct_above ?? 0) > 30)
	);

	async function load() {
		loading = true;
		error = '';
		const s = sector ? `?sector=${sector}` : '';
		const tp = siteType !== 'All' ? `${s ? '&' : '?'}site_type=${siteType}` : '';
		try {
			const [m, d] = await Promise.all([
				api.get(`/operating-modes${s}${tp}`).catch(() => []),
				api.get(`/delivery-queue${s}${tp}`).catch(() => []),
			]);
			modes = Array.isArray(m) ? m : m.modes || [];
			queue = Array.isArray(d) ? d : d.queue || [];
		} catch (e) {
			console.error(e);
			error = 'Failed to load operations data. Check your connection and try again.';
		}
		try {
			const [g, t, a] = await Promise.all([
				api.get(`/generator-risk${s}${tp}`).catch(() => ({ generators: [] })),
				api.get(`/transfers${s}${tp}`).catch(() => ({ transfers: [], load_optimization: [] })),
				api.get(`/anomalies${s}${tp}`).catch(() => ({ anomalies: [] })),
			]);
			generators = g.generators || [];
			transfers = Array.isArray(t.transfers) ? t.transfers : [];
			loadOpt = t.load_optimization || [];
			anomalies = a.anomalies || [];
		} catch {}
		loading = false;
	}

	let prevSector = '';
	let prevSiteType = '';
	onMount(() => { prevSector = sector; prevSiteType = siteType; load(); });
	$effect(() => {
		if (sector !== prevSector || siteType !== prevSiteType) {
			prevSector = sector;
			prevSiteType = siteType;
			load();
		}
	});

	const siteFilteredModes = $derived(sites.length > 0 ? sortedModes.filter(r => sites.includes(r.site_id)) : sortedModes);
	const siteFilteredQueue = $derived(sites.length > 0 ? sortedQueue.filter(r => sites.includes(r.site_id)) : sortedQueue);
	const siteFilteredGenerators = $derived(sites.length > 0 ? sortedGenerators.filter(r => sites.includes(r.site_id)) : sortedGenerators);
	const siteFilteredTransfers = $derived(sites.length > 0 ? transfers.filter(r => sites.includes(r.site_id)) : transfers);
	const siteFilteredLoadOpt = $derived(sites.length > 0 ? loadOpt.filter(r => sites.includes(r.site_id)) : loadOpt);
	const siteFilteredAnomalies = $derived(sites.length > 0 ? anomalies.filter(r => sites.includes(r.site_id)) : anomalies);

	let search = $state('');
	const matchSearch = (r: any) => Object.values(r).some(v => String(v).toLowerCase().includes(search.toLowerCase()));
	const filteredModes = $derived(search ? siteFilteredModes.filter(matchSearch) : siteFilteredModes);
	const filteredQueue = $derived(search ? siteFilteredQueue.filter(matchSearch) : siteFilteredQueue);
	const filteredGenerators = $derived(search ? siteFilteredGenerators.filter(matchSearch) : siteFilteredGenerators);
	const filteredTransfers = $derived(search ? siteFilteredTransfers.filter(matchSearch) : siteFilteredTransfers);
	const filteredLoadOpt = $derived(search ? siteFilteredLoadOpt.filter(matchSearch) : siteFilteredLoadOpt);
	const filteredAnomalies = $derived(search ? siteFilteredAnomalies.filter(matchSearch) : siteFilteredAnomalies);

	// Pagination for Operating Modes table
	let modesPage = $state(1);
	const modesPageSize = 15;
	const modesTotalPages = $derived(Math.ceil(filteredModes.length / modesPageSize));
	const paginatedModes = $derived(filteredModes.slice((modesPage - 1) * modesPageSize, modesPage * modesPageSize));

	// Pagination for Delivery Queue table
	let queuePage = $state(1);
	const queuePageSize = 15;
	const queueTotalPages = $derived(Math.ceil(filteredQueue.length / queuePageSize));
	const paginatedQueue = $derived(filteredQueue.slice((queuePage - 1) * queuePageSize, queuePage * queuePageSize));

	// Reset pages when search changes
	$effect(() => { search; modesPage = 1; queuePage = 1; });

	function fmt(v: any): string {
		if (v == null || v === '' || v === undefined) return '—';
		const n = Number(v);
		if (isNaN(n)) return String(v);
		if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
		if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
		return n.toLocaleString();
	}

	function badgeStyle(color: string): string {
		return `background: ${color}; color: white; padding: 2px 10px; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase;`;
	}
</script>


{#if error}
	<div class="text-center py-4" style="background: #f6f4e9; border: 2px solid #383832;">
		<p class="font-bold uppercase text-sm" style="color: #be2d06;">{error}</p>
		<button onclick={load} class="mt-2 px-4 py-1 text-xs font-black uppercase" style="background: #383832; color: #feffd6;">RETRY</button>
	</div>
{:else}
	<!-- Search Bar -->
	<div class="px-3 py-2 flex items-center gap-2" style="background: #ebe8dd; border-bottom: 1px solid #383832; margin-bottom: 1rem; border: 2px solid #383832;">
		<span class="material-symbols-outlined text-sm" style="color: #65655e;">search</span>
		<input type="text" bind:value={search} placeholder="QUICK_SEARCH..."
			class="flex-1 px-2 py-1 text-xs font-mono uppercase"
			style="background: white; border: 1px solid #383832; color: #383832;" />
	</div>

	<!-- ============================================================ -->
	<!-- SECTION 1: Operating Modes -->
	<div id="ops-modes" class="scroll-mt-36 px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">toggle_on</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 1: OPERATING MODES</div>
				<div class="text-[10px] opacity-75">Should each site stay OPEN, MONITOR, REDUCE hours, or CLOSE?</div>
			</div>
		</div>
		<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which sites should reduce generator hours? Who should close?</div>
	</div>
	<div style="margin-bottom: 1.5rem;">
		<!-- KPI Card (chart style) -->
		<div class="mb-3" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
				<span class="text-[11px] font-black uppercase">OPERATING MODES</span>
				<span class="text-[10px] font-bold">{modes.length} SITES</span>
				<InfoTip {...KPI.operations.operatingModes} />
			</div>
			<div class="flex">
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #007518;">{fullCount}</div>
					<div class="text-[9px] font-bold" style="color: #007518;">FULL OPS</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #ff9d00;">{monitorCount + reducedCount}</div>
					<div class="text-[9px] font-bold" style="color: #ff9d00;">REDUCE</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #be2d06;">{closeCount}</div>
					<div class="text-[9px] font-bold" style="color: #be2d06;">CLOSE</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1;">
					<div class="text-2xl font-black" style="color: #65655e;">{noDataCount}</div>
					<div class="text-[9px] font-bold" style="color: #65655e;">NO DATA</div>
				</div>
			</div>
			<div style="border-top: 1px solid #ebe8dd;">
				{#each [
					{ label: 'FULL', count: fullCount, color: '#007518' },
					{ label: 'MONITOR', count: monitorCount, color: '#d97706' },
					{ label: 'REDUCE', count: reducedCount, color: '#ff9d00' },
					{ label: 'CLOSE', count: closeCount, color: '#be2d06' },
					{ label: 'NO DATA', count: noDataCount, color: '#65655e' },
				] as bar}
					{#if bar.count > 0}
						<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid rgba(56,56,50,0.08);">
							<span class="text-[9px] w-16 shrink-0 font-bold" style="color: {bar.color};">{bar.label}</span>
							<div class="flex-1 h-4" style="background: #f0ede3;">
								<div class="h-full" style="width: {bar.count / totalModes * 100}%; background: {bar.color};"></div>
							</div>
							<span class="text-[9px] w-6 text-right shrink-0 font-black" style="color: #383832;">{bar.count}</span>
						</div>
					{/if}
				{/each}
			</div>
			<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">energy% &divide; sales threshold</div>
		</div>

		<!-- Table -->
		<div style="background: #feffd6; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<div class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between" style="background: #383832; color: #feffd6;">
				<span>OPERATING_MODES</span>
				<div class="flex items-center gap-3">
					<button onclick={() => downloadExcel(sortedModes, 'Operating Modes', { statusColumns: ['mode'] })}
						class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100" style="color: #00fc40;">
						<span class="material-symbols-outlined text-sm">download</span> EXCEL
					</button>
					<span class="text-xs font-bold px-2 py-0.5" style="background: #feffd6; color: #383832;">
						{sortedModes.length} SITES
					</span>
				</div>
			</div>

			{#if sortedModes.length === 0}
				<div class="p-4 text-center text-sm" style="color: #65655e;">No operating mode data available.</div>
			{:else}
				<div style="overflow-x: auto; overflow-y: auto; max-height: 500px;">
					<table style="width: 100%; border-collapse: collapse; font-size: 0.75rem;">
						<thead>
							<tr style="background: #ebe8dd;">
								<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SITE</th>
								<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SECTOR</th>
								<th class="font-black uppercase text-center px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">MODE</th>
								<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">BUFFER</th>
								<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">TANK</th>
								<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">FUEL</th>
								<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">GEN HR</th>
								<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">ENERGY%</th>
								<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SALES</th>
								<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">REASON</th>
							</tr>
						</thead>
						<tbody>
							{#each paginatedModes as row, i}
								{@const rowIdx = (modesPage - 1) * modesPageSize + i}
								{@const bufferDays = row.days_of_buffer ?? 0}
								{@const bufferColor = bufferDays <= 2 ? '#be2d06' : bufferDays <= 5 ? '#ff9d00' : '#007518'}
								<tr style="background: {rowIdx % 2 === 0 ? 'white' : '#f6f4e9'};">
									<td class="px-3 py-2 font-bold text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.site_id || '—'}</td>
									<td class="px-3 py-2 text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.sector_id || '—'}</td>
									<td class="px-3 py-2 text-center" style="border-bottom: 1px solid #ebe8dd;">
										<span style={badgeStyle(modeColors[row.mode] || '#65655e')}>{row.mode || '—'}</span>
									</td>
									<td class="px-3 py-2 text-right font-mono text-xs font-bold" style="border-bottom: 1px solid #ebe8dd; color: {bufferColor};">{fmt(row.days_of_buffer)}</td>
									<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.spare_tank_balance)}</td>
									<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.daily_fuel_cost ?? row.total_daily_used)}</td>
									<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.total_gen_run_hr)}</td>
									<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.energy_pct != null ? row.energy_pct.toFixed(1) + '%' : '—'}</td>
									<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.sales_revenue)}</td>
									<td class="px-3 py-2 text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832; max-width: 180px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title={row.reason || ''}>{row.reason || '—'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				{#if modesTotalPages > 1}
					<div class="px-4 py-2 flex items-center justify-between" style="background: white; border-top: 1px solid #383832;">
						<span class="text-[10px] font-mono" style="color: #65655e;">Page {modesPage} of {modesTotalPages} ({filteredModes.length} sites)</span>
						<div class="flex gap-1">
							<button onclick={() => modesPage = Math.max(1, modesPage - 1)} disabled={modesPage <= 1}
								class="px-2 py-1 text-[10px] font-black uppercase"
								style="background: {modesPage <= 1 ? '#ebe8dd' : '#383832'}; color: {modesPage <= 1 ? '#65655e' : '#feffd6'}; border: 1px solid #383832;">PREV</button>
							{#each Array(modesTotalPages) as _, p}
								<button onclick={() => modesPage = p + 1}
									class="px-2 py-1 text-[10px] font-black"
									style="background: {modesPage === p + 1 ? '#383832' : 'white'}; color: {modesPage === p + 1 ? '#feffd6' : '#383832'}; border: 1px solid #383832;">{p + 1}</button>
							{/each}
							<button onclick={() => modesPage = Math.min(modesTotalPages, modesPage + 1)} disabled={modesPage >= modesTotalPages}
								class="px-2 py-1 text-[10px] font-black uppercase"
								style="background: {modesPage >= modesTotalPages ? '#ebe8dd' : '#383832'}; color: {modesPage >= modesTotalPages ? '#65655e' : '#feffd6'}; border: 1px solid #383832;">NEXT</button>
						</div>
					</div>
				{/if}
			{/if}
		<!-- What each column means -->
		<div class="px-4 py-3" style="background: #f6f4e9; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">WHAT EACH COLUMN MEANS</div>
			<table class="w-full text-[10px]" style="border-collapse: collapse;">
				<thead>
					<tr style="background: #ebe8dd;">
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7; width: 110px;">COLUMN</th>
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7;">WHAT IT TELLS YOU</th>
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7; width: 220px;">HOW IT IS CALCULATED</th>
					</tr>
				</thead>
				<tbody>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832; width: 110px;">SITE / CODE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Site identifier and sector-store code</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e; width: 220px;">From store master reference data</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">SECTOR</td>
						<td class="py-1.5 px-2" style="color: #383832;">Business sector &mdash; CMHL, CP, CFC, or PG</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">From uploaded blackout file mapping</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">MODE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Current operating recommendation. <span class="font-bold" style="color: #007518;">FULL</span> = run normally, <span class="font-bold" style="color: #ff9d00;">MONITOR</span> = watch closely, <span class="font-bold" style="color: #f95630;">REDUCE</span> = cut generator hours, <span class="font-bold" style="color: #be2d06;">CLOSE</span> = shut down (fuel cost exceeds revenue)</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Diesel% &gt;60% &rarr; CLOSE, &gt;30% &rarr; REDUCE, &gt;15% &rarr; MONITOR, else FULL</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #be2d06;">BUFFER</td>
						<td class="py-1.5 px-2" style="color: #383832;">Days of fuel remaining. <span class="font-bold" style="color: #be2d06;">Red &lt;3 days = critical</span>, <span class="font-bold" style="color: #ff9d00;">orange 3&ndash;5 days = warning</span>, <span class="font-bold" style="color: #007518;">green &gt;5 days = OK</span></td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Tank balance &divide; average daily fuel consumption</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">TANK</td>
						<td class="py-1.5 px-2" style="color: #383832;">Current fuel in liters &mdash; how much diesel is physically in the tank right now</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Last reported spare tank balance (sum of all drums)</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">FUEL</td>
						<td class="py-1.5 px-2" style="color: #383832;">Daily fuel consumption or cost &mdash; how much diesel this site burns per day</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Daily liters used &times; date-specific diesel price</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">GEN HR</td>
						<td class="py-1.5 px-2" style="color: #383832;">Generator run hours per day &mdash; how long the generators actually ran</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Sum of all generator run hours at this site</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">ENERGY%</td>
						<td class="py-1.5 px-2" style="color: #383832;">Diesel cost as percentage of sales revenue. Lower is better &mdash; high % means fuel is eating into profits</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">(Liters &times; Price) &divide; Sales &times; 100</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">SALES</td>
						<td class="py-1.5 px-2" style="color: #383832;">Daily sales revenue &mdash; how much money this site earns per day</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">From uploaded sales data (daily total)</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">REASON</td>
						<td class="py-1.5 px-2" style="color: #383832;">Why this mode was assigned &mdash; explains the logic behind the recommendation</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Auto-generated by decision engine based on thresholds</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div class="px-4 py-2.5" style="background: white; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-1.5" style="color: #383832;">HOW TO USE THIS TABLE</div>
			<div class="text-[10px] leading-relaxed" style="color: #65655e;">
				Focus on <span class="font-bold" style="color: #f95630;">REDUCE</span> and <span class="font-bold" style="color: #be2d06;">CLOSE</span> sites first. These are burning fuel faster than they earn revenue. Check the REASON column for specific action items. <span class="font-bold" style="color: #ff9d00;">MONITOR</span> sites should be watched for deterioration &mdash; if their diesel % keeps rising, they will move to REDUCE or CLOSE. <span class="font-bold" style="color: #007518;">FULL</span> sites are healthy and need no action.
			</div>
		</div>
		</div>
	</div>

	<!-- ============================================================ -->
	<!-- SECTION 2: Delivery Queue -->
	<div id="ops-delivery" class="scroll-mt-36 px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">local_shipping</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 2: FUEL DELIVERY QUEUE</div>
				<div class="text-[10px] opacity-75">Priority-ordered list of sites that need fuel delivery.</div>
			</div>
		</div>
		<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Who needs fuel first? How many liters? By when?</div>
	</div>
	<div style="margin-bottom: 1.5rem;">
		<!-- KPI Card (chart style) -->
		<div class="mb-3" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
				<span class="text-[11px] font-black uppercase">DELIVERY QUEUE</span>
				<span class="text-[10px] font-bold">{queue.length} PENDING</span>
				<InfoTip {...KPI.operations.deliveryQueue} />
			</div>
			<div class="flex">
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #be2d06;">{urgentCount}</div>
					<div class="text-[9px] font-bold" style="color: #be2d06;">URGENT</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #383832;">{fmt(totalLitersNeeded)}</div>
					<div class="text-[9px] font-bold" style="color: #65655e;">LITERS</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1;">
					<div class="text-2xl font-black" style="color: #383832;">{fmt(totalEstCost)}</div>
					<div class="text-[9px] font-bold" style="color: #65655e;">EST COST</div>
				</div>
			</div>
			<div style="border-top: 1px solid #ebe8dd;">
				{#each [
					{ label: 'CRITICAL', count: qCritical, color: '#be2d06' },
					{ label: 'HIGH', count: qHigh, color: '#e85d04' },
					{ label: 'MEDIUM', count: qMedium, color: '#ff9d00' },
					{ label: 'LOW', count: qLow, color: '#65655e' },
				] as bar}
					{#if bar.count > 0}
						<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid rgba(56,56,50,0.08);">
							<span class="text-[9px] w-16 shrink-0 font-bold" style="color: {bar.color};">{bar.label}</span>
							<div class="flex-1 h-4" style="background: #f0ede3;">
								<div class="h-full" style="width: {queue.length > 0 ? (bar.count / queue.length * 100) : 0}%; background: {bar.color};"></div>
							</div>
							<span class="text-[9px] w-6 text-right shrink-0 font-black" style="color: #383832;">{bar.count}</span>
						</div>
					{/if}
				{/each}
			</div>
			<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">7d_buffer &minus; tank = liters_needed</div>
		</div>

		<!-- Table -->
		<div style="background: #feffd6; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<div class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between" style="background: #383832; color: #feffd6;">
				<span>DELIVERY_QUEUE</span>
				<div class="flex items-center gap-3">
					<button onclick={() => downloadExcel(sortedQueue, 'Delivery Queue', { statusColumns: ['urgency'] })}
						class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100" style="color: #00fc40;">
						<span class="material-symbols-outlined text-sm">download</span> EXCEL
					</button>
					<span class="text-xs font-bold px-2 py-0.5"
						style="background: {urgentCount > 0 ? '#be2d06' : '#feffd6'}; color: {urgentCount > 0 ? 'white' : '#383832'};">
						{queue.length} PENDING
					</span>
				</div>
			</div>

			{#if sortedQueue.length === 0}
				<div class="p-4 text-center text-sm" style="color: #65655e;">No deliveries pending.</div>
			{:else}
				<div style="overflow-x: auto; overflow-y: auto; max-height: 500px;">
					<table style="width: 100%; border-collapse: collapse; font-size: 0.75rem;">
						<thead>
							<tr style="background: #ebe8dd;">
								<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SITE</th>
								<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SECTOR</th>
								<th class="font-black uppercase text-center px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">URGENCY</th>
								<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">BUFFER</th>
								<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">TANK</th>
								<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">LITERS NEEDED</th>
								<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">DELIVERY BY</th>
								<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">EST COST</th>
							</tr>
						</thead>
						<tbody>
							{#each paginatedQueue as row, i}
								{@const rowIdx = (queuePage - 1) * queuePageSize + i}
								{@const urg = (row.urgency || '').toUpperCase()}
								<tr style="background: {rowIdx % 2 === 0 ? 'white' : '#f6f4e9'};">
									<td class="px-3 py-2 font-bold text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.site_id || '—'}</td>
									<td class="px-3 py-2 text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.sector_id || '—'}</td>
									<td class="px-3 py-2 text-center" style="border-bottom: 1px solid #ebe8dd;">
										<span style={badgeStyle(urgencyColors[urg] || '#383832')}>{urg || '—'}</span>
									</td>
									<td class="px-3 py-2 text-right font-mono text-xs font-bold"
										style="border-bottom: 1px solid #ebe8dd; color: {(row.days_of_buffer ?? 999) <= 2 ? '#be2d06' : '#383832'};">
										{fmt(row.days_of_buffer)}
									</td>
									<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.spare_tank_balance)}</td>
									<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.liters_needed)}</td>
									<td class="px-3 py-2 text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.delivery_by || '—'}</td>
									<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.est_cost)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				{#if queueTotalPages > 1}
					<div class="px-4 py-2 flex items-center justify-between" style="background: white; border-top: 1px solid #383832;">
						<span class="text-[10px] font-mono" style="color: #65655e;">Page {queuePage} of {queueTotalPages} ({filteredQueue.length} sites)</span>
						<div class="flex gap-1">
							<button onclick={() => queuePage = Math.max(1, queuePage - 1)} disabled={queuePage <= 1}
								class="px-2 py-1 text-[10px] font-black uppercase"
								style="background: {queuePage <= 1 ? '#ebe8dd' : '#383832'}; color: {queuePage <= 1 ? '#65655e' : '#feffd6'}; border: 1px solid #383832;">PREV</button>
							{#each Array(queueTotalPages) as _, p}
								<button onclick={() => queuePage = p + 1}
									class="px-2 py-1 text-[10px] font-black"
									style="background: {queuePage === p + 1 ? '#383832' : 'white'}; color: {queuePage === p + 1 ? '#feffd6' : '#383832'}; border: 1px solid #383832;">{p + 1}</button>
							{/each}
							<button onclick={() => queuePage = Math.min(queueTotalPages, queuePage + 1)} disabled={queuePage >= queueTotalPages}
								class="px-2 py-1 text-[10px] font-black uppercase"
								style="background: {queuePage >= queueTotalPages ? '#ebe8dd' : '#383832'}; color: {queuePage >= queueTotalPages ? '#65655e' : '#feffd6'}; border: 1px solid #383832;">NEXT</button>
						</div>
					</div>
				{/if}
			{/if}
		<!-- What each column means -->
		<div class="px-4 py-3" style="background: #f6f4e9; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">WHAT EACH COLUMN MEANS</div>
			<table class="w-full text-[10px]" style="border-collapse: collapse;">
				<thead>
					<tr style="background: #ebe8dd;">
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7; width: 110px;">COLUMN</th>
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7;">WHAT IT TELLS YOU</th>
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7; width: 220px;">HOW IT IS CALCULATED</th>
					</tr>
				</thead>
				<tbody>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832; width: 110px;">SITE / CODE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Which site needs fuel</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e; width: 220px;">From store master reference data</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">SECTOR</td>
						<td class="py-1.5 px-2" style="color: #383832;">Business sector &mdash; CMHL, CP, CFC, or PG</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">From uploaded blackout file mapping</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">URGENCY</td>
						<td class="py-1.5 px-2" style="color: #383832;"><span class="font-bold" style="color: #be2d06;">CRITICAL</span> (red, &lt;2 days), <span class="font-bold" style="color: #ff9d00;">HIGH</span> (orange, 2&ndash;3 days), <span class="font-bold" style="color: #e8b500;">MEDIUM</span> (yellow, 3&ndash;5 days), <span class="font-bold" style="color: #007518;">LOW</span> (green, 5&ndash;7 days)</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Based on buffer days remaining</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #be2d06;">BUFFER</td>
						<td class="py-1.5 px-2" style="color: #383832;">Current days of fuel remaining at this site</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Tank balance &divide; average daily fuel consumption</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">TANK</td>
						<td class="py-1.5 px-2" style="color: #383832;">How many liters of diesel are left in the tank</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Last reported spare tank balance</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">LITERS NEEDED</td>
						<td class="py-1.5 px-2" style="color: #383832;">How much fuel to deliver to reach a 7-day buffer &mdash; tells the tanker how much to load</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">7 &times; avg daily used &minus; current tank</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">DELIVERY BY</td>
						<td class="py-1.5 px-2" style="color: #383832;">Latest date to deliver before the site runs dry &mdash; this is your deadline</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Today + buffer days remaining</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">EST COST</td>
						<td class="py-1.5 px-2" style="color: #383832;">Estimated cost of the delivery at current diesel price</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Liters needed &times; latest diesel price per liter</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div class="px-4 py-2.5" style="background: white; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-1.5" style="color: #383832;">HOW TO USE THIS TABLE</div>
			<div class="text-[10px] leading-relaxed" style="color: #65655e;">
				This is your delivery action list. Work top-to-bottom &mdash; <span class="font-bold" style="color: #be2d06;">CRITICAL</span> sites need fuel today. LITERS NEEDED tells the tanker how much to load. DELIVERY BY is your deadline &mdash; miss it and the site goes dark. Share this table with your logistics team to coordinate tanker schedules.
			</div>
		</div>
		</div>
	</div>

	<!-- ============================================================ -->
	<!-- SECTION 3: Generator Risk -->
	<div id="ops-fleet" class="scroll-mt-36 px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">build</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 3: GENERATOR FLEET</div>
				<div class="text-[10px] opacity-75">Generator health, risk levels, and maintenance schedule.</div>
			</div>
		</div>
		<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which generators need maintenance? How many hours until service?</div>
	</div>
	{#if generators.length > 0}
	<div style="margin-bottom: 1.5rem;">
		<!-- KPI Card (chart style) -->
		<div class="mb-3" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
				<span class="text-[11px] font-black uppercase">GENERATOR FLEET</span>
				<span class="text-[10px] font-bold">{generators.length} GENERATORS</span>
				<InfoTip {...KPI.operations.generatorRisk} />
			</div>
			<div class="flex">
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #be2d06;">{highRiskCount}</div>
					<div class="text-[9px] font-bold" style="color: #be2d06;">HIGH RISK</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #383832;">{avgHoursUntilService.toFixed(0)}</div>
					<div class="text-[9px] font-bold" style="color: #65655e;">AVG HRS SVC</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1;">
					<div class="text-2xl font-black" style="color: #007518;">{runningGens}</div>
					<div class="text-[9px] font-bold" style="color: #007518;">RUNNING</div>
				</div>
			</div>
			<div style="border-top: 1px solid #ebe8dd;">
				{#each [
					{ label: 'LOW', count: genLow, color: '#007518' },
					{ label: 'MEDIUM', count: genMed, color: '#ff9d00' },
					{ label: 'HIGH', count: genHigh, color: '#e85d04' },
					{ label: 'CRITICAL', count: genCrit, color: '#be2d06' },
				] as bar}
					{#if bar.count > 0}
						<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid rgba(56,56,50,0.08);">
							<span class="text-[9px] w-16 shrink-0 font-bold" style="color: {bar.color};">{bar.label}</span>
							<div class="flex-1 h-4" style="background: #f0ede3;">
								<div class="h-full" style="width: {generators.length > 0 ? (bar.count / generators.length * 100) : 0}%; background: {bar.color};"></div>
							</div>
							<span class="text-[9px] w-6 text-right shrink-0 font-black" style="color: #383832;">{bar.count}</span>
						</div>
					{/if}
				{/each}
			</div>
			<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">hours_until_service threshold</div>
		</div>

		<!-- Table -->
		<div style="background: #feffd6; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<div class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between" style="background: #383832; color: #feffd6;">
				<span>GENERATOR_RISK</span>
				<div class="flex items-center gap-3">
					<button onclick={() => downloadExcel(sortedGenerators, 'Generator Risk', { statusColumns: ['risk_level'] })}
						class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100" style="color: #00fc40;">
						<span class="material-symbols-outlined text-sm">download</span> EXCEL
					</button>
					<span class="text-xs font-bold px-2 py-0.5"
						style="background: {highRiskCount > 0 ? '#be2d06' : '#feffd6'}; color: {highRiskCount > 0 ? 'white' : '#383832'};">
						{highRiskCount} HIGH
					</span>
				</div>
			</div>

			<div style="overflow-x: auto; overflow-y: auto; max-height: 500px;">
				<table style="width: 100%; border-collapse: collapse; font-size: 0.75rem;">
					<thead>
						<tr style="background: #ebe8dd;">
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SITE</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #65655e;">CODE</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SECTOR</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">MODEL</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">KVA</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">AVG HR/DAY</th>
							<th class="font-black uppercase text-center px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">RISK</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">HRS TO SERVICE</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">NOTE</th>
						</tr>
					</thead>
					<tbody>
						{#each filteredGenerators as row, i}
							{@const risk = (row.risk_level || '').toUpperCase()}
							<tr style="background: {i % 2 === 0 ? 'white' : '#f6f4e9'};">
								<td class="px-3 py-2 font-bold text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.site_id || '—'}</td>
								<td class="px-3 py-2 font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #65655e;">{row.site_code || ''}</td>
								<td class="px-3 py-2 text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.sector_id || '—'}</td>
								<td class="px-3 py-2 text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.model_name || row.model || '—'}</td>
								<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.power_kva)}</td>
								<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.avg_daily_hours != null ? row.avg_daily_hours.toFixed(1) : '—'}</td>
								<td class="px-3 py-2 text-center" style="border-bottom: 1px solid #ebe8dd;">
									<span style={badgeStyle(urgencyColors[risk] || '#383832')}>{risk || '—'}</span>
								</td>
								<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.hours_until_service)}</td>
								<td class="px-3 py-2 text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832; max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title={row.maintenance_note || row.note || ''}>{row.maintenance_note || row.note || '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		<!-- What each column means -->
		<div class="px-4 py-3" style="background: #f6f4e9; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">WHAT EACH COLUMN MEANS</div>
			<table class="w-full text-[10px]" style="border-collapse: collapse;">
				<thead>
					<tr style="background: #ebe8dd;">
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7; width: 110px;">COLUMN</th>
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7;">WHAT IT TELLS YOU</th>
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7; width: 220px;">HOW IT IS CALCULATED</th>
					</tr>
				</thead>
				<tbody>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832; width: 110px;">SITE / CODE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Where the generator is located</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e; width: 220px;">From store master reference data</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">SECTOR</td>
						<td class="py-1.5 px-2" style="color: #383832;">Business sector &mdash; CMHL, CP, CFC, or PG</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">From uploaded blackout file mapping</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">MODEL</td>
						<td class="py-1.5 px-2" style="color: #383832;">Generator model name &mdash; identifies the specific machine</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">From blackout file generator column</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">KVA</td>
						<td class="py-1.5 px-2" style="color: #383832;">Power capacity in kilovolt-amperes. Bigger number = can power more equipment</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Generator rated capacity from spec sheet</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">AVG HR/DAY</td>
						<td class="py-1.5 px-2" style="color: #383832;">Average hours the generator runs per day &mdash; high number means heavy usage</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Total run hours &divide; number of operating days</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">RISK</td>
						<td class="py-1.5 px-2" style="color: #383832;"><span class="font-bold" style="color: #007518;">LOW</span> (green, healthy), <span class="font-bold" style="color: #ff9d00;">MEDIUM</span> (yellow, monitor), <span class="font-bold" style="color: #be2d06;">HIGH</span> (red, schedule service immediately)</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Based on hours until service and daily usage rate</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">HRS TO SERVICE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Hours remaining until next maintenance is due. Low number = service soon</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Service interval &minus; cumulative hours since last service</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">NOTE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Maintenance notes or known issues &mdash; check this for context before scheduling service</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">From maintenance log / manual entry</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div class="px-4 py-2.5" style="background: white; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-1.5" style="color: #383832;">HOW TO USE THIS TABLE</div>
			<div class="text-[10px] leading-relaxed" style="color: #65655e;">
				Sort by RISK to find generators needing service. <span class="font-bold" style="color: #be2d06;">HIGH</span> risk generators could fail and leave a site without power. Schedule maintenance before HRS TO SERVICE reaches zero. High AVG HR/DAY means heavy usage &mdash; check if the generator is being over-relied upon. If a generator fails at a site with only one unit, that site loses all backup power.
			</div>
		</div>
		</div>
	</div>
	{/if}

	<!-- ============================================================ -->
	<!-- SECTION 4: Fuel Transfers -->
	<div id="ops-transfers" class="scroll-mt-36 px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">swap_horiz</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 4: FUEL TRANSFERS</div>
				<div class="text-[10px] opacity-75">Move fuel from surplus sites to deficit sites — save delivery costs.</div>
			</div>
		</div>
		<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Can we move fuel between nearby sites instead of ordering delivery?</div>
	</div>
	{#if transfers.length > 0}
	<div style="margin-bottom: 1.5rem;">
		<div style="background: #feffd6; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<div class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between" style="background: #383832; color: #feffd6;">
				<span>FUEL_TRANSFERS</span>
				<div class="flex items-center gap-3">
					<button onclick={() => downloadExcel(transfers, 'Fuel Transfers')}
						class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100" style="color: #00fc40;">
						<span class="material-symbols-outlined text-sm">download</span> EXCEL
					</button>
					<span class="text-xs font-bold px-2 py-0.5" style="background: #feffd6; color: #383832;">
						{transfers.length} TRANSFERS
					</span>
				</div>
			</div>

			<div style="overflow-x: auto; overflow-y: auto; max-height: 500px;">
				<table style="width: 100%; border-collapse: collapse; font-size: 0.75rem;">
					<thead>
						<tr style="background: #ebe8dd;">
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">FROM SITE</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">TO SITE</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">LITERS</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">FROM BUFFER</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">TO BUFFER</th>
							<th class="font-black uppercase text-center px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SAVES DELIVERY</th>
						</tr>
					</thead>
					<tbody>
						{#each filteredTransfers as row, i}
							{@const saves = row.saves_delivery ? 'YES' : 'NO'}
							<tr style="background: {i % 2 === 0 ? 'white' : '#f6f4e9'};">
								<td class="px-3 py-2 font-bold text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">
									{row.from_site || '—'} <span class="font-normal" style="color: #65655e;">({row.from_sector || ''})</span>
								</td>
								<td class="px-3 py-2 font-bold text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">
									{row.to_site || '—'} <span class="font-normal" style="color: #65655e;">({row.to_sector || ''})</span>
								</td>
								<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.transfer_liters ?? row.transfer_l)}</td>
								<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.from_buffer)}</td>
								<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.to_buffer)}</td>
								<td class="px-3 py-2 text-center" style="border-bottom: 1px solid #ebe8dd;">
									<span style={badgeStyle(saves === 'YES' ? '#007518' : '#ff9d00')}>{saves}</span>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		<!-- What each column means -->
		<div class="px-4 py-3" style="background: #f6f4e9; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">WHAT EACH COLUMN MEANS</div>
			<table class="w-full text-[10px]" style="border-collapse: collapse;">
				<thead>
					<tr style="background: #ebe8dd;">
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7; width: 110px;">COLUMN</th>
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7;">WHAT IT TELLS YOU</th>
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7; width: 220px;">HOW IT IS CALCULATED</th>
					</tr>
				</thead>
				<tbody>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832; width: 110px;">FROM SITE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Site with excess fuel (surplus) &mdash; the donor</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e; width: 220px;">Sites with buffer &gt;14 days (more fuel than needed)</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">TO SITE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Site that needs fuel (deficit) &mdash; the receiver</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Sites with buffer &lt;3 days (running low)</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">LITERS</td>
						<td class="py-1.5 px-2" style="color: #383832;">How many liters to transfer between sites</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Calculated to balance both sites above 3-day buffer</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">FROM BUFFER</td>
						<td class="py-1.5 px-2" style="color: #383832;">Donor site&rsquo;s buffer days <span class="font-bold">after</span> transfer &mdash; must stay above 3 days</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">(Tank &minus; transfer liters) &divide; daily burn</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">TO BUFFER</td>
						<td class="py-1.5 px-2" style="color: #383832;">Receiving site&rsquo;s buffer days <span class="font-bold">after</span> transfer</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">(Tank + transfer liters) &divide; daily burn</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">SAVES DELIVERY</td>
						<td class="py-1.5 px-2" style="color: #383832;"><span class="font-bold" style="color: #007518;">YES</span> = this transfer avoids ordering a tanker delivery, saving delivery cost. <span class="font-bold" style="color: #ff9d00;">NO</span> = still helpful but a tanker may also be needed</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">YES if transfer brings receiver above 3-day buffer</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div class="px-4 py-2.5" style="background: white; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-1.5" style="color: #383832;">HOW TO USE THIS TABLE</div>
			<div class="text-[10px] leading-relaxed" style="color: #65655e;">
				These are recommended fuel moves between nearby sites. Instead of ordering a new tanker delivery, you can move surplus fuel from one site to another. Only transfer if FROM BUFFER stays above 3 days after the move &mdash; never rob Peter to pay Paul. <span class="font-bold" style="color: #007518;">YES</span> in SAVES DELIVERY means real cost savings by avoiding an external tanker order.
			</div>
		</div>
		</div>
	</div>
	{/if}

	<!-- ============================================================ -->
	<!-- SECTION 5: Load Optimization -->
	<div id="ops-loadopt" class="scroll-mt-36 px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">speed</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 5: LOAD OPTIMIZATION</div>
				<div class="text-[10px] opacity-75">Which generator is most efficient at each site? Prioritize the best ones.</div>
			</div>
		</div>
		<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which generators give the most kVA per liter? What are the savings?</div>
	</div>
	{#if loadOpt.length > 0}
	<div style="margin-bottom: 1.5rem;">
		<div style="background: #feffd6; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<div class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between" style="background: #383832; color: #feffd6;">
				<span>LOAD_OPTIMIZATION</span>
				<div class="flex items-center gap-3">
					<button onclick={() => downloadExcel(loadOpt, 'Load Optimization')}
						class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100" style="color: #00fc40;">
						<span class="material-symbols-outlined text-sm">download</span> EXCEL
					</button>
					<span class="text-xs font-bold px-2 py-0.5" style="background: #feffd6; color: #383832;">
						TOP 15 / {loadOpt.length}
					</span>
				</div>
			</div>

			<div style="overflow-x: auto; overflow-y: auto; max-height: 500px;">
				<table style="width: 100%; border-collapse: collapse; font-size: 0.75rem;">
					<thead>
						<tr style="background: #ebe8dd;">
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SITE</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #65655e;">CODE</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SECTOR</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">MODEL</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">KVA</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">L/HR</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">KVA/L</th>
							<th class="font-black uppercase text-center px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">RANK</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">RECOMMENDATION</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SAVINGS</th>
						</tr>
					</thead>
					<tbody>
						{#each top15LoadOpt as row, i}
							<tr style="background: {i % 2 === 0 ? 'white' : '#f6f4e9'};">
								<td class="px-3 py-2 font-bold text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.site_id || '—'}</td>
								<td class="px-3 py-2 font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #65655e;">{row.site_code || ''}</td>
								<td class="px-3 py-2 text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.sector_id || '—'}</td>
								<td class="px-3 py-2 text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.model_name || row.model || '—'}</td>
								<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.power_kva)}</td>
								<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.consumption_per_hour != null ? row.consumption_per_hour.toFixed(1) : '—'}</td>
								<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.kva_per_liter != null ? row.kva_per_liter.toFixed(2) : (row.kva_per_l != null ? row.kva_per_l.toFixed(2) : '—')}</td>
								<td class="px-3 py-2 text-center font-mono text-xs font-bold" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.rank ?? '—'}</td>
								<td class="px-3 py-2 text-xs" style="border-bottom: 1px solid #ebe8dd; color: #383832; max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title={row.recommendation || ''}>{row.recommendation || '—'}</td>
								<td class="px-3 py-2 text-right font-mono text-xs" style="border-bottom: 1px solid #ebe8dd; color: #007518; font-weight: 700;">{row.savings_per_hour_liters != null ? row.savings_per_hour_liters.toFixed(2) : (row.savings_l_hr != null ? row.savings_l_hr.toFixed(2) : '—')}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		<!-- What each column means -->
		<div class="px-4 py-3" style="background: #f6f4e9; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">WHAT EACH COLUMN MEANS</div>
			<table class="w-full text-[10px]" style="border-collapse: collapse;">
				<thead>
					<tr style="background: #ebe8dd;">
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7; width: 110px;">COLUMN</th>
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7;">WHAT IT TELLS YOU</th>
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7; width: 220px;">HOW IT IS CALCULATED</th>
					</tr>
				</thead>
				<tbody>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832; width: 110px;">SITE / CODE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Site and generator location</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e; width: 220px;">From store master reference data</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">SECTOR</td>
						<td class="py-1.5 px-2" style="color: #383832;">Business sector &mdash; CMHL, CP, CFC, or PG</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">From uploaded blackout file mapping</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">MODEL</td>
						<td class="py-1.5 px-2" style="color: #383832;">Generator model name</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">From blackout file generator column</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">KVA</td>
						<td class="py-1.5 px-2" style="color: #383832;">Power capacity in kilovolt-amperes. Bigger number = powers more equipment</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Generator rated capacity from spec sheet</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">L/HR</td>
						<td class="py-1.5 px-2" style="color: #383832;">Actual fuel consumption per hour &mdash; how thirsty this generator is. Lower is better</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Total liters used &divide; total run hours</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">KVA/L</td>
						<td class="py-1.5 px-2" style="color: #383832;">Power output per liter of fuel &mdash; efficiency rating. <span class="font-bold" style="color: #007518;">Higher = more efficient</span></td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">KVA capacity &divide; liters consumed per hour</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">RANK</td>
						<td class="py-1.5 px-2" style="color: #383832;">Efficiency ranking across the entire fleet. <span class="font-bold">1 = most efficient generator</span></td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Sorted by KVA/L descending (best first)</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">RECOMMENDATION</td>
						<td class="py-1.5 px-2" style="color: #383832;">What action to take &mdash; e.g., &ldquo;Prioritize this generator&rdquo; or &ldquo;Consider replacement&rdquo;</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Auto-generated based on efficiency rank and usage</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #007518;">SAVINGS</td>
						<td class="py-1.5 px-2" style="color: #383832;">Potential liters saved per hour if recommendation is followed</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Actual L/hr &minus; best-in-class L/hr for same KVA</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div class="px-4 py-2.5" style="background: white; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-1.5" style="color: #383832;">HOW TO USE THIS TABLE</div>
			<div class="text-[10px] leading-relaxed" style="color: #65655e;">
				This table helps you decide which generators to run first during blackouts. Run the highest-ranked (most efficient) generators first &mdash; they give you more power per liter of diesel. SAVINGS shows how much fuel you save per hour by choosing efficient generators over inefficient ones. Over a month of blackouts, these savings add up significantly.
			</div>
		</div>
		</div>
	</div>
	{/if}

{/if}

<!-- Formula Reference (always visible) -->
<div style="border-top: 2px solid #383832; margin-top: 1.5rem;">
	<div class="px-4 py-2 flex items-center gap-2" style="background: #383832; color: #feffd6;">
		<span class="material-symbols-outlined text-sm" style="color: #00fc40;">functions</span>
		<span class="text-[11px] font-black uppercase">FORMULA REFERENCE</span>
	</div>
	<div class="overflow-x-auto">
		<table class="w-full text-[10px]" style="border-collapse: collapse;">
			<thead><tr style="background: #ebe8dd;">
				<th class="py-1.5 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832; width: 160px;">METRIC</th>
				<th class="py-1.5 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">FORMULA</th>
				<th class="py-1.5 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">SOURCE</th>
			</tr></thead>
			<tbody>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #383832;">OPERATING MODE</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">if diesel% &gt; 60% → CLOSE, &gt;30% → REDUCE, &gt;15% → MONITOR, else FULL</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">decision_engine</code></td></tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #e85d04;">DELIVERY PRIORITY</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">sites with buffer &lt; 7 days, sorted by urgency</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">decision_engine</code></td></tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #be2d06;">LITERS NEEDED</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">7 × avg_daily_used − current_tank</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">derived</code></td></tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #ff9d00;">GENERATOR RISK</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">based on hours_until_service and avg_daily_hours</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">generators table</code></td></tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #006f7c;">FUEL TRANSFER</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">surplus (buffer&gt;14d) → deficit (buffer&lt;3d)</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">decision_engine</code></td></tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #007518;">LOAD OPTIMIZATION</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">kVA ÷ consumption_per_hour = efficiency ranking</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">generators table</code></td></tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #be2d06;">WASTE RATIO</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">actual_L/hr ÷ rated_L/hr (&gt;2 = suspicious)</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">fleet-stats</code></td></tr>
			</tbody>
		</table>
	</div>
</div>
