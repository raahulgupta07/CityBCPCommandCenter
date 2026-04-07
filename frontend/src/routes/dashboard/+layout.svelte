<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import AppHeader from '$lib/components/AppHeader.svelte';
	import FooterBar from '$lib/components/FooterBar.svelte';

	let { children } = $props();
	let ready = $state(false);
	let currentUser: any = $state(null);
	let bootPhase = $state(0);
	let bootComplete = $state(false);

	const bootAgents = [
		{ icon: 'security', name: 'AUTH_AGENT', task: 'Verifying credentials & session token', color: '#007518' },
		{ icon: 'storage', name: 'DATA_AGENT', task: 'Connecting to BCP database (SQLite WAL)', color: '#006f7c' },
		{ icon: 'local_gas_station', name: 'FUEL_AGENT', task: 'Loading fuel prices & purchase history', color: '#e85d04' },
		{ icon: 'bolt', name: 'BLACKOUT_AGENT', task: 'Processing generator & blackout data', color: '#ff9d00' },
		{ icon: 'analytics', name: 'ANALYTICS_AGENT', task: 'Computing KPIs, buffer days, efficiency', color: '#9d4867' },
		{ icon: 'show_chart', name: 'CHART_AGENT', task: 'Building 50+ charts & visualizations', color: '#383832' },
		{ icon: 'psychology', name: 'AI_AGENT', task: 'Initializing Gemini 3.1 Flash Lite model', color: '#007518' },
		{ icon: 'dashboard', name: 'DASHBOARD_AGENT', task: 'Assembling command center — ready', color: '#00fc40' },
	];

	onMount(async () => {
		if (!api.isLoggedIn()) { goto('/login'); return; }
		try { currentUser = await api.get('/me'); } catch(e) { goto('/login'); return; }

		// Only show boot animation once per session
		const alreadyBooted = sessionStorage.getItem('bcp_booted');
		if (alreadyBooted) {
			bootPhase = bootAgents.length - 1;
			bootComplete = true;
			ready = true;
			return;
		}

		// Boot sequence animation (first time only)
		for (let i = 0; i < bootAgents.length; i++) {
			bootPhase = i;
			await new Promise(r => setTimeout(r, 350));
		}
		await new Promise(r => setTimeout(r, 400));
		bootComplete = true;
		await new Promise(r => setTimeout(r, 300));
		sessionStorage.setItem('bcp_booted', '1');
		ready = true;
	});
</script>

{#if ready}
<AppHeader {currentUser} />
<main class="pt-16 pb-16 px-6 max-w-[1920px] mx-auto min-h-screen" style="background: #feffd6; color: #383832;">
	{@render children()}
</main>
<FooterBar />
{:else}
	<!-- Boot sequence -->
	<div class="min-h-screen flex items-center justify-center" style="background: #383832;">
		<div class="w-full max-w-lg px-8">
			<!-- Logo -->
			<div class="text-center mb-8">
				<div class="text-4xl font-black uppercase tracking-tighter" style="color: #feffd6;">BCP COMMAND CENTER</div>
				<div class="text-xs font-bold uppercase tracking-widest mt-1" style="color: #65655e;">City Holdings Myanmar — Business Continuity Platform</div>
			</div>

			<!-- Agent boot list -->
			<div class="space-y-1.5">
				{#each bootAgents as agent, i}
					<div class="flex items-center gap-3 px-4 py-2 transition-all duration-300"
						style="opacity: {i <= bootPhase ? 1 : 0.15}; background: {i < bootPhase ? 'rgba(0,117,24,0.1)' : i === bootPhase ? 'rgba(254,255,214,0.05)' : 'transparent'}; border-left: 3px solid {i < bootPhase ? '#007518' : i === bootPhase ? agent.color : '#65655e'};">
						<!-- Status icon -->
						{#if i < bootPhase}
							<span class="material-symbols-outlined text-sm" style="color: #007518;">check_circle</span>
						{:else if i === bootPhase}
							<div class="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin" style="border-color: {agent.color}; border-top-color: transparent;"></div>
						{:else}
							<span class="material-symbols-outlined text-sm" style="color: #65655e;">radio_button_unchecked</span>
						{/if}

						<!-- Agent info -->
						<span class="material-symbols-outlined text-sm" style="color: {i <= bootPhase ? agent.color : '#65655e'};">{agent.icon}</span>
						<div class="flex-1">
							<span class="text-[10px] font-black uppercase" style="color: {i <= bootPhase ? '#feffd6' : '#65655e'};">{agent.name}</span>
							<span class="text-[9px] ml-2" style="color: {i <= bootPhase ? '#9d9d91' : '#4a4a44'};">{agent.task}</span>
						</div>

						<!-- Status text -->
						{#if i < bootPhase}
							<span class="text-[9px] font-bold" style="color: #007518;">DONE</span>
						{:else if i === bootPhase}
							<span class="text-[9px] font-bold animate-pulse" style="color: {agent.color};">RUNNING</span>
						{/if}
					</div>
				{/each}
			</div>

			<!-- Progress bar -->
			<div class="mt-6 h-1.5 overflow-hidden" style="background: #4a4a44;">
				<div class="h-full transition-all duration-300" style="background: {bootComplete ? '#00fc40' : '#007518'}; width: {bootComplete ? 100 : Math.round((bootPhase + 1) / bootAgents.length * 100)}%;"></div>
			</div>

			<!-- Status -->
			<div class="text-center mt-3">
				{#if bootComplete}
					<span class="text-sm font-black uppercase" style="color: #00fc40;">ALL SYSTEMS OPERATIONAL</span>
				{:else}
					<span class="text-[10px] font-bold uppercase" style="color: #65655e;">
						Initializing {bootPhase + 1} of {bootAgents.length} agents...
					</span>
				{/if}
			</div>

			<!-- User info -->
			{#if currentUser}
				<div class="text-center mt-4 text-[10px]" style="color: #65655e;">
					Logged in as <span class="font-bold" style="color: #feffd6;">{currentUser.username}</span>
					<span class="px-1.5 py-0.5 ml-1 font-bold uppercase" style="background: #007518; color: white; font-size: 8px;">{currentUser.role}</span>
				</div>
			{/if}
		</div>
	</div>
{/if}
