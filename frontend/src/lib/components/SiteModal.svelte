<script lang="ts">
	import { api, downloadExcel } from '$lib/api';
	import Chart from '$lib/components/Chart.svelte';
	import InfoTip from '$lib/components/InfoTip.svelte';
	import PeakHours from '$lib/components/sections/PeakHours.svelte';
	import { KPI } from '$lib/kpi-definitions';
	import { lineChart, dualAxisChart, barChart, hbarChart, groupedBar, pieChart } from '$lib/charts';

	let { siteId = '', sites = [], siteNames = {} as Record<string, string>, onclose }: { siteId?: string; sites?: string[]; siteNames?: Record<string, string>; onclose?: () => void } = $props();

	let data: any = $state(null);
	let loading = $state(true);
	let error = $state('');
	let selected = $state(siteId);
	let period = $state('daily');
	let siteSearch = $state('');
	let siteDropOpen = $state(false);
	let pdfGenerating = $state(false);

	const filteredSiteList = $derived(
		siteSearch
			? sites.filter(s => s.toLowerCase().includes(siteSearch.toLowerCase()) || (siteNames[s] || '').toLowerCase().includes(siteSearch.toLowerCase()))
			: sites
	);
	const selectedName = $derived(data?.site?.site_name || data?.site?.cost_center_name || siteNames[selected] || '');

	async function load(id: string) {
		if (!id) return;
		loading = true;
		error = '';
		try {
			data = await api.get(`/site/${id}/charts?period=${period}`);
		} catch (e) {
			console.error(e);
			data = null;
			error = `Failed to load data for ${id}. Check your connection and try again.`;
		} finally {
			loading = false;
		}
	}

	$effect(() => { const _s = selected; const _p = period; if (_s) load(_s); });

	function fmt(v: number) { return v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v.toFixed(v < 10 ? 1 : 0); }

	const MN = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
	function fmtPeriodLabel(row: any, per: string): string {
		if (per === 'daily') return row.date || '';
		if (per === 'monthly') {
			const dt = new Date(row.date_start || row.date);
			return MN[dt.getMonth()] + ' ' + dt.getFullYear();
		}
		// weekly: "29 Mar - 04 Apr '26" or "05 - 11 Apr '26"
		const s = new Date(row.date_start || row.date);
		const e = new Date(row.date_end || row.date);
		const sy = String(s.getFullYear()).slice(2);
		const sd = s.getDate();
		const sm = MN[s.getMonth()];
		const ed = e.getDate();
		const em = MN[e.getMonth()];
		if (s.getMonth() === e.getMonth()) return `${String(sd).padStart(2,'0')} - ${String(ed).padStart(2,'0')} ${em} '${sy}`;
		return `${sd} ${sm} - ${String(ed).padStart(2,'0')} ${em} '${sy}`;
	}

	function aggregatePrices(prices: any[], per: string): { date: string; price: number; date_start?: string; date_end?: string }[] {
		if (!prices || prices.length === 0) return [];
		if (per === 'daily') return prices.map((p: any) => ({ date: p.date, price: p.price_per_liter || 0 }));
		// Group by week or month
		const groups: Record<string, { sum: number; count: number; dates: string[]; min: string; max: string }> = {};
		for (const p of prices) {
			const dt = new Date(p.date);
			let key: string;
			if (per === 'weekly') {
				const weekStart = new Date(dt);
				weekStart.setDate(dt.getDate() - dt.getDay());
				key = weekStart.toISOString().slice(0, 10);
			} else {
				key = p.date.slice(0, 7); // YYYY-MM
			}
			if (!groups[key]) groups[key] = { sum: 0, count: 0, dates: [], min: p.date, max: p.date };
			groups[key].sum += (p.price_per_liter || 0);
			groups[key].count++;
			groups[key].dates.push(p.date);
			if (p.date < groups[key].min) groups[key].min = p.date;
			if (p.date > groups[key].max) groups[key].max = p.date;
		}
		return Object.entries(groups)
			.sort(([a], [b]) => a.localeCompare(b))
			.map(([_, g]) => ({ date: g.min, price: Math.round(g.sum / g.count), date_start: g.min, date_end: g.max }));
	}

	async function exportPDF() {
		const el = document.querySelector('.site-report-content');
		if (!el) return;
		pdfGenerating = true;
		try {
			const { default: html2canvas } = await import('html2canvas');
			const { jsPDF } = await import('jspdf');
			const canvas = await html2canvas(el as HTMLElement, { scale: 2, useCORS: true, backgroundColor: '#feffd6' });
			const imgData = canvas.toDataURL('image/png');
			const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
			const pageW = pdf.internal.pageSize.getWidth();
			const pageH = pdf.internal.pageSize.getHeight();
			const imgW = pageW - 20;
			const imgH = (canvas.height * imgW) / canvas.width;
			let y = 10;
			const pageContentH = pageH - 20;
			if (imgH <= pageContentH) {
				pdf.addImage(imgData, 'PNG', 10, y, imgW, imgH);
			} else {
				let remainingH = imgH;
				while (remainingH > 0) {
					pdf.addImage(imgData, 'PNG', 10, y - (imgH - remainingH), imgW, imgH);
					remainingH -= pageContentH;
					if (remainingH > 0) { pdf.addPage(); y = 10; }
				}
			}
			pdf.save(`Site_Report_${selected}_${new Date().toISOString().slice(0,10)}.pdf`);
		} finally {
			pdfGenerating = false;
		}
	}
</script>

