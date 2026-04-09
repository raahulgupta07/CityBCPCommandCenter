<script lang="ts">
	import { api, downloadExcel } from '$lib/api';
	import InfoTip from '$lib/components/InfoTip.svelte';
	import { KPI } from '$lib/kpi-definitions';

	let { sector = '', siteType = 'All', sites = [] as string[] }: { sector?: string; siteType?: string; sites?: string[] } = $props();

	let loading = $state(true);
	let modes: any[] = $state([]);
	let queue: any[] = $state([]);
	let scores: any[] = $state([]);
	let alerts: any[] = $state([]);

	const filteredScores = $derived(sites.length > 0 ? scores.filter((r: any) => sites.includes(r.site_id)) : scores);
	const filteredAlerts = $derived(sites.length > 0 ? alerts.filter((r: any) => sites.includes(r.site_id)) : alerts);

	function fmt(v: any) { if (!v) return '0'; if (v >= 1e6) return (v/1e6).toFixed(1)+'M'; if (v >= 1e3) return (v/1e3).toFixed(1)+'K'; return v.toLocaleString(); }

	async function load() {
		loading = true;
		try {
			const s = sector ? `?sector=${sector}` : '';
			const tp = siteType !== 'All' ? `${s ? '&' : '?'}site_type=${siteType}` : '';
			[modes, queue, scores, alerts] = await Promise.all([
				api.get(`/operating-modes${s}${tp}`),
				api.get(`/delivery-queue${s}${tp}`),
				api.get(`/bcp-scores${s}${tp}`),
				api.get(`/alerts${s}${tp}`),
			]);
		} catch (e) { console.error(e); }
		loading = false;
	}

	$effect(() => { sector; siteType; load(); });
</script>

