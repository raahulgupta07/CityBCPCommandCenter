<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import Chart from '$lib/components/Chart.svelte';
	import { barChart, hbarChart, groupedBar } from '$lib/charts';
	import InfoTip from '$lib/components/InfoTip.svelte';
	import { KPI } from '$lib/kpi-definitions';

	let { dateFrom = '', dateTo = '', sector = '', siteType = 'All', sites = [] as string[] }: { dateFrom?: string; dateTo?: string; sector?: string; siteType?: string; sites?: string[] } = $props();

	let daily: any[] = $state([]);
	let fleet: any = $state({ dow_patterns: [], utilization: [], waste_scores: [] });
	let topGenHours: any[] = $state([]);
	let sectorHeatmap: any[] = $state([]);
	let loading = $state(true);

	async function load() {
		loading = true;
		const p = new URLSearchParams();
		if (dateFrom) p.set('date_from', dateFrom);
		if (dateTo) p.set('date_to', dateTo);
		if (sector) p.set('sector', sector);
		if (siteType !== 'All') p.set('site_type', siteType);
		[daily, fleet, topGenHours, sectorHeatmap] = await Promise.all([
			api.get(`/daily-summary?${p}`),
			api.get(`/operations/fleet-stats?${p}`),
			api.get(`/rankings/gen_hours?${p}&limit=15`).catch(() => []),
			api.get(`/sector-heatmap?${p}`).catch(() => []),
		]);
		loading = false;
	}

	onMount(load);

	// Site filtering
	const fDaily = $derived(sites.length > 0 ? daily.filter((r: any) => sites.includes(r.site_id)) : daily);
	const fWasteScores = $derived(sites.length > 0 ? fleet.waste_scores.filter((r: any) => sites.includes(r.site_id)) : fleet.waste_scores);
	const fUtilization = $derived(sites.length > 0 ? fleet.utilization.filter((r: any) => sites.includes(r.site_id)) : fleet.utilization);

	// ---------- LAST DAY BREAKDOWN ----------
	function lastDayData() {
		if (!fDaily.length) return null;
		const maxDate = fDaily.reduce((m: string, r: any) => r.date > m ? r.date : m, '');
		const rows = fDaily.filter((r: any) => r.date === maxDate);
		if (!rows.length) return null;

		// #33 Top Sites by Fuel Used
		const byFuel = [...rows].sort((a: any, b: any) => (b.total_daily_used || 0) - (a.total_daily_used || 0)).slice(0, 15);
		const fuelChart = hbarChart(
			byFuel.map((r: any) => r.site_id),
			byFuel.map((r: any) => Math.round(r.total_daily_used || 0)),
			{ title: 'TOP SITES BY FUEL USED — LAST DAY', colors: byFuel.map((r: any) => (r.total_daily_used || 0) > 100 ? '#be2d06' : '#007518') }
		);

		// #34 Gen Hours by Site
		const byGen = [...rows].sort((a: any, b: any) => (b.total_gen_run_hr || 0) - (a.total_gen_run_hr || 0)).slice(0, 15);
		const genChart = hbarChart(
			byGen.map((r: any) => r.site_id),
			byGen.map((r: any) => Math.round((r.total_gen_run_hr || 0) * 10) / 10),
			{ title: 'GEN HOURS BY SITE — LAST DAY', colors: byGen.map((r: any) => (r.total_gen_run_hr || 0) > 12 ? '#be2d06' : '#006f7c') }
		);

		// #35 Efficiency L/Hr by Site
		const withEff = rows
			.filter((r: any) => (r.total_gen_run_hr || 0) > 0)
			.map((r: any) => ({ ...r, eff: (r.total_daily_used || 0) / (r.total_gen_run_hr || 1) }))
			.sort((a: any, b: any) => b.eff - a.eff)
			.slice(0, 15);
		const effChart = hbarChart(
			withEff.map((r: any) => r.site_id),
			withEff.map((r: any) => Math.round(r.eff * 10) / 10),
			{ title: 'EFFICIENCY L/HR BY SITE — LAST DAY', colors: withEff.map((r: any) => r.eff > 30 ? '#be2d06' : r.eff > 20 ? '#ff9d00' : '#007518') }
		);

		return { maxDate, fuelChart, genChart, effChart, fuelCount: byFuel.length, genCount: byGen.length, effCount: withEff.length };
	}

	// Week-over-Week
	function wow() {
		if (!fDaily.length) return null;
		const dates = [...new Set(fDaily.map((r: any) => r.date))].sort();
		if (dates.length < 8) return null;
		const mid = dates.length - 7;
		const tw = fDaily.filter((r: any) => dates.indexOf(r.date) >= mid);
		const lw = fDaily.filter((r: any) => dates.indexOf(r.date) >= mid - 7 && dates.indexOf(r.date) < mid);
		const sum = (arr: any[], key: string) => arr.reduce((s: number, r: any) => s + (r[key] || 0), 0);
		const twFuel = sum(tw, 'total_daily_used'), lwFuel = sum(lw, 'total_daily_used');
		const twHrs = sum(tw, 'total_gen_run_hr'), lwHrs = sum(lw, 'total_gen_run_hr');
		const twTank = sum(tw, 'spare_tank_balance'), lwTank = sum(lw, 'spare_tank_balance');
		const twBurn = twFuel / 7, lwBurn = lwFuel / 7;
		const twBuf = twBurn > 0 ? twTank / twBurn : 0, lwBuf = lwBurn > 0 ? lwTank / lwBurn : 0;
		return [
			{ label: 'Fuel (L)', tw: twFuel, lw: lwFuel, good: 'low' },
			{ label: 'Gen Hours', tw: twHrs, lw: lwHrs, good: 'low' },
			{ label: 'Buffer Days', tw: twBuf, lw: lwBuf, good: 'high' },
			{ label: 'Burn/Day', tw: twBurn, lw: lwBurn, good: 'low' },
		];
	}

	function pct(tw: number, lw: number) { return lw > 0 ? ((tw - lw) / lw * 100) : 0; }
	function arrow(v: number) { return v > 0 ? '▲' : v < 0 ? '▼' : '→'; }
	function wowColor(v: number, good: string) {
		if (good === 'low') return v > 5 ? 'color: #be2d06' : v < -5 ? 'color: #007518' : 'color: #ff9d00';
		return v > 5 ? 'color: #007518' : v < -5 ? 'color: #be2d06' : 'color: #ff9d00';
	}
	function fmt(v: number) { return v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v.toFixed(v < 10 ? 1 : 0); }

	// Day of Week
	function dowData() {
		const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
		const buckets: Record<string, { fuel: number[]; hours: number[] }> = {};
		days.forEach(d => buckets[d] = { fuel: [], hours: [] });
		for (const r of fDaily) {
			const dow = new Date(r.date).getDay();
			const name = days[dow];
			buckets[name].fuel.push(r.total_daily_used || 0);
			buckets[name].hours.push(r.total_gen_run_hr || 0);
		}
		const order = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
		const avgFuel = order.map(d => { const a = buckets[d].fuel; return a.length ? Math.round(a.reduce((s,v) => s+v, 0) / a.length) : 0; });
		const avgHrs = order.map(d => { const a = buckets[d].hours; return a.length ? Math.round(a.reduce((s,v) => s+v, 0) / a.length * 10) / 10 : 0; });
		return { order, avgFuel, avgHrs };
	}

	// Recommendations
	function recs() {
		const r: { icon: string; color: string; text: string }[] = [];
		const crit = fDaily.filter((d: any) => (d.days_of_buffer || 99) < 3);
		if (crit.length > 0) {
			const sites = [...new Set(crit.map((c: any) => c.site_id))].slice(0, 5);
			r.push({ icon: '🔴', color: 'border-color: #be2d06', text: `${sites.length} sites have < 3 days diesel — send fuel: ${sites.join(', ')}` });
		}
		return r;
	}
