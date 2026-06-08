with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

import re
match = re.search(r'try \{\s+const res\s+=\s+await fetch\(\'/api/analyze\', \{.*?finally \{\s+newBtn\.innerHTML = origHTML;\s+newBtn\.disabled\s+=\s+false;\s+\}\s+\}\);', content, re.DOTALL)

new_logic = '''try {
                const limit = document.getElementById('toggle-view-btn') && !isPrecomputedView ? 50 : 100;
                const mode = isPrecomputedView ? "demo" : "live"; // Actually if they initiate a new search it's always live
                const res  = await fetch('/api/scrape', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ keyword: text, limit: 50, sources: ['twitter', 'news'], mode: "live" })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Gagal memulai analisis');

                const reqId = data.req_id;
                if (_analysisStatus) _analysisStatus.textContent = 'Memulai proses scraping...';
                if (_analysisTitle)  _analysisTitle.textContent  = Analysis: ;
                showView('analysis');
                
                // Polling logic
                const interval = setInterval(async () => {
                    try {
                        const statusRes = await fetch(/api/status/);
                        const statusData = await statusRes.json();
                        
                        if (_analysisStatus) _analysisStatus.textContent = Processing:  (%);
                        
                        if (statusData.status === 'COMPLETED') {
                            clearInterval(interval);
                            
                            // Fetch final results
                            fetch(/api/results/)
                                .then(r => r.json())
                                .then(finalData => {
                                    if (_analysisTitle)  _analysisTitle.textContent  = Analysis: ;
                                    if (_analysisStatus) _analysisStatus.textContent =
                                        Selesai · Total:  data · Waktu: ;

                                    const badge = document.getElementById('demo-badge');
                                    if(badge) badge.classList.add('hidden');
                                    const toggleBtn = document.getElementById('toggle-view-btn');
                                    if(toggleBtn) {
                                        toggleBtn.classList.remove('hidden');
                                        toggleBtn.innerHTML = '<span class="material-symbols-outlined text-[16px]">dataset</span> View Full Dataset';
                                    }
                                    isPrecomputedView = false;
                                    
                                    const mappedData = {
                                        summary: {
                                            total: finalData.distribution.total,
                                            sentimen_positif: finalData.distribution.positif_count || finalData.distribution.positive,
                                            sentimen_negatif: finalData.distribution.negatif_count || finalData.distribution.negative,
                                            sentimen_netral: finalData.distribution.netral_count || finalData.distribution.neutral
                                        },
                                        results: finalData.top_items,
                                        timeline: finalData.timeline
                                    };
                                    initChartsWithData(mappedData);
                                    
                                    newBtn.innerHTML = origHTML;
                                    newBtn.disabled  = false;
                                })
                                .catch(e => {
                                    console.error("Gagal memuat hasil akhir", e);
                                    if (_analysisStatus) _analysisStatus.textContent = 'Error memuat hasil akhir';
                                    newBtn.innerHTML = origHTML;
                                    newBtn.disabled  = false;
                                });
                        } else if (statusData.status === 'FAILED' || statusData.status === 'NOT_FOUND') {
                            clearInterval(interval);
                            if (_analysisStatus) _analysisStatus.textContent = 'Error: ' + (statusData.message || 'Proses gagal');
                            newBtn.innerHTML = origHTML;
                            newBtn.disabled  = false;
                        }
                    } catch(pollErr) {
                        clearInterval(interval);
                        if (_analysisStatus) _analysisStatus.textContent = 'Error saat mengecek status: ' + pollErr.message;
                        newBtn.innerHTML = origHTML;
                        newBtn.disabled  = false;
                    }
                }, 2000);

            } catch(err) {
                alert('Error: ' + err.message);
                showView('landing');
                newBtn.innerHTML = origHTML;
                newBtn.disabled  = false;
            }
        });'''

if match:
    content = content.replace(match.group(0), new_logic)
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Updated polling logic successfully.")
else:
    print("Could not find the /api/analyze fetch block")
