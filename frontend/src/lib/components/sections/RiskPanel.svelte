<script lang="ts">
	import { api, downloadExcel } from '$lib/api';
	import { onMount } from 'svelte';
	import InfoTip from '$lib/components/InfoTip.svelte';
	import { KPI } from '$lib/kpi-definitions';

	let { siteType = 'All', sites = [] as string[] }: { siteType?: string; sites?: string[] } = $props();

	let scores: any[] = $state([]);
	let alerts: any[] = $state([]);
	let forecast: any[] = $state([]);
	let breakeven: any[] = $state([]);

	function fmt(v: any) {
		if (!v) return '0';
		if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
		if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
		return Number(v).toLocaleString();
	}

	function fmtDec(v: any, d = 1) {
		if (v == null || v === '') return '-';
		return Number(v).toFixed(d);
	}

	function truncate(s: string, max = 80) {
		if (!s) return '';
		return s.length > max ? s.slice(0, max) + '...' : s;
	}

	function trendArrow(trend: string | undefined): string {
		if (!trend) return '\u2192';
		const t = trend.toLowerCase();
		if (t === 'up' || t === 'increasing') return '\u2191';
		if (t === 'down' || t === 'decreasing') return '\u2193';
		return '\u2192';
	}

	function formatDate(d: string | undefined): string {
		if (!d) return '-';
		try {
			const dt = new Date(d);
			return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
		} catch {
			return d;
		}
	}

	function formatTimestamp(d: string | undefined): string {
		if (!d) return '-';
		try {
			const dt = new Date(d);
			return dt.toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
		} catch {
			return d;
		}
	}

	const gradeColors: Record<string, string> = {
		A: '#007518',
		B: '#006f7c',
		C: '#ff9d00',
		D: '#f95630',
		F: '#be2d06',
	};

	const severityColors: Record<string, string> = {
		CRITICAL: '#be2d06',
		WARNING: '#ff9d00',
		INFO: '#65655e',
	};

	const severityOrder = ['CRITICAL', 'WARNING', 'INFO'];

	// Site filtering
	const fScores = $derived(sites.length > 0 ? scores.filter((r: any) => sites.includes(r.site_id)) : scores);
	const fAlerts = $derived(sites.length > 0 ? alerts.filter((r: any) => sites.includes(r.site_id)) : alerts);
	const fForecast = $derived(sites.length > 0 ? forecast.filter((r: any) => sites.includes(r.site_id)) : forecast);
	const fBreakeven = $derived(sites.length > 0 ? breakeven.filter((r: any) => sites.includes(r.site_id)) : breakeven);

	// Derived data
	const sortedForecast = $derived([...fForecast].sort((a, b) => (a.days_until_stockout ?? 999) - (b.days_until_stockout ?? 999)));
	const sortedScores = $derived([...fScores].sort((a, b) => (a.bcp_score ?? 0) - (b.bcp_score ?? 0)));
	const sortedAlerts = $derived(
		[...fAlerts].sort((a, b) => {
			const ai = severityOrder.indexOf((a.severity || '').toUpperCase());
			const bi = severityOrder.indexOf((b.severity || '').toUpperCase());
			const ao = ai === -1 ? 99 : ai;
			const bo = bi === -1 ? 99 : bi;
			if (ao !== bo) return ao - bo;
			return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
		})
	);

	// KPIs
	const stockoutRisk = $derived(fForecast.filter((f) => (f.days_until_stockout ?? 999) <= 7).length);
	const avgDaysToStockout = $derived(
		fForecast.length > 0
			? (fForecast.reduce((s, f) => s + (f.days_until_stockout ?? 0), 0) / fForecast.length).toFixed(1)
			: '-'
	);
	const mostUrgent = $derived(sortedForecast.length > 0 ? sortedForecast[0] : null);
	const riskCrit = $derived(fForecast.filter(f => (f.days_until_stockout ?? 999) < 3).length);
	const riskWarn = $derived(fForecast.filter(f => { const d = f.days_until_stockout ?? 999; return d >= 3 && d <= 5; }).length);
	const riskWatch = $derived(fForecast.filter(f => { const d = f.days_until_stockout ?? 999; return d > 5 && d <= 7; }).length);
	const avgDaysNum = $derived(parseFloat(avgDaysToStockout) || 0);
	const avgDaysColor = $derived(avgDaysNum > 0 && avgDaysNum < 3 ? '#be2d06' : avgDaysNum < 5 ? '#ff9d00' : '#383832');
	const avgDaysBarColor = $derived(avgDaysNum < 3 ? '#be2d06' : avgDaysNum < 5 ? '#ff9d00' : '#007518');

	const gradeA = $derived(fScores.filter((s) => s.grade === 'A').length);
	const gradeB = $derived(fScores.filter((s) => s.grade === 'B').length);
	const gradeC = $derived(fScores.filter((s) => s.grade === 'C').length);
	const gradeD = $derived(fScores.filter((s) => s.grade === 'D' || s.grade === 'F').length);
	const avgScore = $derived(
		fScores.length > 0
			? (fScores.reduce((s, r) => s + (r.bcp_score ?? 0), 0) / fScores.length).toFixed(0)
			: '-'
	);
	const avgGrade = $derived(
		fScores.length > 0
			? (() => {
					const a = fScores.reduce((s, r) => s + (r.bcp_score ?? 0), 0) / fScores.length;
					if (a >= 80) return 'A';
					if (a >= 65) return 'B';
					if (a >= 50) return 'C';
					if (a >= 35) return 'D';
					return 'F';
				})()
			: '-'
	);

	const criticalCount = $derived(fAlerts.filter((a) => (a.severity || '').toUpperCase() === 'CRITICAL').length);
	const warningCount = $derived(fAlerts.filter((a) => (a.severity || '').toUpperCase() === 'WARNING').length);
	const infoCount = $derived(fAlerts.filter((a) => (a.severity || '').toUpperCase() === 'INFO').length);

	// Sector breakdown for stockout risk
	const riskBySector = $derived(() => {
		const map: Record<string, number> = {};
		for (const f of fForecast) { const s = f.sector_id || '?'; map[s] = (map[s] || 0) + 1; }
		return Object.entries(map).sort((a, b) => b[1] - a[1]);
	});

	// Alert type counts for bars
	const alertTypeCounts = $derived(() => {
		const map: Record<string, number> = {};
		for (const a of fAlerts) { const t = a.alert_type || '?'; map[t] = (map[t] || 0) + 1; }
		return Object.entries(map).sort((a, b) => b[1] - a[1]);
	});

	// Alert type breakdown
	const alertTypeBreakdown = $derived(() => {
		const map: Record<string, { count: number; severity: string }> = {};
		for (const a of fAlerts) {
			const t = a.alert_type || 'UNKNOWN';
			if (!map[t]) map[t] = { count: 0, severity: (a.severity || 'INFO').toUpperCase() };
			map[t].count++;
		}
		return Object.entries(map)
			.map(([type, v]) => ({ type, ...v }))
			.sort((a, b) => b.count - a.count);
	});

	// Situation report
	const today = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });
	const situationReport = $derived(() => {
		const parts: string[] = [];
		parts.push(`On ${today}, ${stockoutRisk} site${stockoutRisk !== 1 ? 's are' : ' is'} at risk of stockout within 7 days.`);
		parts.push(`${criticalCount} critical alert${criticalCount !== 1 ? 's' : ''} active.`);
		if (fScores.length > 0) {
			parts.push(`Average BCP score is ${avgScore}/100 (Grade ${avgGrade}).`);
		}
		if (mostUrgent) {
			parts.push(`Most urgent: ${mostUrgent.site_id} (${mostUrgent.sector_id ?? ''}) with ${fmtDec(mostUrgent.days_until_stockout, 1)} days remaining.`);
		}
		return parts.join(' ');
	});

	function daysColor(d: number | undefined): string {
		if (d == null) return '#383832';
		if (d < 3) return '#be2d06';
		if (d < 7) return '#ff9d00';
		return '#007518';
	}

	async function load() {
		const tp = siteType !== 'All' ? `?site_type=${siteType}` : '';
		const tasks = [
			api.get(`/bcp-scores${tp}`).then((d: any) => { scores = Array.isArray(d) ? d : (d.scores || d.data || []); }).catch(() => {}),
			api.get(`/alerts${tp}`).then((d: any) => { alerts = Array.isArray(d) ? d : (d.alerts || d.data || []); }).catch(() => {}),
			api.get(`/stockout-forecast${tp}`).then((d: any) => { forecast = Array.isArray(d) ? d : (d.forecast || d.data || []); }).catch(() => {}),
			api.get(`/break-even${tp}`).then((d: any) => { breakeven = d?.sites || (Array.isArray(d) ? d : []); }).catch(() => {}),
		];
		await Promise.allSettled(tasks);
	}

	onMount(load);
