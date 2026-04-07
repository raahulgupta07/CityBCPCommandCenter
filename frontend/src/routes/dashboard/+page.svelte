<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { api } from '$lib/api';
	import DatePicker from '$lib/components/DatePicker.svelte';
	import KpiCard from '$lib/components/KpiCard.svelte';
	import MiniChart from '$lib/components/MiniChart.svelte';
	import TrendCharts from '$lib/components/sections/TrendCharts.svelte';
	import RollingCharts from '$lib/components/sections/RollingCharts.svelte';
	import GroupExtras from '$lib/components/sections/GroupExtras.svelte';
	import OperationsTables from '$lib/components/sections/OperationsTables.svelte';
	import Predictions from '$lib/components/sections/Predictions.svelte';
	import Rankings from '$lib/components/sections/Rankings.svelte';
	import LngComparison from '$lib/components/sections/LngComparison.svelte';
	import WhatIf from '$lib/components/sections/WhatIf.svelte';
	import SectorHeatmap from '$lib/components/sections/SectorHeatmap.svelte';
	import AiInsights from '$lib/components/sections/AiInsights.svelte';
	import OperatingModes from '$lib/components/sections/OperatingModes.svelte';
	import RiskPanel from '$lib/components/sections/RiskPanel.svelte';
	import FuelIntel from '$lib/components/sections/FuelIntel.svelte';
	import SectorSites from '$lib/components/sections/SectorSites.svelte';
	import SiteModal from '$lib/components/SiteModal.svelte';
	import Dictionary from '$lib/components/sections/Dictionary.svelte';
	import AiInsightPanel from '$lib/components/AiInsightPanel.svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	let showSiteModal = $state(false);
	let showComparison = $state(false);
	let showFilters = $state(false);
	let modalSiteId = $state('');
	let heatmapRows: any[] = $state([]);
	let dashSection = $state('overview');
	let comparison: any[] = $state([]);
	let periodKpis: any = $state({ last_day: null, last_3d: null });
	let monthlySummary: any[] = $state([]);
	let blackoutCalendar: any[] = $state([]);
	let transferData: any[] = $state([]);

	const dashTabs = [
		{ id: 'overview', label: 'OVERVIEW', icon: 'dashboard', sub: 'KPIs & Status', step: '01' },
		{ id: 'trends', label: 'WHAT HAPPENED', icon: 'history', sub: 'Trends & Patterns', step: '02' },
		{ id: 'sector', label: 'WHERE', icon: 'map', sub: 'Sectors & Sites', step: '03' },
		{ id: 'operations', label: 'HOW WE RAN', icon: 'precision_manufacturing', sub: 'Operations & Fleet', step: '04' },
		{ id: 'risk', label: 'WHAT\'S AT RISK', icon: 'warning', sub: 'Alerts & Scores', step: '05' },
		{ id: 'fuel', label: 'FUEL & COST', icon: 'local_gas_station', sub: 'Intel & Budget', step: '06' },
		{ id: 'predictions', label: 'WHAT\'S NEXT', icon: 'query_stats', sub: 'Forecast & Actions', step: '07' },
	];

	// Filter state
	let sector = $state('All Sectors');
	let company = $state('All Companies');
	let siteId = $state('All Sites');
	let selectedSites: string[] = $state([]);
	let siteDropOpen = $state(false);
	let siteType = $state('All');

	// Default 60 days
	const _defaultEnd = new Date();
	const _defaultStart = new Date(); _defaultStart.setDate(_defaultStart.getDate() - 60);
	let dateFrom = $state(_defaultStart.toISOString().slice(0, 10));
	let dateTo = $state(_defaultEnd.toISOString().slice(0, 10));

	function quickDate(days: number) {
		const end = new Date();
		dateTo = end.toISOString().slice(0, 10);
		if (days === 0) { dateFrom = dateTo; }
		else if (days < 0) { dateFrom = ''; dateTo = ''; }
		else { const s = new Date(); s.setDate(s.getDate() - days); dateFrom = s.toISOString().slice(0, 10); }
	}

	function resetFilters() {
		sector = 'All Sectors';
		company = 'All Companies';
		activeCompany = 'All';
		selectedSites = [];
		siteType = 'All';
		quickDate(60);
	}

	// Sector friendly names for Layer 1 pills
	const sectorOptions = [
		{ label: 'Group', value: '' },
		{ label: 'Distribution', value: 'PG' },
		{ label: 'F&B', value: 'CFC' },
		{ label: 'Property', value: 'CP' },
		{ label: 'Retail', value: 'CMHL' },
	];

	// Active company filter
	let activeCompany = $state('All');

	// Derived: companies from actual data
	function availableCompanies(): string[] {
		let pool = econ;
		if (sector !== 'All Sectors') pool = pool.filter((e: any) => e.sector_id === sector);
		return [...new Set(pool.map((e: any) => e.company).filter(Boolean))].sort();
	}

	// Derived: sites for selected sector + company (with name + code)
	function availableSites(): { id: string; name: string; code: string }[] {
		let pool = econ;
		if (sector !== 'All Sectors') pool = pool.filter((e: any) => e.sector_id === sector);
		if (activeCompany !== 'All') pool = pool.filter((e: any) => e.company === activeCompany);
		const seen = new Set<string>();
		return pool.filter((e: any) => { if (!e.site_id || seen.has(e.site_id)) return false; seen.add(e.site_id); return true; })
			.map((e: any) => ({ id: e.site_id, name: e.site_name || e.cost_center_description || '', code: e.site_code || e.region || '' }))
			.sort((a, b) => a.name.localeCompare(b.name));
	}

	function isDictionary() { return page.url.searchParams.get('view') === 'dictionary'; }

	// Data
	let loading = $state(true);
	let error = $state('');
	let econ: any[] = $state([]);
	let sectors: string[] = $state([]);
	let companies: string[] = $state([]);
	let sites: string[] = $state([]);

	// Build sector options dynamically from data
	let dynamicSectorOptions: { label: string; value: string }[] = $state([]);

	async function fetchData() {
		loading = true;
		error = '';
		try {
			const p = new URLSearchParams();
			if (dateFrom) p.set('date_from', dateFrom);
			if (dateTo) p.set('date_to', dateTo);
			econ = await api.get(`/economics?${p}`);
			sectors = [...new Set(econ.map((e: any) => e.sector_id).filter(Boolean))].sort();

			// Build sector options from data: use business_sector as label if available
			const sectorMap = new Map<string, string>();
			for (const e of econ) {
				if (e.sector_id && !sectorMap.has(e.sector_id)) {
					sectorMap.set(e.sector_id, e.business_sector || e.sector_id);
				}
			}
			dynamicSectorOptions = [
				{ label: 'Group', value: 'All Sectors' },
				...Array.from(sectorMap.entries()).sort().map(([id, biz]) => ({
					label: `${biz} (${id})`, value: id
				})),
			];
			// Fetch yesterday vs 3-day comparison + period KPIs (with sector filter)
			try {
				let effSector = sector !== 'All Sectors' ? sector : '';
				if (!effSector && activeCompany !== 'All') {
					const m = econ.find((e: any) => e.company === activeCompany);
					if (m) effSector = m.sector_id || '';
				}
				const sp = effSector ? `?sector=${effSector}` : '';
				const dtParam = dateTo ? `${sp ? '&' : '?'}date_to=${dateTo}` : '';
				const typeParam = siteType !== 'All' ? `${(sp || dtParam) ? '&' : '?'}site_type=${siteType}` : '';
				const [c, pk, ms, bc, tr] = await Promise.all([
					api.get('/yesterday-comparison'),
					api.get(`/period-kpis${sp}${dtParam}${typeParam}`),
					api.get(`/monthly-summary${sp}`).catch(() => []),
					api.get(`/blackout-calendar${sp}`).catch(() => ({ days: [] })),
					api.get('/transfers').catch(() => ({ transfers: [] })),
				]);
				comparison = c.metrics || [];
				periodKpis = pk;
				monthlySummary = ms || [];
				blackoutCalendar = bc?.days || [];
				transferData = (tr?.transfers || []);
			} catch {}
		} catch (e) { console.error(e); error = 'Failed to load dashboard data. Check your connection and try again.'; }
		finally { loading = false; }
	}

	// Reset cascading filters + re-fetch period KPIs on sector change
	$effect(() => { sector; activeCompany = 'All'; company = 'All Companies'; siteId = 'All Sites'; selectedSites = []; });
	$effect(() => { activeCompany; selectedSites = []; });
	$effect(() => {
		// Re-fetch period KPIs when sector, company, or siteType changes
		const s = sector;
		const c = activeCompany;
		const t = siteType;
		if (!loading) {
			let effectiveSector = s !== 'All Sectors' ? s : '';
			if (!effectiveSector && c !== 'All') {
				const match = econ.find((e: any) => e.company === c);
				if (match) effectiveSector = match.sector_id || '';
			}
			const sp = effectiveSector ? `?sector=${effectiveSector}` : '';
			const dt2 = dateTo ? `${sp ? '&' : '?'}date_to=${dateTo}` : '';
			const tp = t !== 'All' ? `${(sp || dt2) ? '&' : '?'}site_type=${t}` : '';
			api.get(`/period-kpis${sp}${dt2}${tp}`).then(pk => { periodKpis = pk; }).catch(() => {});
		}
	});

	// Auto-refetch when date range changes
	let _prevDateKey = '';
	$effect(() => {
		const key = `${dateFrom}|${dateTo}`;
		if (key !== _prevDateKey && _prevDateKey !== '') {
			fetchData();
		}
		_prevDateKey = key;
	});

	function syncURL() {
		const p = new URLSearchParams();
		if (sector !== 'All Sectors') p.set('sector', sector);
		if (activeCompany !== 'All') p.set('company', activeCompany);
		if (siteType !== 'All') p.set('type', siteType);
		if (dateFrom) p.set('from', dateFrom);
		if (dateTo) p.set('to', dateTo);
		if (dashSection !== 'trends') p.set('tab', dashSection);
		const url = p.toString() ? `?${p}` : window.location.pathname;
		window.history.replaceState({}, '', url);
	}

	$effect(() => { sector; activeCompany; siteType; dateFrom; dateTo; dashSection; syncURL(); });

	onMount(() => {
		const params = page.url.searchParams;
		if (params.get('sector')) sector = params.get('sector')!;
		if (params.get('company')) activeCompany = params.get('company')!;
		if (params.get('type')) siteType = params.get('type')!;
		if (params.get('from')) dateFrom = params.get('from')!;
		if (params.get('to')) dateTo = params.get('to')!;
		if (params.get('tab')) dashSection = params.get('tab')!;
		fetchData();
	});

	function filtered() {
		let f = econ;
		if (sector !== 'All Sectors') f = f.filter((e: any) => e.sector_id === sector);
		if (activeCompany !== 'All') f = f.filter((e: any) => e.company === activeCompany);
		if (selectedSites.length > 0) f = f.filter((e: any) => selectedSites.includes(e.site_id));
		if (siteType !== 'All') f = f.filter((e: any) => e.site_type === siteType);
		return f;
	}

	function sectorApiParam(): string {
		return sector !== 'All Sectors' ? sector : '';
	}

	function kpis(data: any[]) {
		if (!data.length) return null;
		const wb = data.filter((e: any) => e.avg_daily_liters > 0);
		const wt = wb.filter((e: any) => e.diesel_available > 0);
		const tank = wt.reduce((s: number, e: any) => s + (e.diesel_available || 0), 0);
		const burn = wb.reduce((s: number, e: any) => s + (e.avg_daily_liters || 0), 0);
		const buffer = burn > 0 ? tank / burn : 0;
		const cost = data.reduce((s: number, e: any) => s + (e.energy_cost || 0), 0);
		const crit = wt.filter((e: any) => e.latest_buffer_days < 3).length;
		const warn = wt.filter((e: any) => e.latest_buffer_days >= 3 && e.latest_buffer_days < 7).length;
		const safe = wt.filter((e: any) => e.latest_buffer_days >= 7).length;
		const noData = data.filter((e: any) => !e.diesel_available && !e.avg_daily_liters).length;
		const total = data.length;
		const pct = total > 0 ? Math.round(safe / total * 100) : 0;
		const needed = wt.filter((e: any) => (e.latest_buffer_days || 0) < 7).reduce((s: number, e: any) => s + Math.max(0, 7 * (e.avg_daily_liters || 0) - (e.diesel_available || 0)), 0);
		const sales = data.reduce((s: number, e: any) => s + (e.total_sales || 0), 0);
		const dieselPct = sales > 0 ? (cost / sales * 100) : 0;
		const genHours = data.reduce((s: number, e: any) => s + (e.total_gen_hours || 0), 0);
		return { tank, burn, buffer, cost, crit, warn, safe, noData, total, pct, needed, sales, dieselPct, genHours };
	}

	function fmt(v: number, type = 'num'): string {
		if (type === 'M') return (v / 1e6).toFixed(1) + 'M';
		if (type === 'K') return (v / 1e3).toFixed(1) + 'k';
		if (type === 'd') return v.toFixed(1);
		return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
	}

	function compareData() {
		if (selectedSites.length !== 2) return [];
		const s1 = econ.find((e: any) => e.site_id === selectedSites[0]);
		const s2 = econ.find((e: any) => e.site_id === selectedSites[1]);
		if (!s1 || !s2) return [];

		const metrics = [
			{ name: 'Buffer Days', v1: s1.latest_buffer_days, v2: s2.latest_buffer_days, higher: true },
			{ name: 'Tank (L)', v1: s1.diesel_available, v2: s2.diesel_available, higher: true },
			{ name: 'Daily Burn (L)', v1: s1.avg_daily_liters, v2: s2.avg_daily_liters, higher: false },
			{ name: 'Gen Hours', v1: s1.total_gen_hours, v2: s2.total_gen_hours, higher: false },
			{ name: 'Efficiency L/Hr', v1: s1.avg_daily_liters && s1.total_gen_hours ? s1.avg_daily_liters / s1.total_gen_hours : 0, v2: s2.avg_daily_liters && s2.total_gen_hours ? s2.avg_daily_liters / s2.total_gen_hours : 0, higher: false },
			{ name: 'Energy Cost', v1: s1.energy_cost, v2: s2.energy_cost, higher: false },
			{ name: 'Total Sales', v1: s1.total_sales, v2: s2.total_sales, higher: true },
			{ name: 'Diesel %', v1: s1.diesel_pct, v2: s2.diesel_pct, higher: false },
		];
		return metrics;
	}

	function handleKeydown(e: KeyboardEvent) {
		// Don't capture when typing in inputs
		if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;

		// 1-7: Switch tabs
		const num = parseInt(e.key);
		if (num >= 1 && num <= 7 && !e.ctrlKey && !e.metaKey && !e.altKey) {
			const tab = dashTabs[num - 1];
			if (tab) dashSection = tab.id;
			return;
		}

		// Ctrl+K or Cmd+K: Focus search (if it exists in header)
		if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
			e.preventDefault();
			const searchBtn = document.querySelector('[data-search-toggle]') as HTMLButtonElement;
			if (searchBtn) searchBtn.click();
		}

		// Escape: Close modals
		if (e.key === 'Escape') {
			if (showSiteModal) { showSiteModal = false; return; }
		}
	}

	$effect(() => { page.url.searchParams; });

	if (typeof window !== 'undefined') window.addEventListener('keydown', handleKeydown);
	onDestroy(() => { if (typeof window !== 'undefined') window.removeEventListener('keydown', handleKeydown); });
