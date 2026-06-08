from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('http://localhost:5000')
        print(f"Page Title: {page.title()}")
        print("Theme attribute:", page.evaluate("document.documentElement.getAttribute('data-theme')"))
        print("Dark class present:", page.evaluate("document.documentElement.classList.contains('dark')"))
        
        # Click toggle
        page.click('#theme-toggle')
        print("Theme attribute after click:", page.evaluate("document.documentElement.getAttribute('data-theme')"))
        print("Dark class present after click:", page.evaluate("document.documentElement.classList.contains('dark')"))
        
        # Click batch analysis to load data (we simulate or click the same mock flow)
        # We can just check if DataTable is in DOM
        print("DataTable exists:", page.locator('#dataTable-body').count() > 0)
        
        browser.close()

run()
