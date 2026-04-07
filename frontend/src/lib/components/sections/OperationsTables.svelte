<script lang="ts">
	import { onMount } from 'svelte';
	import { api, downloadExcel } from '$lib/api';
	import AiInsightPanel from '$lib/components/AiInsightPanel.svelte';

	let { sector = '' }: { sector?: string } = $props();

	let loading = $state(true);
	let modes: any[] = $state([]);
	let queue: any[] = $state([]);
	let scores: any[] = $state([]);
	let alerts: any[] = $state([]);

	function fmt(v: any) { if (!v) return '0'; if (v >= 1e6) return (v/1e6).toFixed(1)+'M'; if (v >= 1e3) return (v/1e3).toFixed(1)+'K'; return v.toLocaleString(); }

	async function load() {
		loading = true;
		try {
			const s = sector ? `?sector=${sector}` : '';
			[modes, queue, scores, alerts] = await Promise.all([
				api.get(`/operating-modes${s}`),
				api.get(`/delivery-queue${s}`),
				api.get('/bcp-scores'),
				api.get('/alerts'),
			]);
		} catch (e) { console.error(e); }
		loading = false;
	}

	onMount(load);
	$effect(() => { sector; load(); });
</script>

<AiInsightPanel type="kpi" data={{ tab: 'scores_alerts', summary: 'BCP scores and grades (A-F), active alerts (CRITICAL/WARNING/INFO), site resilience assessment' }} title="AI INSIGHT — SCORES & ALERTS" />