</script>

<!-- Filter Bar: Sticky below header -->
<section class="p-4 sticky top-16 z-30" style="background: #f6f4e9; border-bottom: 3px solid #383832; box-shadow: 0 4px 8px rgba(56,56,50,0.15);">
	<!-- Mobile filter toggle -->
	<button onclick={() => showFilters = !showFilters}
		class="md:hidden px-3 py-1.5 text-[10px] font-black uppercase flex items-center gap-1 mb-2"
		style="background: #383832; color: #feffd6;">
		<span class="material-symbols-outlined text-sm">tune</span>
		{showFilters ? 'HIDE FILTERS' : 'SHOW FILTERS'}
	</button>
	<div class="{showFilters ? 'flex' : 'hidden'} md:flex flex-wrap items-end gap-4">
		<!-- Sector -->
		<div class="flex-1 min-w-[140px]">
			<div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">SECTOR</div>
			<select bind:value={sector} class="w-full px-3 py-2 text-sm font-bold uppercase" style="background: white; border: 2px solid #383832; color: #383832;">
				{#each dynamicSectorOptions as opt}
					<option value={opt.value}>{opt.label}</option>
				{/each}
				{#if dynamicSectorOptions.length === 0}
					<option value="All Sectors">Group</option>
				{/if}
			</select>
		</div>

		<!-- Company (disabled when Group selected) -->
		<div class="flex-1 min-w-[140px]">
			<div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">COMPANY</div>
			<select bind:value={activeCompany}
				disabled={sector === 'All Sectors'}
				class="w-full px-3 py-2 text-sm font-bold uppercase"
				style="background: {sector === 'All Sectors' ? '#ebe8dd' : 'white'}; border: 2px solid #383832; color: {sector === 'All Sectors' ? '#65655e' : '#383832'}; {sector === 'All Sectors' ? 'cursor: not-allowed;' : ''}">
				<option value="All">All Companies</option>
				{#each availableCompanies() as c}<option value={c}>{c}</option>{/each}
			</select>
		</div>

		<!-- Site (disabled when Group selected and no company chosen) -->
		{#if true}
		{@const siteList = availableSites()}
		{@const siteDisabled = sector === 'All Sectors' && activeCompany === 'All'}
		<div class="flex-1 min-w-[180px] relative">
			<div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">SITE_ID</div>
			<button onclick={() => { if (!siteDisabled) siteDropOpen = !siteDropOpen; }}
				class="w-full flex items-center gap-2 px-3 py-2 text-sm font-bold uppercase text-left"
				style="background: {siteDisabled ? '#ebe8dd' : 'white'}; border: 2px solid #383832; color: {siteDisabled ? '#65655e' : '#383832'}; {siteDisabled ? 'cursor: not-allowed;' : ''}">
				<span class="flex-1 truncate">{selectedSites.length === 0 ? 'ALL SITES' : selectedSites.length === 1 ? (siteList.find(s => s.id === selectedSites[0])?.name || selectedSites[0]) : selectedSites.length + ' SELECTED'}</span>
				<span class="text-[8px]">{siteDropOpen ? '▲' : '▼'}</span>
			</button>

			{#if siteDropOpen}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="fixed inset-0 z-40" onclick={() => siteDropOpen = false}></div>
				<div class="absolute top-full left-0 z-50 mt-1 w-full max-h-[300px] overflow-y-auto" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<!-- Select All / Clear -->
					<div class="flex gap-2 p-2" style="border-bottom: 1px solid #ebe8dd;">
						<button onclick={() => { selectedSites = siteList.map(s => s.id); }} class="text-[10px] font-bold uppercase" style="color: #007518;">SELECT ALL</button>
						<span style="color: #ebe8dd;">|</span>
						<button onclick={() => { selectedSites = []; }} class="text-[10px] font-bold uppercase" style="color: #be2d06;">CLEAR</button>
						<span class="text-[9px] ml-auto" style="color: #65655e;">{siteList.length} sites</span>
					</div>
					{#each siteList as s}
						<label class="flex items-center gap-2 px-3 py-1.5 text-xs cursor-pointer transition-colors hover:bg-[#f6f4e9]" style="color: #383832;">
							<input type="checkbox" checked={selectedSites.includes(s.id)}
								onchange={() => {
									if (selectedSites.includes(s.id)) selectedSites = selectedSites.filter(x => x !== s.id);
									else selectedSites = [...selectedSites, s.id];
								}}
								style="accent-color: #007518;" />
							<span class="font-bold">{s.name}</span>
							<span class="text-[9px] ml-auto font-mono" style="color: #65655e;">{s.code || s.id}</span>
						</label>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Site Type -->
		<div class="min-w-[100px]">
			<div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">TYPE</div>
			<select bind:value={siteType} class="w-full px-3 py-2 text-sm font-bold uppercase" style="background: white; border: 2px solid #383832; color: #383832;">
				<option value="All">ALL</option>
				<option value="Regular">REGULAR</option>
				<option value="LNG">LNG</option>
			</select>
		</div>

		<!-- Date Range -->
		<div class="flex-1 min-w-[180px]">
			<div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">DATE_RANGE</div>
			<DatePicker bind:from={dateFrom} bind:to={dateTo} />
		</div>

		<!-- RESET Button -->
		<div class="flex items-end">
			<button onclick={resetFilters}
				class="px-6 py-2 text-xs font-black uppercase active:translate-x-[1px] active:translate-y-[1px] flex items-center gap-1.5"
				style="background: #be2d06; border: 2px solid #383832; color: #feffd6; box-shadow: 4px 4px 0px 0px #383832;">
				<span class="material-symbols-outlined text-sm">restart_alt</span>
				RESET
			</button>
		</div>
		{/if}

		<!-- Deep Dive button (when exactly 1 site selected) -->
		{#if selectedSites.length === 1}
			<button onclick={() => { modalSiteId = selectedSites[0]; showSiteModal = true; }}
				class="px-5 py-2 text-xs font-black uppercase active:translate-x-[1px] active:translate-y-[1px]"
				style="background: #00fc40; border: 2px solid #383832; color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
				DEEP_DIVE
			</button>
		{/if}

		<!-- Compare button (when exactly 2 sites selected) -->
		{#if selectedSites.length === 2}
			<button onclick={() => showComparison = true}
				class="px-5 py-2 text-xs font-black uppercase active:translate-x-[1px] active:translate-y-[1px]"
				style="background: #006f7c; border: 2px solid #383832; color: white; box-shadow: 4px 4px 0px 0px #383832;">
				COMPARE
			</button>
		{/if}
	</div>
</section>

{#if isDictionary()}
	<Dictionary />
{:else if loading}
	<div class="text-center py-20">
		<span class="material-symbols-outlined text-4xl animate-pulse" style="color: #007518;">bolt</span>
		<p class="font-bold mt-3 uppercase tracking-widest text-sm" style="color: #383832;">INITIALIZING_COMMAND_CENTER...</p>
	</div>
{:else if error}
	<div class="text-center py-20">
		<span class="material-symbols-outlined text-4xl" style="color: #be2d06;">error</span>
		<p class="font-bold mt-3 uppercase tracking-widest text-sm" style="color: #be2d06;">{error}</p>
		<button onclick={fetchData} class="mt-4 px-6 py-2 text-xs font-black uppercase"
			style="background: #383832; color: #feffd6; border: 2px solid #383832;">
			<span class="material-symbols-outlined text-sm align-middle">refresh</span> RETRY
		</button>
	</div>
{:else}
	{@const data = filtered()}
	{@const k = kpis(data)}

	{#if k}
		<!-- ═══ STORY TABS ═══ -->
		<div class="mb-6">
			<!-- Story Flow Bar -->
			<div class="overflow-x-auto">
			<div class="flex items-stretch min-w-[700px]" style="border: 3px solid #383832; border-bottom: 0;">
				{#each dashTabs as tab, idx}
					{@const active = dashSection === tab.id}
					{@const stepIdx = dashTabs.findIndex(t => t.id === dashSection)}
					{@const isPast = idx < stepIdx}
					<button
						onclick={() => dashSection = tab.id}
						class="flex-1 px-2 py-3 flex flex-col items-center justify-center gap-0.5 transition-all relative"
						style="{active
							? 'background: #383832; color: #feffd6;'
							: isPast
								? 'background: #007518; color: white;'
								: 'background: #f6f4e9; color: #383832; border-right: 1px solid #383832;'}"
					>
						<!-- Step number -->
						<span class="text-[8px] font-black tracking-widest opacity-60">{tab.step}</span>
						<!-- Icon -->
						<span class="material-symbols-outlined {active ? 'text-lg' : 'text-base'}" style="{active ? 'color: #00fc40;' : ''}">{tab.icon}</span>
						<!-- Label -->
						<span class="text-[10px] font-black uppercase leading-tight">{tab.label}</span>
						<span class="text-[7px] uppercase opacity-60 leading-tight">{tab.sub}</span>
						<!-- Active indicator -->
						{#if active}
							<div class="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-full w-0 h-0" style="border-left: 8px solid transparent; border-right: 8px solid transparent; border-top: 8px solid #383832;"></div>
						{/if}
						<!-- Connector arrow between tabs -->
						{#if idx < dashTabs.length - 1 && !active}
							<div class="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 z-10 text-[8px] font-black" style="color: {isPast ? 'white' : '#65655e'};">→</div>
						{/if}
					</button>
				{/each}
				<!-- Site Deep Dive -->
				{#if sites.length > 0}
					<button
						onclick={() => { modalSiteId = sites[0]; showSiteModal = true; }}
						class="px-4 py-3 flex flex-col items-center justify-center gap-0.5"
						style="background: #00fc40; color: #383832;"
					>
						<span class="text-[8px] font-black tracking-widest opacity-60">++</span>
						<span class="material-symbols-outlined text-base">search</span>
						<span class="text-[10px] font-black uppercase">SITE DIVE</span>
						<span class="text-[7px] uppercase opacity-60">Deep Analysis</span>
					</button>
				{/if}
			</div>
			<div class="text-[8px] font-mono px-2 py-1 text-right" style="color: #65655e;">
				KEYS: 1-7 switch tab | ESC close modal
			</div>
			</div>

			<!-- Story chapter intro -->
			{#each dashTabs.filter(t => t.id === dashSection) as currentTab}
				<div class="flex items-center gap-3 px-5 py-2.5" style="background: #383832; color: #feffd6; border-left: 3px solid #383832; border-right: 3px solid #383832;">
					<span class="text-2xl font-black" style="color: #00fc40;">{currentTab.step}</span>
					<div>
						<span class="text-sm font-black uppercase">{currentTab.label}</span>
						<span class="text-[10px] ml-2 opacity-60">— {currentTab.sub}</span>
					</div>
				</div>
			{/each}

			<!-- Tab Content -->
			<div class="p-4" style="border: 3px solid #383832; border-top: 0; min-height: 400px;">
				{#if dashSection === 'overview'}
				{@const ld = periodKpis.last_day}
				{@const td = periodKpis.last_3d}
				{@const opModes = periodKpis.operating_modes || { OPEN: 0, MONITOR: 0, REDUCE: 0, CLOSE: 0 }}
				{@const sectorSnap = periodKpis.sector_snapshot || []}
				<div class="space-y-4 section-animate">

					<!-- AI Executive Briefing (top of overview) -->
					{#if periodKpis.last_day}
						{@const aiData = {
							date: periodKpis.last_day.date,
							sites_reporting: periodKpis.last_day.sites,
							total_sites: periodKpis.last_day.total_sites,
							generators: periodKpis.last_day.generators,
							buffer_days: periodKpis.last_day.buffer,
							buffer_3d: periodKpis.last_3d?.buffer,
							buffer_change_pct: periodKpis.last_3d?.buffer ? Math.round((periodKpis.last_day.buffer - periodKpis.last_3d.buffer) / Math.max(periodKpis.last_3d.buffer, 0.1) * 100) : 0,
							total_fuel: periodKpis.last_day.total_fuel,
							fuel_3d_avg: periodKpis.last_3d?.burn,
							total_gen_hr: periodKpis.last_day.total_gen_hr,
							total_tank: periodKpis.last_day.tank,
							total_blackout: periodKpis.last_day.total_blackout,
							blackout_per_site: periodKpis.last_day.blackout_per_site,
							cost: periodKpis.last_day.cost,
							fuel_price: periodKpis.last_day.fuel_price,
							sales: periodKpis.last_day.sales,
							diesel_pct: periodKpis.last_day.diesel_pct,
							efficiency: periodKpis.last_day.efficiency,
							critical_sites: periodKpis.last_day.crit,
							warning_sites: periodKpis.last_day.warn,
							safe_sites: periodKpis.last_day.safe,
							sites_not_reported: periodKpis.last_day.sites_not_reported,
							sector_snapshot: periodKpis.sector_snapshot || [],
						}}
						<AiInsightPanel type="executive" data={aiData} title="AI EXECUTIVE BRIEFING — OVERVIEW" />
					{/if}

					<!-- ═══ UNIFIED COCKPIT: LATEST vs 3D ═══ -->
					{#if ld}
						{@const bc1 = ld.buffer >= 7 ? '#007518' : ld.buffer >= 3 ? '#ff9d00' : '#be2d06'}
						{@const bl1 = ld.buffer >= 7 ? 'SAFE' : ld.buffer >= 3 ? 'WARNING' : 'CRITICAL'}
						{@const daysAgo = Math.floor((Date.now() - new Date(ld.date).getTime()) / 86400000)}
						{@const ageColor = daysAgo <= 1 ? '#007518' : daysAgo <= 3 ? '#ff9d00' : '#be2d06'}
						{@const fmtV = (v: number) => { if (v >= 1e9) return (v/1e9).toLocaleString(undefined, {minimumFractionDigits:1, maximumFractionDigits:1})+'B'; if (v >= 1e6) return (v/1e6).toLocaleString(undefined, {minimumFractionDigits:1, maximumFractionDigits:1})+'M'; if (v >= 1e3) return (v/1e3).toLocaleString(undefined, {minimumFractionDigits:1, maximumFractionDigits:1})+'K'; return v.toLocaleString(); }}
						<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
							<!-- Header -->
							<div class="px-4 py-2 flex justify-between items-center" style="background: #383832; color: #feffd6;">
								<span class="font-black uppercase text-sm">LATEST DATA <span class="font-normal text-[10px] opacity-75 ml-2">{ld.date} <span class="px-1.5 py-0.5 font-black" style="background: {ageColor}; color: white;">{daysAgo === 0 ? 'TODAY' : daysAgo === 1 ? 'YESTERDAY' : daysAgo + 'd AGO'}</span> | {ld.sites}/{ld.total_sites || ld.sites} sites | {ld.generators || 0} gens | {fmtV(ld.fuel_price || 0)} MMK/L</span></span>
								<span class="px-3 py-1 text-xs font-black uppercase" style="background: {bc1}; color: white;">{bl1}: {ld.buffer} DAYS</span>
							</div>

							<!-- Data quality warning -->
							{#if (ld.sites_not_reported || 0) > 0 || (ld.tank_missing || 0) > 0}
								<div class="px-4 py-1.5 text-[10px] font-bold flex gap-4" style="background: #fff3cd; border-bottom: 1px solid #383832; color: #856404;">
									{#if (ld.sites_not_reported || 0) > 0}<span>⚠️ {ld.sites_not_reported} sites did not report on {ld.date}</span>{/if}
									{#if (ld.tank_missing || 0) > 0}<span>⚠️ Tank balance missing for {ld.tank_missing} sites</span>{/if}
								</div>
							{/if}

							<!-- Buffer Hero + Daily Buffer Chart side by side -->
							{#if true}
							{@const rd = periodKpis.recent_daily || []}
							{@const bufVals = rd.map((d: any) => d.buffer || 0)}
							{@const bufMax = Math.max(...bufVals, 20)}
							{@const buf3 = td?.buffer || (rd.length >= 4 ? (bufVals[0] + bufVals[1] + bufVals[2]) / 3 : 0)}
							<div class="flex flex-col lg:flex-row" style="background: white; border-bottom: 2px solid #383832;">
								<!-- Left: Buffer Hero -->
								<div class="p-6 text-center flex flex-col justify-center" style="flex: 0 0 380px; border-right: 2px solid #383832;">
									<div class="text-5xl sm:text-7xl font-black" style="color: {bc1};">{ld.buffer}</div>
									<div class="text-lg font-bold mt-2" style="color: #383832;">DAYS OF FUEL LEFT</div>
									{#if td}
										{@const bufDiff = td.buffer ? ((ld.buffer - td.buffer) / Math.max(td.buffer, 0.1) * 100) : 0}
										<div class="text-sm font-bold mt-1" style="color: {bufDiff > 1 ? '#007518' : bufDiff < -1 ? '#be2d06' : '#65655e'};">
											{bufDiff > 1 ? '▲' : bufDiff < -1 ? '▼' : '→'} {Math.abs(bufDiff).toFixed(0)}% vs Prior 3 Days ({td.buffer}d)
										</div>
									{/if}
									<div class="mx-auto mt-3 h-4 overflow-hidden w-full" style="background: #ebe8dd; border: 2px solid #383832; max-width: 240px;">
										<div class="h-full" style="background: {bc1}; width: {Math.min(100, ld.buffer / 20 * 100)}%;"></div>
									</div>
									<div class="text-xs mt-1" style="color: #65655e;">{Math.round(ld.buffer / 20 * 100)}% of 20-day target</div>
								</div>
								<!-- Right: Daily Buffer Bar Chart -->
								<div class="flex-1" style="border-top: none;">
									<div class="px-3 py-1.5" style="background: #383832; color: #feffd6;">
										<span class="text-[11px] font-black uppercase">BUFFER DAYS — DAILY</span>
									</div>
									{#each rd as day, di}
										{@const isLatest = di === rd.length - 1}
										{@const bv = bufVals[di]}
										{@const bPct = bufMax > 0 ? (bv / bufMax * 100) : 0}
										{@const bClr = bv >= 7 ? '#007518' : bv >= 3 ? '#ff9d00' : '#be2d06'}
										{#if isLatest && rd.length >= 4}
											<div class="px-3 py-0.5 flex items-center gap-2" style="border-top: 2px dashed #007518;">
												<span class="text-[8px] font-bold" style="color: #007518;">3D AVG: {buf3.toFixed(1)}d</span>
											</div>
										{/if}
										<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid {isLatest ? bClr : 'rgba(56,56,50,0.08)'}; {isLatest ? 'background: rgba(56,56,50,0.03);' : ''}">
											<span class="text-[9px] w-10 shrink-0 {isLatest ? 'font-black' : ''}" style="color: {isLatest ? bClr : '#828179'};">{day.date.slice(5)}</span>
											<div class="flex-1 h-4 relative" style="background: #f0ede3;">
												<div class="h-full" style="width: {bPct}%; background: {isLatest ? bClr : bClr + '60'};"></div>
												{#if buf3 > 0}
													<div class="absolute top-0 h-full w-px" style="left: {Math.min(buf3/bufMax*100, 100)}%; background: #007518; opacity: 0.5;"></div>
												{/if}
											</div>
											<span class="text-[9px] w-12 text-right shrink-0 font-bold {isLatest ? 'font-black' : ''}" style="color: {bClr};">{bv.toFixed(1)}d</span>
											<span class="text-[8px] w-16 text-right shrink-0" style="color: #9d9d91;">{fmtV(day.tank)}L / {fmtV(day.fuel)}L</span>
											{#if isLatest && buf3 > 0}
												{@const vsAvg = (bv - buf3) / buf3 * 100}
												<span class="text-[8px] font-bold w-14 text-right shrink-0" style="color: {vsAvg > 1 ? '#007518' : vsAvg < -1 ? '#be2d06' : '#65655e'};">{vsAvg > 0 ? '▲' : vsAvg < 0 ? '▼' : '→'}{Math.abs(vsAvg).toFixed(0)}%</span>
											{:else}
												<span class="w-14 shrink-0"></span>
											{/if}
										</div>
									{/each}
									<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">tank ÷ 3d_avg_fuel</div>
								</div>
							</div>

							{/if}

							<!-- KPI Cards: Option 3 — Compact with horizontal bars -->
							<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-2">
								{#each [
									{ t1: ld.total_gen_hr||0, t3: td?.gen_hr||0, tl: 'GEN RUN HR', tc: 'SUM(gen_run_hr)',
									  s1: ld.gen_hr_per_site||0, s3: td?.gen_hr_per_site||0, sl: '/SITE', sdec: 1,
									  good: 'low', key: 'gen_hr', color: '#ff9d00' },
									{ t1: ld.total_fuel||ld.burn||0, t3: td?.burn||0, tl: 'FUEL USED (L)', tc: 'SUM(daily_used)',
									  s1: ld.fuel_per_site||0, s3: td?.fuel_per_site||0, sl: '/SITE', sdec: 1,
									  good: 'low', key: 'fuel', color: '#e85d04' },
									{ t1: ld.tank, t3: td?.tank||0, tl: 'TANK BAL (L)', tc: 'SUM(spare_tank)',
									  s1: ld.tank_per_site||0, s3: td?.tank_per_site||0, sl: '/SITE',
									  good: 'high', key: 'tank', color: '#007518' },
									{ t1: ld.total_blackout||0, t3: td?.total_blackout ? td.total_blackout / (td.days || 3) : 0, tl: 'BLACKOUT HR', tc: 'SUM(blackout)', tdec: 1,
									  s1: ld.blackout_per_site||ld.blackout||0, s3: td?.blackout_per_site||td?.blackout||0, sl: '/SITE', sdec: 1,
									  good: 'low', key: 'blackout', color: '#be2d06' },
									{ t1: ld.burn, t3: td?.burn||0, tl: 'BURN/DAY (L)', tc: 'SUM(used) ÷ days',
									  s1: ld.efficiency||0, s3: td?.efficiency||0, sl: 'L/HR', sdec: 1,
									  good: 'low', key: 'fuel', color: '#9d4867' },
									{ t1: ld.cost, t3: td?.cost||0, tl: 'COST (MMK)', tc: 'burn × price',
									  s1: ld.needed, s3: td?.needed||0, sl: 'NEEDED',
									  good: 'low', key: 'fuel', color: '#6d597a' },
								] as m, i}
									{@const rd = periodKpis.recent_daily || []}
									{@const tDiff = m.t3 ? ((m.t1 - m.t3) / Math.max(Math.abs(m.t3), 0.01) * 100) : 0}
									{@const tImpr = m.good === 'high' ? tDiff > 1 : tDiff < -1}
									{@const tClr = Math.abs(tDiff) < 1 ? '#65655e' : tImpr ? '#007518' : '#be2d06'}
									{@const tArr = tDiff > 1 ? '▲' : tDiff < -1 ? '▼' : '→'}
									{@const vals = rd.map((d: any) => d[m.key] || 0)}
									{@const maxVal = Math.max(...vals, 1)}
									{@const avg3 = m.t3 || (rd.length >= 4 ? (vals[0] + vals[1] + vals[2]) / 3 : 0)}
									{@const sites = rd.map((d: any) => d.sites || 1)}
									{@const avg3PerSite = m.s3 || (rd.length >= 4 ? ((vals[0]/sites[0] + vals[1]/sites[1] + vals[2]/sites[2]) / 3) : 0)}
									<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
										<!-- Header -->
										<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
											<span class="text-[11px] font-black uppercase">{m.tl}</span>
											<span class="text-[10px] font-bold" style="color: {tClr};">{tArr}{Math.abs(tDiff).toFixed(0)}% vs 3D</span>
										</div>
										<!-- KPIs row -->
										<div class="flex">
											<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
												<div class="text-2xl font-black" style="color: #383832;">{m.tdec ? m.t1.toFixed(m.tdec) : fmtV(m.t1)}</div>
												<div class="text-[9px] font-bold" style="color: #65655e;">TOTAL</div>
												<div class="text-[8px]" style="color: #9d9d91;">3D: {m.tdec ? m.t3.toFixed(m.tdec) : fmtV(m.t3)}</div>
											</div>
											<div class="p-3 flex flex-col justify-center" style="flex: 1;">
												<div class="text-2xl font-black" style="color: #383832;">{m.sdec ? m.s1.toFixed(m.sdec) : fmtV(m.s1)}</div>
												<div class="text-[9px] font-bold" style="color: #65655e;">{m.sl}</div>
												<div class="text-[8px]" style="color: #9d9d91;">3D: {m.sdec ? m.s3.toFixed(m.sdec) : fmtV(m.s3)}</div>
											</div>
										</div>
										<!-- Horizontal bar chart with daily values -->
										<div style="border-top: 1px solid #ebe8dd;">
											{#each rd as day, di}
												{@const isLatest = di === rd.length - 1}
												{@const v = vals[di]}
												{@const pct = maxVal > 0 ? (v / maxVal * 100) : 0}
												{@const perSite = sites[di] > 0 ? v / sites[di] : 0}
												<!-- 3D avg line -->
												{#if isLatest && rd.length >= 4}
													<div class="px-3 py-0.5 flex items-center gap-2" style="border-top: 2px dashed {m.color};">
														<span class="text-[8px] font-bold" style="color: {m.color};">3D AVG: {fmtV(Math.round(avg3))} ({avg3PerSite.toFixed(1)}{m.sl})</span>
													</div>
												{/if}
												<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid {isLatest ? m.color : 'rgba(56,56,50,0.08)'}; {isLatest ? 'background: rgba(56,56,50,0.03);' : ''}">
													<span class="text-[9px] w-10 shrink-0 {isLatest ? 'font-black' : ''}" style="color: {isLatest ? m.color : '#828179'};">
														{day.date.slice(5)}
													</span>
													<!-- Bar -->
													<div class="flex-1 h-4 relative" style="background: #f0ede3;">
														<div class="h-full" style="width: {pct}%; background: {isLatest ? m.color : m.color + '60'};"></div>
														{#if avg3 > 0}
															<div class="absolute top-0 h-full w-px" style="left: {Math.min(avg3/maxVal*100, 100)}%; background: {m.color}; opacity: 0.5;"></div>
														{/if}
													</div>
													<span class="text-[9px] w-12 text-right shrink-0 {isLatest ? 'font-black' : ''}" style="color: #383832;">{fmtV(Math.round(v))}</span>
													<span class="text-[8px] w-12 text-right shrink-0" style="color: #9d9d91;">{perSite.toFixed(1)}{m.sl}</span>
													{#if isLatest && avg3 > 0}
														{@const vsAvg = (v - avg3) / avg3 * 100}
														{@const vClr = (m.good === 'high' ? vsAvg > 1 : vsAvg < -1) ? '#007518' : (m.good === 'high' ? vsAvg < -1 : vsAvg > 1) ? '#be2d06' : '#65655e'}
														<span class="text-[8px] font-bold w-14 text-right shrink-0" style="color: {vClr};">{vsAvg > 0 ? '▲' : vsAvg < 0 ? '▼' : '→'}{Math.abs(vsAvg).toFixed(0)}%</span>
													{:else}
														<span class="w-14 shrink-0"></span>
													{/if}
												</div>
											{/each}
										</div>
										<!-- Formula -->
										<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">{m.tc}</div>
									</div>
								{/each}
							</div>

							<!-- Sales, Cost, Diesel% — same card style with bar charts -->
							<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
								{#each [
									{ t1: ld.has_sales ? ld.sales : 0, t3: td?.has_sales ? td.sales : 0, tl: 'SALES (MMK)', tc: 'SUM(sales_amt)',
									  s1: ld.has_sales && ld.sites > 0 ? ld.sales / ld.sites : 0, s3: td && td.has_sales && td.sites > 0 ? td.sales / td.sites : 0, sl: '/SITE', sdec: 0,
									  good: 'high', key: 'sales', color: '#006f7c', na: !ld.has_sales },
									{ t1: ld.cost, t3: td?.cost || 0, tl: 'DIESEL COST (MMK)', tc: 'burn × fuel_price',
									  s1: ld.sites > 0 ? ld.cost / ld.sites : 0, s3: td && td.sites > 0 ? td.cost / td.sites : 0, sl: '/SITE', sdec: 0,
									  good: 'low', key: 'cost', color: '#9d4867', na: false },
									{ t1: ld.has_sales ? ld.diesel_pct : 0, t3: td?.has_sales ? td.diesel_pct : 0, tl: 'DIESEL % OF SALES', tc: 'cost ÷ sales × 100', tdec: 2,
									  s1: 0, s3: 0, sl: '', sdec: 0, noSite: true,
									  good: 'low', key: 'diesel_pct', color: ld.has_sales && ld.diesel_pct > 3 ? '#be2d06' : '#007518', na: !ld.has_sales },
								] as m, i}
									{@const rd = periodKpis.recent_daily || []}
									{@const tDiff = m.t3 ? ((m.t1 - m.t3) / Math.max(Math.abs(m.t3), 0.01) * 100) : 0}
									{@const tImpr = m.good === 'high' ? tDiff > 1 : tDiff < -1}
									{@const tClr = Math.abs(tDiff) < 1 ? '#65655e' : tImpr ? '#007518' : '#be2d06'}
									{@const tArr = tDiff > 1 ? '▲' : tDiff < -1 ? '▼' : '→'}
									{@const vals = rd.map((d: any) => d[m.key] || 0)}
									{@const maxVal = Math.max(...vals, 1)}
									{@const avg3 = m.t3 || (rd.length >= 4 ? (vals[0] + vals[1] + vals[2]) / 3 : 0)}
									{@const sites = rd.map((d: any) => d.sites || 1)}
									<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
										<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
											<span class="text-[11px] font-black uppercase">{m.tl}</span>
											{#if !m.na}
												<span class="text-[10px] font-bold" style="color: {tClr};">{tArr}{Math.abs(tDiff).toFixed(0)}% vs 3D</span>
											{/if}
										</div>
										<div class="flex">
											<div class="p-3 flex flex-col justify-center" style="flex: 1; {m.noSite ? '' : 'border-right: 1px dashed #ebe8dd;'}">
												<div class="text-2xl font-black" style="color: {m.na ? '#828179' : '#383832'};">{m.na ? 'N/A' : m.tdec ? m.t1.toFixed(m.tdec) + '%' : fmtV(m.t1)}</div>
												<div class="text-[9px] font-bold" style="color: #65655e;">TOTAL</div>
												<div class="text-[8px]" style="color: #9d9d91;">3D: {m.na ? 'N/A' : m.tdec ? m.t3.toFixed(m.tdec) + '%' : fmtV(m.t3)}</div>
											</div>
											{#if !m.noSite}
												<div class="p-3 flex flex-col justify-center" style="flex: 1;">
													<div class="text-2xl font-black" style="color: {m.na ? '#828179' : '#383832'};">{m.na ? 'N/A' : fmtV(m.s1)}</div>
													<div class="text-[9px] font-bold" style="color: #65655e;">{m.sl}</div>
													<div class="text-[8px]" style="color: #9d9d91;">3D: {m.na ? 'N/A' : fmtV(m.s3)}</div>
												</div>
											{/if}
										</div>
										<!-- Horizontal bar chart with daily values -->
										<div style="border-top: 1px solid #ebe8dd;">
											{#each rd as day, di}
												{@const isLatest = di === rd.length - 1}
												{@const v = vals[di]}
												{@const pct = maxVal > 0 ? (v / maxVal * 100) : 0}
												{@const perSite = sites[di] > 0 ? v / sites[di] : 0}
												{#if isLatest && rd.length >= 4}
													<div class="px-3 py-0.5 flex items-center gap-2" style="border-top: 2px dashed {m.color};">
														<span class="text-[8px] font-bold" style="color: {m.color};">3D AVG: {m.tdec ? avg3.toFixed(m.tdec) + '%' : fmtV(Math.round(avg3))}{m.noSite ? '' : ' (' + fmtV(Math.round(avg3 / ((sites[0]+sites[1]+sites[2])/3))) + m.sl + ')'}</span>
													</div>
												{/if}
												<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid {isLatest ? m.color : 'rgba(56,56,50,0.08)'}; {isLatest ? 'background: rgba(56,56,50,0.03);' : ''}">
													<span class="text-[9px] w-10 shrink-0 {isLatest ? 'font-black' : ''}" style="color: {isLatest ? m.color : '#828179'};">{day.date.slice(5)}</span>
													<div class="flex-1 h-4 relative" style="background: #f0ede3;">
														<div class="h-full" style="width: {pct}%; background: {isLatest ? m.color : m.color + '60'};"></div>
														{#if avg3 > 0}
															<div class="absolute top-0 h-full w-px" style="left: {Math.min(avg3/maxVal*100, 100)}%; background: {m.color}; opacity: 0.5;"></div>
														{/if}
													</div>
													<span class="text-[9px] w-12 text-right shrink-0 {isLatest ? 'font-black' : ''}" style="color: #383832;">{m.tdec ? v.toFixed(m.tdec) + '%' : fmtV(Math.round(v))}</span>
													{#if !m.noSite}
														<span class="text-[8px] w-12 text-right shrink-0" style="color: #9d9d91;">{fmtV(Math.round(perSite))}{m.sl}</span>
													{/if}
													{#if isLatest && avg3 > 0}
														{@const vsAvg = (v - avg3) / avg3 * 100}
														{@const vClr = (m.good === 'high' ? vsAvg > 1 : vsAvg < -1) ? '#007518' : (m.good === 'high' ? vsAvg < -1 : vsAvg > 1) ? '#be2d06' : '#65655e'}
														<span class="text-[8px] font-bold w-14 text-right shrink-0" style="color: {vClr};">{vsAvg > 0 ? '▲' : vsAvg < 0 ? '▼' : '→'}{Math.abs(vsAvg).toFixed(0)}%</span>
													{:else}
														<span class="w-14 shrink-0"></span>
													{/if}
												</div>
											{/each}
										</div>
										<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">{m.tc}</div>
									</div>
								{/each}
							</div>

							<!-- Storyline -->
							{#if periodKpis.story && periodKpis.story.length > 0}
								<div class="px-4 py-3" style="background: white; border-top: 2px solid #383832;">
									<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">SITUATION REPORT</div>
									<div class="text-xs leading-relaxed" style="color: #383832;">
										{#each periodKpis.story as line}
											<p class="mb-1">{line}</p>
										{/each}
									</div>
								</div>
							{/if}

							<!-- Sector Snapshot (Group view only) -->
							{#if sectorSnap.length > 1}
								<div class="px-4 py-2" style="background: white; border-top: 2px solid #383832;">
									<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">SECTOR SNAPSHOT</div>
									<div class="overflow-x-auto">
										<table class="w-full text-xs">
											<thead><tr style="background: #ebe8dd;">
												<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">SECTOR</th>
												<th class="py-1.5 px-2 text-center font-black">SITES</th>
												<th class="py-1.5 px-2 text-center font-black">GENS</th>
												<th class="py-1.5 px-2 text-center font-black">RUNNING</th>
												<th class="py-1.5 px-2 text-center font-black">BUFFER</th>
												<th class="py-1.5 px-2 text-center font-black">BURN</th>
												<th class="py-1.5 px-2 text-center font-black">COST</th>
												<th class="py-1.5 px-2 text-center font-black">BO HR</th>
												<th class="py-1.5 px-2 text-center font-black">DIESEL%</th>
												<th class="py-1.5 px-2 text-center font-black">CRIT</th>
												<th class="py-1.5 px-2 text-center font-black">STATUS</th>
											</tr></thead>
											<tbody>
												{#each sectorSnap as ss, si}
													{@const bfc = ss.buffer >= 7 ? '#007518' : ss.buffer >= 3 ? '#ff9d00' : '#be2d06'}
													{@const runPct = ss.total_gens > 0 ? Math.round(ss.running_gens / ss.total_gens * 100) : 0}
													<tr style="background: {si % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
														<td class="py-1.5 px-2 font-bold">{ss.sector}</td>
														<td class="py-1.5 px-2 text-center">{ss.sites}</td>
														<td class="py-1.5 px-2 text-center font-mono">{ss.total_gens || 0}</td>
														<td class="py-1.5 px-2 text-center font-bold" style="color: {runPct >= 80 ? '#007518' : runPct >= 50 ? '#ff9d00' : '#be2d06'};">{ss.running_gens || 0}/{ss.total_gens || 0} <span class="text-[8px] font-normal">({runPct}%)</span></td>
														<td class="py-1.5 px-2 text-center font-bold" style="color: {bfc};">{ss.buffer}d</td>
														<td class="py-1.5 px-2 text-center font-mono">{fmtV(ss.burn)}</td>
														<td class="py-1.5 px-2 text-center font-mono">{fmtV(ss.cost)}</td>
														<td class="py-1.5 px-2 text-center font-mono">{ss.blackout}</td>
														<td class="py-1.5 px-2 text-center font-mono">{ss.diesel_pct != null ? ss.diesel_pct + '%' : 'N/A'}</td>
														<td class="py-1.5 px-2 text-center font-black" style="color: {ss.crit > 0 ? '#be2d06' : '#65655e'};">{ss.crit}</td>
														<td class="py-1.5 px-2 text-center">{ss.status}</td>
													</tr>
												{/each}
											</tbody>
										</table>
									</div>
								</div>
							{/if}


							<!-- Formula Reference -->
							<div style="border-top: 2px solid #383832;">
								<div class="px-4 py-2 flex items-center gap-2" style="background: #383832; color: #feffd6;">
									<span class="material-symbols-outlined text-sm" style="color: #00fc40;">functions</span>
									<span class="text-[11px] font-black uppercase">FORMULA REFERENCE</span>
								</div>
								<div class="overflow-x-auto">
									<table class="w-full text-[10px]" style="border-collapse: collapse;">
										<thead>
											<tr style="background: #ebe8dd;">
												<th class="py-1.5 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832; width: 130px;">METRIC</th>
												<th class="py-1.5 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">FORMULA</th>
												<th class="py-1.5 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">PER SITE</th>
												<th class="py-1.5 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">SOURCE</th>
											</tr>
										</thead>
										<tbody>
											{#each [
												{ m: 'BUFFER DAYS', f: 'last_day_tank ÷ 3d_avg_daily_fuel', ps: '—', src: 'daily_site_summary', clr: '#007518' },
												{ m: 'GEN RUN HR', f: 'SUM(gen_run_hr)', ps: 'total ÷ sites', src: 'daily_site_summary', clr: '#ff9d00' },
												{ m: 'FUEL USED', f: 'SUM(daily_used)', ps: 'total ÷ sites', src: 'daily_site_summary', clr: '#e85d04' },
												{ m: 'TANK BAL', f: 'SUM(spare_tank) on last day', ps: 'total ÷ sites', src: 'daily_site_summary', clr: '#007518' },
												{ m: 'BLACKOUT HR', f: 'SUM(blackout_hr)', ps: 'total ÷ sites', src: 'daily_site_summary', clr: '#be2d06' },
												{ m: 'BURN / DAY', f: 'SUM(daily_used) ÷ days', ps: 'L/HR = fuel ÷ gen_hr', src: 'daily_site_summary', clr: '#9d4867' },
												{ m: 'COST (MMK)', f: 'fuel_used × latest_purchase_price', ps: 'total ÷ sites', src: 'fuel_purchases', clr: '#6d597a' },
												{ m: 'SALES (MMK)', f: 'SUM(sales_amt)', ps: 'total ÷ sites', src: 'daily_sales', clr: '#006f7c' },
												{ m: 'DIESEL %', f: '(cost ÷ sales) × 100', ps: '—', src: 'derived', clr: '#be2d06' },
												{ m: 'MARGIN %', f: '(margin ÷ sales) × 100', ps: '—', src: 'daily_sales', clr: '#007518' },
												{ m: 'EFFICIENCY', f: 'SUM(fuel) ÷ SUM(gen_hr)', ps: '—', src: 'derived', clr: '#65655e' },
												{ m: '3D AVG', f: 'prior 3 days daily avg (not sum)', ps: 'avg of daily per-site', src: '/period-kpis', clr: '#65655e' },
												{ m: '1D vs 3D', f: '(1D − 3D) ÷ 3D × 100%', ps: '▲ up ▼ down → flat', src: 'derived', clr: '#65655e' },
											] as r, i}
												<tr style="background: {i % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
													<td class="py-1.5 px-3 font-bold" style="color: {r.clr};">{r.m}</td>
													<td class="py-1.5 px-3 font-mono" style="color: #383832;">{r.f}</td>
													<td class="py-1.5 px-3 font-mono" style="color: #65655e;">{r.ps}</td>
													<td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">{r.src}</code></td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							</div>

						</div>
					{/if}
				</div>
				{:else if dashSection === 'trends'}
					<!-- Quick Navigation -->
					{@const storyChapters = [
						{ id: 'ch-blackout', icon: 'power_off', label: '1. BLACKOUTS' },
						{ id: 'ch-fuel', icon: 'local_gas_station', label: '2. FUEL' },
						{ id: 'ch-cost', icon: 'payments', label: '3. COST' },
						{ id: 'ch-revenue', icon: 'trending_down', label: '4. REVENUE' },
						{ id: 'ch-buffer', icon: 'battery_alert', label: '5. BUFFER' },
						{ id: 'ch-efficiency', icon: 'speed', label: '6. WASTE' },
						{ id: 'ch-rolling', icon: 'trending_up', label: '7. TRENDS' },
						{ id: 'ch-monthly', icon: 'calendar_month', label: '8. GRADES' },
					]}
					<div class="flex flex-wrap gap-1 mb-4 p-2 sticky top-28 z-20" style="background: #f6f4e9; border: 2px solid #383832;">
						<span class="text-[9px] font-black uppercase self-center mr-2" style="color: #65655e;">JUMP TO:</span>
						{#each storyChapters as ch}
							<button onclick={() => document.getElementById(ch.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
								class="px-3 py-1.5 text-[9px] font-black uppercase flex items-center gap-1 transition-colors hover:bg-[#383832] hover:text-[#feffd6]"
								style="background: white; color: #383832; border: 1px solid #383832;">
								<span class="material-symbols-outlined text-xs">{ch.icon}</span>
								{ch.label}
							</button>
						{/each}
					</div>

					<div class="space-y-6 section-animate">
						<TrendCharts dateFrom={dateFrom} dateTo={dateTo} sector={sectorApiParam()} />
						<RollingCharts dateFrom={dateFrom} dateTo={dateTo} sector={sectorApiParam()} />


						<!-- #77 Blackout Calendar -->
						{#if blackoutCalendar.length > 0}
							{@const calMonths = [...new Set(blackoutCalendar.map((d: any) => d.date.slice(0, 7)))].sort().reverse().slice(0, 3)}
							<div>
								<div class="px-4 py-2.5 font-black text-sm uppercase" style="background: #383832; color: #feffd6;">BLACKOUT CALENDAR</div>
								<div class="mt-3 flex flex-wrap gap-6">
									{#each calMonths as month}
										{@const mData = blackoutCalendar.filter((d: any) => d.date.startsWith(month))}
										{@const year = parseInt(month.slice(0, 4))}
										{@const mon = parseInt(month.slice(5, 7))}
										{@const firstDow = new Date(year, mon - 1, 1).getDay()}
										{@const daysInMonth = new Date(year, mon, 0).getDate()}
										{@const dayMap = new Map(mData.map((d: any) => [parseInt(d.date.slice(8, 10)), d.avg_bo]))}
										<div>
											<div class="font-black text-sm mb-2" style="color: #383832;">{month}</div>
											<div class="grid gap-[3px]" style="grid-template-columns: repeat(7, 28px);">
												{#each ['M','T','W','T','F','S','S'] as dow}
													<div class="text-center text-[9px] font-bold" style="color: #65655e;">{dow}</div>
												{/each}
												{#each Array(firstDow === 0 ? 6 : firstDow - 1) as _}
													<div></div>
												{/each}
												{#each Array(daysInMonth) as _, i}
													{@const day = i + 1}
													{@const v = dayMap.get(day)}
													{@const bg = v == null ? '#ebe8dd' : v < 4 ? '#007518' : v < 8 ? '#ff9d00' : v < 12 ? '#f95630' : '#be2d06'}
													{@const tc = v == null ? '#65655e' : 'white'}
													<div class="text-center text-[10px] font-bold rounded-sm cursor-default"
														style="background: {bg}; color: {tc}; padding: 3px 0;"
														title="{v != null ? v + 'hr' : 'No data'}">{day}</div>
												{/each}
											</div>
										</div>
									{/each}
								</div>
								<div class="flex gap-3 mt-3 text-[10px] font-bold">
									<span class="px-2 py-0.5" style="background: #007518; color: white;">{'<'}4hr</span>
									<span class="px-2 py-0.5" style="background: #ff9d00; color: white;">4-8hr</span>
									<span class="px-2 py-0.5" style="background: #f95630; color: white;">8-12hr</span>
									<span class="px-2 py-0.5" style="background: #be2d06; color: white;">12hr+</span>
									<span class="px-2 py-0.5" style="background: #ebe8dd; color: #65655e;">No data</span>
								</div>
							</div>
						{/if}
					</div>
				{:else if dashSection === 'sector'}
					<!-- Quick Navigation -->
					{@const whereChapters = [
						{ id: 'where-sites', icon: 'pin_drop', label: '1. ALL SITES' },
						{ id: 'where-lng', icon: 'bolt', label: '2. REG vs LNG' },
					]}
					<div class="flex flex-wrap gap-1 mb-4 p-2 sticky top-28 z-20" style="background: #f6f4e9; border: 2px solid #383832;">
						<span class="text-[9px] font-black uppercase self-center mr-2" style="color: #65655e;">JUMP TO:</span>
						{#each whereChapters as ch}
							<button onclick={() => document.getElementById(ch.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
								class="px-3 py-1.5 text-[9px] font-black uppercase flex items-center gap-1 transition-colors hover:bg-[#383832] hover:text-[#feffd6]"
								style="background: white; color: #383832; border: 1px solid #383832;">
								<span class="material-symbols-outlined text-xs">{ch.icon}</span>
								{ch.label}
							</button>
						{/each}
					</div>

					<div class="space-y-6 section-animate">
						<!-- CH1: ALL SITES (summary + site table) -->
						<div id="where-sites" class="scroll-mt-36"></div>
						<SectorSites sector={sectorApiParam()} company={activeCompany} sites={selectedSites} />

						<!-- CH3: REGULAR vs LNG -->
						<div id="where-lng" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3">
									<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">bolt</span>
									<div>
										<div class="font-black uppercase text-sm">CHAPTER 3: REGULAR vs LNG</div>
										<div class="text-[10px] opacity-75">Comparing diesel generators vs LNG — which fuel type is more efficient?</div>
									</div>
								</div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">
									? Is LNG cheaper per hour? Do LNG sites have better buffer days?
								</div>
							</div>
						</div>
						<LngComparison dateFrom={dateFrom} dateTo={dateTo} />
					</div>
				<!-- ═══ TAB 04: HOW WE RAN ═══ -->
				{:else if dashSection === 'operations'}
					{@const opsNav = [
						{ id: 'ops-modes', icon: 'toggle_on', label: '1. MODES' },
						{ id: 'ops-delivery', icon: 'local_shipping', label: '2. DELIVERY' },
						{ id: 'ops-fleet', icon: 'build', label: '3. FLEET' },
						{ id: 'ops-transfers', icon: 'swap_horiz', label: '4. TRANSFERS' },
						{ id: 'ops-loadopt', icon: 'speed', label: '5. OPTIMIZATION' },
						{ id: 'ops-scores', icon: 'shield', label: '6. SCORES' },
						{ id: 'ops-alerts', icon: 'notifications_active', label: '7. ALERTS' },
						{ id: 'ops-patterns', icon: 'date_range', label: '8. PATTERNS' },
						{ id: 'ops-waste', icon: 'warning', label: '9. WASTE' },
					]}
					<div class="flex flex-wrap gap-1 mb-4 p-2 sticky top-28 z-20" style="background: #f6f4e9; border: 2px solid #383832;">
						<span class="text-[9px] font-black uppercase self-center mr-2" style="color: #65655e;">JUMP TO:</span>
						{#each opsNav as ch}
							<button onclick={() => document.getElementById(ch.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
								class="px-3 py-1.5 text-[9px] font-black uppercase flex items-center gap-1 transition-colors hover:bg-[#383832] hover:text-[#feffd6]"
								style="background: white; color: #383832; border: 1px solid #383832;">
								<span class="material-symbols-outlined text-xs">{ch.icon}</span> {ch.label}
							</button>
						{/each}
					</div>
					<div class="space-y-6 section-animate">
						<!-- Operations Situation Report -->
						{#if periodKpis.last_day}
							{@const ld = periodKpis.last_day}
							{@const snap = periodKpis.sector_snapshot || []}
							{@const totalGens = snap.reduce((s: number, ss: any) => s + (ss.total_gens || 0), 0)}
							{@const runningGens = snap.reduce((s: number, ss: any) => s + (ss.running_gens || 0), 0)}
							{@const runPct = totalGens > 0 ? Math.round(runningGens / totalGens * 100) : 0}
							{@const critSectors = snap.filter((ss: any) => ss.crit > 0)}
							{@const fmtOps = (v: number) => { if (v >= 1e9) return (v/1e9).toLocaleString(undefined, {minimumFractionDigits:1, maximumFractionDigits:1})+'B'; if (v >= 1e6) return (v/1e6).toLocaleString(undefined, {minimumFractionDigits:1, maximumFractionDigits:1})+'M'; if (v >= 1e3) return (v/1e3).toLocaleString(undefined, {minimumFractionDigits:1, maximumFractionDigits:1})+'K'; return v.toLocaleString(); }}
							<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832; background: white;">
								<div class="px-4 py-2" style="background: #383832; color: #feffd6;">
									<span class="text-[11px] font-black uppercase">OPERATIONS SITUATION REPORT</span>
									<span class="text-[9px] opacity-75 ml-2">{ld.date}</span>
								</div>
								<div class="px-4 py-3 text-xs leading-relaxed" style="color: #383832;">
									<p class="mb-1.5">On {ld.date}, <strong>{ld.sites} sites</strong> reported across {snap.length} sectors with <strong>{totalGens} generators</strong> ({runningGens} running, <span style="color: {runPct >= 80 ? '#007518' : runPct >= 50 ? '#ff9d00' : '#be2d06'}; font-weight: bold;">{runPct}% utilization</span>).</p>
									<p class="mb-1.5">Generators ran <strong>{fmtOps(ld.total_gen_hr || 0)} hours</strong> total, consuming <strong>{fmtOps(ld.total_fuel || 0)}L</strong> of diesel at <strong>{ld.efficiency || 0} L/Hr</strong> efficiency, costing <strong>{fmtOps(ld.cost || 0)} MMK</strong>.</p>
									{#if ld.crit > 0}
										<p class="mb-1.5" style="color: #be2d06;"><strong>{ld.crit} sites are CRITICAL</strong> (&lt;3 days fuel) and need immediate delivery of <strong>{fmtOps(ld.needed || 0)}L</strong>.</p>
									{/if}
									{#if critSectors.length > 0}
										<p class="mb-1.5">Sectors with critical sites: {#each critSectors as cs, ci}<strong style="color: #be2d06;">{cs.sector} ({cs.crit})</strong>{ci < critSectors.length - 1 ? ', ' : ''}{/each}.</p>
									{/if}
									{#if (ld.sites_not_reported || 0) > 0}
										<p class="mb-1.5" style="color: #ff9d00;">{ld.sites_not_reported} sites did not report — data may be incomplete.</p>
									{/if}
									<p>Fleet buffer stands at <strong style="color: {ld.buffer >= 7 ? '#007518' : ld.buffer >= 3 ? '#ff9d00' : '#be2d06'};">{ld.buffer} days</strong> — {ld.buffer >= 7 ? 'fuel supply is healthy.' : ld.buffer >= 3 ? 'fuel supply needs monitoring.' : 'fuel supply is critical, prioritize deliveries.'}</p>
								</div>
							</div>
						{/if}

						<OperatingModes sector={sectorApiParam()} company={activeCompany} />
						<OperationsTables sector={sectorApiParam()} />
						<GroupExtras dateFrom={dateFrom} dateTo={dateTo} sector={sectorApiParam()} />
					</div>

				<!-- ═══ TAB 05: WHAT'S AT RISK ═══ -->
				{:else if dashSection === 'risk'}
					<RiskPanel />

				<!-- ═══ TAB 06: FUEL & COST ═══ -->
				{:else if dashSection === 'fuel'}
					<FuelIntel />

				<!-- ═══ TAB 07: WHAT'S NEXT ═══ -->
				{:else if dashSection === 'predictions'}
					<div class="space-y-6 section-animate">
						<Predictions sector={sectorApiParam()} dateFrom={dateFrom} dateTo={dateTo} />
						<WhatIf />
						{#if transferData.length > 0}
							<div style="border: 2px solid #383832; background: white;">
								<div class="px-4 py-2 flex justify-between items-center" style="background: #383832; color: #feffd6;">
									<span class="font-bold uppercase text-sm">RECOMMENDED FUEL TRANSFERS</span>
									<span class="text-[10px]">{transferData.length} opportunities</span>
								</div>
								<div class="overflow-x-auto">
									<table class="w-full text-xs">
										<thead><tr style="background: #ebe8dd;">
											<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">From</th>
											<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">To</th>
											<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">Liters</th>
											<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">From Buffer</th>
											<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">To Buffer</th>
											<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">Priority</th>
										</tr></thead>
										<tbody>
											{#each transferData.slice(0, 20) as t, i}
												<tr style="background: {i % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
													<td class="py-2 px-3 font-bold" style="color: #007518;">{t.from_site || t.donor || '—'}</td>
													<td class="py-2 px-3 font-bold" style="color: #be2d06;">{t.to_site || t.recipient || '—'}</td>
													<td class="py-2 px-3 text-center font-mono">{Math.round(t.liters || t.transfer_liters || 0).toLocaleString()}</td>
													<td class="py-2 px-3 text-center font-mono">{(t.from_buffer || t.donor_buffer || 0).toFixed?.(1) ?? '—'}d</td>
													<td class="py-2 px-3 text-center font-mono">{(t.to_buffer || t.recipient_buffer || 0).toFixed?.(1) ?? '—'}d</td>
													<td class="py-2 px-3 text-center">
														<span class="px-2 py-0.5 text-[10px] font-black uppercase"
															style="background: {(t.priority || t.urgency || 'MEDIUM') === 'HIGH' || (t.priority || t.urgency || 'MEDIUM') === 'CRITICAL' ? '#be2d06' : (t.priority || t.urgency || 'MEDIUM') === 'MEDIUM' ? '#ff9d00' : '#007518'}; color: white;">{t.priority || t.urgency || 'MEDIUM'}</span>
													</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							</div>
						{/if}
					</div>
				{/if}
			</div>
		</div>

		<!-- Site Modal -->
		{#if showSiteModal}
			<SiteModal siteId={modalSiteId} {sites} onclose={() => showSiteModal = false} />
		{/if}

		<!-- Site Comparison Modal -->
		{#if showComparison && selectedSites.length === 2}
			<div class="fixed inset-0 z-[200] flex items-center justify-center" style="background: rgba(0,0,0,0.6);"
				onclick={() => showComparison = false}>
				<div class="w-[90vw] max-w-[800px] max-h-[80vh] overflow-y-auto"
					style="background: #feffd6; border: 3px solid #383832; box-shadow: 6px 6px 0px 0px #383832;"
					onclick={(e) => e.stopPropagation()}>

					<div class="px-4 py-3 flex justify-between items-center" style="background: #383832; color: #feffd6;">
						<span class="font-black uppercase text-sm">SITE COMPARISON</span>
						<button onclick={() => showComparison = false} class="font-black text-lg">&#10005;</button>
					</div>

					<div class="overflow-x-auto">
						<table class="w-full text-xs">
							<thead><tr style="background: #ebe8dd;">
								<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">METRIC</th>
								<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832; color: #006f7c;">{selectedSites[0]}</th>
								<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832; color: #9d4867;">{selectedSites[1]}</th>
								<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">WINNER</th>
							</tr></thead>
							<tbody>
								{#each compareData() as m, i}
									{@const better1 = m.higher ? (m.v1 || 0) > (m.v2 || 0) : (m.v1 || 0) < (m.v2 || 0)}
									{@const better2 = !better1 && (m.v1 || 0) !== (m.v2 || 0)}
									<tr style="background: {i % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
										<td class="py-2 px-3 font-bold" style="color: #383832;">{m.name}</td>
										<td class="py-2 px-3 text-center font-mono" style="color: {better1 ? '#007518' : '#383832'}; font-weight: {better1 ? '800' : '400'};">
											{typeof m.v1 === 'number' ? m.v1.toLocaleString(undefined, {maximumFractionDigits: 1}) : '\u2014'}
										</td>
										<td class="py-2 px-3 text-center font-mono" style="color: {better2 ? '#007518' : '#383832'}; font-weight: {better2 ? '800' : '400'};">
											{typeof m.v2 === 'number' ? m.v2.toLocaleString(undefined, {maximumFractionDigits: 1}) : '\u2014'}
										</td>
										<td class="py-2 px-3 text-center font-black text-[10px]" style="color: {better1 ? '#006f7c' : better2 ? '#9d4867' : '#65655e'};">
											{better1 ? selectedSites[0].split('-').pop() : better2 ? selectedSites[1].split('-').pop() : 'TIE'}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>
			</div>
		{/if}
	{:else}
		<div class="text-center py-16" style="background: #f6f4e9; border: 2px solid #383832;">
			<span class="material-symbols-outlined text-5xl" style="color: #65655e;">inbox</span>
			<p class="font-bold mt-3 uppercase text-sm" style="color: #383832;">NO DATA FOR SELECTED FILTERS</p>
			<p class="text-xs mt-2" style="color: #65655e;">Try selecting a different sector, date range, or upload data first.</p>
		</div>
	{/if}
{/if}
