"""
Capture Scholar-Bot UI screenshots for the README.
Run while the app is live on http://localhost:8503.
Outputs to docs/screenshots/.
"""
from pathlib import Path
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

OUT = Path("docs/screenshots")
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:8503"

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1440,900")
opts.add_argument("--hide-scrollbars")
opts.add_argument("--force-device-scale-factor=2")
opts.add_argument("--disable-gpu")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

try:
    print(f"Loading {URL} ...")
    driver.get(URL)
    # Streamlit takes a moment to render
    time.sleep(5)

    # Set window to full content height for full-page screenshot
    full_height = driver.execute_script(
        "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);"
    )
    driver.set_window_size(1440, max(900, min(full_height, 3500)))
    time.sleep(1)

    out_main = OUT / "01-upload-tab.png"
    driver.save_screenshot(str(out_main))
    print(f"  saved {out_main}  ({out_main.stat().st_size // 1024} KB)")

    # Try clicking each tab and capture
    tabs = driver.find_elements(By.CSS_SELECTOR, '[role="tab"]')
    print(f"  found {len(tabs)} tabs")
    for i, tab in enumerate(tabs):
        try:
            label = tab.text.strip().replace(" ", "_").lower()[:30] or f"tab_{i}"
            driver.execute_script("arguments[0].scrollIntoView(true);", tab)
            tab.click()
            time.sleep(2)
            out = OUT / f"0{i+2}-{label}.png"
            driver.save_screenshot(str(out))
            print(f"  saved {out}")
        except Exception as e:
            print(f"  tab {i} skipped: {e}")

finally:
    driver.quit()
    print("Done.")