{#if !loading || scores.length > 0 || alerts.length > 0}

	<!-- ============================================================ -->
	<!-- SECTION 1: BCP GRADES -->
	<div id="ops-scores" class="scroll-mt-36 px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">shield</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 6: BCP SCORES & GRADES</div>
				<div class="text-[10px] opacity-75">Business Continuity Planning grades — fuel coverage, generator capacity, resilience.</div>
			</div>
		</div>
		<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which sites score best? Who needs improvement?</div>
	</div>
	{#if scores.length > 0}
		{@const sorted = [...scores].sort((a: any, b: any) => (b.bcp_score || 0) - (a.bcp_score || 0))}
		{@const gradeA = scores.filter((s: any) => s.grade === 'A').length}
		{@const gradeB = scores.filter((s: any) => s.grade === 'B').length}
		{@const gradeC = scores.filter((s: any) => s.grade === 'C').length}
		{@const gradeD = scores.filter((s: any) => s.grade === 'D').length}
		{@const avgScore = scores.length ? (scores.reduce((sum: number, s: any) => sum + (s.bcp_score || 0), 0) / scores.length).toFixed(1) : '0'}

		<div class="mb-2 flex items-center justify-between">
			<h2 class="text-lg font-black uppercase" style="color: #383832;">BCP Grades</h2>
			<button
				class="px-3 py-1 text-xs font-bold uppercase cursor-pointer"
				style="background: #383832; color: #feffd6; border: none;"
				onclick={() => downloadExcel(sorted, 'BCP_Grades')}
			>Download Excel</button>
		</div>

		<!-- KPI Cards -->
		<div class="grid grid-cols-5 gap-3 mb-4">
			<div class="p-3 text-center" style="background: white; border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832;">
				<div class="text-2xl font-black" style="color: #007518;">{gradeA}</div>
				<div class="text-xs font-bold" style="color: #383832;">GRADE A</div>
			</div>
			<div class="p-3 text-center" style="background: white; border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832;">
				<div class="text-2xl font-black" style="color: #006f7c;">{gradeB}</div>
				<div class="text-xs font-bold" style="color: #383832;">GRADE B</div>
			</div>
			<div class="p-3 text-center" style="background: white; border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832;">
				<div class="text-2xl font-black" style="color: #ff9d00;">{gradeC}</div>
				<div class="text-xs font-bold" style="color: #383832;">GRADE C</div>
			</div>
			<div class="p-3 text-center" style="background: white; border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832;">
				<div class="text-2xl font-black" style="color: #be2d06;">{gradeD}</div>
				<div class="text-xs font-bold" style="color: #383832;">GRADE D</div>
			</div>
			<div class="p-3 text-center" style="background: #383832; border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832;">
				<div class="text-2xl font-black" style="color: #feffd6;">AVG: {avgScore}</div>
				<div class="text-xs font-bold" style="color: #feffd6;">{scores.length} SITES</div>
			</div>
		</div>

		<!-- BCP Scores Table -->
		<div class="overflow-x-auto overflow-y-auto mb-8" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832; max-height: 500px;">
			<table class="w-full text-xs">
				<thead>
					<tr style="background: #383832; color: #feffd6;">
						<th class="px-3 py-2 text-left font-bold uppercase">Site</th>
						<th class="px-3 py-2 text-left font-bold uppercase">Sector</th>
						<th class="px-3 py-2 text-center font-bold uppercase">Grade</th>
						<th class="px-3 py-2 text-right font-bold uppercase font-mono">Score</th>
						<th class="px-3 py-2 text-right font-bold uppercase font-mono">Fuel Score</th>
						<th class="px-3 py-2 text-right font-bold uppercase font-mono">Coverage</th>
						<th class="px-3 py-2 text-right font-bold uppercase font-mono">Power</th>
						<th class="px-3 py-2 text-right font-bold uppercase font-mono">Resilience</th>
						<th class="px-3 py-2 text-right font-bold uppercase font-mono">Buffer</th>
						<th class="px-3 py-2 text-right font-bold uppercase font-mono">KVA</th>
					</tr>
				</thead>
				<tbody>
					{#each sorted as row, i}
						{@const gc = row.grade === 'A' ? '#007518' : row.grade === 'B' ? '#006f7c' : row.grade === 'C' ? '#ff9d00' : row.grade === 'D' ? '#f95630' : '#be2d06'}
						{@const gtc = row.grade === 'C' ? '#383832' : 'white'}
						<tr style="background: {i % 2 === 0 ? 'white' : '#f6f4e9'};">
							<td class="px-3 py-1.5 font-bold" style="color: #383832;">{row.site_id || '-'}</td>
							<td class="px-3 py-1.5" style="color: #65655e;">{row.sector_id || '-'}</td>
							<td class="px-3 py-1.5 text-center">
								<span class="inline-block px-2 py-0.5 text-xs font-black rounded-sm" style="background: {gc}; color: {gtc};">{row.grade || '-'}</span>
							</td>
							<td class="px-3 py-1.5 text-right font-mono font-bold" style="color: #383832;">{row.bcp_score != null ? row.bcp_score.toFixed(1) : '-'}</td>
							<td class="px-3 py-1.5 text-right font-mono" style="color: #65655e;">{row.fuel_score != null ? row.fuel_score.toFixed(1) : '-'}</td>
							<td class="px-3 py-1.5 text-right font-mono" style="color: #65655e;">{row.coverage_score != null ? row.coverage_score.toFixed(1) : '-'}</td>
							<td class="px-3 py-1.5 text-right font-mono" style="color: #65655e;">{row.power_score != null ? row.power_score.toFixed(1) : '-'}</td>
							<td class="px-3 py-1.5 text-right font-mono" style="color: #65655e;">{row.resilience_score != null ? row.resilience_score.toFixed(1) : '-'}</td>
							<td class="px-3 py-1.5 text-right font-mono" style="color: #65655e;">{row.days_of_buffer != null ? row.days_of_buffer.toFixed(1) : '-'}</td>
							<td class="px-3 py-1.5 text-right font-mono" style="color: #65655e;">{row.total_kva != null ? fmt(row.total_kva) : '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	<!-- ============================================================ -->
	<!-- SECTION 2: ACTIVE ALERTS -->
	<div id="ops-alerts" class="scroll-mt-36 px-4 py-3 mb-3 mt-6" style="background: #383832; color: #feffd6;">
		<div class="flex items-center gap-3">
			<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">notifications_active</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 7: ACTIVE ALERTS</div>
				<div class="text-[10px] opacity-75">Live alert feed — critical, warning, and info notifications.</div>
			</div>
		</div>
		<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? What needs immediate attention? Any new critical alerts?</div>
	</div>
	{#if alerts.length > 0}
		{@const critCount = alerts.filter((a: any) => a.severity === 'CRITICAL').length}
		{@const warnCount = alerts.filter((a: any) => a.severity === 'WARNING').length}
		{@const infoCount = alerts.filter((a: any) => a.severity !== 'CRITICAL' && a.severity !== 'WARNING').length}
		{@const sevOrder: Record<string, number> = { CRITICAL: 0, WARNING: 1, INFO: 2 }}
		{@const sortedAlerts = [...alerts]
			.sort((a: any, b: any) => {
				const sa = sevOrder[a.severity] ?? 3;
				const sb = sevOrder[b.severity] ?? 3;
				if (sa !== sb) return sa - sb;
				return (b.created_at || '').localeCompare(a.created_at || '');
			})
			.slice(0, 50)}
		{@const typeCounts = alerts.reduce((acc: Record<string, number>, a: any) => { acc[a.alert_type] = (acc[a.alert_type] || 0) + 1; return acc; }, {} as Record<string, number>)}

		<div class="mb-2 flex items-center justify-between">
			<h2 class="text-lg font-black uppercase" style="color: #383832;">Active Alerts</h2>
			<button
				class="px-3 py-1 text-xs font-bold uppercase cursor-pointer"
				style="background: #383832; color: #feffd6; border: none;"
				onclick={() => downloadExcel(sortedAlerts, 'Active_Alerts')}
			>Download Excel</button>
		</div>

		<!-- KPI Cards -->
		<div class="grid grid-cols-3 gap-3 mb-3">
			<div class="p-3 text-center" style="background: white; border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832;">
				<div class="text-2xl font-black" style="color: #be2d06;">{critCount}</div>
				<div class="text-xs font-bold" style="color: #383832;">CRITICAL</div>
			</div>
			<div class="p-3 text-center" style="background: white; border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832;">
				<div class="text-2xl font-black" style="color: #ff9d00;">{warnCount}</div>
				<div class="text-xs font-bold" style="color: #383832;">WARNING</div>
			</div>
			<div class="p-3 text-center" style="background: white; border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832;">
				<div class="text-2xl font-black" style="color: #65655e;">{infoCount}</div>
				<div class="text-xs font-bold" style="color: #383832;">INFO</div>
			</div>
		</div>

		<!-- Alert Type Breakdown -->
		<div class="flex flex-wrap gap-2 mb-4">
			{#each Object.entries(typeCounts) as [type, count]}
				<span class="inline-block px-2 py-1 text-xs font-bold" style="background: #ebe8dd; border: 1px solid #383832; color: #383832;">
					{type}: {count}
				</span>
			{/each}
		</div>

		<!-- Alerts Table -->
		<div class="overflow-x-auto overflow-y-auto mb-8" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832; max-height: 500px;">
			<table class="w-full text-xs">
				<thead>
					<tr style="background: #383832; color: #feffd6;">
						<th class="px-3 py-2 text-center font-bold uppercase">Severity</th>
						<th class="px-3 py-2 text-left font-bold uppercase">Type</th>
						<th class="px-3 py-2 text-left font-bold uppercase">Site</th>
						<th class="px-3 py-2 text-left font-bold uppercase">Message</th>
						<th class="px-3 py-2 text-right font-bold uppercase font-mono">Timestamp</th>
					</tr>
				</thead>
				<tbody>
					{#each sortedAlerts as row, i}
						{@const sc = row.severity === 'CRITICAL' ? '#be2d06' : row.severity === 'WARNING' ? '#ff9d00' : '#65655e'}
						{@const stc = row.severity === 'WARNING' ? '#383832' : 'white'}
						<tr style="background: {i % 2 === 0 ? 'white' : '#f6f4e9'};">
							<td class="px-3 py-1.5 text-center">
								<span class="inline-block px-2 py-0.5 text-xs font-black rounded-sm" style="background: {sc}; color: {stc};">{row.severity || '-'}</span>
							</td>
							<td class="px-3 py-1.5 font-bold" style="color: #383832;">{row.alert_type || '-'}</td>
							<td class="px-3 py-1.5" style="color: #65655e;">{row.site_id || '-'}</td>
							<td class="px-3 py-1.5" style="color: #383832;">{(row.message || '-').length > 80 ? (row.message || '').slice(0, 80) + '...' : (row.message || '-')}</td>
							<td class="px-3 py-1.5 text-right font-mono" style="color: #65655e;">{row.created_at || '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
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
			<thead>
				<tr style="background: #ebe8dd;">
					<th class="py-1.5 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832; width: 160px;">METRIC</th>
					<th class="py-1.5 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">FORMULA</th>
					<th class="py-1.5 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">SOURCE</th>
				</tr>
			</thead>
			<tbody>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;">
					<td class="py-1.5 px-3 font-bold" style="color: #383832;">BCP SCORE</td>
					<td class="py-1.5 px-3 font-mono" style="color: #383832;">weighted composite (fuel 30% + coverage 25% + power 25% + resilience 20%)</td>
					<td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">bcp_engine</code></td>
				</tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
					<td class="py-1.5 px-3 font-bold" style="color: #007518;">GRADE</td>
					<td class="py-1.5 px-3 font-mono" style="color: #383832;">A &gt;= 80, B &gt;= 65, C &gt;= 50, D &gt;= 35, F &lt; 35</td>
					<td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">bcp_engine</code></td>
				</tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;">
					<td class="py-1.5 px-3 font-bold" style="color: #e85d04;">FUEL SCORE</td>
					<td class="py-1.5 px-3 font-mono" style="color: #383832;">buffer_days normalized to 0-100</td>
					<td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">bcp_engine</code></td>
				</tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
					<td class="py-1.5 px-3 font-bold" style="color: #006f7c;">COVERAGE SCORE</td>
					<td class="py-1.5 px-3 font-mono" style="color: #383832;">% of sites with buffer &gt; 3 days</td>
					<td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">bcp_engine</code></td>
				</tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;">
					<td class="py-1.5 px-3 font-bold" style="color: #ff9d00;">POWER SCORE</td>
					<td class="py-1.5 px-3 font-mono" style="color: #383832;">total_kVA capacity adequacy</td>
					<td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">bcp_engine</code></td>
				</tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
					<td class="py-1.5 px-3 font-bold" style="color: #be2d06;">ALERT SEVERITY</td>
					<td class="py-1.5 px-3 font-mono" style="color: #383832;">CRITICAL = immediate action, WARNING = monitor, INFO = awareness</td>
					<td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">alert_engine</code></td>
				</tr>
			</tbody>
		</table>
	</div>
</div>
