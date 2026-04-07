<script lang="ts">
	import { api, downloadExcel } from '$lib/api';
	import { onMount } from 'svelte';
	import AiInsightPanel from '$lib/components/AiInsightPanel.svelte';

	let { sector = '', company = 'All', sites: selectedSiteIds = [] as string[] }: { sector?: string; company?: string; sites?: string[] } = $props();
	let sites: any[] = $state([]);
	let count = $state(0);
	let loading = $state(true);
	let sector3dAvgFuel: Record<string, number> = $state({});

	async function load() {
		loading = true;
		try {
			const p = sector ? `?sector=${sector}` : '';
			const data = await api.get(`/sector-sites${p}`);
			sites = (data.sites || []).sort((a: any, b: any) => (b.exp_pct || 0) - (a.exp_pct || 0));
			count = data.count || 0;
			sector3dAvgFuel = data.sector_3d_avg_fuel || {};
		} catch (e) {
			console.error(e);
		}
		loading = false;
	}

	onMount(load);
	$effect(() => {
		sector;
		load();
	});

	function icon(val: number, thresholds: number[], reverse = false): string {
		const [g, y, a] = thresholds;
		if (reverse) return val <= g ? '\u{1F7E2}' : val <= y ? '\u{1F7E1}' : val <= a ? '\u{1F7E0}' : '\u{1F534}';
		return val >= g ? '\u{1F7E2}' : val >= y ? '\u{1F7E1}' : val >= a ? '\u{1F7E0}' : '\u{1F534}';
	}

	function fmt(v: number): string {
		if (!v) return '0';
		if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
		if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
		return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
	}

	function fmtDec(v: number, d = 1): string {
		if (!v && v !== 0) return '0';
		return v.toFixed(d);
	}

	/** % change between 1D and 3D. For "higher is good" metrics (sales, margin), up=green. For "lower is good" (cost, diesel%), up=red. */
	function pctChg(v1d: number, v3d: number, higherIsGood = true): { text: string; color: string } {
		if (!v3d || v3d === 0) return { text: '—', color: '#65655e' };
		const pct = (v1d - v3d) / Math.abs(v3d) * 100;
		const arrow = pct > 1 ? '▲' : pct < -1 ? '▼' : '→';
		const good = higherIsGood ? pct > 1 : pct < -1;
		const bad = higherIsGood ? pct < -1 : pct > 1;
		const color = good ? '#007518' : bad ? '#be2d06' : '#65655e';
		return { text: `${arrow}${Math.abs(pct).toFixed(0)}%`, color };
	}

	let search = $state('');
	const filteredSites = $derived.by(() => {
		let f = sites;
		if (company && company !== 'All') f = f.filter((r: any) => r.company === company);
		if (selectedSiteIds && selectedSiteIds.length > 0) f = f.filter((r: any) => selectedSiteIds.includes(r.site_id));
		if (search) f = f.filter(r => Object.values(r).some(v => String(v).toLowerCase().includes(search.toLowerCase())));
		return f;
	});


	// Grouped column headers for merged header row
	const siteColGroups = [
		{ group: '', cols: [
			{ key: 'site', label: 'SITE', formula: 'cost_center_code', align: 'left' },
			{ key: 'code', label: 'CODE', formula: 'sector-store', align: 'left' },
		]},
		{ group: '', cols: [
			{ key: 'price', label: 'PRICE/L', formula: 'latest', align: 'center' },
			{ key: 'buffer', label: 'BUFFER', formula: 'tank÷3d_fuel', align: 'center' },
		]},
		{ group: 'BLACKOUT HR', color: '#65655e', cols: [
			{ key: 'bo_1d', label: '1D', formula: 'last day', align: 'center' },
			{ key: 'bo_3d', label: '3D AVG', formula: 'avg 3 days', align: 'center' },
			{ key: 'bo_chg', label: '1D vs 3D', formula: '% change', align: 'center' },
		]},
		{ group: 'TANK (L)', color: '#007518', cols: [
			{ key: 'tank_1d', label: '1D', formula: 'last day', align: 'center' },
			{ key: 'tank_3d', label: '3D AVG', formula: 'avg 3 days', align: 'center' },
			{ key: 'tank_chg', label: '1D vs 3D', formula: '% change', align: 'center' },
		]},
		{ group: 'BURN/DAY (L)', color: '#e85d04', cols: [
			{ key: 'burn_1d', label: '1D', formula: 'last day', align: 'center' },
			{ key: 'burn_3d', label: '3D AVG', formula: 'avg 3 days', align: 'center' },
			{ key: 'burn_chg', label: '1D vs 3D', formula: '% change', align: 'center' },
		]},
		{ group: 'SALES (MMK)', color: '#006f7c', cols: [
			{ key: 'sales_total', label: 'TOTAL', formula: 'all dates', align: 'center' },
			{ key: 'sales_avg', label: 'AVG/DAY', formula: 'total÷days', align: 'center' },
			{ key: 'sales_1d', label: '1D', formula: 'last day', align: 'center' },
			{ key: 'sales_3d', label: '3D AVG', formula: 'avg 3 days', align: 'center' },
			{ key: 'sales_chg', label: '1D vs 3D', formula: '% change', align: 'center' },
		]},
		{ group: 'DIESEL COST (MMK)', color: '#9d4867', cols: [
			{ key: 'cost_total', label: 'TOTAL', formula: 'all dates', align: 'center' },
			{ key: 'cost_avg', label: 'AVG/DAY', formula: 'total÷days', align: 'center' },
			{ key: 'cost_1d', label: '1D', formula: 'fuel×price', align: 'center' },
			{ key: 'cost_3d', label: '3D AVG', formula: 'avg fuel×price', align: 'center' },
			{ key: 'cost_chg', label: '1D vs 3D', formula: '% change', align: 'center' },
		]},
		{ group: 'MARGIN %', color: '#007518', cols: [
			{ key: 'margin_total', label: 'TOTAL', formula: 'all dates', align: 'center' },
			{ key: 'margin_avg', label: 'AVG/DAY', formula: 'avg all days', align: 'center' },
			{ key: 'margin_1d', label: '1D', formula: 'last day', align: 'center' },
			{ key: 'margin_3d', label: '3D AVG', formula: 'avg 3 days', align: 'center' },
			{ key: 'margin_chg', label: '1D vs 3D', formula: '% change', align: 'center' },
		]},
		{ group: 'DIESEL % SALES', color: '#be2d06', cols: [
			{ key: 'exp_total', label: 'TOTAL', formula: 'cost÷sales', align: 'center' },
			{ key: 'exp_avg', label: 'AVG/DAY', formula: 'avg all days', align: 'center' },
			{ key: 'exp_1d', label: '1D', formula: 'last day', align: 'center' },
			{ key: 'exp_3d', label: '3D AVG', formula: 'avg 3 days', align: 'center' },
			{ key: 'exp_chg', label: '1D vs 3D', formula: '% change', align: 'center' },
		]},
	];

	const actionColors: Record<string, string> = {
		OPEN: '#007518',
		MONITOR: '#ff9d00',
		REDUCE: '#f95630',
		CLOSE: '#be2d06'
	};
