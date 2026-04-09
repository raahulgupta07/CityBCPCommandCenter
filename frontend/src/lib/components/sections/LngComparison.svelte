<script lang="ts">
	import { api } from '$lib/api';
	import Chart from '$lib/components/Chart.svelte';
	import { groupedBar } from '$lib/charts';

	let { dateFrom = '', dateTo = '', siteType = 'All' }: { dateFrom?: string; dateTo?: string; siteType?: string } = $props();

	let data: any[] = $state([]);
	let loading = $state(true);

	async function load() {
		loading = true;
		const p = new URLSearchParams();
		if (dateFrom) p.set('date_from', dateFrom);
		if (dateTo) p.set('date_to', dateTo);
		try { data = await api.get(`/trends/lng-comparison?${p}`); }
		catch (e) { console.error(e); }
		loading = false;
	}

	$effect(() => { dateFrom; dateTo; load(); });

	function val(type: string, key: string): number {
		const r = data.find((d: any) => d.site_type === type);
		return r ? Math.round((r[key] || 0) * 100) / 100 : 0;
	}

	const cats = ['Gen Hours', 'Fuel Used (L)', 'Efficiency (L/Hr)', 'Buffer Days', 'Diesel Cost', 'Blackout Hr'];
	const keys = ['avg_gen_hr', 'avg_fuel', 'efficiency', 'avg_buffer', 'avg_cost', 'avg_blackout'];
</script>

{#if loading}
	<p class="text-sm" style="color: #65655e; py-4 text-center">Loading...</p>
{:else if data.length >= 2}
	<h2 class="text-lg font-black uppercase mt-6 mb-3 px-3 py-1" style="background: #383832; color: #feffd6;">REGULAR VS LNG COMPARISON</h2>
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
		{#each cats as cat, i}
			<Chart option={groupedBar(
				['Regular', 'LNG'],
				[
					{ name: cat, data: [val('Regular', keys[i]), val('LNG', keys[i])], color: i % 2 === 0 ? '#3b82f6' : '#8b5cf6' }
				],
				{ title: `${cat} — Regular vs LNG` }
			)} height="260px" guide={{ formula: `Side-by-side comparison of Regular vs LNG generators for <b>${cat}</b>.`, sources: [{ data: cat, file: 'Blackout Hr Excel', col: keys[i], method: 'AVG by site_type' }], reading: [{ color: 'blue', text: 'Blue/Purple bar = metric value per type' }, { color: 'green', text: 'Lower fuel/cost = better; higher buffer = better' }], explain: `Compares <b>diesel vs LNG</b> generator performance for ${cat}. Helps evaluate which fuel type is more efficient.` }} />
		{/each}
	</div>
	<div class="flex gap-4 mt-3 text-xs" style="color: #65655e;">
		<span>Regular: {data.find((d: any) => d.site_type === 'Regular')?.site_count || 0} sites</span>
		<span>LNG: {data.find((d: any) => d.site_type === 'LNG')?.site_count || 0} sites</span>
	</div>
{:else}
	<p class="text-sm" style="color: #65655e; py-4 text-center">Need both Regular and LNG site types for comparison.</p>
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
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #383832;">REGULAR vs LNG</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">comparison by site_type (Regular/LNG)</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">sites.site_type</code></td></tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #e85d04;">AVG FUEL/SITE</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">SUM(fuel) &divide; COUNT(sites) per type</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">daily_site_summary</code></td></tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #ff9d00;">AVG GEN HR/SITE</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">SUM(gen_hr) &divide; COUNT(sites) per type</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">daily_site_summary</code></td></tr>
				<tr style="background: #f6f4e9; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #007518;">AVG BUFFER</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">tank &divide; fuel per type</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">derived</code></td></tr>
				<tr style="background: white; border-bottom: 1px solid #ebe8dd;"><td class="py-1.5 px-3 font-bold" style="color: #65655e;">EFFICIENCY</td><td class="py-1.5 px-3 font-mono" style="color: #383832;">fuel &divide; gen_hr per type</td><td class="py-1.5 px-3" style="color: #9d9d91;"><code class="px-1 py-0.5 text-[9px]" style="background: #ebe8dd; color: #65655e;">derived</code></td></tr>
			</tbody>
		</table>
	</div>
</div>