<!-- Modal Overlay -->
<div class="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm overflow-y-auto" role="dialog">
	<div class="w-full sm:w-[95vw] max-w-[1400px] max-h-[90vh] overflow-y-auto mx-auto py-6 px-4">
		<!-- Header -->
		<div class="flex items-center justify-between mb-6 p-4" style="background: #383832; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px rgba(0,0,0,0.3);">
			<div class="flex items-center gap-4 flex-wrap">
				<h1 class="text-xl font-black uppercase" style="color: #feffd6;">SITE_DEEP_DIVE</h1>
				<!-- Searchable site selector -->
				<div class="relative">
					<button onclick={() => { siteDropOpen = !siteDropOpen; siteSearch = ''; }}
						class="px-3 py-2 text-sm font-bold uppercase flex items-center gap-2"
						style="background: #feffd6; border: 2px solid #feffd6; color: #383832; min-width: 200px;">
						<span>{selected}</span>
						{#if selectedName}
							<span class="text-[10px] font-normal truncate max-w-[150px]" style="color: #65655e;">{selectedName}</span>
						{/if}
						<span class="ml-auto text-xs">▾</span>
					</button>
					{#if siteDropOpen}
						<!-- svelte-ignore a11y_no_static_element_interactions -->
						<div class="fixed inset-0 z-40" onclick={() => siteDropOpen = false}></div>
						<div class="absolute top-full left-0 z-50 mt-1 w-[320px]" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
							<input type="text" bind:value={siteSearch} placeholder="Search by name or code..."
								class="w-full px-3 py-2 text-xs font-mono uppercase"
								style="border: none; border-bottom: 2px solid #383832; color: #383832;" />
							<div class="max-h-[250px] overflow-y-auto">
								{#each filteredSiteList as s}
									<button onclick={() => { selected = s; siteDropOpen = false; }}
										class="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-100 flex justify-between items-center"
										style="border-bottom: 1px solid #ebe8dd; {s === selected ? 'background: #f0ede3; font-weight: 900;' : ''}">
										<span class="font-bold" style="color: #383832;">{siteNames[s] || s}</span>
										<span class="text-[10px] font-mono" style="color: #65655e;">{s}</span>
									</button>
								{/each}
								{#if filteredSiteList.length === 0}
									<div class="px-3 py-3 text-center text-xs" style="color: #65655e;">No sites match "{siteSearch}"</div>
								{/if}
							</div>
						</div>
					{/if}
				</div>
				<div class="flex">
					{#each [['daily','D'],['weekly','W'],['monthly','M']] as [val, lbl]}
						<button
							onclick={() => { period = val; }}
							class="px-3 py-2 text-xs font-black uppercase"
							style="border: 2px solid #feffd6; {period === val ? 'background: #feffd6; color: #383832;' : 'background: transparent; color: #feffd6;'}"
						>{lbl}</button>
					{/each}
				</div>
			</div>
			<div class="flex items-center gap-2">
				<button onclick={exportPDF} disabled={pdfGenerating} class="flex items-center gap-1 px-3 py-1.5 text-[10px] font-black uppercase no-print"
					style="background: #feffd6; color: #383832; border: 2px solid #feffd6;">
					<span class="material-symbols-outlined text-sm">picture_as_pdf</span> {pdfGenerating ? '...' : 'PDF'}
				</button>
				<button onclick={() => onclose?.()} class="text-2xl px-2 font-black no-print" style="color: #feffd6;">✕</button>
			</div>
		</div>

		<div class="p-6 site-report-content" style="background: #feffd6; border: 2px solid #383832;">
		{#if data}
		<!-- Site Info (inside PDF capture area) -->
		<div class="px-4 py-3 mb-4 -mx-6 -mt-6" style="background: #ebe8dd; border-bottom: 2px solid #383832;">
			<div class="flex items-center gap-3 mb-1">
				<span class="text-lg font-black" style="color: #383832;">BCP SITE REPORT</span>
				<span class="text-[10px]" style="color: #65655e;">|</span>
				<span class="text-sm font-black" style="color: #383832;">{data.site?.site_name || data.site?.cost_center_name || selected}</span>
				<span class="text-[10px] font-mono px-1.5 py-0.5" style="background: #383832; color: #feffd6;">{data.site?.site_id || selected}</span>
				{#if data.site?.site_code || data.site?.region}
					<span class="text-[10px] font-mono" style="color: #65655e;">{data.site?.site_code || data.site?.region}</span>
				{/if}
			</div>
			<div class="flex flex-wrap gap-4 text-[10px]">
				{#each [
					['SEGMENT', data.site?.segment_name || ''],
					['SECTOR', data.site?.sector_id || ''],
					['LOCATION', [data.site?.address_state, data.site?.address_township].filter(Boolean).join(', ')],
					['SIZE', data.site?.store_size || ''],
					['GENERATED', new Date().toLocaleString()],
				].filter(([,v]) => v) as [label, value]}
					<div><span style="color: #65655e;">{label}:</span> <span class="font-bold" style="color: #383832;">{value}</span></div>
				{/each}
			</div>
		</div>
		{/if}
		{#if loading}
			<p class="text-center py-20 font-bold uppercase" style="color: #65655e;">Loading site data...</p>
		{:else if error}
			<div class="text-center py-12" style="background: #f6f4e9; border: 2px solid #383832;">
				<span class="material-symbols-outlined text-3xl" style="color: #be2d06;">error</span>
				<p class="font-bold mt-2 uppercase text-xs" style="color: #be2d06;">{error}</p>
				<button onclick={() => load(selected)} class="mt-3 px-4 py-1.5 text-[10px] font-black uppercase"
					style="background: #383832; color: #feffd6; border: 2px solid #383832;">
					<span class="material-symbols-outlined text-xs align-middle">refresh</span> RETRY
				</button>
			</div>
		{:else if !data}
			<div class="text-center py-12" style="background: #f6f4e9; border: 2px solid #383832;">
				<span class="material-symbols-outlined text-3xl" style="color: #65655e;">inbox</span>
				<p class="font-bold mt-2 uppercase text-xs" style="color: #383832;">NO DATA AVAILABLE FOR {selected}</p>
				<p class="text-[10px] mt-1" style="color: #65655e;">This site has no records. Upload data or select a different site.</p>
			</div>
		{:else}
			{@const d = data.daily || []}
			{@const gens = data.generators || []}
			{@const gd = data.gen_daily || []}
			{@const dates = d.map((r: any) => fmtPeriodLabel(r, period))}
			{@const price = data.fuel_price || 0}

			{@const last = d.length > 0 ? d[d.length - 1] : null}
			{@const rawDates = d.map((r: any) => r.date)}
			{@const firstDate = d.length > 0 ? (d[0].date_start || d[0].date || '—') : '—'}
			{@const lastDate = d.length > 0 ? (d[d.length-1].date_end || d[d.length-1].date || '—') : '—'}
			{@const rd = d.slice(-4)}
			{@const pL = period === 'daily' ? 'day' : period === 'weekly' ? 'week' : 'month'}
			{@const pU = pL.charAt(0).toUpperCase()}
			{@const isD = period === 'daily'}
			{@const suffix = isD ? '' : '/day'}

			<!-- Date Range Bar -->
			<div class="flex items-center gap-3 mb-3 px-3 py-1.5" style="background: #ebe8dd; border: 1px solid #d5d2c7;">
				<span class="text-[9px] font-black uppercase" style="color: #65655e;">DATA RANGE:</span>
				<span class="text-[10px] font-mono font-bold" style="color: #383832;">{firstDate} &rarr; {lastDate}</span>
				<span class="text-[9px]" style="color: #9d9d91;">({d.length} {pL}s)</span>
				<span class="text-[9px] font-bold ml-auto" style="color: #65655e;">PERIOD: {period === 'daily' ? 'DAILY' : period === 'weekly' ? 'WEEKLY' : 'MONTHLY'}</span>
				{#if !isD}
					<span class="text-[8px]" style="color: #9d9d91;">values = daily avg</span>
				{/if}
			</div>

			<!-- KPI Cards (Overview chart style) -->
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
				{#each [
					{ tl: 'BUFFER (DAYS)', key: 'buffer', t1: last?.buffer || 0, dec: 1, good: 'high', color: '#007518', tc: isD ? 'tank &divide; avg_burn' : 'AVG(daily buffer) per ' + pL, unit: 'd', tip: KPI.siteModal.buffer },
					{ tl: 'TANK BAL (L)', key: 'tank', t1: last?.tank || 0, dec: 0, good: 'high', color: '#006f7c', tc: isD ? 'spare_tank on date' : 'AVG(daily tank) per ' + pL, unit: 'L', tip: KPI.siteModal.tank },
					{ tl: isD ? 'FUEL USED (L)' : 'FUEL (L' + suffix + ')', key: 'fuel', t1: last?.fuel || 0, dec: 0, good: 'low', color: '#e85d04', tc: isD ? 'total_daily_used' : 'AVG(daily_used) per ' + pL, unit: 'L', tip: KPI.siteModal.fuelUsed },
					{ tl: isD ? 'GEN RUN HR' : 'GEN HR' + suffix, key: 'gen_hr', t1: last?.gen_hr || 0, dec: 1, good: 'low', color: '#ff9d00', tc: isD ? 'gen_run_hr' : 'AVG(daily gen_hr) per ' + pL, unit: 'hr', tip: KPI.siteModal.genHr },
					{ tl: isD ? 'BLACKOUT HR' : 'BLACKOUT' + suffix, key: 'blackout_hr', t1: last?.blackout_hr || 0, dec: 1, good: 'low', color: '#be2d06', tc: isD ? 'blackout_hr' : 'AVG(daily blackout) per ' + pL, unit: 'hr', tip: KPI.siteModal.blackout },
					{ tl: isD ? 'DIESEL COST (MMK)' : 'COST (MMK' + suffix + ')', key: 'cost', t1: last?.cost || 0, dec: 0, good: 'low', color: '#9d4867', tc: isD ? 'fuel &times; price' : 'AVG(daily cost) per ' + pL, unit: '', tip: KPI.siteModal.cost },
				] as m}
					{@const vals = rd.map((r: any) => r[m.key] || 0)}
					{@const maxVal = Math.max(...vals, 1)}
					{@const avg3 = rd.length >= 4 ? (vals[0] + vals[1] + vals[2]) / 3 : (vals.length > 1 ? vals.slice(0, -1).reduce((a: number, b: number) => a + b, 0) / Math.max(vals.length - 1, 1) : 0)}
					{@const tDiff = avg3 ? ((m.t1 - avg3) / Math.max(Math.abs(avg3), 0.01) * 100) : 0}
					{@const tImpr = m.good === 'high' ? tDiff > 1 : tDiff < -1}
					{@const tClr = Math.abs(tDiff) < 1 ? '#65655e' : tImpr ? '#007518' : '#be2d06'}
					{@const tArr = tDiff > 1 ? '▲' : tDiff < -1 ? '▼' : '→'}
					<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
						<!-- Header -->
						<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
							<span class="text-[11px] font-black uppercase">{m.tl}</span>
							<span class="flex items-center gap-2">
								<span class="text-[10px] font-bold" style="color: {tClr};">{tArr}{Math.abs(tDiff).toFixed(0)}% vs 3{pU}</span>
								<InfoTip {...m.tip} />
							</span>
						</div>
						<!-- KPIs row -->
						<div class="flex">
							<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
								<div class="text-2xl font-black" style="color: #383832;">{m.dec ? m.t1.toFixed(m.dec) : fmt(m.t1)}</div>
								<div class="text-[9px] font-bold" style="color: #65655e;">{isD ? 'TODAY' : period === 'weekly' ? 'THIS WEEK' : 'THIS MONTH'}</div>
								<div class="text-[8px]" style="color: #9d9d91;">{last ? fmtPeriodLabel(last, period) : ''}</div>
							</div>
							<div class="p-3 flex flex-col justify-center" style="flex: 1;">
								<div class="text-2xl font-black" style="color: #383832;">{m.dec ? avg3.toFixed(m.dec) : fmt(avg3)}</div>
								<div class="text-[9px] font-bold" style="color: #65655e;">{isD ? '3D AVG' : period === 'weekly' ? '3W AVG' : '3M AVG'}</div>
								<div class="text-[8px]" style="color: #9d9d91;">prior 3 {pL}s avg</div>
							</div>
						</div>
						<!-- Horizontal bar chart -->
						<div style="border-top: 1px solid #ebe8dd;">
							{#each rd as day, di}
								{@const isLatest = di === rd.length - 1}
								{@const v = vals[di]}
								{@const pct = maxVal > 0 ? (v / maxVal * 100) : 0}
								{#if isLatest && rd.length >= 4}
									<div class="px-3 py-0.5 flex items-center gap-2" style="border-top: 2px dashed {m.color};">
										<span class="text-[8px] font-bold" style="color: {m.color};">3{pU} AVG: {m.dec ? avg3.toFixed(m.dec) : fmt(Math.round(avg3))}{suffix}</span>
									</div>
								{/if}
								<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid {isLatest ? m.color : 'rgba(56,56,50,0.08)'}; {isLatest ? 'background: rgba(56,56,50,0.03);' : ''}">
									<span class="text-[9px] shrink-0 {isLatest ? 'font-black' : ''}" style="color: {isLatest ? m.color : '#828179'}; {isD ? 'width: 2.5rem;' : 'width: 7rem; font-size: 7px;'}">
										{fmtPeriodLabel(day, period)}
									</span>
									<div class="flex-1 h-4 relative" style="background: #f0ede3;">
										<div class="h-full" style="width: {pct}%; background: {isLatest ? m.color : m.color + '60'};"></div>
										{#if avg3 > 0}
											<div class="absolute top-0 h-full w-px" style="left: {Math.min(avg3/maxVal*100, 100)}%; background: {m.color}; opacity: 0.5;"></div>
										{/if}
									</div>
									<span class="text-[9px] w-12 text-right shrink-0 {isLatest ? 'font-black' : ''}" style="color: #383832;">{m.dec ? v.toFixed(m.dec) : fmt(Math.round(v))}{suffix}</span>
									{#if isLatest && avg3 > 0}
										{@const vsAvg = (v - avg3) / avg3 * 100}
										{@const vClr = (m.good === 'high' ? vsAvg > 1 : vsAvg < -1) ? '#007518' : (m.good === 'high' ? vsAvg < -1 : vsAvg > 1) ? '#be2d06' : '#65655e'}
										<span class="text-[8px] font-bold w-10 text-right shrink-0" style="color: {vClr};">{vsAvg > 0 ? '▲' : vsAvg < 0 ? '▼' : '→'}{Math.abs(vsAvg).toFixed(0)}%</span>
									{:else}
										<span class="w-10 shrink-0"></span>
									{/if}
								</div>
							{/each}
						</div>
						<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">{@html m.tc}</div>
					</div>
				{/each}
			</div>

			<!-- Generator Fleet Table -->
			{#if gens.length > 0}
				<details open class="mb-6">
					<summary class="cursor-pointer text-sm font-black uppercase px-4 py-2.5 flex items-center justify-between" style="background: #383832; color: #feffd6;">
						<span>GENERATOR_FLEET ({gens.length})</span>
						<button onclick={(e) => { e.preventDefault(); downloadExcel(gens, 'Generator Fleet'); }}
							class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
							style="color: #00fc40;">
							<span class="material-symbols-outlined text-sm">download</span> EXCEL
						</button>
					</summary>
					<div class="overflow-x-auto" style="border: 2px solid #383832; border-top: 0;">
						<table class="w-full text-xs">
							<thead><tr style="background: #ebe8dd; border-bottom: 2px solid #383832;">
								<th class="text-left py-2 px-3 font-black uppercase" style="color: #383832;">Model</th>
								<th class="text-left py-2 px-3 font-black uppercase" style="color: #383832;">KVA</th>
								<th class="text-left py-2 px-3 font-black uppercase" style="color: #383832;">Rated L/Hr</th>
								<th class="text-left py-2 px-3 font-black uppercase" style="color: #383832;">Total Run Hr</th>
								<th class="text-left py-2 px-3 font-black uppercase" style="color: #383832;">Total Fuel</th>
							</tr></thead>
							<tbody>
								{#each gens as g, i}
									<tr style="border-bottom: 1px solid #ebe8dd; {i % 2 ? 'background: #f6f4e9;' : 'background: white;'}"><td class="py-2 px-3 font-bold" style="color: #383832;">{g.model_name}</td><td class="py-2 px-3" style="color: #65655e;">{g.power_kva || '—'}</td><td class="py-2 px-3" style="color: #65655e;">{g.consumption_per_hour || '—'}</td><td class="py-2 px-3" style="color: #65655e;">{fmt(g.total_run_hr || 0)}</td><td class="py-2 px-3" style="color: #65655e;">{fmt(g.total_fuel || 0)}L</td></tr>
								{/each}
							</tbody>
						</table>
					</div>
				</details>
			{/if}

			<!-- Trend Charts (10) -->
			{#if d.length >= 2}
				<h3 class="text-sm font-black uppercase mb-3" style="color: #383832;">📈 Site Trends</h3>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
					<!-- 1. Buffer Trend -->
					<Chart option={lineChart(dates, [{ name: 'Buffer Days', data: d.map((r: any) => r.buffer || 0), color: '#3b82f6' }],
						{ title: 'Buffer Days', markLines: [{ value: 7, label: 'Safe', color: '#16a34a' }, { value: 3, label: 'Critical', color: '#dc2626' }] })} height="260px" guide={{
						formula: "Tank Balance ÷ (7d Avg Blackout Hr × Rated L/Hr) = <b>Days of fuel left</b>.",
						sources: [{ data: 'Buffer', file: 'Blackout Hr Excel', col: 'Tank ÷ Burn', method: 'Daily calc' }],
						reading: [{ color: 'green', text: '🟢 Above 7 = Safe' }, { color: 'amber', text: '🟡 3-7 = Plan refuel' }, { color: 'red', text: '🔴 Below 3 = Emergency' }],
						explain: "Your site's <b>fuel countdown</b>. Green zone = comfortable. Dropping toward red = fuel truck needed ASAP."
					}} />

					<!-- 2. Efficiency -->
					<Chart option={lineChart(dates, [{ name: 'L/Hr', data: d.map((r: any) => r.efficiency || 0), color: '#8b5cf6' }],
						{ title: 'Efficiency — L per Gen Hour' })} height="260px" guide={{
						formula: "Liters Used ÷ Generator Hours = <b>L/Hr</b>. Normal: 15-20 for most models.",
						sources: [{ data: 'Efficiency', file: 'Blackout Hr Excel', col: 'Used ÷ Hours', method: 'Daily calc' }],
						reading: [{ color: 'green', text: '✅ Flat line = Healthy generator' }, { color: 'red', text: '🔴 Spike up = Waste, theft, or malfunction' }],
						explain: "Like your car's <b>fuel economy</b>. Should be flat. A sudden jump means the generator is burning more — check for <b>leaks or unauthorized use</b>."
					}} />

					<!-- 3. Gen Hours vs Fuel -->
					<Chart option={dualAxisChart(dates,
						d.map((r: any) => Math.round(r.gen_hr || 0)),
						d.map((r: any) => Math.round(r.fuel || 0)),
						{ title: 'Gen Hours vs Fuel', barName: 'Gen Hr', lineName: 'Fuel (L)', barColor: '#3b82f6', lineColor: '#ef4444' }
					)} height="260px" guide={{
						formula: "Blue bars = generator run time. Red line = fuel consumed. They should <b>move together</b>.",
						sources: [{ data: 'Gen Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'SUM' }, { data: 'Fuel', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM' }],
						reading: [{ color: 'green', text: '✅ Bars and line track together = Normal correlation' }, { color: 'red', text: '🔴 Line spikes without bars = Fuel loss without run time' }],
						explain: "If the generator runs more, it should use more fuel. When fuel goes up but run hours don't — <b>check for leaks or theft</b>."
					}} />

					<!-- 4. Daily Used vs Tank -->
					<Chart option={dualAxisChart(dates,
						d.map((r: any) => Math.round(r.fuel || 0)),
						d.map((r: any) => Math.round(r.tank || 0)),
						{ title: 'Daily Used vs Tank Balance', barName: 'Used (L)', lineName: 'Tank (L)', barColor: '#ef4444', lineColor: '#22c55e' }
					)} height="260px" guide={{
						formula: "Red bars = fuel burned today. Green line = remaining tank level.",
						sources: [{ data: 'Used', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM' }, { data: 'Tank', file: 'Blackout Hr Excel', col: 'Spare Tank Balance', method: 'LATEST' }],
						reading: [{ color: 'green', text: '✅ Green line stable/rising = Refueled recently' }, { color: 'red', text: '🔴 Green line dropping = Fuel depleting, plan refuel' }],
						explain: "Like watching your <b>fuel gauge</b>. Red bars eat the green line. When green drops too low, time to <b>order fuel</b>."
					}} />

					<!-- 5. Cumulative Fuel -->
					<Chart option={lineChart(dates, [{ name: 'Cumulative L', data: d.map((r: any) => Math.round(r.cumulative_fuel || 0)), color: '#f59e0b' }],
						{ title: 'Cumulative Fuel Consumption' })} height="260px" guide={{
						formula: "Running total of all fuel consumed: <b>SUM(daily_used) from day 1 to current</b>.",
						sources: [{ data: 'Cumulative Fuel', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM' }],
						reading: [{ color: 'green', text: '✅ Steady slope = Consistent burn rate' }, { color: 'amber', text: '🟡 Steeper slope = Burning more recently' }, { color: 'red', text: '🔴 Sudden jumps = Unusual high-consumption days' }],
						explain: "Total fuel ever used at this site. A <b>steeper line</b> means faster consumption — check if blackouts increased."
					}} />

					<!-- 6. Daily Cost -->
					<Chart option={lineChart(dates, [{ name: 'Cost (MMK)', data: d.map((r: any) => Math.round(r.cost || 0)), color: '#f59e0b' }],
						{ title: 'Daily Diesel Cost' })} height="260px" guide={{
						formula: "Daily Used (L) × Price per Liter (date-specific) = <b>Daily Cost in MMK</b>.",
						sources: [{ data: 'Cost', file: 'Blackout + Fuel Price', col: 'Used × Price', method: 'Daily calc' }],
						reading: [{ color: 'green', text: '✅ Low/stable = Efficient operation' }, { color: 'red', text: '🔴 Spike = High fuel use or price increase' }],
						explain: "How much <b>money</b> you spent on diesel each day. Spikes mean either more blackouts or higher fuel prices."
					}} />

					<!-- 7. Blackout vs Fuel -->
					<Chart option={dualAxisChart(dates,
						d.map((r: any) => Math.round((r.blackout_hr || 0) * 10) / 10),
						d.map((r: any) => Math.round(r.fuel || 0)),
						{ title: 'Blackout vs Fuel', barName: 'Blackout Hr', lineName: 'Fuel (L)', barColor: '#f59e0b', lineColor: '#ef4444' }
					)} height="260px" guide={{
						formula: "Yellow bars = hours without city power. Red line = fuel burned. More blackout → more fuel.",
						sources: [{ data: 'Blackout', file: 'Blackout Hr Excel', col: 'Blackout Hr', method: 'SUM' }, { data: 'Fuel', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM' }],
						reading: [{ color: 'green', text: '✅ Low bars + low line = Good power supply' }, { color: 'amber', text: '🟡 High bars + proportional line = Expected correlation' }, { color: 'red', text: '🔴 Low bars + high line = Fuel waste without blackouts' }],
						explain: "Blackouts force generators to run. More blackout = more fuel. If fuel is high but blackouts are low — <b>investigate waste</b>."
					}} />

					<!-- 7b. #107 Daily Blackout Hours -->
					<Chart option={barChart(dates, d.map((r: any) => Math.round((r.blackout_hr || 0) * 10) / 10), { title: 'Daily Blackout Hours', color: '#d97706' })} height="260px" guide={{
						formula: "Hours per day without city power = <b>Blackout Hours</b>. MAX(blackout per date per site).",
						sources: [{ data: 'Blackout Hr', file: 'Blackout Hr Excel', col: 'Blackout Hr', method: 'MAX per date' }],
						reading: [{ color: 'green', text: '🟢 Low bars = Stable city power' }, { color: 'amber', text: '🟡 4-8 hr = Moderate outages' }, { color: 'red', text: '🔴 8+ hr = Severe power crisis' }],
						explain: "Each bar is how many hours the site was <b>without city power</b> that day. Taller bars = longer outages = more generator fuel burned."
					}} />

					<!-- 8. Fuel Price -->
					{#if data.fuel_prices?.length > 0}
						{@const aggPrices = aggregatePrices(data.fuel_prices, period)}
						<Chart option={lineChart(
							aggPrices.map((r: any) => isD ? r.date : fmtPeriodLabel(r, period)),
							[{ name: isD ? 'Price/L' : 'Avg Price/L', data: aggPrices.map((r: any) => r.price || 0), color: '#06b6d4' }],
							{ title: isD ? 'Fuel Price Trend' : 'Fuel Price Trend (Avg per ' + pL + ')' }
						)} height="260px" guide={{
							formula: isD ? "Latest purchase price per liter (MMK) for this sector on each date." : "AVG(price_per_liter) per " + pL + " — averaged across all purchases in each " + pL + ".",
							sources: [{ data: 'Price', file: 'Fuel Price Excel', col: 'Price Per Liter', method: isD ? 'LATEST' : 'AVG' }],
							reading: [{ color: 'green', text: '✅ Stable/dropping = Good procurement' }, { color: 'red', text: '🔴 Rising trend = Cost pressure, consider bulk buying' }],
							explain: "Tracks how much you pay per liter over time. Rising prices multiply into <b>higher daily costs</b>."
						}} />
					{/if}

					<!-- 9. Anomaly Detection (7d MA) -->
					<Chart option={lineChart(dates, [
						{ name: 'Daily Fuel', data: d.map((r: any) => Math.round(r.fuel || 0)), color: '#fca5a5' },
						{ name: '7-Day MA', data: d.map((r: any) => Math.round(r.fuel_7d_ma || 0)), color: '#ef4444' },
					], { title: 'Anomaly Detection — Fuel vs 7-Day MA' })} height="260px" guide={{
						formula: "Light line = daily fuel. Dark line = 7-day moving average. Gap between them = <b>anomaly</b>.",
						sources: [{ data: 'Daily Fuel', file: 'Blackout Hr Excel', col: 'Daily Used', method: '7d rolling AVG' }],
						reading: [{ color: 'green', text: '✅ Lines track together = Normal' }, { color: 'red', text: '🔴 Light spikes above dark = Possible theft/waste' }, { color: 'blue', text: '📉 Light drops below = Less usage than usual' }],
						explain: "The moving average is the <b>expected normal</b>. When daily fuel jumps way above it, something unusual happened — <b>investigate that day</b>."
					}} />

					<!-- #122 Anomaly Days Table -->
					{#each [(() => {
						const rows: { date: string; actual: number; avg7d: number; pctAbove: number }[] = [];
						for (let i = 0; i < d.length; i++) {
							const actual = d[i].total_daily_used || d[i].fuel || 0;
							if (i < 6) continue;
							const w = d.slice(i - 6, i + 1);
							const avg7d = w.reduce((s: number, r: any) => s + (r.total_daily_used || r.fuel || 0), 0) / 7;
							if (avg7d > 0 && actual > avg7d * 1.3) {
								rows.push({ date: d[i].date, actual: Math.round(actual), avg7d: Math.round(avg7d), pctAbove: Math.round(((actual - avg7d) / avg7d) * 100) });
							}
						}
						return rows;
					})()] as anomalyRows}
						{#if anomalyRows.length > 0}
							<div class="col-span-1 md:col-span-2">
								<details class="mb-0">
									<summary class="cursor-pointer text-sm font-black uppercase px-4 py-2.5 flex items-center justify-between" style="background: #383832; color: #feffd6;">
										<span>ANOMALY_DAYS — FUEL &gt; 130% OF 7D AVG ({anomalyRows.length})</span>
										<button onclick={(e) => { e.preventDefault(); downloadExcel(anomalyRows, 'Anomaly Days'); }}
											class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
											style="color: #00fc40;">
											<span class="material-symbols-outlined text-sm">download</span> EXCEL
										</button>
									</summary>
									<div class="overflow-x-auto" style="border: 2px solid #383832; border-top: 0; background: #feffd6;">
										<table class="w-full text-xs">
											<thead><tr style="background: #383832;">
												<th class="text-left py-2 px-3 font-black uppercase" style="color: #feffd6;">Date</th>
												<th class="text-left py-2 px-3 font-black uppercase" style="color: #feffd6;">Actual (L)</th>
												<th class="text-left py-2 px-3 font-black uppercase" style="color: #feffd6;">7D Avg (L)</th>
												<th class="text-left py-2 px-3 font-black uppercase" style="color: #feffd6;">% Above</th>
											</tr></thead>
											<tbody>
												{#each anomalyRows as row, i}
													<tr style="border-bottom: 1px solid #ebe8dd; {i % 2 ? 'background: #f6f4e9;' : 'background: white;'}">
														<td class="py-1.5 px-3 font-bold" style="color: #383832;">{row.date}</td>
														<td class="py-1.5 px-3 font-mono" style="color: #be2d06;">{row.actual.toLocaleString()}</td>
														<td class="py-1.5 px-3 font-mono" style="color: #65655e;">{row.avg7d.toLocaleString()}</td>
														<td class="py-1.5 px-3 font-mono font-bold" style="color: #be2d06;">+{row.pctAbove}%</td>
													</tr>
												{/each}
											</tbody>
										</table>
									</div>
								</details>
							</div>
						{/if}
					{/each}

					<!-- 10. Site vs Sector Comparison -->
					{#if data.sector_avg?.length > 0}
						{@const sa = data.sector_avg}
						{@const saDates = sa.map((r: any) => r.date)}
						<Chart option={lineChart(saDates, [
							{ name: 'Site Fuel', data: d.slice(0, saDates.length).map((r: any) => Math.round(r.fuel || 0)), color: '#3b82f6' },
							{ name: 'Sector Avg', data: sa.map((r: any) => Math.round(r.sector_fuel || 0)), color: '#6b7280' },
						], { title: 'Site vs Sector Average — Fuel' })} height="260px" guide={{
							formula: "Blue = this site's fuel. Gray = average of all sites in the same sector.",
							sources: [{ data: 'Site Fuel', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM' }, { data: 'Sector Avg', file: 'Blackout Hr Excel', col: 'AVG(Daily Used)', method: 'AVG' }],
							reading: [{ color: 'green', text: '✅ Blue below gray = This site uses less than average' }, { color: 'red', text: '🔴 Blue above gray = This site is a heavy consumer' }],
							explain: "Compares this site to its peers. Consistently above average? This site may need <b>efficiency improvements or generator upgrades</b>."
						}} />

						<!-- #114 Buffer — Site vs Sector Avg -->
						{@const bufferSaDates = sa.map((r: any) => r.date)}
						<Chart option={lineChart(bufferSaDates, [
							{ name: 'Site Buffer', data: d.slice(0, bufferSaDates.length).map((r: any) => Math.round((r.buffer || 0) * 10) / 10), color: '#3b82f6' },
							{ name: 'Sector Avg Buffer', data: sa.map((r: any) => Math.round((r.sector_buffer || 0) * 10) / 10), color: '#6b7280' },
						], { title: 'Buffer — Site vs Sector Average', markLines: [{ value: 7, label: 'Safe', color: '#16a34a' }, { value: 3, label: 'Critical', color: '#dc2626' }] })} height="260px" guide={{
							formula: "Blue = this site's buffer days. Gray = sector average buffer. Lines at 7d (safe) and 3d (critical).",
							sources: [{ data: 'Site Buffer', file: 'Blackout Hr Excel', col: 'Tank / Burn', method: 'Daily calc' }, { data: 'Sector Avg', file: 'Blackout Hr Excel', col: 'AVG(Buffer)', method: 'AVG' }],
							reading: [{ color: 'green', text: '🟢 Blue above gray and above 7 = Better than peers, safe' }, { color: 'amber', text: '🟡 Blue below gray = Worse buffer than sector average' }, { color: 'red', text: '🔴 Blue below 3 = Critical regardless of sector' }],
							explain: "Compares this site's <b>fuel runway</b> to the sector average. If your site is consistently below the gray line, it needs <b>more frequent refueling</b> than its peers."
						}} />
					{/if}
				</div>

				<!-- Sales + Diesel% (if mapped) -->
				{#if data.has_sales && data.merged?.length > 0}
					{@const m = data.merged}
					<h3 class="text-sm font-black uppercase mb-3" style="color: #383832;">💰 Sales vs Diesel</h3>
					<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
						<Chart option={dualAxisChart(
							m.map((r: any) => r.date),
							m.map((r: any) => Math.round((r.sales || 0) / 1e6 * 10) / 10),
							m.map((r: any) => Math.round(r.cost || 0)),
							{ title: 'Sales vs Diesel Cost', barName: 'Sales (M)', lineName: 'Diesel Cost', barColor: '#22c55e', lineColor: '#ef4444' }
						)} height="280px" guide={{
							formula: "Green bars = daily sales (millions MMK). Red line = diesel cost (MMK). Gap between = <b>net benefit</b>.",
							sources: [{ data: 'Sales', file: 'Sales Excel', col: 'Sales Amt', method: 'SUM' }, { data: 'Cost', file: 'Blackout + Fuel', col: 'Used × Price', method: 'Daily calc' }],
							reading: [{ color: 'green', text: '✅ Big green bars, small red line = Profitable operation' }, { color: 'red', text: '🔴 Red line approaching green = Diesel eating into revenue' }],
							explain: "Shows if the store <b>earns more than it spends on diesel</b>. If red line gets close to green bars, consider reducing hours."
						}} />
						<Chart option={lineChart(
							m.map((r: any) => r.date),
							[{ name: 'Diesel %', data: m.map((r: any) => Math.round((r.diesel_pct || 0) * 10) / 10), color: '#ec4899' }],
							{ title: 'Diesel % of Sales', markLines: [{ value: 3, label: 'High', color: '#ef4444' }, { value: 0.9, label: 'OK', color: '#22c55e' }] }
						)} height="280px" guide={{
							formula: "(Diesel Cost ÷ Sales) × 100 = <b>Diesel % of Sales</b>. Lower is better.",
							sources: [{ data: 'Diesel %', file: 'Blackout + Sales', col: '(Used×Price) ÷ Sales', method: 'Daily calc' }],
							reading: [{ color: 'green', text: '🟢 Below 0.9% = Excellent, diesel negligible' }, { color: 'amber', text: '🟡 0.9-3% = Watch zone' }, { color: 'red', text: '🔴 Above 3% = Diesel too expensive, consider closing' }],
							explain: "The <b>key decision metric</b>. If diesel costs more than 3% of what you sell, the store may not be worth keeping open during blackouts."
						}} />

						<!-- #109 Diesel % vs Margin % -->
						{#each [m.map((r: any) => {
							const sales = r.sales || 0;
							const cost = r.cost || 0;
							return { date: r.date, diesel_pct: Math.round((r.diesel_pct || 0) * 10) / 10, margin_pct: sales > 0 ? Math.round(((sales - cost) / sales) * 1000) / 10 : 0 };
						})] as marginData}
						<Chart option={lineChart(
							marginData.map((r: any) => r.date),
							[
								{ name: 'Diesel %', data: marginData.map((r: any) => r.diesel_pct), color: '#ec4899' },
								{ name: 'Margin %', data: marginData.map((r: any) => r.margin_pct), color: '#22c55e' },
							],
							{ title: 'Diesel % vs Margin %', markLines: [{ value: 3, label: '3% Threshold', color: '#ef4444' }] }
						)} height="280px" guide={{
							formula: "Diesel % = (Diesel Cost / Sales) x 100. Margin % = ((Sales - Diesel Cost) / Sales) x 100. Threshold at <b>3%</b>.",
							sources: [{ data: 'Diesel %', file: 'Blackout + Sales', col: '(Used x Price) / Sales', method: 'Daily calc' }, { data: 'Margin %', file: 'Sales + Fuel', col: '(Sales - Cost) / Sales', method: 'Daily calc' }],
							reading: [{ color: 'green', text: '🟢 Pink below 3% + green high = Healthy store' }, { color: 'amber', text: '🟡 Pink approaching 3% = Diesel costs rising relative to sales' }, { color: 'red', text: '🔴 Pink above 3% = Consider reducing generator hours' }],
							explain: "Plots diesel cost as a <b>percentage of sales</b> versus the remaining <b>margin</b>. When diesel % crosses the 3% red line, the store is spending too much on fuel relative to what it earns."
						}} />
						{/each}
					</div>
				{/if}
			{/if}

			<!-- Per-Generator Charts (4) -->
			{#if gd.length > 0}
				{@const genNames = [...new Set(gd.map((r: any) => r.model_name))] as string[]}
				{@const genDates = [...new Set(gd.map((r: any) => r.date))].sort() as string[]}
				{@const genLabels = genDates.map(d => {
				const row = gd.find((x: any) => x.date === d);
				return period === 'daily' ? d : fmtPeriodLabel(row, period);
			})}
			{@const genColors = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6']}

				<h3 class="text-sm font-black uppercase mb-3" style="color: #383832;">🔧 Per-Generator Breakdown</h3>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
					<!-- Per-Gen Run Hours -->
					<Chart option={groupedBar(genLabels,
						genNames.map((g, i) => ({
							name: String(g),
							data: genDates.map(d => { const r = gd.find((x: any) => x.date === d && x.model_name === g); return Math.round(r?.gen_run_hr || 0); }),
							color: genColors[i % genColors.length]
						})),
						{ title: 'Run Hours per Generator' }
					)} height="280px" guide={{
						formula: "Hours each generator ran per day. Total site hours = <b>SUM of all generators</b>.",
						sources: [{ data: 'Run Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'SUM' }],
						reading: [{ color: 'green', text: '✅ Even distribution = Load sharing working' }, { color: 'amber', text: '🟡 One gen dominates = Check rotation policy' }],
						explain: "Shows which generator works hardest. <b>Rotate load</b> to extend equipment life."
					}} />

					<!-- Per-Gen Fuel Used -->
					<Chart option={groupedBar(genLabels,
						genNames.map((g, i) => ({
							name: String(g),
							data: genDates.map(d => { const r = gd.find((x: any) => x.date === d && x.model_name === g); return Math.round(r?.daily_used_liters || 0); }),
							color: genColors[i % genColors.length]
						})),
						{ title: 'Fuel Used per Generator (L)' }
					)} height="280px" guide={{
						formula: "Liters consumed by each generator per day.",
						sources: [{ data: 'Fuel Used', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM' }],
						reading: [{ color: 'green', text: '✅ Proportional to run hours = Normal' }, { color: 'red', text: '🔴 High fuel but low hours = Inefficient generator' }],
						explain: "Compare with run hours chart — a gen using lots of fuel for few hours is <b>inefficient and may need maintenance</b>."
					}} />

					<!-- Expected vs Actual -->
					<Chart option={groupedBar(genNames.map(String),
						[
							{ name: 'Expected', data: genNames.map(g => { const rs = gd.filter((x: any) => x.model_name === g); return Math.round(rs.reduce((s: number, r: any) => s + (r.expected || 0), 0)); }), color: '#3b82f6' },
							{ name: 'Actual', data: genNames.map(g => { const rs = gd.filter((x: any) => x.model_name === g); return Math.round(rs.reduce((s: number, r: any) => s + (r.daily_used_liters || 0), 0)); }), color: '#ef4444' },
						],
						{ title: 'Expected vs Actual Consumption' }
					)} height="280px" guide={{
						formula: "Expected = Rated L/Hr × Run Hours. Actual = Reported daily used. Variance = <b>Actual − Expected</b>.",
						sources: [{ data: 'Expected', file: 'Generators Table', col: 'consumption_per_hour × gen_run_hr', method: 'SUM' }, { data: 'Actual', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM' }],
						reading: [{ color: 'green', text: '✅ Blue ≈ Red = Generator performing to spec' }, { color: 'red', text: '🔴 Red >> Blue = Over-consuming, check for issues' }, { color: 'blue', text: '📉 Red << Blue = Under-reporting or measurement error' }],
						explain: "Compares what the generator <b>should</b> use vs what it <b>actually</b> used. Large gaps signal <b>theft, leaks, or aging equipment</b>."
					}} />

					<!-- Cost Split Pie -->
					<Chart option={pieChart(
						genNames.map(g => {
							const rs = gd.filter((x: any) => x.model_name === g);
							return { name: String(g), value: Math.round(rs.reduce((s: number, r: any) => s + (r.cost || 0), 0)) };
						}),
						{ title: 'Cost Split by Generator' }
					)} height="280px" guide={{
						formula: "Each slice = generator's total diesel cost. Cost = <b>Liters Used × Price per Liter</b>.",
						sources: [{ data: 'Cost', file: 'Blackout + Fuel Price', col: 'Used × Price', method: 'SUM' }],
						reading: [{ color: 'green', text: '✅ Even slices = Cost shared across fleet' }, { color: 'red', text: '🔴 One big slice = That generator is the cost driver' }],
						explain: "Which generator costs the most? If one slice dominates, consider <b>replacing or servicing</b> that unit."
					}} />
					<!-- #120 Stacked Diesel by Generator -->
					<Chart option={(() => {
						const stackDates = [...new Set(gd.map((r: any) => r.date))].sort() as string[];
						const stackLabels = stackDates.map(d => {
							const row = gd.find((x: any) => x.date === d);
							return period === 'daily' ? d : fmtPeriodLabel(row, period);
						});
						const stackSeries = genNames.map((g, i) => ({
							type: 'bar' as const,
							name: String(g),
							stack: 'total',
							data: stackDates.map(dt => { const r = gd.find((x: any) => x.date === dt && x.model_name === g); return Math.round(r?.daily_used_liters || 0); }),
							itemStyle: { color: genColors[i % genColors.length] },
							emphasis: { focus: 'series' as const }
						}));
						return {
							title: { text: 'Stacked Diesel by Generator', left: 'center', textStyle: { fontSize: 14 } },
							tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
							legend: { bottom: 0, textStyle: { fontSize: 10 } },
							xAxis: { type: 'category', data: stackLabels, axisLabel: { rotate: stackLabels.length > 10 ? 45 : 0, fontSize: 10 } },
							yAxis: { type: 'value', name: 'Liters', axisLabel: { formatter: (v: number) => v >= 1e3 ? (v/1e3).toFixed(1)+'K' : String(v) } },
							series: stackSeries,
							grid: { top: 50, bottom: 40, left: 60, right: 20 }
						};
					})()} height="280px" guide={{
						formula: "Each colored segment = liters consumed by one generator. Total bar height = <b>site total for that day</b>.",
						sources: [{ data: 'Generator Fuel', file: 'Blackout Hr Excel', col: 'Daily Used per Gen', method: 'SUM' }],
						reading: [{ color: 'green', text: '✅ Even color distribution = Load balanced across generators' }, { color: 'amber', text: '🟡 One color dominates = That generator carries most load' }, { color: 'red', text: '🔴 Total bar height spiking = Investigate high-consumption days' }],
						explain: "Shows how diesel consumption is <b>split across generators</b> each day. Helps identify which generator is the biggest fuel consumer and whether load is balanced."
					}} />
				</div>

				<!-- Variance Table -->
				<details class="mb-6">
					<summary class="cursor-pointer text-sm font-black uppercase px-4 py-2.5 flex items-center justify-between" style="background: #383832; color: #feffd6;">
						<span>VARIANCE_ANALYSIS</span>
						<button onclick={(e) => { e.preventDefault(); downloadExcel(gd, 'Variance Analysis'); }}
							class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
							style="color: #00fc40;">
							<span class="material-symbols-outlined text-sm">download</span> EXCEL
						</button>
					</summary>
					<div class="overflow-x-auto" style="border: 2px solid #383832; border-top: 0;">
						<table class="w-full text-xs">
							<thead><tr style="background: #ebe8dd; border-bottom: 2px solid #383832;">
								<th class="text-left py-2 px-3 font-black uppercase" style="color: #383832;">Date</th>
								<th class="text-left py-2 px-3 font-black uppercase" style="color: #383832;">Generator</th>
								<th class="text-left py-2 px-3 font-black uppercase" style="color: #383832;">Expected (L)</th>
								<th class="text-left py-2 px-3 font-black uppercase" style="color: #383832;">Actual (L)</th>
								<th class="text-left py-2 px-3 font-black uppercase" style="color: #383832;">Variance</th>
								<th class="text-left py-2 px-3 font-black uppercase" style="color: #383832;">Status</th>
							</tr></thead>
							<tbody>
								{#each gd.slice(-20) as row, i}
									{@const v = (row.variance || 0)}
									<tr style="border-bottom: 1px solid #ebe8dd; {i % 2 ? 'background: #f6f4e9;' : 'background: white;'}">
										<td class="py-1.5 px-3" style="color: #65655e;">{row.date}</td>
										<td class="py-1.5 px-3 font-bold" style="color: #383832;">{row.model_name}</td>
										<td class="py-1.5 px-3" style="color: #65655e;">{Math.round(row.expected || 0)}</td>
										<td class="py-1.5 px-3" style="color: #65655e;">{Math.round(row.daily_used_liters || 0)}</td>
										<td class="py-1.5 px-3 font-mono font-bold" style="color: {v > 0 ? '#be2d06' : '#007518'};">{v > 0 ? '+' : ''}{Math.round(v)}</td>
										<td class="py-1.5 px-3">{Math.abs(v) > 50 ? '🔴' : Math.abs(v) > 20 ? '🟡' : '🟢'}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</details>
			{/if}

			<!-- Peak Hours -->
			<PeakHours siteId={selected} />
		{/if}
		</div>

	</div>
</div>