</script>

<AiInsightPanel type="table" data={{ tab: 'sectors', summary: 'Sector and site-level data with buffer, blackout, sales, cost, margin, diesel% comparisons across 1D vs 3D' }} title="AI INSIGHT — SECTORS & SITES" />

{#if loading}
	<p class="text-sm py-4 text-center" style="color: #65655e;">Loading sector sites...</p>
{:else if sites.length > 0}
	<h2 class="text-lg font-black uppercase mt-6 mb-3" style="color: #383832;">
		{sector || 'ALL'} &mdash; {count} sites
	</h2>

	<!-- Build aggregation maps -->
	{@const buildAgg = (sites: any[], keyFn: (s: any) => string) => {
		const map = new Map<string, any>();
		for (const s of sites) {
			const key = keyFn(s) || 'Unknown';
			const e = map.get(key) || {
				count: 0, crit: 0, warn: 0, safe: 0, sumPrice: 0,
				// Blackout
				sumBO1d: 0, sumBO3d: 0, boCount: 0,
				// Tank
				sumTank1d: 0, sumTank3d: 0,
				// Burn
				sumBurn1d: 0, sumBurn3d: 0,
				// Sales
				sumSalesTotal: 0, sumSalesAvg: 0, sumSales1d: 0, sumSales3d: 0,
				// Cost
				sumCostTotal: 0, sumCostAvg: 0, sumCost1d: 0, sumCost3d: 0,
				// Margin
				sumMarginTotal: 0, sumMarginAvg: 0, sumMargin1d: 0, sumMargin3d: 0,
				// Diesel %
				sumExpTotal: 0, sumExpAvg: 0, sumExp1d: 0, sumExp3d: 0,
				// Totals
				sumTotalFuel: 0, sumTotalGenHr: 0,
				sectors: new Set(), companies: new Set(),
			};
			const buf = s.buffer_days || 0;
			e.count++;
			e.sumPrice += (s.price || 0);
			// Blackout
			e.sumBO1d += (s.last_day_blackout || 0);
			e.sumBO3d += (s.blackout_hr || 0);
			if (s.blackout_hr && s.blackout_hr > 0) e.boCount++;
			// Tank
			e.sumTank1d += (s.tank || 0);
			e.sumTank3d += (s.avg3d_tank || 0);
			// Burn
			e.sumBurn1d += (s.last_day_fuel || 0);
			e.sumBurn3d += (s.daily_fuel || 0);
			// Sales
			e.sumSalesTotal += (s.total_sales || 0);
			e.sumSalesAvg += (s.daily_sales || 0);
			e.sumSales1d += (s.last_day_sales || 0);
			e.sumSales3d += (s.avg3d_sales || 0);
			// Cost
			e.sumCostTotal += (s.total_cost || 0);
			e.sumCostAvg += (s.daily_cost || 0);
			e.sumCost1d += (s.last_day_fuel_cost || 0);
			e.sumCost3d += (s.avg3d_fuel_cost || 0);
			// Margin (avg)
			e.sumMarginTotal += (s.margin_pct || 0);
			e.sumMarginAvg += (s.margin_pct || 0);
			e.sumMargin1d += (s.margin_pct_last_day || 0);
			e.sumMargin3d += (s.margin_pct_3d || 0);
			// Diesel %
			e.sumExpTotal += (s.exp_pct_total || 0);
			e.sumExpAvg += (s.exp_pct || 0);
			e.sumExp1d += (s.exp_pct_last_day || 0);
			e.sumExp3d += (s.exp_pct_3d || 0);
			// Totals
			e.sumTotalFuel += (s.total_fuel || 0); e.sumTotalGenHr += (s.total_gen_hr || 0);
			if (s.sector_id) e.sectors.add(s.sector_id);
			if (s.company) e.companies.add(s.company);
			e.crit += (buf > 0 && buf < 3 ? 1 : 0); e.warn += (buf >= 3 && buf < 7 ? 1 : 0); e.safe += (buf >= 7 ? 1 : 0);
			map.set(key, e);
		}
		return [...map.entries()].sort((a, b) => b[1].count - a[1].count);
	}}
	{@const groupAgg = buildAgg(sites, () => 'ALL')}
	{@const companyAgg = buildAgg(sites, (s: any) => s.company)}
	<!-- Summary uses same column groups as site table (minus SITE/CODE identity + ACTION) -->
	{@const fmtN = (v: number) => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v.toFixed(0)}

	<!-- Combined GROUP + COMPANY Summary (one table) -->
	{@const combinedData = [...groupAgg, ...companyAgg]}
	{@const summaryLevels = [
		{ label: 'GROUP & COMPANY SUMMARY', data: combinedData, dlName: 'Summary', color: '#383832', showSC: false },
	]}
	<!-- Summary column groups (same as site table minus identity+action, plus NAME/OUTLETS/STATUS) -->
	{@const sumColGroups = [
		{ group: '', cols: ['NAME', 'SITES'] },
		{ group: '', cols: ['PRICE/L', 'BUFFER'] },
		{ group: 'BLACKOUT HR', color: '#65655e', cols: ['1D', '3D AVG', '1D vs 3D'] },
		{ group: 'TANK (L)', color: '#007518', cols: ['1D', '3D AVG', '1D vs 3D'] },
		{ group: 'BURN/DAY (L)', color: '#e85d04', cols: ['1D', '3D AVG', '1D vs 3D'] },
		{ group: 'SALES (MMK)', color: '#006f7c', cols: ['TOTAL', 'AVG/DAY', '1D', '3D AVG', '1D vs 3D'] },
		{ group: 'DIESEL COST (MMK)', color: '#9d4867', cols: ['TOTAL', 'AVG/DAY', '1D', '3D AVG', '1D vs 3D'] },
		{ group: 'MARGIN %', color: '#007518', cols: ['TOTAL', 'AVG/DAY', '1D', '3D AVG', '1D vs 3D'] },
		{ group: 'DIESEL % SALES', color: '#be2d06', cols: ['TOTAL', 'AVG/DAY', '1D', '3D AVG', '1D vs 3D'] },
	]}
	{#if combinedData.length > 0}
		<!-- Chapter heading -->
		<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
			<div class="flex items-center gap-3">
				<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">apartment</span>
				<div>
					<div class="font-black uppercase text-sm">CHAPTER 1: GROUP & COMPANY OVERVIEW</div>
					<div class="text-[10px] opacity-75">Aggregated view — how does each company perform across all metrics?</div>
				</div>
			</div>
			<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which company uses the most fuel? Who has the best margin? Worst diesel %?</div>
		</div>
		<div class="mb-4 overflow-x-auto" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<div class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between" style="background: #383832; color: #feffd6;">
				<span>GROUP & COMPANY SUMMARY</span>
				<button onclick={() => {
					const rows = combinedData.map(([name, d]: [string, any]) => {
						const n = d.count || 1;
						const sids = [...d.sectors];
						const sf = sids.reduce((s: number, sid: string) => s + (sector3dAvgFuel[sid] || 0), 0);
						const buf = sf > 0 ? d.sumTank1d / sf : (d.sumBurn3d > 0 ? d.sumTank1d / d.sumBurn3d : 0);
						return {
							name, sites: d.count,
							'price_l': Math.round(d.sumPrice / n),
							buffer: buf.toFixed(1) + 'd',
							blackout_1d: (d.sumBO1d / n).toFixed(1), blackout_3d_avg: (d.sumBO3d / n).toFixed(1),
							'blackout_1d_vs_3d': pctChg(d.sumBO1d, d.sumBO3d, false).text,
							tank_1d: Math.round(d.sumTank1d), tank_3d_avg: Math.round(d.sumTank3d),
							'tank_1d_vs_3d': pctChg(d.sumTank1d, d.sumTank3d, true).text,
							burn_1d: Math.round(d.sumBurn1d), burn_3d_avg: Math.round(d.sumBurn3d),
							'burn_1d_vs_3d': pctChg(d.sumBurn1d, d.sumBurn3d, false).text,
							sales_total: Math.round(d.sumSalesTotal), sales_avg_day: Math.round(d.sumSalesAvg),
							sales_1d: Math.round(d.sumSales1d), sales_3d_avg: Math.round(d.sumSales3d),
							'sales_1d_vs_3d': pctChg(d.sumSales1d, d.sumSales3d, true).text,
							cost_total: Math.round(d.sumCostTotal), cost_avg_day: Math.round(d.sumCostAvg),
							cost_1d: Math.round(d.sumCost1d), cost_3d_avg: Math.round(d.sumCost3d),
							'cost_1d_vs_3d': pctChg(d.sumCost1d, d.sumCost3d, false).text,
							margin_total: (d.sumMarginTotal / n).toFixed(1) + '%', margin_avg_day: (d.sumMarginAvg / n).toFixed(1) + '%',
							margin_1d: (d.sumMargin1d / n).toFixed(1) + '%', margin_3d_avg: (d.sumMargin3d / n).toFixed(1) + '%',
							'margin_1d_vs_3d': pctChg(d.sumMargin1d, d.sumMargin3d, true).text,
							diesel_pct_total: (d.sumExpTotal / n).toFixed(2) + '%', diesel_pct_avg: (d.sumExpAvg / n).toFixed(2) + '%',
							diesel_pct_1d: (d.sumExp1d / n).toFixed(2) + '%', diesel_pct_3d_avg: (d.sumExp3d / n).toFixed(2) + '%',
							'diesel_pct_1d_vs_3d': pctChg(d.sumExp1d, d.sumExp3d, false).text,
						};
					});
					downloadExcel(rows, 'Group Company Summary', {
						columnGroups: [
							{ group: '', cols: ['name', 'sites'] },
							{ group: '', cols: ['price_l', 'buffer'] },
							{ group: 'BLACKOUT HR', color: '#65655e', cols: ['blackout_1d', 'blackout_3d_avg', 'blackout_1d_vs_3d'] },
							{ group: 'TANK (L)', color: '#007518', cols: ['tank_1d', 'tank_3d_avg', 'tank_1d_vs_3d'] },
							{ group: 'BURN/DAY (L)', color: '#e85d04', cols: ['burn_1d', 'burn_3d_avg', 'burn_1d_vs_3d'] },
							{ group: 'SALES (MMK)', color: '#006f7c', cols: ['sales_total', 'sales_avg_day', 'sales_1d', 'sales_3d_avg', 'sales_1d_vs_3d'] },
							{ group: 'DIESEL COST (MMK)', color: '#9d4867', cols: ['cost_total', 'cost_avg_day', 'cost_1d', 'cost_3d_avg', 'cost_1d_vs_3d'] },
							{ group: 'MARGIN %', color: '#007518', cols: ['margin_total', 'margin_avg_day', 'margin_1d', 'margin_3d_avg', 'margin_1d_vs_3d'] },
							{ group: 'DIESEL % SALES', color: '#be2d06', cols: ['diesel_pct_total', 'diesel_pct_avg', 'diesel_pct_1d', 'diesel_pct_3d_avg', 'diesel_pct_1d_vs_3d'] },
						]
					});
				}}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100" style="color: #00fc40;">
					<span class="material-symbols-outlined text-sm">download</span> EXCEL
				</button>
			</div>
			<table class="w-full text-xs" style="border-collapse: collapse;">
				<thead class="sticky top-0 z-10">
					<tr style="background: #383832;">
						{#each sumColGroups as g}
							{#if g.group}
								<th colspan={g.cols.length} class="text-center px-1 py-1.5 text-[9px] font-black uppercase tracking-wider"
									style="color: white; border-left: 2px solid #feffd6; border-right: 2px solid #feffd6; background: {g.color};">{g.group}</th>
							{:else}
								{#each g.cols as _c}<th class="px-1 py-1.5" style="background: #383832;"></th>{/each}
							{/if}
						{/each}
					</tr>
					<tr style="background: #ebe8dd;">
						{#each sumColGroups as g}
							{#each g.cols as label}
								<th class="text-center py-2 px-2 text-[10px] font-black uppercase"
									style="border-bottom: 2px solid #383832; {g.color ? 'border-left: 1px solid #d5d2c7;' : ''} {label === 'CRIT' ? 'color:#be2d06' : label === 'WARN' ? 'color:#ff9d00' : label === 'SAFE' ? 'color:#007518' : ''}">{label}</th>
							{/each}
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each combinedData as [name, d], i}
						{@const n = d.count || 1}
						{@const isGroupRow = name === 'ALL'}
						{@const sectorIds = [...d.sectors]}
						{@const sec3dFuel = sectorIds.reduce((s: number, sid: string) => s + (sector3dAvgFuel[sid] || 0), 0)}
						{@const avgBuf = sec3dFuel > 0 ? d.sumTank1d / sec3dFuel : (d.sumBurn3d > 0 ? d.sumTank1d / d.sumBurn3d : 0)}
						{@const bufColor = avgBuf >= 7 ? '#007518' : avgBuf >= 3 ? '#ff9d00' : '#be2d06'}
						<tr style="background: {isGroupRow ? '#f0ede3' : i % 2 ? '#f6f4e9' : 'white'}; border-bottom: {isGroupRow ? '2px' : '1px'} solid {isGroupRow ? '#383832' : '#ebe8dd'};">
							<td class="py-1.5 px-2 font-bold" style="color: #383832;">{isGroupRow ? '▸ ALL' : '  ' + name}</td>
							<td class="py-1.5 px-2 text-center font-black">{d.count}</td>
							<!-- Price + Buffer -->
							<td class="py-1.5 px-2 text-center font-mono">{fmtN(d.sumPrice / n)}</td>
							<td class="py-1.5 px-2 text-center font-bold" style="color: {bufColor};">{avgBuf.toFixed(1)}d</td>
							<!-- Blackout -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7;">{fmtDec(d.sumBO1d / n)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtDec(d.sumBO3d / n)}</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(d.sumBO1d, d.sumBO3d, false).color};">{pctChg(d.sumBO1d, d.sumBO3d, false).text}</td>
							<!-- Tank -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7;">{fmtN(d.sumTank1d)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtN(d.sumTank3d)}</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(d.sumTank1d, d.sumTank3d, true).color};">{pctChg(d.sumTank1d, d.sumTank3d, true).text}</td>
							<!-- Burn -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7;">{fmtN(d.sumBurn1d)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtN(d.sumBurn3d)}</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(d.sumBurn1d, d.sumBurn3d, false).color};">{pctChg(d.sumBurn1d, d.sumBurn3d, false).text}</td>
							<!-- Sales -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7;">{fmtN(d.sumSalesTotal)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtN(d.sumSalesAvg)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtN(d.sumSales1d)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtN(d.sumSales3d)}</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(d.sumSales1d, d.sumSales3d, true).color};">{pctChg(d.sumSales1d, d.sumSales3d, true).text}</td>
							<!-- Diesel Cost -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7;">{fmtN(d.sumCostTotal)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtN(d.sumCostAvg)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtN(d.sumCost1d)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtN(d.sumCost3d)}</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(d.sumCost1d, d.sumCost3d, false).color};">{pctChg(d.sumCost1d, d.sumCost3d, false).text}</td>
							<!-- Margin -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7;">{fmtDec(d.sumMarginTotal / n)}%</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtDec(d.sumMarginAvg / n)}%</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtDec(d.sumMargin1d / n)}%</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtDec(d.sumMargin3d / n)}%</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(d.sumMargin1d, d.sumMargin3d, true).color};">{pctChg(d.sumMargin1d, d.sumMargin3d, true).text}</td>
							<!-- Diesel % -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7; color: {(d.sumExpTotal/n) > 3 ? '#be2d06' : (d.sumExpTotal/n) > 1.5 ? '#ff9d00' : '#007518'};">{icon(d.sumExpTotal/n,[0.9,1.5,3],true)} {fmtDec(d.sumExpTotal / n, 2)}%</td>
							<td class="py-1.5 px-2 text-center font-mono" style="color: {(d.sumExpAvg/n) > 3 ? '#be2d06' : (d.sumExpAvg/n) > 1.5 ? '#ff9d00' : '#007518'};">{icon(d.sumExpAvg/n,[0.9,1.5,3],true)} {fmtDec(d.sumExpAvg / n, 2)}%</td>
							<td class="py-1.5 px-2 text-center font-mono" style="color: {(d.sumExp1d/n) > 3 ? '#be2d06' : (d.sumExp1d/n) > 1.5 ? '#ff9d00' : '#007518'};">{icon(d.sumExp1d/n,[0.9,1.5,3],true)} {fmtDec(d.sumExp1d / n, 2)}%</td>
							<td class="py-1.5 px-2 text-center font-mono" style="color: {(d.sumExp3d/n) > 3 ? '#be2d06' : (d.sumExp3d/n) > 1.5 ? '#ff9d00' : '#007518'};">{icon(d.sumExp3d/n,[0.9,1.5,3],true)} {fmtDec(d.sumExp3d / n, 2)}%</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(d.sumExp1d, d.sumExp3d, false).color};">{pctChg(d.sumExp1d, d.sumExp3d, false).text}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	<!-- Chapter heading for site table -->
	<div class="px-4 py-3 mb-3 mt-6" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">pin_drop</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 2: EVERY SITE</div>
				<div class="text-[10px] opacity-75">Site-by-site data — search, filter, and drill down into individual locations.</div>
			</div>
		</div>
		<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which specific site needs fuel? Who has the worst efficiency? Where is diesel % highest?</div>
	</div>
	<div
		class="overflow-hidden"
		style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;"
	>
		<div class="px-3 py-2 flex items-center gap-2" style="background: #ebe8dd; border-bottom: 1px solid #383832;">
			<span class="material-symbols-outlined text-sm" style="color: #65655e;">search</span>
			<input type="text" bind:value={search} placeholder="QUICK_SEARCH..."
				class="flex-1 px-2 py-1 text-xs font-mono uppercase"
				style="background: white; border: 1px solid #383832; color: #383832;" />
		</div>
		<div
			class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between"
			style="background: #383832; color: #feffd6;"
		>
			<span>SECTOR_SITES</span>
			<button onclick={() => {
				const rows = filteredSites.map((s: any) => ({
					site: s.site_id, code: s.site_code || s.region || '',
					price_l: s.price || 0, buffer: (s.buffer_days || 0).toFixed(1) + 'd',
					blackout_1d: (s.last_day_blackout || 0).toFixed(1), blackout_3d: (s.blackout_hr || 0).toFixed(1),
					blackout_chg: pctChg(s.last_day_blackout||0, s.blackout_hr||0, false).text,
					tank_1d: Math.round(s.tank || 0), tank_3d: Math.round(s.avg3d_tank || 0),
					tank_chg: pctChg(s.tank||0, s.avg3d_tank||0, true).text,
					burn_1d: Math.round(s.last_day_fuel || 0), burn_3d: Math.round(s.daily_fuel || 0),
					burn_chg: pctChg(s.last_day_fuel||0, s.daily_fuel||0, false).text,
					sales_total: Math.round(s.total_sales || 0), sales_avg: Math.round(s.daily_sales || 0),
					sales_1d: Math.round(s.last_day_sales || 0), sales_3d: Math.round(s.avg3d_sales || 0),
					sales_chg: pctChg(s.last_day_sales||0, s.avg3d_sales||0, true).text,
					cost_total: Math.round(s.total_cost || 0), cost_avg: Math.round(s.daily_cost || 0),
					cost_1d: Math.round(s.last_day_fuel_cost || 0), cost_3d: Math.round(s.avg3d_fuel_cost || 0),
					cost_chg: pctChg(s.last_day_fuel_cost||0, s.avg3d_fuel_cost||0, false).text,
					margin_total: (s.margin_pct || 0).toFixed(1) + '%', margin_avg: (s.margin_pct || 0).toFixed(1) + '%',
					margin_1d: (s.margin_pct_last_day || 0).toFixed(1) + '%', margin_3d: (s.margin_pct_3d || 0).toFixed(1) + '%',
					margin_chg: pctChg(s.margin_pct_last_day||0, s.margin_pct_3d||0, true).text,
					diesel_pct_total: (s.exp_pct_total || 0).toFixed(2) + '%', diesel_pct_avg: (s.exp_pct || 0).toFixed(2) + '%',
					diesel_pct_1d: (s.exp_pct_last_day || 0).toFixed(2) + '%', diesel_pct_3d: (s.exp_pct_3d || 0).toFixed(2) + '%',
					diesel_pct_chg: pctChg(s.exp_pct_last_day||0, s.exp_pct_3d||0, false).text,
				}));
				downloadExcel(rows, 'Sector Sites', {
					columnGroups: [
						{ group: '', cols: ['site', 'code'] },
						{ group: '', cols: ['price_l', 'buffer'] },
						{ group: 'BLACKOUT HR', color: '#65655e', cols: ['blackout_1d', 'blackout_3d', 'blackout_chg'] },
						{ group: 'TANK (L)', color: '#007518', cols: ['tank_1d', 'tank_3d', 'tank_chg'] },
						{ group: 'BURN/DAY (L)', color: '#e85d04', cols: ['burn_1d', 'burn_3d', 'burn_chg'] },
						{ group: 'SALES (MMK)', color: '#006f7c', cols: ['sales_total', 'sales_avg', 'sales_1d', 'sales_3d', 'sales_chg'] },
						{ group: 'DIESEL COST (MMK)', color: '#9d4867', cols: ['cost_total', 'cost_avg', 'cost_1d', 'cost_3d', 'cost_chg'] },
						{ group: 'MARGIN %', color: '#007518', cols: ['margin_total', 'margin_avg', 'margin_1d', 'margin_3d', 'margin_chg'] },
						{ group: 'DIESEL % SALES', color: '#be2d06', cols: ['diesel_pct_total', 'diesel_pct_avg', 'diesel_pct_1d', 'diesel_pct_3d', 'diesel_pct_chg'] },
					]
				});
			}}
				class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
				style="color: #00fc40;">
				<span class="material-symbols-outlined text-sm">download</span> EXCEL
			</button>
		</div>
		<div class="overflow-x-auto overflow-y-auto" style="max-height: 600px;">
			<table class="w-full text-xs" style="border-collapse: collapse;">
				<thead class="sticky top-0 z-10">
					<!-- Row 1: Merged group headers -->
					<tr style="background: #383832;">
						{#each siteColGroups as g}
							{#if g.group}
								<th colspan={g.cols.length} class="text-center px-1 py-1.5 text-[9px] font-black uppercase tracking-wider"
									style="color: white; border-left: 2px solid #feffd6; border-right: 2px solid #feffd6; background: {g.color};">
									{g.group}
								</th>
							{:else}
								{#each g.cols as _c}
									<th class="px-1 py-1.5" style="background: #383832;"></th>
								{/each}
							{/if}
						{/each}
					</tr>
					<!-- Row 2: Sub-column labels -->
					<tr style="background: #ebe8dd;">
						{#each siteColGroups as g}
							{#each g.cols as col}
								<th class="text-{col.align} pt-1.5 px-2 text-[10px] font-black uppercase"
									style="border-bottom: 0; {g.color ? 'border-left: 1px solid #d5d2c7;' : ''}">{col.label}</th>
							{/each}
						{/each}
					</tr>
					<!-- Row 3: Formula hints -->
					<tr style="background: #ebe8dd;">
						{#each siteColGroups as g}
							{#each g.cols as col}
								<th class="text-{col.align} pb-1.5 px-2 font-normal text-[7px]"
									style="border-bottom: 2px solid #383832; color: #65655e; font-style: italic; {g.color ? 'border-left: 1px solid #d5d2c7;' : ''}">{col.formula}</th>
							{/each}
						{/each}
					</tr>
				</thead>
				<tbody>
					<!-- AVG row (sticky at top of scroll) -->
					{#if filteredSites.length > 0}
					{@const n = filteredSites.length || 1}
					{@const avg = (key: string) => filteredSites.reduce((s: number, r: any) => s + (r[key] || 0), 0) / n}
					{@const sum = (key: string) => filteredSites.reduce((s: number, r: any) => s + (r[key] || 0), 0)}
					{@const avgSectorIds = [...new Set(filteredSites.map((s: any) => s.sector_id))]}
					{@const avgSec3dFuel = avgSectorIds.reduce((s: number, sid: string) => s + (sector3dAvgFuel[sid] || 0), 0)}
					{@const avgBufAll = avgSec3dFuel > 0 ? sum('tank') / avgSec3dFuel : (sum('daily_fuel') > 0 ? sum('tank') / sum('daily_fuel') : 0)}
					{@const avgBufColor = avgBufAll >= 7 ? '#007518' : avgBufAll >= 3 ? '#ff9d00' : '#be2d06'}
					<tr style="background: #383832; color: #feffd6; border-bottom: 3px solid #383832;">
						<td class="py-2 px-2 font-black">AVG / TOTAL</td>
						<td class="py-2 px-2 text-center text-[9px]">{filteredSites.length} sites</td>
						<!-- Price + Buffer -->
						<td class="py-2 px-2 text-center font-mono">{fmtN(avg('price'))}</td>
						<td class="py-2 px-2 text-center font-bold" style="color: {avgBufColor};">{avgBufAll.toFixed(1)}d</td>
						<!-- Blackout: 1D, 3D, change -->
						<td class="py-2 px-2 text-center font-mono" style="border-left: 1px solid #65655e;">{fmtDec(avg('last_day_blackout'))}</td>
						<td class="py-2 px-2 text-center font-mono">{fmtDec(avg('blackout_hr'))}</td>
						<td class="py-2 px-2 text-center font-bold text-[10px]" style="color: {pctChg(avg('last_day_blackout'), avg('blackout_hr'), false).color};">{pctChg(avg('last_day_blackout'), avg('blackout_hr'), false).text}</td>
						<!-- Tank: 1D, 3D, change -->
						<td class="py-2 px-2 text-center font-mono" style="border-left: 1px solid #65655e;">{fmtN(sum('tank'))}</td>
						<td class="py-2 px-2 text-center font-mono">{fmtN(sum('avg3d_tank'))}</td>
						<td class="py-2 px-2 text-center font-bold text-[10px]" style="color: {pctChg(sum('tank'), sum('avg3d_tank'), true).color};">{pctChg(sum('tank'), sum('avg3d_tank'), true).text}</td>
						<!-- Burn: 1D, 3D, change -->
						<td class="py-2 px-2 text-center font-mono" style="border-left: 1px solid #65655e;">{fmtN(sum('last_day_fuel'))}</td>
						<td class="py-2 px-2 text-center font-mono">{fmtN(sum('daily_fuel'))}</td>
						<td class="py-2 px-2 text-center font-bold text-[10px]" style="color: {pctChg(sum('last_day_fuel'), sum('daily_fuel'), false).color};">{pctChg(sum('last_day_fuel'), sum('daily_fuel'), false).text}</td>
						<!-- Sales -->
						<td class="py-2 px-2 text-center font-mono" style="border-left: 1px solid #65655e;">{fmtN(sum('total_sales'))}</td>
						<td class="py-2 px-2 text-center font-mono">{fmtN(sum('daily_sales'))}</td>
						<td class="py-2 px-2 text-center font-mono">{fmtN(sum('last_day_sales'))}</td>
						<td class="py-2 px-2 text-center font-mono">{fmtN(sum('avg3d_sales'))}</td>
						<td class="py-2 px-2 text-center font-bold text-[10px]" style="color: {pctChg(sum('last_day_sales'), sum('avg3d_sales'), true).color};">{pctChg(sum('last_day_sales'), sum('avg3d_sales'), true).text}</td>
						<!-- Diesel Cost -->
						<td class="py-2 px-2 text-center font-mono" style="border-left: 1px solid #65655e;">{fmtN(sum('total_cost'))}</td>
						<td class="py-2 px-2 text-center font-mono">{fmtN(sum('daily_cost'))}</td>
						<td class="py-2 px-2 text-center font-mono">{fmtN(sum('last_day_fuel_cost'))}</td>
						<td class="py-2 px-2 text-center font-mono">{fmtN(sum('avg3d_fuel_cost'))}</td>
						<td class="py-2 px-2 text-center font-bold text-[10px]" style="color: {pctChg(sum('last_day_fuel_cost'), sum('avg3d_fuel_cost'), false).color};">{pctChg(sum('last_day_fuel_cost'), sum('avg3d_fuel_cost'), false).text}</td>
						<!-- Margin -->
						<td class="py-2 px-2 text-center font-mono" style="border-left: 1px solid #65655e;">{fmtDec(avg('margin_pct'))}%</td>
						<td class="py-2 px-2 text-center font-mono">{fmtDec(avg('margin_pct'))}%</td>
						<td class="py-2 px-2 text-center font-mono">{fmtDec(avg('margin_pct_last_day'))}%</td>
						<td class="py-2 px-2 text-center font-mono">{fmtDec(avg('margin_pct_3d'))}%</td>
						<td class="py-2 px-2 text-center font-bold text-[10px]" style="color: {pctChg(avg('margin_pct_last_day'), avg('margin_pct_3d'), true).color};">{pctChg(avg('margin_pct_last_day'), avg('margin_pct_3d'), true).text}</td>
						<!-- Diesel % -->
						<td class="py-2 px-2 text-center font-mono" style="border-left: 1px solid #65655e;">{fmtDec(avg('exp_pct_total'), 2)}%</td>
						<td class="py-2 px-2 text-center font-mono">{fmtDec(avg('exp_pct'), 2)}%</td>
						<td class="py-2 px-2 text-center font-mono">{fmtDec(avg('exp_pct_last_day'), 2)}%</td>
						<td class="py-2 px-2 text-center font-mono">{fmtDec(avg('exp_pct_3d'), 2)}%</td>
						<td class="py-2 px-2 text-center font-bold text-[10px]" style="color: {pctChg(avg('exp_pct_last_day'), avg('exp_pct_3d'), false).color};">{pctChg(avg('exp_pct_last_day'), avg('exp_pct_3d'), false).text}</td>
					</tr>
					{/if}
					{#each filteredSites as s, i}
						<tr style="background: {i % 2 === 0 ? 'white' : '#f6f4e9'}; border-bottom: 1px solid #ebe8dd;">
							<!-- Identity -->
							<td class="py-1.5 px-2 font-bold" style="color: #383832;">{s.site_id}</td>
							<td class="py-1.5 px-2 font-mono text-xs" style="color: #383832;">{s.site_code || s.region || ''}</td>
							<!-- Price + Buffer -->
							<td class="py-1.5 px-2 text-center font-mono">{icon(s.price||0,[3500,5000,8000],true)} {fmt(s.price||0)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{icon(s.buffer_days||0,[7,5,3])} {fmtDec(s.buffer_days||0)}</td>
							<!-- Blackout: 1D, 3D, change (lower=good) -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7;">{icon(s.last_day_blackout||0,[4,8,12],true)} {fmtDec(s.last_day_blackout||0)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtDec(s.blackout_hr||0)}</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(s.last_day_blackout||0, s.blackout_hr||0, false).color};">{pctChg(s.last_day_blackout||0, s.blackout_hr||0, false).text}</td>
							<!-- Tank: 1D, 3D, change (higher=good) -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7;">{fmt(s.tank||0)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmt(s.avg3d_tank||0)}</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(s.tank||0, s.avg3d_tank||0, true).color};">{pctChg(s.tank||0, s.avg3d_tank||0, true).text}</td>
							<!-- Burn: 1D, 3D, change (lower=good) -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7;">{fmt(s.last_day_fuel||0)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmt(s.daily_fuel||0)}</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(s.last_day_fuel||0, s.daily_fuel||0, false).color};">{pctChg(s.last_day_fuel||0, s.daily_fuel||0, false).text}</td>
							<!-- Sales: TOTAL, AVG/DAY, 1D, 3D, 1D vs 3D -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7;">{fmt(s.total_sales||0)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmt(s.daily_sales||0)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmt(s.last_day_sales||0)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmt(s.avg3d_sales||0)}</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(s.last_day_sales||0, s.avg3d_sales||0, true).color};">{pctChg(s.last_day_sales||0, s.avg3d_sales||0, true).text}</td>
							<!-- Diesel Cost: TOTAL, AVG/DAY, 1D, 3D, 1D vs 3D -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7;">{fmt(s.total_cost||0)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmt(s.daily_cost||0)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmt(s.last_day_fuel_cost||s.daily_cost||0)}</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmt(s.avg3d_fuel_cost||0)}</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(s.last_day_fuel_cost||0, s.avg3d_fuel_cost||0, false).color};">{pctChg(s.last_day_fuel_cost||0, s.avg3d_fuel_cost||0, false).text}</td>
							<!-- Margin: TOTAL, AVG/DAY, 1D, 3D, 1D vs 3D -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7;">{fmtDec(s.margin_pct||0)}%</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtDec(s.margin_pct||0)}%</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtDec(s.margin_pct_last_day||0)}%</td>
							<td class="py-1.5 px-2 text-center font-mono">{fmtDec(s.margin_pct_3d||0)}%</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(s.margin_pct_last_day||0, s.margin_pct_3d||0, true).color};">{pctChg(s.margin_pct_last_day||0, s.margin_pct_3d||0, true).text}</td>
							<!-- Diesel % SALES: TOTAL, AVG/DAY, 1D, 3D, 1D vs 3D -->
							<td class="py-1.5 px-2 text-center font-mono" style="border-left: 1px solid #d5d2c7; color: {(s.exp_pct_total||0) > 3 ? '#be2d06' : (s.exp_pct_total||0) > 1.5 ? '#ff9d00' : '#007518'};">{icon(s.exp_pct_total||0,[0.9,1.5,3],true)} {fmtDec(s.exp_pct_total||0,2)}%</td>
							<td class="py-1.5 px-2 text-center font-mono" style="color: {(s.exp_pct||0) > 3 ? '#be2d06' : (s.exp_pct||0) > 1.5 ? '#ff9d00' : '#007518'};">{icon(s.exp_pct||0,[0.9,1.5,3],true)} {fmtDec(s.exp_pct||0,2)}%</td>
							<td class="py-1.5 px-2 text-center font-mono" style="color: {(s.exp_pct_last_day||0) > 3 ? '#be2d06' : (s.exp_pct_last_day||0) > 1.5 ? '#ff9d00' : '#007518'};">{icon(s.exp_pct_last_day||0,[0.9,1.5,3],true)} {fmtDec(s.exp_pct_last_day||0,2)}%</td>
							<td class="py-1.5 px-2 text-center font-mono" style="color: {(s.exp_pct_3d||0) > 3 ? '#be2d06' : (s.exp_pct_3d||0) > 1.5 ? '#ff9d00' : '#007518'};">{icon(s.exp_pct_3d||0,[0.9,1.5,3],true)} {fmtDec(s.exp_pct_3d||0,2)}%</td>
							<td class="py-1.5 px-2 text-center font-bold text-[10px]" style="color: {pctChg(s.exp_pct_last_day||0, s.exp_pct_3d||0, false).color};">{pctChg(s.exp_pct_last_day||0, s.exp_pct_3d||0, false).text}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<!-- Legend -->
		<div
			class="px-4 py-2 flex gap-4 text-[10px]"
			style="background: #ebe8dd; border-top: 1px solid #383832; color: #65655e;"
		>
			<span>{'\u{1F7E2}'} Good</span>
			<span>{'\u{1F7E1}'} Watch</span>
			<span>{'\u{1F7E0}'} Warning</span>
			<span>{'\u{1F534}'} Danger</span>
			<span class="ml-auto text-[9px]"
				>Price: &lt;3.5K/5K/8K | Blackout: &lt;4/8/12h | Exp%: &lt;0.9/1.5/3 | Buffer:
				&gt;7/5/3d</span
			>
		</div>
	</div>
{/if}

<!-- Formula Reference -->
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
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #007518;">BUFFER DAYS</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">last_day_tank &divide; 3d_avg_daily_fuel</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">daily_site_summary</code></td></tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #be2d06;">BLACKOUT HR</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">SUM(blackout_hr) per site, AVG over 3 days</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">daily_site_summary</code></td></tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #007518;">TANK BAL</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">SUM(spare_tank) on last day per site</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">daily_site_summary</code></td></tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #e85d04;">BURN/DAY</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">AVG(daily_used) over 3 days per site</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">daily_site_summary</code></td></tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #006f7c;">SALES</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">SUM(sales_amt) from daily_sales</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">daily_sales</code></td></tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #9d4867;">DIESEL COST</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">fuel_used &times; latest_purchase_price</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">fuel_purchases</code></td></tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #007518;">MARGIN %</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">margin &divide; sales &times; 100</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">daily_sales</code></td></tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #be2d06;">DIESEL %</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">(cost &divide; sales) &times; 100</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">derived</code></td></tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #65655e;">1D vs 3D</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">(1D &minus; 3D) &divide; 3D &times; 100%</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">derived</code></td></tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #383832;">3D AVG FUEL</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">SUM(fuel over 3 prior days) &divide; 3 (sector level)</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">daily_site_summary</code></td></tr>
			</tbody>
		</table>
	</div>
</div>