</script>

{#if fDaily.length > 0 || !loading}
	<!-- Last Day Breakdown -->
	{@const ld = lastDayData()}
	{#if ld}
		<details class="mb-6" open>
			<summary class="cursor-pointer text-sm font-black uppercase px-4 py-2.5" style="background: #383832; color: #feffd6;">LAST DAY BREAKDOWN — {ld.maxDate}</summary>
			<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-3">
				<!-- #33 Top Sites by Fuel Used -->
				<Chart option={ld.fuelChart} height="{Math.max(280, ld.fuelCount * 26)}px" guide={{ formula: 'total_daily_used for each site on the latest date, sorted descending, top 15.', sources: [{ data: 'Daily Used', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'Filter max date, sort DESC' }], reading: [{ color: 'red', text: 'Long red bar = Heavy fuel consumer on this day' }, { color: 'green', text: 'Short green bar = Low fuel usage' }], explain: 'Shows which sites <b>burned the most fuel yesterday</b>. Target the top bars for efficiency audits.' }} />

				<!-- #34 Gen Hours by Site -->
				<Chart option={ld.genChart} height="{Math.max(280, ld.genCount * 26)}px" guide={{ formula: 'total_gen_run_hr for each site on the latest date, sorted descending, top 15.', sources: [{ data: 'Gen Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'Filter max date, sort DESC' }], reading: [{ color: 'red', text: 'Long red bar = Generator ran 12+ hours' }, { color: 'green', text: 'Teal bar = Moderate generator usage' }], explain: 'Shows which sites had the <b>longest generator run time yesterday</b>. Long bars mean severe blackouts at that site.' }} />

				<!-- #35 Efficiency L/Hr by Site -->
				<Chart option={ld.effChart} height="{Math.max(280, ld.effCount * 26)}px" guide={{ formula: 'total_daily_used ÷ total_gen_run_hr for each site on the latest date (sites with gen hours > 0).', sources: [{ data: 'Efficiency', file: 'Blackout Hr Excel', col: 'Daily Used ÷ Gen Run Hr', method: 'Compute ratio, sort DESC' }], reading: [{ color: 'red', text: 'Red bar > 30 L/Hr = Possible waste or theft' }, { color: 'amber', text: 'Amber 20-30 L/Hr = Monitor closely' }, { color: 'green', text: 'Green < 20 L/Hr = Normal range' }], explain: 'How many <b>liters each generator burns per hour</b>. Compare against the rated spec — high values mean fuel is being wasted.' }} />
			</div>
		</details>
	{/if}

	<!-- Week over Week -->
	{@const w = wow()}
	{#if w}
		<div style="background: #383832; color: #feffd6;" class="px-4 py-2.5 font-black text-sm uppercase mt-6 flex items-center gap-2">📅 WEEK OVER WEEK <span class="ml-auto"></span><InfoTip {...KPI.waste.weekOverWeek} /></div>
		<div class="flex flex-wrap gap-2 p-3 mb-6" style="background: #f6f4e9; border: 1px solid #383832; border-top: 0;">
			{#each w as m}
				{@const p = pct(m.tw, m.lw)}
				<div class="flex-1 min-w-[130px] p-3 text-center" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<div class="text-xs mb-1" style="color: #65655e;">{m.label}</div>
					<div class="text-xl font-extrabold" style="{wowColor(p, m.good)}">{arrow(p)} {Math.abs(p).toFixed(0)}%</div>
					<div class="text-[11px] mt-1" style="color: #65655e;">{fmt(m.tw)} vs {fmt(m.lw)}</div>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Day of Week -->
	{@const dow = dowData()}
	<details class="mb-6" open>
		<summary class="cursor-pointer text-sm font-black uppercase px-4 py-2.5" style="background: #383832; color: #feffd6;">📅 Day-of-Week Patterns</summary>
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
			<Chart option={barChart(dow.order, dow.avgFuel, { title: 'Avg Fuel Used (L) by Day', color: '#be2d06' })} height="280px" guide={{ formula: 'Average daily fuel (liters) grouped by day of week.', sources: [{ data: 'Fuel Used', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'AVG per DOW' }], reading: [{ color: 'green', text: '✅ Even bars = Consistent fuel use' }, { color: 'red', text: '🔴 Spike on a day = Pattern worth investigating' }], explain: 'Like checking which day you <b>spend the most on gas</b>. Spikes reveal weekly patterns.' }} />
			<Chart option={barChart(dow.order, dow.avgHrs, { title: 'Avg Gen Hours by Day', color: '#006f7c' })} height="280px" guide={{ formula: 'Average generator run hours grouped by day of week.', sources: [{ data: 'Gen Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'AVG per DOW' }], reading: [{ color: 'green', text: '✅ Even bars = Consistent blackout pattern' }, { color: 'red', text: '🔴 Tall bar = Worst blackout day' }], explain: 'Shows which days have the <b>longest blackouts</b>. Plan staffing and fuel deliveries around peaks.' }} />
		</div>
	</details>

	<!-- Recommendations -->
	{@const rc = recs()}
	{#if rc.length > 0}
		<div class="p-4 mb-6" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<div class="font-black text-sm uppercase mb-2" style="color: #383832;">RECOMMENDATIONS</div>
			{#each rc as r}
				<div class="border-l-4 pl-3 py-1 text-sm mb-1" style="border-color: #be2d06; color: #383832;">{r.icon} {r.text}</div>
			{/each}
		</div>
	{/if}

	<!-- Fleet Stats -->
	{#if fleet.dow_patterns.length > 0}
		{@const dowDays = fleet.dow_patterns.map((d: any) => d.dow)}
		<details class="mb-6" open>
			<summary class="cursor-pointer text-sm font-black uppercase px-4 py-2.5" style="background: #383832; color: #feffd6;">⚙️ Operations & Fleet</summary>
			<div class="mt-3 space-y-4">
				<!-- DOW patterns: Gen Hours + Blackout -->
				<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
					<Chart option={barChart(dowDays, fleet.dow_patterns.map((d: any) => Math.round(d.avg_fuel || 0)), { title: 'Avg Fuel by Day of Week', color: '#be2d06' })} height="260px" guide={{ formula: 'Average fuel liters per day-of-week across all sites.', sources: [{ data: 'Fuel', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'AVG per DOW' }], reading: [{ color: 'green', text: '✅ Even bars = Consistent' }, { color: 'red', text: '🔴 Spike = High-burn day' }], explain: 'Shows <b>which days burn the most fuel</b>. Plan deliveries before peak days.' }} />
					<Chart option={barChart(dowDays, fleet.dow_patterns.map((d: any) => Math.round((d.avg_gen_hr || 0) * 10) / 10), { title: 'Avg Gen Hours by Day of Week', color: '#006f7c' })} height="260px" guide={{ formula: 'Average generator run hours per day-of-week.', sources: [{ data: 'Gen Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'AVG per DOW' }], reading: [{ color: 'green', text: '✅ Even = Predictable schedule' }, { color: 'red', text: '🔴 Spike = Worst blackout day' }], explain: 'Like knowing <b>traffic is worst on Fridays</b> — plan generator maintenance around low days.' }} />
					<Chart option={barChart(dowDays, fleet.dow_patterns.map((d: any) => Math.round((d.avg_blackout || 0) * 10) / 10), { title: 'Avg Blackout Hr by Day of Week', color: '#ff9d00' })} height="260px" guide={{ formula: 'Average blackout hours per day-of-week.', sources: [{ data: 'Blackout', file: 'Blackout Hr Excel', col: 'Blackout Hr', method: 'AVG per DOW' }], reading: [{ color: 'green', text: '✅ Low bars = Good grid days' }, { color: 'red', text: '🔴 Tall bar = Worst power day' }], explain: 'Reveals <b>weekly power grid patterns</b>. Schedule critical operations on low-blackout days.' }} />
				</div>

				<!-- Generator Utilization -->
				{#if fUtilization.length > 0}
					<Chart option={hbarChart(
						fUtilization.map((u: any) => `${u.site_id} ${u.model_name || ''}`),
						fUtilization.map((u: any) => u.utilization_pct || 0),
						{ title: 'Generator Utilization %', colors: fUtilization.map((u: any) => (u.utilization_pct || 0) > 80 ? '#be2d06' : (u.utilization_pct || 0) > 50 ? '#ff9d00' : '#007518') }
					)} height="{Math.max(300, fUtilization.length * 24)}px" guide={{ formula: 'Active days ÷ Total reporting days × 100 = <b>utilization %</b>.', sources: [{ data: 'Gen Run Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'COUNT days > 0' }], reading: [{ color: 'red', text: '🔴 > 80% = Running almost daily — heavy blackout area' }, { color: 'green', text: '🟢 < 30% = Generator rarely needed' }], explain: 'Shows how often each generator <b>actually runs</b>. High % = frequent blackouts in that area.' }} />
				{/if}

				<!-- Waste/Theft Scores -->
				{#if fWasteScores.length > 0}
					<Chart option={hbarChart(
						fWasteScores.map((w: any) => w.site_id),
						fWasteScores.map((w: any) => w.waste_score || 0),
						{ title: 'Theft/Waste Probability Score', colors: fWasteScores.map((w: any) => (w.waste_score || 0) > 30 ? '#be2d06' : (w.waste_score || 0) > 15 ? '#ff9d00' : '#007518') }
					)} height="{Math.max(200, fWasteScores.length * 28)}px" guide={{ formula: '(Actual L/Hr ÷ Rated L/Hr − 1) × 100 = <b>waste score %</b>. Only sites with 3+ data points.', sources: [{ data: 'Efficiency', file: 'Blackout Hr Excel', col: 'Daily Used ÷ Gen Run Hr', method: 'AVG vs rated' }], reading: [{ color: 'red', text: '🔴 > 30% = Likely theft or major leak' }, { color: 'amber', text: '🟡 15-30% = Investigate maintenance' }, { color: 'green', text: '🟢 < 15% = Normal variation' }], explain: 'Compares <b>actual vs expected</b> fuel burn. A generator rated 20L/Hr burning 30L/Hr scores 50% — something is wrong.' }} />
				{/if}
			</div>
		</details>
	{/if}

	<!-- #59 Top 15 Sites by Gen Run Hours -->
	{#if topGenHours.length > 0}
		<Chart option={hbarChart(
			topGenHours.map((s: any) => s.site_id),
			topGenHours.map((s: any) => Math.round(s.gen_hours || s.total_gen_hr || 0)),
			{ title: 'Top 15 Sites by Gen Run Hours', colors: topGenHours.map((s: any) => (s.gen_hours || s.total_gen_hr || 0) > 100 ? '#be2d06' : '#006f7c') }
		)} height="{Math.max(300, topGenHours.length * 28)}px" guide={{ formula: 'SUM of generator run hours per site. Higher = more blackout exposure.', sources: [{ data: 'Gen Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'SUM per site' }], reading: [{ color: 'red', text: '🔴 Top bars = Most blackout-affected sites' }, { color: 'green', text: '🟢 Short bars = Light blackout exposure' }], explain: 'Sites with the <b>most generator hours</b> suffer the worst blackouts. These are the priority for fuel delivery.' }} />
	{/if}

	<!-- #39 Sector Comparison Scorecard -->
	{#if sectorHeatmap.length > 1}
		{@const metrics = ['Buffer', 'Efficiency', 'Low Fuel', 'Low Blackout', 'Low Diesel%']}
		{@const sColors: Record<string, string> = { CMHL: '#FF9800', CP: '#2196F3', CFC: '#4CAF50', PG: '#9C27B0' }}
		{@const maxBuf = Math.max(...sectorHeatmap.map((s: any) => s.buffer_days || 0), 1)}
		{@const maxEff = Math.max(...sectorHeatmap.map((s: any) => s.avg_fuel > 0 && s.avg_gen_hr > 0 ? s.avg_fuel / s.avg_gen_hr : 0), 1)}
		{@const maxFuel = Math.max(...sectorHeatmap.map((s: any) => s.avg_fuel || 0), 1)}
		{@const maxBO = Math.max(...sectorHeatmap.map((s: any) => s.blackout_hr || 0), 1)}
		{@const maxDP = Math.max(...sectorHeatmap.map((s: any) => s.diesel_pct || 0), 1)}
		<Chart option={groupedBar(metrics,
			sectorHeatmap.map((s: any) => ({
				name: s.sector_id,
				data: [
					Math.round((s.buffer_days || 0) / maxBuf * 100),
					Math.round((1 - (s.avg_fuel > 0 && s.avg_gen_hr > 0 ? (s.avg_fuel / s.avg_gen_hr) / maxEff : 0)) * 100),
					Math.round((1 - (s.avg_fuel || 0) / maxFuel) * 100),
					Math.round((1 - (s.blackout_hr || 0) / maxBO) * 100),
					Math.round((1 - (s.diesel_pct || 0) / maxDP) * 100),
				],
				color: sColors[s.sector_id] || '#6b7280'
			})),
			{ title: 'Sector Scores (0-100, higher = better)' }
		)} guide={{ formula: 'Each metric normalized 0-100. Buffer: higher = more fuel. Others: lower raw value = higher score (inverted).', sources: [{ data: 'All Metrics', file: 'All Sources', col: 'Buffer/Efficiency/Fuel/Blackout/Diesel%', method: 'Normalized 0-100' }], reading: [{ color: 'green', text: '✅ Tall bars = Good performance in that metric' }, { color: 'red', text: '🔴 Short bars = Weak area to improve' }], explain: 'Like a <b>school report card</b> for each sector. Higher bar = better grade. Find which sectors need help in which areas.' }} />
	{/if}

	<!-- CHAPTER 8: DAY OF WEEK PATTERNS -->
	<div id="ops-patterns" class="scroll-mt-36 px-4 py-3 mb-3 mt-6" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">date_range</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 8: WEEKLY PATTERNS</div>
				<div class="text-[10px] opacity-75">Day-of-week fuel and blackout patterns — which days burn the most?</div>
			</div>
		</div>
		<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Is Tuesday worse than Monday? Which day has lowest consumption?</div>
	</div>
	{#if fleet.dow_patterns.length > 0}
		{@const dowCats = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']}
		{@const dowSorted = dowCats.map(d => fleet.dow_patterns.find((p: any) => p.dow === d) || { avg_fuel: 0, avg_blackout: 0 })}
		{@const dowFuelVals = dowSorted.map((p: any) => Math.round((p.avg_fuel || 0) * 10) / 10)}
		{@const dowBlackoutVals = dowSorted.map((p: any) => Math.round((p.avg_blackout || 0) * 10) / 10)}
		<div class="mb-6">
			<div class="px-4 py-2.5 font-black text-sm uppercase" style="background: #383832; color: #feffd6;">DAY OF WEEK PATTERNS</div>
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
				<div class="h-[300px]">
					<Chart option={barChart(dowCats, dowFuelVals, { title: 'Avg Fuel Used by Day', color: '#383832' })} height="300px" />
				</div>
				<div class="h-[300px]">
					<Chart option={barChart(dowCats, dowBlackoutVals, { title: 'Avg Blackout Hr by Day', color: '#be2d06' })} height="300px" />
				</div>
			</div>
		</div>
	{/if}

	<!-- CHAPTER 9: WASTE / THEFT DETECTION -->
	<div id="ops-waste" class="scroll-mt-36 px-4 py-3 mb-3 mt-6" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">warning</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 9: WASTE & THEFT DETECTION</div>
				<div class="text-[10px] opacity-75">Sites burning more fuel than generator rating — possible waste or theft.</div>
			</div>
		</div>
		<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which sites have suspiciously high fuel consumption vs rated capacity?</div>
	</div>
	{#if fWasteScores.length > 0}
		{@const wasteRows = [...fWasteScores].sort((a: any, b: any) => (b.waste_score || 0) - (a.waste_score || 0))}
		<div class="mb-6">
			<div class="px-4 py-2.5 font-black text-sm uppercase flex items-center gap-2" style="background: #383832; color: #feffd6;">WASTE / THEFT DETECTION <span class="ml-auto"></span><InfoTip {...KPI.waste.wasteRatio} /></div>
			<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832; overflow-x: auto; overflow-y: auto; max-height: 500px;" class="mt-3">
				<table class="w-full text-xs">
					<thead>
						<tr style="background: #ebe8dd;">
							<th class="px-3 py-2 text-left font-black uppercase">SITE</th>
							<th class="px-3 py-2 text-left font-black uppercase" style="color: #65655e;">CODE</th>
							<th class="px-3 py-2 text-left font-black uppercase">SECTOR</th>
							<th class="px-3 py-2 text-right font-black uppercase font-mono">ACTUAL L/HR</th>
							<th class="px-3 py-2 text-right font-black uppercase font-mono">RATED L/HR</th>
							<th class="px-3 py-2 text-right font-black uppercase font-mono">WASTE RATIO</th>
							<th class="px-3 py-2 text-right font-black uppercase font-mono">WASTE SCORE</th>
						</tr>
					</thead>
					<tbody>
						{#each wasteRows as row, i}
							{@const wr = row.waste_ratio || 0}
							{@const wrColor = wr > 2 ? '#be2d06' : wr > 1.5 ? '#ff9d00' : '#007518'}
							<tr style="background: {i % 2 === 0 ? 'white' : '#f6f4e9'};">
								<td class="px-3 py-2 text-left">{row.site_id}</td>
								<td class="px-3 py-2 text-left font-mono" style="color: #65655e;">{row.site_code || ''}</td>
								<td class="px-3 py-2 text-left">{row.sector_id}</td>
								<td class="px-3 py-2 text-right font-mono">{(row.actual_lph || 0).toFixed(1)}</td>
								<td class="px-3 py-2 text-right font-mono">{(row.rated_lph || 0).toFixed(1)}</td>
								<td class="px-3 py-2 text-right font-mono font-bold" style="color: {wrColor};">{wr.toFixed(2)}</td>
								<td class="px-3 py-2 text-right font-mono font-bold">{(row.waste_score || 0).toFixed(1)}</td>
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
							<td class="py-1.5 px-2 font-bold" style="color: #383832;">SITE / CODE</td>
							<td class="py-1.5 px-2" style="color: #383832;">Site identifier and sector-store code</td>
							<td class="py-1.5 px-2 font-mono" style="color: #65655e;">From uploaded Excel data</td>
						</tr>
						<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
							<td class="py-1.5 px-2 font-bold" style="color: #383832;">SECTOR</td>
							<td class="py-1.5 px-2" style="color: #383832;">Business sector</td>
							<td class="py-1.5 px-2 font-mono" style="color: #65655e;">From uploaded Excel data</td>
						</tr>
						<tr style="border-bottom: 1px solid #ebe8dd;">
							<td class="py-1.5 px-2 font-bold" style="color: #383832;">ACTUAL L/HR</td>
							<td class="py-1.5 px-2" style="color: #383832;">How much fuel the generator actually consumed per hour</td>
							<td class="py-1.5 px-2 font-mono" style="color: #65655e;">total_daily_used &divide; total_gen_run_hr</td>
						</tr>
						<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
							<td class="py-1.5 px-2 font-bold" style="color: #383832;">RATED L/HR</td>
							<td class="py-1.5 px-2" style="color: #383832;">How much fuel the generator SHOULD consume per hour (manufacturer spec)</td>
							<td class="py-1.5 px-2 font-mono" style="color: #65655e;">From generator specifications</td>
						</tr>
						<tr style="border-bottom: 1px solid #ebe8dd;">
							<td class="py-1.5 px-2 font-bold" style="color: #383832;">WASTE RATIO</td>
							<td class="py-1.5 px-2" style="color: #383832;">Actual &divide; Rated. 1.0 = normal. <span class="font-bold" style="color: #ff9d00;">&gt;1.5 = wasteful</span>. <span class="font-bold" style="color: #be2d06;">&gt;2.0 = likely theft or major leak</span></td>
							<td class="py-1.5 px-2 font-mono" style="color: #65655e;">actual_lph &divide; rated_lph</td>
						</tr>
						<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
							<td class="py-1.5 px-2 font-bold" style="color: #383832;">WASTE SCORE</td>
							<td class="py-1.5 px-2" style="color: #383832;">Higher = worse. Score above 30 = needs investigation</td>
							<td class="py-1.5 px-2 font-mono" style="color: #65655e;">(waste_ratio &minus; 1) &times; 100</td>
						</tr>
					</tbody>
				</table>
			</div>
			<!-- How to use this table -->
			<div class="px-4 py-2.5" style="background: white; border-top: 1px solid #ebe8dd;">
				<div class="text-[10px] font-black uppercase mb-1" style="color: #383832;">HOW TO USE THIS TABLE</div>
				<div class="text-[10px] leading-relaxed" style="color: #65655e;">
					Sites with high waste ratios are consuming more fuel than expected. Possible causes: fuel theft, generator malfunction, fuel leaks, or incorrect tank readings. Investigate sites with WASTE RATIO above 1.5 &mdash; check physical tank levels, review security cameras, and inspect generator condition. A ratio above 2.0 is almost certainly theft or a serious mechanical problem.
				</div>
			</div>
		</div>
	{/if}
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
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #383832;">WEEK OVER WEEK</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">this_week_total &divide; last_week_total &times; 100 &minus; 100</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">daily_site_summary</code></td></tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #e85d04;">LAST DAY BREAKDOWN</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">per-sector SUM on latest date</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">daily_site_summary</code></td></tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #383832;">AVG FUEL BY DOW</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">AVG(daily_used) grouped by day_of_week</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">fleet-stats</code></td></tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #be2d06;">AVG BLACKOUT BY DOW</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">AVG(blackout_hr) grouped by day_of_week</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">fleet-stats</code></td></tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #be2d06;">WASTE RATIO</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">actual_L/hr &divide; rated_L/hr (&gt;2 = suspicious)</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">fleet-stats</code></td></tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #ff9d00;">WASTE SCORE</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">(waste_ratio &minus; 1) &times; 100 (higher = worse)</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">fleet-stats</code></td></tr>
			</tbody>
		</table>
	</div>
</div>
