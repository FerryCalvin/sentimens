import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update theme toggle button
html = html.replace(
    '<button aria-label="Toggle dark mode"',
    '<button id="theme-toggle" aria-label="Toggle dark mode"'
)

# 2. Add loading spinner logic and UI to the Analyze button
# Currently: <button class="h-12 w-full ..." id="analyze-btn">Analyze Sentiment</button>
html = html.replace(
    '<button class="h-12 w-full max-w-[200px] bg-primary text-on-primary font-label-caps text-label-caps rounded-full hover:bg-primary-fixed active:scale-95 transition-all duration-300 shadow-md flex items-center justify-center relative overflow-hidden group" id="analyze-btn">',
    '<button class="h-12 w-full max-w-[200px] bg-primary text-on-primary font-label-caps text-label-caps rounded-full hover:bg-primary-fixed active:scale-95 transition-all duration-300 shadow-md flex items-center justify-center relative overflow-hidden group" id="analyze-btn">'
)
# Make the text change to spinner
html = html.replace(
    'Analyze Sentiment',
    '<span id="btn-text">Analyze Sentiment</span><span id="btn-spinner" class="hidden material-symbols-outlined animate-spin ml-2">progress_activity</span>'
)

# 3. Add DataTable HTML
data_table_html = '''
  <!-- Data Table -->
  <div class="chart-container col-span-1 md:col-span-2 lg:col-span-3 mt-6">
  <div class="flex justify-between items-center mb-4">
      <h3 class="font-label-caps text-label-caps text-on-surface-variant uppercase">Top Items</h3>
      <div class="text-xs text-on-surface-variant" id="table-page-info">Page 1</div>
  </div>
  <div class="overflow-x-auto">
      <table class="w-full text-left text-sm text-on-surface">
          <thead class="text-xs text-on-surface-variant uppercase bg-surface-bright/5 border-b border-on-surface/10">
              <tr>
                  <th scope="col" class="px-4 py-3">Date</th>
                  <th scope="col" class="px-4 py-3">Source</th>
                  <th scope="col" class="px-4 py-3 w-1/2">Text</th>
                  <th scope="col" class="px-4 py-3 cursor-pointer hover:text-primary transition-colors" id="sort-confidence">Confidence ↓</th>
                  <th scope="col" class="px-4 py-3">Sentiment</th>
              </tr>
          </thead>
          <tbody id="dataTable-body">
              <!-- Rows injected via JS -->
          </tbody>
      </table>
  </div>
  <div class="flex justify-end gap-2 mt-4">
      <button id="prev-page-btn" class="px-3 py-1 bg-surface-bright/20 rounded text-xs hover:bg-surface-bright/50 transition-colors disabled:opacity-50" disabled>Prev</button>
      <button id="next-page-btn" class="px-3 py-1 bg-surface-bright/20 rounded text-xs hover:bg-surface-bright/50 transition-colors disabled:opacity-50" disabled>Next</button>
  </div>
  </div>
'''

html = html.replace('<!-- Overall Score -->', data_table_html + '\n  <!-- Overall Score -->')

# 4. Add Empty State
empty_state_html = '''
  <!-- Empty State -->
  <div id="empty-state" class="hidden w-full h-64 flex flex-col items-center justify-center border border-on-surface/10 rounded bg-surface/50 mt-6 backdrop-blur-md">
      <span class="material-symbols-outlined text-6xl text-on-surface-variant mb-4">sentiment_dissatisfied</span>
      <h3 class="text-lg font-bold text-on-surface">No Data Found</h3>
      <p class="text-sm text-on-surface-variant mt-2">Try searching for a different topic.</p>
  </div>
'''
html = html.replace('<!-- Analysis View -->\n  <div class="analysis-view w-full max-w-container-max flex-col gap-6 hidden" id="analysis-view">\n  <div class="flex items-center justify-between border-b border-on-surface/10 pb-4">\n  <h2 class="font-display-base text-display-base text-on-surface" id="analysis-title">Analysis: -</h2>\n  <button class="px-4 py-2 bg-surface-bright/20 text-primary font-label-base text-label-base rounded hover:bg-surface-bright/40 transition-colors" id="new-analysis-btn">New Search</button>\n  </div>', 
'<!-- Analysis View -->\n  <div class="analysis-view w-full max-w-container-max flex-col gap-6 hidden" id="analysis-view">\n  <div class="flex items-center justify-between border-b border-on-surface/10 pb-4">\n  <h2 class="font-display-base text-display-base text-on-surface" id="analysis-title">Analysis: -</h2>\n  <button class="px-4 py-2 bg-surface-bright/20 text-primary font-label-base text-label-base rounded hover:bg-surface-bright/40 transition-colors" id="new-analysis-btn">New Search</button>\n  </div>' + empty_state_html)

# 5. Update Footer
html = html.replace('© 2024 Sentiments SPA. All rights reserved.', 'Ferry Calvin | NIM: 123456789 | Universitas X | 2026')

# 6. Replace tailwind config with variables
tailwind_match = re.search(r'"colors": (\{.*?\})', html, re.DOTALL)
if tailwind_match:
    import json
    colors_dict = json.loads(tailwind_match.group(1).replace("'", '"'))
    
    css_vars = ":root {\n"
    for k, v in colors_dict.items():
        css_vars += f"  --color-{k}: {v};\n"
    css_vars += "}\n"
    
    # Simple light theme overrides (invert lightness roughly for essential ones)
    css_vars += ":root[data-theme='light'] {\n"
    css_vars += "  --color-background: #ffffff;\n"
    css_vars += "  --color-surface: #f8f9fa;\n"
    css_vars += "  --color-surface-dim: #e9ecef;\n"
    css_vars += "  --color-surface-bright: #dee2e6;\n"
    css_vars += "  --color-on-surface: #07122a;\n"
    css_vars += "  --color-on-surface-variant: #425273;\n"
    css_vars += "  --color-primary: #4a6fa5;\n"
    css_vars += "}\n"

    new_colors_dict = {k: f"var(--color-{k})" for k in colors_dict.keys()}
    
    html = html.replace(tailwind_match.group(1), json.dumps(new_colors_dict, indent=16))
    
    # Inject css vars
    html = html.replace('</style>', f'{css_vars}</style>')