{#if !loading || filteredScores.length > 0 || filteredAlerts.length > 0}

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
	{#if filteredScores.length > 0}
		{@const sorted = [...filteredScores].sort((a: any, b: any) => (b.bcp_score || 0) - (a.bcp_score || 0))}
		{@const gradeA = filteredScores.filter((s: any) => s.grade === 'A').length}
		{@const gradeB = filteredScores.filter((s: any) => s.grade === 'B').length}
		{@const gradeC = filteredScores.filter((s: any) => s.grade === 'C').length}
		{@const gradeD = filteredScores.filter((s: any) => s.grade === 'D').length}
		{@const avgScore = filteredScores.length ? (filteredScores.reduce((sum: number, s: any) => sum + (s.bcp_score || 0), 0) / filteredScores.length).toFixed(1) : '0'}

		<!-- KPI Card (chart style) -->
		<div class="mb-3" style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
			<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
				<span class="text-[11px] font-black uppercase">GRADE DISTRIBUTION</span>
				<span class="text-[10px] font-bold">{filteredScores.length} SITES &mdash; AVG {avgScore}</span>
				<InfoTip {...KPI.risk.bcpGrades} />
			</div>
			<div class="flex">
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #007518;">{gradeA}</div>
					<div class="text-[9px] font-bold" style="color: #007518;">A</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #006f7c;">{gradeB}</div>
					<div class="text-[9px] font-bold" style="color: #006f7c;">B</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
					<div class="text-2xl font-black" style="color: #ff9d00;">{gradeC}</div>
					<div class="text-[9px] font-bold" style="color: #ff9d00;">C</div>
				</div>
				<div class="p-3 flex flex-col justify-center" style="flex: 1;">
					<div class="text-2xl font-black" style="color: #be2d06;">{gradeD}</div>
					<div class="text-[9px] font-bold" style="color: #be2d06;">D/F</div>
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
						<div class="flex-1 h-4" style="background: #f0ede3;">
							<div class="h-full" style="width: {filteredScores.length > 0 ? (bar.count / filteredScores.length * 100) : 0}%; background: {bar.color};"></div>
						</div>
						<span class="text-[9px] w-6 text-right shrink-0 font-black" style="color: #383832;">{bar.count}</span>
					</div>
				{/each}
			</div>
			<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">fuel(35%) + coverage(30%) + power(20%) + resilience(15%)</div>
		</div>

		<!-- BCP Scores Table -->
		<div class="overflow-x-auto overflow-y-auto mb-8" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832; max-height: 500px;">
			<table class="w-full text-xs">
				<thead>
					<tr style="background: #383832; color: #feffd6;">
						<th class="px-3 py-2 text-left font-bold uppercase">Site</th>
						<th class="px-3 py-2 text-left font-bold uppercase" style="color: #9ca3af;">Code</th>
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
							<td class="px-3 py-1.5 font-mono" style="color: #65655e;">{row.site_code || ''}</td>
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
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">GRADE</td>
						<td class="py-1.5 px-2" style="color: #383832;">A-F rating. <span class="font-bold" style="color: #007518;">A(&ge;80) = Resilient</span>, <span class="font-bold" style="color: #006f7c;">B(60-79) = Adequate</span>, <span class="font-bold" style="color: #ff9d00;">C(40-59) = At Risk</span>, <span class="font-bold" style="color: #f95630;">D(20-39) = Vulnerable</span>, <span class="font-bold" style="color: #be2d06;">F(&lt;20) = Critical</span></td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Based on overall BCP score thresholds</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">SCORE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Overall BCP score 0&ndash;100</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Weighted: Fuel 35% + Coverage 30% + Power 20% + Resilience 15%</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">FUEL SCORE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Fuel reserve adequacy</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Based on buffer days &mdash; 7+ days = full score</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">COVERAGE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Generator coverage of blackout hours</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">gen_hr &divide; blackout_hr</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">POWER</td>
						<td class="py-1.5 px-2" style="color: #383832;">Generator capacity adequacy</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Based on total KVA</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">RESILIENCE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Operational consistency &mdash; stable sites score higher</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Variance in daily metrics over time</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">BUFFER</td>
						<td class="py-1.5 px-2" style="color: #383832;">Days of fuel remaining at current burn rate</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Tank balance &divide; avg daily fuel used</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">KVA</td>
						<td class="py-1.5 px-2" style="color: #383832;">Total generator power capacity</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">SUM of all generator KVA ratings at site</td>
					</tr>
				</tbody>
			</table>
		</div>
		<!-- How to use this table -->
		<div class="px-4 py-2.5" style="background: white; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-1" style="color: #383832;">HOW TO USE THIS TABLE</div>
			<div class="text-[10px] leading-relaxed" style="color: #65655e;">
				Focus on D and F grade sites &mdash; they need immediate attention. Check which sub-score is lowest (Fuel, Coverage, Power, Resilience) to understand WHY a site scored poorly. A site with low FUEL score needs a delivery. A site with low COVERAGE needs its generator running more hours.
			</div>
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
	{#if filteredAlerts.length > 0}
		{@const critCount = filteredAlerts.filter((a: any) => a.severity === 'CRITICAL').length}
		{@const warnCount = filteredAlerts.filter((a: any) => a.severity === 'WARNING').length}
		{@const infoCount = filteredAlerts.filter((a: any) => a.severity !== 'CRITICAL' && a.severity !== 'WARNING').length}
		{@const sevOrder: Record<string, number> = { CRITICAL: 0, WARNING: 1, INFO: 2 }}
		{@const sortedAlerts = [...filteredAlerts]
			.sort((a: any, b: any) => {
				const sa = sevOrder[a.severity] ?? 3;
				const sb = sevOrder[b.severity] ?? 3;
				if (sa !== sb) return sa - sb;
				return (b.created_at || '').localeCompare(a.created_at || '');
			})
			.slice(0, 50)}
		{@const typeCounts = filteredAlerts.reduce((acc: Record<string, number>, a: any) => { acc[a.alert_type] = (acc[a.alert_type] || 0) + 1; return acc; }, {} as Record<string, number>)}

		<!-- KPI Card (chart style) -->
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-3">
			<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
				<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
					<span class="text-[11px] font-black uppercase">ALERT SEVERITY</span>
					<span class="text-[10px] font-bold">{filteredAlerts.length} TOTAL</span>
					<InfoTip {...KPI.risk.alertSeverity} />
				</div>
				<div class="flex">
					<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
						<div class="text-2xl font-black" style="color: #be2d06;">{critCount}</div>
						<div class="text-[9px] font-bold" style="color: #be2d06;">CRITICAL</div>
					</div>
					<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
						<div class="text-2xl font-black" style="color: #ff9d00;">{warnCount}</div>
						<div class="text-[9px] font-bold" style="color: #ff9d00;">WARNING</div>
					</div>
					<div class="p-3 flex flex-col justify-center" style="flex: 1;">
						<div class="text-2xl font-black" style="color: #65655e;">{infoCount}</div>
						<div class="text-[9px] font-bold" style="color: #65655e;">INFO</div>
					</div>
				</div>
				<div style="border-top: 1px solid #ebe8dd;">
					{#each [
						{ label: 'CRITICAL', count: critCount, color: '#be2d06' },
						{ label: 'WARNING', count: warnCount, color: '#ff9d00' },
						{ label: 'INFO', count: infoCount, color: '#65655e' },
					] as bar}
						<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid rgba(56,56,50,0.08);">
							<span class="text-[9px] w-16 shrink-0 font-bold" style="color: {bar.color};">{bar.label}</span>
							<div class="flex-1 h-4" style="background: #f0ede3;">
								<div class="h-full" style="width: {filteredAlerts.length > 0 ? (bar.count / filteredAlerts.length * 100) : 0}%; background: {bar.color};"></div>
							</div>
							<span class="text-[9px] w-6 text-right shrink-0 font-black" style="color: #383832;">{bar.count}</span>
						</div>
					{/each}
				</div>
				<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">11 conditions checked per upload</div>
			</div>
			<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
				<div class="px-3 py-1.5" style="background: #383832; color: #feffd6;">
					<span class="text-[11px] font-black uppercase">ALERT TYPES</span>
				</div>
				<div style="max-height: 200px; overflow-y: auto;">
					{#each Object.entries(typeCounts).sort((a, b) => (b[1] as number) - (a[1] as number)) as [type, count]}
						<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid rgba(56,56,50,0.08);">
							<span class="text-[9px] w-28 shrink-0 font-mono uppercase" style="color: #828179; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{type}</span>
							<div class="flex-1 h-4" style="background: #f0ede3;">
								<div class="h-full" style="width: {filteredAlerts.length > 0 ? ((count as number) / filteredAlerts.length * 100) : 0}%; background: #383832;"></div>
							</div>
							<span class="text-[9px] w-6 text-right shrink-0 font-black" style="color: #383832;">{count}</span>
						</div>
					{/each}
				</div>
				<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">COUNT(alert_type)</div>
			</div>
		</div>
		<div class="flex flex-wrap gap-2 mb-4 hidden">
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
						<th class="px-3 py-2 text-left font-bold uppercase" style="color: #9ca3af;">Code</th>
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
							<td class="px-3 py-1.5 font-mono" style="color: #65655e;">{row.site_code || ''}</td>
							<td class="px-3 py-1.5" style="color: #383832;">{(row.message || '-').length > 80 ? (row.message || '').slice(0, 80) + '...' : (row.message || '-')}</td>
							<td class="px-3 py-1.5 text-right font-mono" style="color: #65655e;">{row.created_at || '-'}</td>
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
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">SEVERITY</td>
						<td class="py-1.5 px-2" style="color: #383832;"><span class="font-bold" style="color: #be2d06;">CRITICAL</span> = act today (fuel running out, generator at risk). <span class="font-bold" style="color: #ff9d00;">WARNING</span> = act within 1&ndash;2 days. <span class="font-bold" style="color: #65655e;">INFO</span> = for awareness</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Rule-based thresholds in alert engine</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">TYPE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Alert category &mdash; LOW_BUFFER, HIGH_BLACKOUT, PRICE_SPIKE, MISSING_DATA, EFFICIENCY</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Categorized by the condition that triggered it</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">SITE / CODE</td>
						<td class="py-1.5 px-2" style="color: #383832;">Which site has the issue</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">From uploaded Excel data</td>
					</tr>
					<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">MESSAGE</td>
						<td class="py-1.5 px-2" style="color: #383832;">What happened and specific numbers</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Auto-generated description with actual values</td>
					</tr>
					<tr style="border-bottom: 1px solid #ebe8dd;">
						<td class="py-1.5 px-2 font-bold" style="color: #383832;">TIMESTAMP</td>
						<td class="py-1.5 px-2" style="color: #383832;">When the alert was detected</td>
						<td class="py-1.5 px-2 font-mono" style="color: #65655e;">Date and time the alert was created</td>
					</tr>
				</tbody>
			</table>
		</div>
		<!-- How to use this table -->
		<div class="px-4 py-2.5" style="background: white; border-top: 1px solid #ebe8dd;">
			<div class="text-[10px] font-black uppercase mb-1" style="color: #383832;">HOW TO USE THIS TABLE</div>
			<div class="text-[10px] leading-relaxed" style="color: #65655e;">
				Start with CRITICAL alerts &mdash; these need same-day response. The system checks 11 conditions automatically: low fuel buffer, high blackout hours, diesel price spikes, generator idle, abnormal efficiency, missing data, sector-level issues, predicted stockouts, and energy cost thresholds.
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
