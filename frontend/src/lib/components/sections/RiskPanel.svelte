<script lang="ts">
	import { api, downloadExcel } from '$lib/api';
	import { onMount } from 'svelte';
	import AiInsightPanel from '$lib/components/AiInsightPanel.svelte';

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

	// Derived data
	const sortedForecast = $derived([...forecast].sort((a, b) => (a.days_until_stockout ?? 999) - (b.days_until_stockout ?? 999)));
	const sortedScores = $derived([...scores].sort((a, b) => (a.bcp_score ?? 0) - (b.bcp_score ?? 0)));
	const sortedAlerts = $derived(
		[...alerts].sort((a, b) => {
			const ai = severityOrder.indexOf((a.severity || '').toUpperCase());
			const bi = severityOrder.indexOf((b.severity || '').toUpperCase());
			const ao = ai === -1 ? 99 : ai;
			const bo = bi === -1 ? 99 : bi;
			if (ao !== bo) return ao - bo;
			return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
		})
	);

	// KPIs
	const stockoutRisk = $derived(forecast.filter((f) => (f.days_until_stockout ?? 999) <= 7).length);
	const avgDaysToStockout = $derived(
		forecast.length > 0
			? (forecast.reduce((s, f) => s + (f.days_until_stockout ?? 0), 0) / forecast.length).toFixed(1)
			: '-'
	);
	const mostUrgent = $derived(sortedForecast.length > 0 ? sortedForecast[0] : null);

	const gradeA = $derived(scores.filter((s) => s.grade === 'A').length);
	const gradeB = $derived(scores.filter((s) => s.grade === 'B').length);
	const gradeC = $derived(scores.filter((s) => s.grade === 'C').length);
	const gradeD = $derived(scores.filter((s) => s.grade === 'D' || s.grade === 'F').length);
	const avgScore = $derived(
		scores.length > 0
			? (scores.reduce((s, r) => s + (r.bcp_score ?? 0), 0) / scores.length).toFixed(0)
			: '-'
	);
	const avgGrade = $derived(
		scores.length > 0
			? (() => {
					const a = scores.reduce((s, r) => s + (r.bcp_score ?? 0), 0) / scores.length;
					if (a >= 80) return 'A';
					if (a >= 65) return 'B';
					if (a >= 50) return 'C';
					if (a >= 35) return 'D';
					return 'F';
				})()
			: '-'
	);

	const criticalCount = $derived(alerts.filter((a) => (a.severity || '').toUpperCase() === 'CRITICAL').length);
	const warningCount = $derived(alerts.filter((a) => (a.severity || '').toUpperCase() === 'WARNING').length);
	const infoCount = $derived(alerts.filter((a) => (a.severity || '').toUpperCase() === 'INFO').length);

	// Alert type breakdown
	const alertTypeBreakdown = $derived(() => {
		const map: Record<string, { count: number; severity: string }> = {};
		for (const a of alerts) {
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
		if (scores.length > 0) {
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
		const tasks = [
			api.get('/bcp-scores').then((d: any) => { scores = Array.isArray(d) ? d : (d.scores || d.data || []); }).catch(() => {}),
			api.get('/alerts').then((d: any) => { alerts = Array.isArray(d) ? d : (d.alerts || d.data || []); }).catch(() => {}),
			api.get('/stockout-forecast').then((d: any) => { forecast = Array.isArray(d) ? d : (d.forecast || d.data || []); }).catch(() => {}),
			api.get('/break-even').then((d: any) => { breakeven = d?.sites || (Array.isArray(d) ? d : []); }).catch(() => {}),
		];
		await Promise.allSettled(tasks);
	}

	onMount(load);
</script>

<AiInsightPanel type="kpi" data={{ tab: 'risk', summary: 'Stockout forecast, BCP risk grades, active alerts, break-even analysis — which sites are at risk?' }} title="AI INSIGHT — RISK ANALYSIS" />

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

	<!-- Stockout KPIs -->
	<div class="grid grid-cols-3 gap-3 px-1 mb-3">
		<div class="p-3 text-center" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="text-2xl font-black" style="color: #be2d06;">{stockoutRisk}</div>
			<div class="text-[10px] font-bold uppercase mt-1" style="color: #383832;">SITES AT RISK (&le;7D)</div>
		</div>
		<div class="p-3 text-center" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="text-2xl font-black font-mono" style="color: #383832;">{avgDaysToStockout}</div>
			<div class="text-[10px] font-bold uppercase mt-1" style="color: #383832;">AVG DAYS TO STOCKOUT</div>
		</div>
		<div class="p-3 text-center" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="text-2xl font-black font-mono" style="color: {mostUrgent ? daysColor(mostUrgent.days_until_stockout) : '#383832'};">
				{mostUrgent ? mostUrgent.site_id : '-'}
			</div>
			<div class="text-[10px] font-bold uppercase mt-1" style="color: #383832;">MOST URGENT SITE</div>
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
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">SECTOR</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">TANK (L)</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">AVG BURN (L)</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">DAYS LEFT</th>
						<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">STOCKOUT DATE</th>
						<th class="px-2 py-1.5 text-center font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">TREND</th>
						<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">CONFIDENCE</th>
					</tr>
				</thead>
				<tbody>
					{#each sortedForecast as row, i}
						{@const dl = row.days_until_stockout ?? 999}
						<tr style="background: {i % 2 === 0 ? '#ffffff' : '#f6f4e9'};">
							<td class="px-2 py-1 font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{row.site_id ?? ''}</td>
							<td class="px-2 py-1 text-[11px]" style="border-bottom: 1px solid #ddd;">{row.sector_id ?? ''}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{fmt(row.current_balance)}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{fmtDec(row.smoothed_daily_used ?? row.avg_daily_used)}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px] font-black" style="border-bottom: 1px solid #ddd; color: {daysColor(dl)};">{fmtDec(dl, 1)}</td>
							<td class="px-2 py-1 font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{formatDate(row.projected_stockout_date)}</td>
							<td class="px-2 py-1 text-center text-base font-black" style="border-bottom: 1px solid #ddd;">{trendArrow(row.trend)}</td>
							<td class="px-2 py-1 text-right font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{row.confidence != null ? fmtDec(row.confidence, 0) + '%' : '-'}</td>
						</tr>
					{/each}
					{#if forecast.length === 0}
						<tr><td colspan="8" class="text-center py-6 font-bold uppercase text-[10px] opacity-50">NO FORECAST DATA</td></tr>
					{/if}
				</tbody>
			</table>
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

	<!-- BCP KPIs -->
	<div class="grid grid-cols-5 gap-3 px-1 mb-3">
		<div class="p-3 text-center" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="text-2xl font-black" style="color: #007518;">{gradeA}</div>
			<div class="text-[10px] font-bold uppercase mt-1" style="color: #007518;">GRADE A</div>
		</div>
		<div class="p-3 text-center" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="text-2xl font-black" style="color: #006f7c;">{gradeB}</div>
			<div class="text-[10px] font-bold uppercase mt-1" style="color: #006f7c;">GRADE B</div>
		</div>
		<div class="p-3 text-center" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="text-2xl font-black" style="color: #ff9d00;">{gradeC}</div>
			<div class="text-[10px] font-bold uppercase mt-1" style="color: #ff9d00;">GRADE C</div>
		</div>
		<div class="p-3 text-center" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="text-2xl font-black" style="color: #be2d06;">{gradeD}</div>
			<div class="text-[10px] font-bold uppercase mt-1" style="color: #be2d06;">GRADE D/F</div>
		</div>
		<div class="p-3 text-center" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="text-2xl font-black" style="color: #383832;">{avgScore}</div>
			<div class="text-[10px] font-bold uppercase mt-1" style="color: #383832;">AVG SCORE</div>
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
					{#if scores.length === 0}
						<tr><td colspan="10" class="text-center py-6 font-bold uppercase text-[10px] opacity-50">NO BCP DATA</td></tr>
					{/if}
				</tbody>
			</table>
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

	<!-- Alert KPIs -->
	<div class="grid grid-cols-3 gap-3 px-1 mb-3">
		<div class="p-3 text-center" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="text-2xl font-black" style="color: #be2d06;">{criticalCount}</div>
			<div class="text-[10px] font-bold uppercase mt-1" style="color: #be2d06;">CRITICAL</div>
		</div>
		<div class="p-3 text-center" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="text-2xl font-black" style="color: #ff9d00;">{warningCount}</div>
			<div class="text-[10px] font-bold uppercase mt-1" style="color: #ff9d00;">WARNING</div>
		</div>
		<div class="p-3 text-center" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="text-2xl font-black" style="color: #65655e;">{infoCount}</div>
			<div class="text-[10px] font-bold uppercase mt-1" style="color: #65655e;">INFO</div>
		</div>
	</div>

	<!-- Alert type breakdown -->
	{#if alerts.length > 0}
		<div class="flex flex-wrap gap-1.5 px-1 mb-3">
			{#each alertTypeBreakdown() as item}
				<span class="inline-block px-2 py-0.5 text-[10px] font-bold uppercase" style="background: {severityColors[item.severity] ?? '#65655e'}; color: {item.severity === 'WARNING' ? '#383832' : '#feffd6'};">
					{item.type}: {item.count}
				</span>
			{/each}
		</div>
	{/if}

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
							<td class="px-2 py-1 text-[11px]" style="border-bottom: 1px solid #ddd;" title={row.message ?? ''}>{truncate(row.message ?? '')}</td>
							<td class="px-2 py-1 font-mono text-[10px] whitespace-nowrap" style="border-bottom: 1px solid #ddd;">{formatTimestamp(row.created_at)}</td>
						</tr>
					{/each}
					{#if alerts.length === 0}
						<tr><td colspan="5" class="text-center py-6 font-bold uppercase text-[10px] opacity-50">NO ACTIVE ALERTS</td></tr>
					{/if}
				</tbody>
			</table>
		</div>
	</div>

	<!-- ═══════ SECTION 5: BREAK-EVEN ANALYSIS ═══════ -->
	{#if breakeven.length > 0}
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
				<button onclick={() => downloadExcel(breakeven, 'Break-Even Analysis')}
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
							<th class="px-2 py-1.5 text-left font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">SECTOR</th>
							<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">AVG FUEL/DAY</th>
							<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">AVG SALES</th>
							<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">DAILY FUEL COST</th>
							<th class="px-2 py-1.5 text-right font-black text-[10px] uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">DIESEL %</th>
						</tr>
					</thead>
					<tbody>
						{#each breakeven as row, i}
							<tr style="background: {i % 2 === 0 ? '#ffffff' : '#f6f4e9'};">
								<td class="px-2 py-1 font-mono text-[11px]" style="border-bottom: 1px solid #ddd;">{row.site_id ?? ''}</td>
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
