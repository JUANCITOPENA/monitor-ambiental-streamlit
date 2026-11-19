import os
import subprocess
import time
import requests
from playwright.sync_api import sync_playwright

def main():
    base_dir = r"C:\Users\User\Desktop\CARPETA DE TRABAJO DE ANTIGRAVITY CLI-JPV\monitor_ambiental_streamlit"
    docs_dir = os.path.join(base_dir, "docs", "screenshots")
    os.makedirs(docs_dir, exist_ok=True)
    python_exe = os.path.join(base_dir, ".venv", "Scripts", "python.exe")
    
    print("[1] Levantando servidor Streamlit...")
    cmd_streamlit = [python_exe, "-m", "streamlit", "run", "app.py", "--server.headless=true", "--server.port=8501"]
    proc = subprocess.Popen(cmd_streamlit, cwd=base_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Esperar conexión
    url = "http://localhost:8501"
    for _ in range(30):
        time.sleep(1)
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200:
                print("[2] Streamlit respondiendo HTTP 200.")
                break
        except Exception:
            pass
            
    # Esperar carga completa y renderizado de Plotly
    time.sleep(6)
    
    print("[3] Conectando Playwright con Microsoft Edge nativo...")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1.25)
        page = context.new_page()
        page.goto(url, wait_until="networkidle")
        time.sleep(5)
        
        # 1. Captura Hero / KPIs
        print("[4] Tomando Captura 1: Portada, KPIs y Narrador...")
        cap1_path = os.path.join(docs_dir, "01_hero_kpis_narrador.png")
        page.screenshot(path=cap1_path)
        
        # 2. Captura Gráficos Analíticos
        print("[5] Haciendo scroll y tomando Captura 2: Gráficos de Clima y Calidad de Aire...")
        page.evaluate("window.scrollTo(0, 520);")
        time.sleep(2)
        cap2_path = os.path.join(docs_dir, "02_graficos_analiticos_clima_aire.png")
        page.screenshot(path=cap2_path)
        
        # 3. Captura Heatmap UV y Tabla
        print("[6] Haciendo scroll y tomando Captura 3: Mapa de Calor UV y Repositorio...")
        page.evaluate("window.scrollTo(0, 1150);")
        time.sleep(2)
        cap3_path = os.path.join(docs_dir, "03_heatmap_uv_tabla_consolidada.png")
        page.screenshot(path=cap3_path)
        
        # 4. Captura completa panorámica (Full Page)
        print("[7] Tomando Captura Panorámica Completa...")
        full_path = os.path.join(docs_dir, "00_dashboard_completo.png")
        page.screenshot(path=full_path, full_page=True)
        
        browser.close()
        print("[8] Capturas guardadas exitosamente en docs/screenshots/")
        
    print("[9] Cerrando proceso Streamlit...")
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except Exception:
        proc.kill()
    print("[OK] Todo completado con exito.")

if __name__ == "__main__":
    main()
