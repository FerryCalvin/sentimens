with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Add demo badge and toggle button in analysis view
old_header = '''<div class="flex items-center justify-between border-b border-on-surface/10 pb-4">
  <h2 class="font-display-base text-display-base text-on-surface" id="analysis-title">Analysis: -</h2>
  <button class="px-4 py-2 bg-surface-bright/20 text-primary font-label-base text-label-base rounded hover:bg-surface-bright/40 transition-colors" id="new-analysis-btn">New Search</button>
  </div>'''

new_header = '''<div class="flex items-center justify-between border-b border-on-surface/10 pb-4">
  <div class="flex items-center gap-3">
    <h2 class="font-display-base text-display-base text-on-surface" id="analysis-title">Analysis: -</h2>
    <span id="demo-badge" class="hidden px-2 py-1 text-xs font-bold bg-[#ffb4ab]/20 text-[#ffb4ab] border border-[#ffb4ab]/30 rounded">DEMO</span>
  </div>
  <div class="flex items-center gap-3">
    <button class="px-4 py-2 bg-surface-bright/20 text-primary font-label-base text-label-base rounded hover:bg-surface-bright/40 transition-colors hidden" id="toggle-view-btn">View Full Dataset</button>
    <button class="px-4 py-2 bg-surface-bright/20 text-primary font-label-base text-label-base rounded hover:bg-surface-bright/40 transition-colors" id="new-analysis-btn">New Search</button>
  </div>
  </div>'''

html = html.replace(old_header, new_header)

# Update the toggle button logic
js_additions = '''
        const toggleViewBtn = document.getElementById('toggle-view-btn');
        let isPrecomputedView = false;
        toggleViewBtn.addEventListener('click', () => {
            if (!isPrecomputedView) {
                // Switch to precomputed
                document.getElementById('analysis-status').textContent = 'Loading Full Dataset...';
                fetch('/api/results/precomputed')
                    .then(r => r.json())
                    .then(finalData => {
                        document.getElementById('analysis-title').textContent = 'Analysis: Pre-computed Dataset';
                        document.getElementById('demo-badge').classList.remove('hidden');
                        document.getElementById('analysis-status').textContent = Selesai · Total:  data;
                        toggleViewBtn.textContent = 'View Live Analysis';
                        isPrecomputedView = true;
                        
                        const mappedData = {
                            summary: { total: finalData.distribution.total, sentimen_positif: finalData.distribution.positif_count, sentimen_negatif: finalData.distribution.negatif_count, sentimen_netral: finalData.distribution.netral_count },
                            results: finalData.top_items,
                            timeline: finalData.timeline
                        };
                        initChartsWithData(mappedData);
                    });
            } else {
                // Return to landing page or recent live view
                showView('landing');
                toggleViewBtn.textContent = 'View Full Dataset';
                isPrecomputedView = false;
            }
        });
'''

html = html.replace('// Theme Toggle', js_additions + '\n        // Theme Toggle')

# Update the fetch result logic to show DEMO badge if needed
# The reqId data fetching already is there, let's just make the demo badge logic
logic_to_insert = '''
                                    // finalData memiliki struktur: { distribution, timeline, top_items }
                                    // However, in live mode, app.py /api/results/req_id returns { distribution, timeline, top_items }
                                    document.getElementById('demo-badge').classList.remove('hidden');
                                    toggleViewBtn.classList.remove('hidden');
                                    toggleViewBtn.textContent = 'View Full Dataset';
                                    isPrecomputedView = false;
'''

html = html.replace('// finalData memiliki struktur: { distribution, timeline, top_items }', logic_to_insert)

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated index.html for Phase 5")