# 7. Add JS for Theme Toggle, Spinner, and DataTable
js_additions = '''
        // Theme Toggle
        const themeToggleBtn = document.getElementById('theme-toggle');
        const rootHtml = document.documentElement;
        const themeIcon = themeToggleBtn.querySelector('span');
        themeToggleBtn.addEventListener('click', () => {
            if (rootHtml.getAttribute('data-theme') === 'light') {
                rootHtml.setAttribute('data-theme', 'dark');
                rootHtml.classList.add('dark');
                themeIcon.textContent = 'dark_mode';
            } else {
                rootHtml.setAttribute('data-theme', 'light');
                rootHtml.classList.remove('dark');
                themeIcon.textContent = 'light_mode';
            }
        });

        // DataTable Logic
        let tableData = [];
        let currentPage = 1;
        const rowsPerPage = 10;
        let sortDesc = true;

        function renderTable() {
            const tbody = document.getElementById('dataTable-body');
            const pageInfo = document.getElementById('table-page-info');
            const prevBtn = document.getElementById('prev-page-btn');
            const nextBtn = document.getElementById('next-page-btn');
            
            tbody.innerHTML = '';
            
            if (!tableData || tableData.length === 0) {
                pageInfo.textContent = 'No data';
                prevBtn.disabled = true;
                nextBtn.disabled = true;
                return;
            }

            // Sort
            tableData.sort((a, b) => {
                let diff = (b.confidence || 0) - (a.confidence || 0);
                return sortDesc ? diff : -diff;
            });

            const totalPages = Math.ceil(tableData.length / rowsPerPage);
            if (currentPage > totalPages) currentPage = totalPages;
            if (currentPage < 1) currentPage = 1;

            const startIdx = (currentPage - 1) * rowsPerPage;
            const endIdx = startIdx + rowsPerPage;
            const pageData = tableData.slice(startIdx, endIdx);

            pageData.forEach(row => {
                const tr = document.createElement('tr');
                tr.className = 'border-b border-on-surface/5 hover:bg-surface-bright/5 transition-colors';
                
                let badgeColor = 'bg-surface-bright/20 text-on-surface-variant';
                if (row.sentimen === 'Positif') badgeColor = 'bg-[#d9e2ff]/20 text-[#d9e2ff]';
                else if (row.sentimen === 'Negatif') badgeColor = 'bg-[#ffb4ab]/20 text-[#ffb4ab]';

                tr.innerHTML = 
                    <td class="px-4 py-3 whitespace-nowrap"></td>
                    <td class="px-4 py-3 whitespace-nowrap"></td>
                    <td class="px-4 py-3 truncate max-w-xs" title=""></td>
                    <td class="px-4 py-3 font-mono-code">%</td>
                    <td class="px-4 py-3"><span class="px-2 py-1 rounded text-xs "></span></td>
                ;
                tbody.appendChild(tr);
            });

            pageInfo.textContent = Page  of ;
            prevBtn.disabled = currentPage === 1;
            nextBtn.disabled = currentPage === totalPages;
        }

        document.getElementById('prev-page-btn').addEventListener('click', () => {
            if (currentPage > 1) { currentPage--; renderTable(); }
        });
        document.getElementById('next-page-btn').addEventListener('click', () => {
            currentPage++; renderTable();
        });
        document.getElementById('sort-confidence').addEventListener('click', () => {
            sortDesc = !sortDesc;
            document.getElementById('sort-confidence').textContent = sortDesc ? 'Confidence ?' : 'Confidence ?';
            renderTable();
        });
'''

html = html.replace('// -- Three.js Particle System', js_additions + '\n        // -- Three.js Particle System')

# Hook DataTable into initChartsWithData
html = html.replace(
    '// Timeline Chart (Stacked Bar Chart',
    '''
        if (apiData.results && apiData.results.length > 0) {
            document.getElementById('empty-state').classList.add('hidden');
            document.querySelector('.grid.grid-cols-1.md\\\\:grid-cols-2.lg\\\\:grid-cols-3').classList.remove('hidden');
            tableData = apiData.results;
            currentPage = 1;
            renderTable();
        } else {
            document.getElementById('empty-state').classList.remove('hidden');
            document.querySelector('.grid.grid-cols-1.md\\\\:grid-cols-2.lg\\\\:grid-cols-3').classList.add('hidden');
        }

        // Timeline Chart (Stacked Bar Chart
'''
)

# Fix loading spinner in Analyze button
html = html.replace(
    "const topic = _topicInput.value.trim();",
    "const topic = _topicInput.value.trim();\n            document.getElementById('btn-text').textContent = 'Processing...';\n            document.getElementById('btn-spinner').classList.remove('hidden');\n            _analyzeBtn.disabled = true;"
)

html = html.replace(
    "showView('landing');",
    "showView('landing');\n            const btnText = document.getElementById('btn-text');\n            if(btnText) btnText.textContent = 'Analyze Sentiment';\n            const btnSpin = document.getElementById('btn-spinner');\n            if(btnSpin) btnSpin.classList.add('hidden');\n            if(_analyzeBtn) _analyzeBtn.disabled = false;"
)

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated index.html")