</script>

<div class="space-y-4 pb-8">

	<!-- ═══════ SECTION 1: RISK SITUATION REPORT ═══════ -->
	<div class="mx-1 mt-4 p-4" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832; background: #fefff0;">
		<div class="flex items-center gap-2 mb-2">
			<span class="material-symbols-outlined text-lg" style="color: #be2d06;">campaign</span>
			<span class="font-black uppercase text-xs" style="color: #383832;">RISK SITUATION REPORT</span>
			<span class="text-[10px] font-mono opacity-60" style="color: #65655e;">{today}</span>
		</div>
		<p class="text-xs leading-relaxed" style="color: #383832;">{situationReport()}</p>
	</div>

	<!-- ═══════ SECTION 2: STOCKOUT FORECAST ═══════ -->
	<div id="risk-stockout" class="scroll-mt-36 px-4 py-3 mb-3 mt-6" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">hourglass_bottom</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 1: STOCKOUT FORECAST</div>
				<div class="text-[10px] opacity-75">Fuel depletion timeline across all monitored sites</div>
			</div>
		</div>
		<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which sites will run out of fuel first and when?</div>
	</div>

	<!-- Stockout KPIs (Overview chart style) -->
	<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 px-1 mb-3">
		<!-- SITES AT RISK -->
		<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
				<span class="text-[11px] font-black uppercase">SITES AT RISK</span>
				<span class="text-[10px] font-bold" style="color: #f95630;">&le;7 DAYS</span>
				<InfoTip {...KPI.risk.sitesAtRisk} />
			</div>
			<div class="flex">
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #be2d06;">{stockoutRisk}</div>
					<div class="text-[9px] font-bold" style="color: #65655e;">TOTAL</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1;">
					<div class="text-2xl font-black" style="color: #383832;">{riskCrit}</div>
					<div class="text-[9px] font-bold" style="color: #be2d06;">&lt;3 DAYS</div>
				</div>
			</div>
			<div style="border-top: 1px solid #ebe8dd;">
				{#each [
					{ label: '&lt;3D CRITICAL', count: riskCrit, color: '#be2d06' },
					{ label: '3-5D WARNING', count: riskWarn, color: '#ff9d00' },
					{ label: '5-7D WATCH', count: riskWatch, color: '#65655e' },
				] as bar}
					<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid rgba(56,56,50,0.08);">
						<span class="text-[9px] w-20 shrink-0" style="color: #828179;">{@html bar.label}</span>
						<div class="flex-1 h-4 relative" style="background: #f0ede3;">
							<div class="h-full" style="width: {stockoutRisk > 0 ? (bar.count / stockoutRisk * 100) : 0}%; background: {bar.color};"></div>
						</div>
						<span class="text-[9px] w-6 text-right shrink-0 font-black" style="color: #383832;">{bar.count}</span>
					</div>
				{/each}
			</div>
			<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">sites where days_left &le; 7</div>
		</div>
		<!-- AVG DAYS TO STOCKOUT -->
		<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
				<span class="text-[11px] font-black uppercase">AVG DAYS TO STOCKOUT</span>
				<InfoTip {...KPI.risk.avgDaysToStockout} />
			</div>
			<div class="flex">
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: {avgDaysColor};">{avgDaysToStockout}</div>
					<div class="text-[9px] font-bold" style="color: #65655e;">DAYS</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1;">
					<div class="text-2xl font-black" style="color: #383832;">{fForecast.length}</div>
					<div class="text-[9px] font-bold" style="color: #65655e;">SITES</div>
				</div>
			</div>
			<div style="border-top: 1px solid #ebe8dd;">
				{#each riskBySector() as [sector, count]}
					<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid rgba(56,56,50,0.08);">
						<span class="text-[9px] w-12 shrink-0 font-bold" style="color: #828179;">{sector}</span>
						<div class="flex-1 h-4 relative" style="background: #f0ede3;">
							<div class="h-full" style="width: {fForecast.length > 0 ? (count / fForecast.length * 100) : 0}%; background: {avgDaysBarColor};"></div>
						</div>
						<span class="text-[9px] w-6 text-right shrink-0 font-black" style="color: #383832;">{count}</span>
					</div>
				{/each}
			</div>
			<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">AVG(days_until_stockout)</div>
		</div>
		<!-- MOST URGENT SITE -->
		<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
				<span class="text-[11px] font-black uppercase">MOST URGENT SITE</span>
				<InfoTip {...KPI.risk.mostUrgent} />
			</div>
			{#if mostUrgent}
				<div class="flex">
					<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
						<div class="text-lg font-black" style="color: {daysColor(mostUrgent.days_until_stockout)};">{mostUrgent.site_code || mostUrgent.site_id}</div>
						<div class="text-[9px] font-bold" style="color: #65655e;">{mostUrgent.sector_id}</div>
					</div>
					<div class="p-3 flex flex-col justify-center" style="flex: 1;">
						<div class="text-2xl font-black" style="color: {daysColor(mostUrgent.days_until_stockout)};">{fmtDec(mostUrgent.days_until_stockout, 1)}</div>
						<div class="text-[9px] font-bold" style="color: #65655e;">DAYS LEFT</div>
					</div>
				</div>
				<div style="border-top: 1px solid #ebe8dd;">
					{#each [
						{ label: 'TANK', value: mostUrgent.current_balance || 0, max: 3000, unit: 'L', color: '#007518' },
						{ label: 'BURN/DAY', value: mostUrgent.smoothed_daily_used || mostUrgent.avg_daily_used || 0, max: 1000, unit: 'L', color: '#e85d04' },
						{ label: '7D BURN', value: mostUrgent.predicted_7d_burn || 0, max: 7000, unit: 'L', color: '#9d4867' },
					] as bar}
						<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid rgba(56,56,50,0.08);">
							<span class="text-[9px] w-16 shrink-0" style="color: #828179;">{bar.label}</span>
							<div class="flex-1 h-4 relative" style="background: #f0ede3;">
								<div class="h-full" style="width: {Math.min(100, bar.value / bar.max * 100)}%; background: {bar.color};"></div>
							</div>
							<span class="text-[9px] w-12 text-right shrink-0 font-black" style="color: #383832;">{fmt(bar.value)}{bar.unit}</span>
						</div>
					{/each}
				</div>
				<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">MIN(days_until_stockout)</div>
			{:else}
				<div class="p-6 text-center">
					<div class="text-2xl font-black" style="color: #007518;">&mdash;</div>
					<div class="text-[9px] font-bold uppercase" style="color: #65655e;">NO SITES AT RISK</div>
				</div>
			{/if}
		</div>
	</div>

	<!-- Stockout Table -->
	<div class="mx-1 mb-6" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
		<div class="flex items-center justify-between px-3 py-1.5" style="background: #383832;">
			<span class="text-[10px] font-bold uppercase" style="color: #feffd6;">STOCKOUT FORECAST TABLE</span>
			<button onclick={() => downloadExcel(sortedForecast, 'Stockout Forecast')}
				class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
				style="color: #00fc40;">
				<span class="material-symbols-outlined text-sm">download</span> EXCEL
			</button>
		</div>
		<div class="overflow-auto" style="max-height: 500px;">
			<table class="w-full text-xs" style="border-collapse: collapse;">
				<thead>
					<tr style="background: #ebe8dd;">
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">SITE</th>
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832; color: #65655e;">CODE</th>
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">SECTOR</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">TANK (L)</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">AVG BURN (L)</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">DAYS LEFT</th>
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">STOCKOUT DATE</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">7D BURN</th>
						<th class="px-2 py-1.5 text-center font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">TREND</th>
						<th class="px-2 py-1.5 text-center font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">METHOD</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">CONFIDENCE</th>
					</tr>
				</thead>
				<tbody>
					{#each sortedForecast as row, i}
						{@const dl = row.days_until_stockout ?? 999}
						<tr style="background: {i % 2 === 0 ? '#ffffff' : '#f6f4e9'};">
							<td class="px-2 py-1 font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{row.site_id ?? ''}</td>
							<td class="px-2 py-1 font-mono text-[11px]" style="border-bottom: 1px solid #ddd; color: #65655e;">{row.site_code ?? ''}</td>
							<td class="px-2 py-1 text-[11px]" style="border-bottom: 1px solid #ddd;">{row.sector_id ?? ''}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{fmt(row.current_balance)}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{fmtDec(row.smoothed_daily_used ?? row.avg_daily_used)}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px] font-black" style="border-bottom: 1px solid #ddd; color: {daysColor(dl)};">{fmtDec(dl, 1)}</td>
							<td class="px-2 py-1 font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{formatDate(row.projected_stockout_date)}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{row.predicted_7d_burn ? fmt(row.predicted_7d_burn) : '-'}</td>
							<td class="px-2 py-1 text-center text-base font-black" style="border-bottom: 1px solid #ddd;">{trendArrow(row.trend)}</td>
							<td class="px-2 py-1 text-center" style="border-bottom: 1px solid #ddd;">
								<span class="inline-block px-1.5 py-0.5 text-[9px] font-black uppercase" style="background: {row.method === 'ridge' ? '#006f7c' : '#65655e'}; color: white;">{row.method ?? 'ema'}</span>
							</td>
							<td class="px-2 py-1 text-right font-mono text-[11px] font-bold" style="border-bottom: 1px solid #ddd; color: {(row.confidence_pct ?? 0) >= 70 ? '#007518' : (row.confidence_pct ?? 0) >= 40 ? '#ff9d00' : '#be2d06'};">{row.confidence_pct != null ? row.confidence_pct + '%' : '-'}</td>
						</tr>
					{/each}
					{#if fForecast.length === 0}
						<tr><td colspan="11" class="text-center py-6 font-bold uppercase text-[10px] opacity-50">NO FORECAST DATA</td></tr>
					{/if}
				</tbody>
			</table>
		</div>
		<!-- What each column means (plain English) -->
		<div class="px-4 py-3" style="background: #f6f4e9; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">WHAT EACH COLUMN MEANS</div>
			<table class="w-full text-[10px]" style="border-collapse: collapse;">
				<thead>
					<tr style="background: #ebe8dd;">
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7; width: 110px;">COLUMN</th>
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7;">WHAT IT TELLS YOU</th>
						<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 1px solid #d5d2c7; width: 240px;">HOW IT IS CALCULATED</th>
					</tr>
				</thead>
				<tbody>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">TANK (L)</td>
						<td class="py-1.5 px-2" style="color: #383832;">How many liters of diesel are in the tank right now</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Last reported spare tank balance</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">AVG BURN (L)</td>
						<td class="py-1.5 px-2" style="color: #383832;">How many liters this site uses per day on average, giving more importance to recent days</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Smoothed average: 30% latest day + 70% previous average</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #be2d06;">DAYS LEFT</td>
						<td class="py-1.5 px-2" style="color: #383832;">How many days until the tank is completely empty if no delivery arrives. <span class="font-bold" style="color: #be2d06;">Red = urgent (&lt;3 days)</span>, <span class="font-bold" style="color: #ff9d00;">orange = warning (3&ndash;5 days)</span></td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;"><span style="color: #006f7c;">RIDGE:</span> Adds up predicted daily burn until total exceeds tank<br><span style="color: #65655e;">EMA:</span> Tank &divide; daily burn rate</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">STOCKOUT DATE</td>
						<td class="py-1.5 px-2" style="color: #383832;">The actual calendar date when fuel will run out &mdash; use this to schedule deliveries before this date</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Today + DAYS LEFT</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">7D BURN</td>
						<td class="py-1.5 px-2" style="color: #383832;">Total liters the site is predicted to consume over the next 7 days &mdash; use this to plan delivery volumes</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Sum of predicted burn for each of the next 7 days (accounts for weekday/weekend patterns)</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">TREND</td>
						<td class="py-1.5 px-2" style="color: #383832;">&darr; Site is using <span class="font-bold">less</span> fuel recently (good &mdash; lasting longer) &nbsp; &uarr; Using <span class="font-bold">more</span> fuel (bad &mdash; running out faster) &nbsp; &rarr; Stable</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Compares last 3 days average vs prior 3 days. &gt;10% change = arrow</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">METHOD</td>
						<td class="py-1.5 px-2" style="color: #383832;"><span class="font-bold" style="color: #006f7c;">RIDGE</span> = smarter prediction (learns from patterns) &nbsp; <span class="font-bold" style="color: #65655e;">EMA</span> = simple average (used when not enough history)</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">RIDGE used when &ge;5 days of data, EMA when 2&ndash;4 days</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">CONFIDENCE</td>
						<td class="py-1.5 px-2" style="color: #383832;">How reliable is this prediction? <span class="font-bold" style="color: #007518;">&ge;70% = trustworthy</span>, <span class="font-bold" style="color: #ff9d00;">40&ndash;69% = rough estimate</span>, <span class="font-bold" style="color: #be2d06;">&lt;40% = unreliable</span> (irregular usage or too few data points)</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">RIDGE: How well the model fits past data (R&sup2;)<br>EMA: Based on number of data points &amp; consistency</td>
					</tr>
				</tbody>
			</table>
		</div>
		<!-- How it works (plain English) -->
		<div class="px-4 py-3" style="background: white; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">HOW THE FORECAST WORKS</div>
			<div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-[10px]" style="color: #383832;">
				<div class="flex gap-2">
					<span class="inline-block px-1.5 py-0.5 font-black uppercase shrink-0 self-start mt-0.5" style="background: #006f7c; color: white; font-size: 9px;">RIDGE</span>
					<div>
						<div class="font-bold mb-1">Smart Prediction (Primary Method)</div>
						<ol class="list-decimal ml-3 leading-relaxed" style="color: #65655e;">
							<li>Looks at the last 30 days of fuel usage for each site</li>
							<li>Learns the pattern &mdash; does this site burn more on weekdays vs weekends?</li>
							<li>Detects if usage is going up or down over time</li>
							<li>Predicts how much fuel will be used <span class="font-bold" style="color: #383832;">each day for the next 7 days</span></li>
							<li>Adds up daily predictions until the total exceeds what is in the tank</li>
							<li>That day = stockout date</li>
						</ol>
						<div class="mt-1 font-bold" style="color: #006f7c;">Best for: Sites with 5+ days of history and regular patterns</div>
					</div>
				</div>
				<div class="flex gap-2">
					<span class="inline-block px-1.5 py-0.5 font-black uppercase shrink-0 self-start mt-0.5" style="background: #65655e; color: white; font-size: 9px;">EMA</span>
					<div>
						<div class="font-bold mb-1">Simple Prediction (Fallback)</div>
						<ol class="list-decimal ml-3 leading-relaxed" style="color: #65655e;">
							<li>Calculates a smoothed daily burn rate from past data</li>
							<li>Recent days count more (30% weight) than older days (70%)</li>
							<li>Divides tank balance by this burn rate</li>
							<li>Result = estimated days until empty</li>
						</ol>
						<div class="mt-1 font-bold" style="color: #65655e;">Best for: New sites with only 2&ndash;4 days of data</div>
					</div>
				</div>
			</div>
			<div class="mt-3 px-2 py-1.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">
				<span class="font-bold" style="color: #383832;">NOTE:</span> These are predictions, not guarantees. Actual stockout depends on generator runtime, blackout hours, and delivery schedules. Always verify with site managers before making delivery decisions.
			</div>
		</div>
	</div>

	<!-- ═══════ SECTION 3: BCP RISK GRADES ═══════ -->
	<div id="risk-grades" class="scroll-mt-36 px-4 py-3 mb-3 mt-6" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">shield</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 2: BCP RISK GRADES</div>
				<div class="text-[10px] opacity-75">Business continuity preparedness scores for all sites</div>
			</div>
		</div>
		<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? How prepared is each site for power disruption?</div>
	</div>

	<!-- BCP KPIs (Overview chart style) -->
	<div class="grid grid-cols-1 sm:grid-cols-2 gap-4 px-1 mb-3">
		<!-- GRADE DISTRIBUTION -->
		<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
				<span class="text-[11px] font-black uppercase">GRADE DISTRIBUTION</span>
				<span class="text-[10px] font-bold">{fScores.length} SITES</span>
				<InfoTip {...KPI.risk.bcpGrades} />
			</div>
			<div class="flex">
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #383832;">{avgScore}</div>
					<div class="text-[9px] font-bold" style="color: #65655e;">AVG SCORE</div>
					<div class="text-[8px]" style="color: #9d9d91;">Grade {avgGrade}</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1;">
					<div class="text-2xl font-black" style="color: #be2d06;">{gradeD}</div>
					<div class="text-[9px] font-bold" style="color: #be2d06;">D/F SITES</div>
					<div class="text-[8px]" style="color: #9d9d91;">Need action</div>
				</div>
			</div>
			<div style="border-top: 1px solid #ebe8dd;">
				{#each [
					{ label: 'A RESILIENT', count: gradeA, color: '#007518' },
					{ label: 'B ADEQUATE', count: gradeB, color: '#006f7c' },
					{ label: 'C AT RISK', count: gradeC, color: '#ff9d00' },
					{ label: 'D/F CRITICAL', count: gradeD, color: '#be2d06' },
				] as bar}
					<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid rgba(56,56,50,0.08);">
						<span class="text-[9px] w-20 shrink-0 font-bold" style="color: {bar.color};">{bar.label}</span>
						<div class="flex-1 h-4 relative" style="background: #f0ede3;">
							<div class="h-full" style="width: {fScores.length > 0 ? (bar.count / fScores.length * 100) : 0}%; background: {bar.color};"></div>
						</div>
						<span class="text-[9px] w-6 text-right shrink-0 font-black" style="color: #383832;">{bar.count}</span>
					</div>
				{/each}
			</div>
			<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">fuel(35%) + coverage(30%) + power(20%) + resilience(15%)</div>
		</div>
		<!-- SCORE BREAKDOWN -->
		<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
				<span class="text-[11px] font-black uppercase">SCORE COMPONENTS</span>
			</div>
			<div class="flex">
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #007518;">{gradeA + gradeB}</div>
					<div class="text-[9px] font-bold" style="color: #007518;">A+B SAFE</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1;">
					<div class="text-2xl font-black" style="color: #ff9d00;">{gradeC + gradeD}</div>
					<div class="text-[9px] font-bold" style="color: #ff9d00;">C+D/F RISK</div>
				</div>
			</div>
			{#if fScores.length > 0}
				{@const avgFuel = fScores.reduce((s, r) => s + (r.fuel_score ?? 0), 0) / fScores.length}
				{@const avgCov = fScores.reduce((s, r) => s + (r.coverage_score ?? 0), 0) / fScores.length}
				{@const avgPow = fScores.reduce((s, r) => s + (r.power_score ?? 0), 0) / fScores.length}
				{@const avgRes = fScores.reduce((s, r) => s + (r.resilience_score ?? 0), 0) / fScores.length}
				<div style="border-top: 1px solid #ebe8dd;">
					{#each [
						{ label: 'FUEL (35%)', value: avgFuel, color: '#007518' },
						{ label: 'COVERAGE (30%)', value: avgCov, color: '#006f7c' },
						{ label: 'POWER (20%)', value: avgPow, color: '#e85d04' },
						{ label: 'RESILIENCE (15%)', value: avgRes, color: '#9d4867' },
					] as bar}
						<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid rgba(56,56,50,0.08);">
							<span class="text-[9px] w-24 shrink-0" style="color: #828179;">{bar.label}</span>
							<div class="flex-1 h-4 relative" style="background: #f0ede3;">
								<div class="h-full" style="width: {bar.value}%; background: {bar.color};"></div>
							</div>
							<span class="text-[9px] w-8 text-right shrink-0 font-black" style="color: #383832;">{bar.value.toFixed(0)}</span>
						</div>
					{/each}
				</div>
			{/if}
			<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">AVG component scores across all sites</div>
		</div>
	</div>

	<!-- BCP Table -->
	<div class="mx-1 mb-6" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
		<div class="flex items-center justify-between px-3 py-1.5" style="background: #383832;">
			<span class="text-[10px] font-bold uppercase" style="color: #feffd6;">BCP SCORES TABLE</span>
			<button onclick={() => downloadExcel(sortedScores, 'BCP Scores', { statusColumns: ['grade'] })}
				class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
				style="color: #00fc40;">
				<span class="material-symbols-outlined text-sm">download</span> EXCEL
			</button>
		</div>
		<div class="overflow-auto" style="max-height: 500px;">
			<table class="w-full text-xs" style="border-collapse: collapse;">
				<thead class="sticky top-0 z-10">
					<tr style="background: #ebe8dd;">
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">SITE</th>
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832; color: #65655e;">CODE</th>
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">SECTOR</th>
						<th class="px-2 py-1.5 text-center font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">GRADE</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">SCORE</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">FUEL</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">COVERAGE</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">POWER</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">RESILIENCE</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">BUFFER</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">KVA</th>
					</tr>
				</thead>
				<tbody>
					{#each sortedScores as row, i}
						<tr style="background: {i % 2 === 0 ? '#ffffff' : '#f6f4e9'};">
							<td class="px-2 py-1 font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{row.site_id ?? ''}</td>
							<td class="px-2 py-1 font-mono text-[11px]" style="border-bottom: 1px solid #ddd; color: #65655e;">{row.site_code ?? ''}</td>
							<td class="px-2 py-1 text-[11px]" style="border-bottom: 1px solid #ddd;">{row.sector_id ?? ''}</td>
							<td class="px-2 py-1 text-center" style="border-bottom: 1px solid #ddd;">
								<span class="inline-block px-2 py-0.5 font-black text-[10px] uppercase" style="background: {gradeColors[row.grade] ?? '#383832'}; color: #feffd6;">
									{row.grade ?? ''}
								</span>
							</td>
							<td class="px-2 py-1 text-right font-mono text-[11px] font-bold" style="border-bottom: 1px solid #ddd;">{fmtDec(row.bcp_score, 0)}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{fmtDec(row.fuel_score, 0)}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{fmtDec(row.coverage_score, 0)}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{fmtDec(row.power_score, 0)}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{fmtDec(row.resilience_score, 0)}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{fmtDec(row.days_of_buffer, 1)}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{fmt(row.total_kva)}</td>
						</tr>
					{/each}
					{#if fScores.length === 0}
						<tr><td colspan="11" class="text-center py-6 font-bold uppercase text-[10px] opacity-50">NO BCP DATA</td></tr>
					{/if}
				</tbody>
			</table>
		</div>
		<!-- BCP column explanation -->
		<div class="px-4 py-3" style="background: #f6f4e9; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">WHAT EACH COLUMN MEANS</div>
			<table class="w-full text-[10px]" style="border-collapse: collapse;">
				<tbody>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832; width: 110px;">GRADE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Overall preparedness rating. <span class="font-bold" style="color: #007518;">A = Resilient</span> (ready for long outages), <span class="font-bold" style="color: #006f7c;">B = Adequate</span>, <span class="font-bold" style="color: #ff9d00;">C = At Risk</span>, <span class="font-bold" style="color: #be2d06;">D/F = Vulnerable/Critical</span> (needs immediate action)</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e; width: 220px;">Weighted composite of 4 scores below</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">SCORE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Overall BCP score from 0&ndash;100. Higher is better. This is the number that determines the grade</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Fuel (35%) + Coverage (30%) + Power (20%) + Resilience (15%)</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">FUEL</td>
						<td class="py-1.5 px-2" style="color: #383832;">How many days of fuel reserve does this site have? More days = higher score</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Based on buffer days (tank &divide; daily burn). 7+ days = full score</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">COVERAGE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Can the generators actually cover the blackout hours? High coverage = generators run enough to keep the site powered</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Generator run hours &divide; blackout hours. 100% = fully covered</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">POWER</td>
						<td class="py-1.5 px-2" style="color: #383832;">Is the generator big enough for the site? Larger KVA = more electrical capacity</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Based on total KVA capacity of all generators at site</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">RESILIENCE</td>
						<td class="py-1.5 px-2" style="color: #383832;">How consistent is the site? Sites with stable, predictable fuel usage score higher than erratic ones</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Based on usage variance and data completeness</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">BUFFER</td>
						<td class="py-1.5 px-2" style="color: #383832;">Days of fuel remaining at current burn rate &mdash; same as DAYS LEFT in stockout forecast</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Tank balance &divide; average daily fuel consumption</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">KVA</td>
						<td class="py-1.5 px-2" style="color: #383832;">Total generator power capacity in kilovolt-amperes. Bigger number = can power more equipment</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Sum of all generator KVA ratings at this site</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div class="px-4 py-2.5" style="background: white; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-1.5" style="color: #383832;">HOW GRADES ARE CALCULATED</div>
			<div class="text-[10px] leading-relaxed" style="color: #65655e;">
				Each site gets a score from 0&ndash;100 based on four weighted factors: <span class="font-bold" style="color: #383832;">Fuel Reserve (35%)</span> &mdash; how many days of diesel remain, <span class="font-bold" style="color: #383832;">Generator Coverage (30%)</span> &mdash; can generators cover blackout hours, <span class="font-bold" style="color: #383832;">Power Capacity (20%)</span> &mdash; is KVA sufficient, <span class="font-bold" style="color: #383832;">Operational Resilience (15%)</span> &mdash; is usage consistent. The score maps to a letter grade: A (&ge;80), B (60&ndash;79), C (40&ndash;59), D (20&ndash;39), F (&lt;20). Focus on D/F sites first &mdash; they are most vulnerable to power disruptions.
			</div>
		</div>
	</div>

	<!-- ═══════ SECTION 4: ACTIVE ALERTS ═══════ -->
	<div id="risk-alerts" class="scroll-mt-36 px-4 py-3 mb-3 mt-6" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">notifications_active</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 3: ACTIVE ALERTS</div>
				<div class="text-[10px] opacity-75">All system alerts sorted by severity and time</div>
			</div>
		</div>
		<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? What requires immediate attention right now?</div>
	</div>

	<!-- Alert KPIs (Overview chart style) -->
	<div class="grid grid-cols-1 sm:grid-cols-2 gap-4 px-1 mb-3">
		<!-- SEVERITY BREAKDOWN -->
		<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
				<span class="text-[11px] font-black uppercase">ALERT SEVERITY</span>
				<span class="text-[10px] font-bold">{fAlerts.length} TOTAL</span>
				<InfoTip {...KPI.risk.alertSeverity} />
			</div>
			<div class="flex">
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #be2d06;">{criticalCount}</div>
					<div class="text-[9px] font-bold" style="color: #be2d06;">CRITICAL</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #ff9d00;">{warningCount}</div>
					<div class="text-[9px] font-bold" style="color: #ff9d00;">WARNING</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1;">
					<div class="text-2xl font-black" style="color: #65655e;">{infoCount}</div>
					<div class="text-[9px] font-bold" style="color: #65655e;">INFO</div>
				</div>
			</div>
			<div style="border-top: 1px solid #ebe8dd;">
				{#each [
					{ label: 'CRITICAL', count: criticalCount, color: '#be2d06' },
					{ label: 'WARNING', count: warningCount, color: '#ff9d00' },
					{ label: 'INFO', count: infoCount, color: '#65655e' },
				] as bar}
					<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid rgba(56,56,50,0.08);">
						<span class="text-[9px] w-16 shrink-0 font-bold" style="color: {bar.color};">{bar.label}</span>
						<div class="flex-1 h-4 relative" style="background: #f0ede3;">
							<div class="h-full" style="width: {fAlerts.length > 0 ? (bar.count / fAlerts.length * 100) : 0}%; background: {bar.color};"></div>
						</div>
						<span class="text-[9px] w-6 text-right shrink-0 font-black" style="color: #383832;">{bar.count}</span>
					</div>
				{/each}
			</div>
			<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">11 conditions checked per upload</div>
		</div>
		<!-- ALERT TYPE BREAKDOWN -->
		<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
				<span class="text-[11px] font-black uppercase">ALERT TYPES</span>
			</div>
			<div style="max-height: 180px; overflow-y: auto;">
				{#each alertTypeCounts() as [type, count]}
					<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid rgba(56,56,50,0.08);">
						<span class="text-[9px] w-28 shrink-0 font-mono uppercase" style="color: #828179; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{type}</span>
						<div class="flex-1 h-4 relative" style="background: #f0ede3;">
							<div class="h-full" style="width: {fAlerts.length > 0 ? (count / fAlerts.length * 100) : 0}%; background: #383832;"></div>
						</div>
						<span class="text-[9px] w-6 text-right shrink-0 font-black" style="color: #383832;">{count}</span>
					</div>
				{/each}
			</div>
			<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">COUNT(alert_type)</div>
		</div>
	</div>

	<!-- Alerts Table -->
	<div class="mx-1 mb-6" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
		<div class="flex items-center justify-between px-3 py-1.5" style="background: #383832;">
			<span class="text-[10px] font-bold uppercase" style="color: #feffd6;">ALERTS TABLE</span>
			<button onclick={() => downloadExcel(sortedAlerts, 'Active Alerts', { statusColumns: ['severity'] })}
				class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
				style="color: #00fc40;">
				<span class="material-symbols-outlined text-sm">download</span> EXCEL
			</button>
		</div>
		<div class="overflow-auto" style="max-height: 500px;">
			<table class="w-full text-xs" style="border-collapse: collapse;">
				<thead class="sticky top-0 z-10">
					<tr style="background: #ebe8dd;">
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">SEVERITY</th>
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">TYPE</th>
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">SITE</th>
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832; color: #65655e;">CODE</th>
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">MESSAGE</th>
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">TIMESTAMP</th>
					</tr>
				</thead>
				<tbody>
					{#each sortedAlerts as row, i}
						{@const sev = (row.severity || '').toUpperCase()}
						<tr style="background: {i % 2 === 0 ? '#ffffff' : '#f6f4e9'};">
							<td class="px-2 py-1" style="border-bottom: 1px solid #ddd;">
								<span class="inline-block px-2 py-0.5 font-black text-[10px] uppercase whitespace-nowrap" style="background: {severityColors[sev] ?? '#383832'}; color: {sev === 'WARNING' ? '#383832' : '#feffd6'};">
									{sev}
								</span>
							</td>
							<td class="px-2 py-1 font-mono text-[11px] uppercase" style="border-bottom: 1px solid #ddd;">{row.alert_type ?? ''}</td>
							<td class="px-2 py-1 font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{row.site_id ?? ''}</td>
							<td class="px-2 py-1 font-mono text-[11px]" style="border-bottom: 1px solid #ddd; color: #65655e;">{row.site_code ?? ''}</td>
							<td class="px-2 py-1 text-[11px]" style="border-bottom: 1px solid #ddd;" title={row.message ?? ''}>{truncate(row.message ?? '')}</td>
							<td class="px-2 py-1 font-mono text-[10px] whitespace-nowrap" style="border-bottom: 1px solid #ddd;">{formatTimestamp(row.created_at)}</td>
						</tr>
					{/each}
					{#if fAlerts.length === 0}
						<tr><td colspan="6" class="text-center py-6 font-bold uppercase text-[10px] opacity-50">NO ACTIVE ALERTS</td></tr>
					{/if}
				</tbody>
			</table>
		</div>
		<!-- Alert column explanation -->
		<div class="px-4 py-3" style="background: #f6f4e9; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">WHAT EACH COLUMN MEANS</div>
			<table class="w-full text-[10px]" style="border-collapse: collapse;">
				<tbody>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832; width: 110px;">SEVERITY</td>
						<td class="py-1.5 px-2" style="color: #383832;"><span class="font-bold" style="color: #be2d06;">CRITICAL</span> = needs immediate action (fuel running out, generator failing). <span class="font-bold" style="color: #ff9d00;">WARNING</span> = needs attention soon. <span class="font-bold" style="color: #65655e;">INFO</span> = for awareness only, no action needed</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e; width: 220px;">Based on threshold rules per alert type</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">TYPE</td>
						<td class="py-1.5 px-2" style="color: #383832;">What kind of problem: LOW_BUFFER (fuel running low), HIGH_BLACKOUT (long power outages), PRICE_SPIKE (diesel price jumped), MISSING_DATA (site stopped reporting), EFFICIENCY (unusual fuel consumption)</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">11 alert types checked automatically</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">MESSAGE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Human-readable description of what triggered the alert, including specific numbers (e.g., "Buffer at 1.2 days, below 3-day threshold")</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Auto-generated from alert conditions</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">TIMESTAMP</td>
						<td class="py-1.5 px-2" style="color: #383832;">When the alert was created &mdash; recent alerts are more urgent than old ones</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Auto-generated when condition is detected</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div class="px-4 py-2.5" style="background: white; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-1.5" style="color: #383832;">HOW ALERTS ARE GENERATED</div>
			<div class="text-[10px] leading-relaxed" style="color: #65655e;">
				The system automatically checks <span class="font-bold" style="color: #383832;">11 conditions</span> every time data is uploaded:
				fuel buffer below 3 days (critical) or 7 days (warning),
				blackout hours above 8 hours,
				diesel price spike above 10% or 20%,
				generator idle for 3+ days,
				abnormal fuel efficiency (too high or too low consumption per hour),
				missing data for 2+ days,
				sector-level low buffer,
				predicted stockout within 5 days,
				and energy cost exceeding sales thresholds.
				<span class="font-bold" style="color: #383832;">Action:</span> Start with CRITICAL alerts &mdash; these need same-day response. WARNING alerts should be addressed within 1&ndash;2 days.
			</div>
		</div>
	</div>

	<!-- ═══════ SECTION 5: BREAK-EVEN ANALYSIS ═══════ -->
	{#if fBreakeven.length > 0}
		<div id="risk-breakeven" class="scroll-mt-36 px-4 py-3 mb-3 mt-6" style="background: #383832; color: #feffd6;">
			<div class="flex items-center gap-3">
				<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">account_balance</span>
				<div>
					<div class="font-black uppercase text-sm">CHAPTER 4: BREAK-EVEN ANALYSIS</div>
					<div class="text-[10px] opacity-75">Fuel cost vs revenue economics per site</div>
				</div>
			</div>
			<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Is the fuel cost justified by site revenue?</div>
		</div>

		<div class="mx-1 mb-6" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<div class="flex items-center justify-between px-3 py-1.5" style="background: #383832;">
				<span class="text-[10px] font-bold uppercase" style="color: #feffd6;">BREAK-EVEN TABLE</span>
				<button onclick={() => downloadExcel(fBreakeven, 'Break-Even Analysis')}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
					style="color: #00fc40;">
					<span class="material-symbols-outlined text-sm">download</span> EXCEL
				</button>
				<InfoTip {...KPI.risk.breakEven} />
			</div>
			<div class="overflow-auto" style="max-height: 500px;">
				<table class="w-full text-xs" style="border-collapse: collapse;">
					<thead class="sticky top-0 z-10">
						<tr style="background: #ebe8dd;">
							<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">SITE</th>
							<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832; color: #65655e;">CODE</th>
							<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">SECTOR</th>
							<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">AVG FUEL/DAY</th>
							<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">AVG SALES</th>
							<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">DAILY FUEL COST</th>
							<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">DIESEL %</th>
						</tr>
					</thead>
					<tbody>
						{#each fBreakeven as row, i}
							<tr style="background: {i % 2 === 0 ? '#ffffff' : '#f6f4e9'};">
								<td class="px-2 py-1 font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{row.site_id ?? ''}</td>
								<td class="px-2 py-1 font-mono text-[11px]" style="border-bottom: 1px solid #ddd; color: #65655e;">{row.site_code ?? ''}</td>
								<td class="px-2 py-1 text-[11px]" style="border-bottom: 1px solid #ddd;">{row.sector_id ?? ''}</td>
								<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{fmtDec(row.avg_daily_fuel, 1)}</td>
								<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{fmt(row.avg_daily_sales)}</td>
								<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{fmt(row.daily_fuel_cost)}</td>
								<td class="px-2 py-1 text-right font-mono text-[11px] font-bold" style="border-bottom: 1px solid #ddd; color: {(row.diesel_pct ?? 0) > 15 ? '#be2d06' : (row.diesel_pct ?? 0) > 10 ? '#ff9d00' : '#007518'};">
									{fmtDec(row.diesel_pct, 1)}%
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
		<!-- Break-even column explanation -->
		<div class="px-4 py-3" style="background: #f6f4e9; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">WHAT EACH COLUMN MEANS</div>
			<table class="w-full text-[10px]" style="border-collapse: collapse;">
				<tbody>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832; width: 120px;">AVG FUEL/DAY</td>
						<td class="py-1.5 px-2" style="color: #383832;">Average liters of diesel this site consumes per day. Higher number = more expensive to operate</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e; width: 220px;">AVG(total_daily_used) across all dates</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">AVG SALES</td>
						<td class="py-1.5 px-2" style="color: #383832;">Average daily sales revenue (MMK) for this site. This is what the store earns &mdash; fuel cost should be a small fraction of this</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">AVG(sales_amt) from daily_sales</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">DAILY FUEL COST</td>
						<td class="py-1.5 px-2" style="color: #383832;">How much this site spends on diesel per day in MMK. This is what you are paying to keep the generator running</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">AVG FUEL/DAY &times; latest diesel price per liter</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">DIESEL %</td>
						<td class="py-1.5 px-2" style="color: #383832;">What percentage of sales revenue goes to diesel. <span class="font-bold" style="color: #007518;">&lt;5% = healthy</span> (fuel cost is manageable), <span class="font-bold" style="color: #ff9d00;">5&ndash;15% = monitor</span>, <span class="font-bold" style="color: #be2d06;">&gt;15% = critical</span> (fuel is eating into profits &mdash; consider reducing hours)</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">(Daily Fuel Cost &divide; Avg Sales) &times; 100</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div class="px-4 py-2.5" style="background: white; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-1.5" style="color: #383832;">HOW TO USE THIS TABLE</div>
			<div class="text-[10px] leading-relaxed" style="color: #65655e;">
				This table answers: <span class="font-bold" style="color: #383832;">"Is it worth keeping this store open during power outages?"</span>
				If diesel cost is a tiny fraction of sales (&lt;5%), running the generator makes financial sense &mdash; the store earns far more than it spends on fuel.
				If diesel % is high (&gt;15%), the store is spending too much on fuel relative to revenue. Consider:
				<span class="font-bold" style="color: #383832;">reducing generator hours</span> (run only during peak sales hours),
				<span class="font-bold" style="color: #383832;">sharing a generator</span> with a nearby site, or
				<span class="font-bold" style="color: #383832;">temporarily closing</span> during extended blackouts (&gt;30% = losing money on fuel alone).
				Sort by DIESEL % descending to find the most expensive sites first.
			</div>
		</div>
	{/if}

</div>

<!-- Formula Reference -->
<div style="border-top: 2px solid #383832; margin-top: 1.5rem;">
	<div class="px-4 py-2 flex items-center gap-2" style="background: #383832; color: #feffd6;">
		<span class="material-symbols-outlined text-sm" style="color: #00fc40;">functions</span>
		<span class="text-[11px] font-black uppercase">FORMULA REFERENCE</span>
	</div>
	<div class="overflow-x-auto">
		<table class="w-full text-[10px]" style="border-collapse: collapse;">
			<thead>
				<tr style="background: #ebe8dd;">
					<th class="py-1.5 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832; width: 160px;">METRIC</th>
					<th class="py-1.5 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">FORMULA</th>
					<th class="py-1.5 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">SOURCE</th>
				</tr>
			</thead>
			<tbody>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;">
					<td class="py-1.5 px-3 font-bold" style="color: #be2d06;">DAYS UNTIL STOCKOUT</td>
					<td class="py-1.5 px-3 font-mono" style="color: #383832;">current_tank ÷ smoothed_daily_consumption</td>
					<td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">buffer_predictor</code></td>
				</tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
					<td class="py-1.5 px-3 font-bold" style="color: #ff9d00;">PROJECTED DATE</td>
					<td class="py-1.5 px-3 font-mono" style="color: #383832;">today + days_until_stockout</td>
					<td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">derived</code></td>
				</tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;">
					<td class="py-1.5 px-3 font-bold" style="color: #383832;">TREND</td>
					<td class="py-1.5 px-3 font-mono" style="color: #383832;">exponential smoothing of daily consumption (increasing/decreasing/stable)</td>
					<td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">buffer_predictor</code></td>
				</tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
					<td class="py-1.5 px-3 font-bold" style="color: #65655e;">CONFIDENCE</td>
					<td class="py-1.5 px-3 font-mono" style="color: #383832;">based on data_points count (&gt;=7 high, &gt;=3 medium, else low)</td>
					<td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">buffer_predictor</code></td>
				</tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;">
					<td class="py-1.5 px-3 font-bold" style="color: #383832;">BCP SCORE</td>
					<td class="py-1.5 px-3 font-mono" style="color: #383832;">weighted composite (fuel 30% + coverage 25% + power 25% + resilience 20%)</td>
					<td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">bcp_engine</code></td>
				</tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
					<td class="py-1.5 px-3 font-bold" style="color: #9d4867;">BREAK-EVEN</td>
					<td class="py-1.5 px-3 font-mono" style="color: #383832;">daily_fuel_cost ÷ daily_sales × 100 (diesel % of revenue)</td>
					<td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">energy_cost</code></td>
				</tr>
			</tbody>
		</table>
	</div>
</div>
