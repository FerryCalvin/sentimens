import re

html_path = "templates/index.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update the polling logic
old_polling_logic = """if (statusData.status === 'COMPLETED') {
                            clearInterval(interval);
                            
                            if (_analysisTitle)  _analysisTitle.textContent  = `Analysis: ${text}`;
                            if (_analysisStatus) _analysisStatus.textContent =
                                `Selesai · Total: ${statusData.total_results} data · Waktu: ${new Date(statusData.updated_at).toLocaleTimeString()}`;

                            showView('analysis');
                            initChartsWithData(statusData);
                        }"""

new_polling_logic = """if (statusData.status === 'COMPLETED') {
                            clearInterval(interval);
                            
                            // Ambil data agregasi final dari endpoint results
                            fetch(`/api/results/${reqId}`)
                                .then(r => r.json())
                                .then(finalData => {
                                    if (_analysisTitle)  _analysisTitle.textContent  = `Analysis: ${text}`;
                                    if (_analysisStatus) _analysisStatus.textContent =
                                        `Selesai · Total: ${statusData.total_results} data · Waktu: ${new Date().toLocaleTimeString()}`;

                                    showView('analysis');
                                    // finalData memiliki struktur: { distribution, timeline, top_items }
                                    // Namun kita perlu me-mapping agar initChartsWithData tetap bisa bekerja:
                                    const mappedData = {
                                        summary: {
                                            total: finalData.distribution.total,
                                            positif: finalData.distribution.positive,
                                            negatif: finalData.distribution.negative,
                                            netral: finalData.distribution.neutral,
                                            timeline: finalData.timeline
                                        },
                                        results: finalData.top_items
                                    };
                                    initChartsWithData(mappedData);
                                })
                                .catch(e => {
                                    console.error("Gagal memuat hasil akhir", e);
                                    alert("Gagal memuat hasil akhir");
                                    showView('landing');
                                });
                        }"""

html = html.replace(old_polling_logic, new_polling_logic)

# 2. Add Precomputed button on landing view
if "id=\"precomputed-btn\"" not in html:
    old_btn_area = """<button id="analyze-btn" type="button" class="btn btn-primary w-100 mb-3 glass-panel">
                                <span class="material-symbols-outlined me-2">analytics</span>
                                Mulai Analisis
                            </button>"""
                            
    new_btn_area = old_btn_area + """
                            <div class="text-center mt-2">
                                <button id="precomputed-btn" type="button" class="btn btn-outline-light w-100" style="border-radius: 8px; border: 1px solid rgba(255,255,255,0.2);">
                                    <span class="material-symbols-outlined me-2">dataset</span>
                                    Load Pre-computed Dataset (Demo)
                                </button>
                            </div>"""
    
    html = html.replace(old_btn_area, new_btn_area)

# 3. Add JS for precomputed button
if "document.getElementById('precomputed-btn')" not in html:
    precomputed_js = """
    const _precomputedBtn = document.getElementById('precomputed-btn');
    if (_precomputedBtn) {
        _precomputedBtn.addEventListener('click', () => {
            showView('waiting');
            document.getElementById('waiting-status').textContent = 'Memuat dataset pre-computed...';
            document.getElementById('waiting-progress').style.width = '100%';
            
            fetch('/api/results/precomputed')
                .then(r => r.json())
                .then(finalData => {
                    if (_analysisTitle)  _analysisTitle.textContent  = `Analysis: Pre-computed Dataset (Demo)`;
                    if (_analysisStatus) _analysisStatus.textContent =
                        `Selesai · Total: ${finalData.distribution.total} data · Waktu: ${new Date().toLocaleTimeString()}`;

                    showView('analysis');
                    const mappedData = {
                        summary: {
                            total: finalData.distribution.total,
                            positif: finalData.distribution.positive,
                            negatif: finalData.distribution.negative,
                            netral: finalData.distribution.neutral,
                            timeline: finalData.timeline
                        },
                        results: finalData.top_items
                    };
                    initChartsWithData(mappedData);
                })
                .catch(e => {
                    console.error(e);
                    alert("Dataset pre-computed tidak ditemukan.");
                    showView('landing');
                });
        });
    }
    """
    
    # Append the JS inside the existing script tag (right before the last </script>)
    html = html.replace("</script>\n</body>", precomputed_js + "\n</script>\n</body>")

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("index.html updated.")
