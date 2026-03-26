from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import os
import base64

app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


@app.route('/cotizar', methods=['POST'])
def cotizar():
    data = request.json
    username = data.get('username', 'standard_user')
    password = data.get('password', 'secret_sauce')

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login
            page.goto('https://www.saucedemo.com')
            page.fill('#user-name', username)
            page.fill('#password', password)
            page.click('#login-button')

            # Esperar que cargue la pagina de productos
            page.wait_for_selector('.inventory_list')

            # Extraer productos (simulando cotizaciones)
            items = page.query_selector_all('.inventory_item')
            cotizaciones = []
            for item in items:
                nombre = item.query_selector('.inventory_item_name').inner_text()
                precio = item.query_selector('.inventory_item_price').inner_text()
                cotizaciones.append({"nombre": nombre, "precio": precio})

            browser.close()

            return jsonify({
                "status": "success",
                "aseguradora": "saucedemo (prueba)",
                "cotizaciones": cotizaciones
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "mensaje": str(e)
        }), 500


@app.route('/experta/debug-login', methods=['GET'])
def experta_debug_login():
    """Toma screenshot del login y devuelve el HTML para inspeccionar selectores"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto('https://www.experta.com.ar/ARTServicio/ART/Transaccion/LoginInput.lnk', wait_until='domcontentloaded')
            page.wait_for_timeout(5000)

            screenshot = page.screenshot()
            screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

            inputs = page.eval_on_selector_all('input', 'els => els.map(e => ({id: e.id, name: e.name, type: e.type, placeholder: e.placeholder}))')
            url_actual = page.url

            browser.close()

            return jsonify({
                "status": "success",
                "url": url_actual,
                "inputs": inputs,
                "screenshot_base64": screenshot_b64
            })
    except Exception as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 200


@app.route('/experta/cotizar', methods=['POST'])
def experta_cotizar():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    cuit = data.get('cuit')
    actividad = data.get('actividad', '')  # texto de búsqueda, vacío = primera opción
    capitas = str(data.get('capitas', 1))
    masa_salarial = str(data.get('masa_salarial', 0))

    if not username or not password or not cuit:
        return jsonify({"status": "error", "mensaje": "username, password y cuit son requeridos"}), 400

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 1. Login (Keycloak)
            page.goto('https://www.experta.com.ar/ARTServicio/ART/Transaccion/LoginInput.lnk', wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            page.fill('#username', username)
            page.fill('#password', password)
            page.click('#kc-login')
            # networkidle nunca se alcanza (Keycloak redirects + analytics) -> esperamos el nav
            page.wait_for_selector('#jetmenu', timeout=30000)

            # 2. Click en Cotizador (nav) - navega via form POST al Cotizador Multiproducto
            page.locator('text=Cotizador').first.click(no_wait_after=True)
            page.wait_for_selector('text=Cotizador Multiproducto', timeout=30000)

            # 3. Click en Cotizar de ART + VIDA (primer boton COTIZAR de la grilla, case-sensitive)
            page.get_by_text('COTIZAR', exact=True).first.click(no_wait_after=True)
            page.wait_for_selector('text=Ingresá la CUIT', timeout=30000)

            # 4. Ingresar CUIT y buscar (input[type="text"] evita los hidden del form de nav)
            page.locator('input[type="text"]').first.fill(cuit)
            page.get_by_text('Buscar', exact=True).click()
            page.wait_for_selector('text=Seleccione la actividad', timeout=30000)

            # 5. Seleccionar actividad del dropdown (custom searchable select)
            page.click('text=Seleccione la actividad')
            page.wait_for_selector('input[placeholder*="búsqueda"], input[placeholder*="busqueda"]')
            if actividad:
                page.fill('input[placeholder*="búsqueda"], input[placeholder*="busqueda"]', actividad)
                page.wait_for_timeout(1000)
            # Seleccionar primera opción visible
            page.locator('li, .option, [role="option"]').filter(has_text='-').first.click()
            page.wait_for_timeout(500)

            # 6. Ingresar cápitas y masa salarial
            page.locator('input[id*="capita"], input[name*="capita"]').first.fill(capitas)
            page.locator('input[id*="masa"], input[id*="salarial"], input[name*="masa"]').first.fill(masa_salarial)

            # Click Siguiente
            page.click('text=Siguiente')
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(2000)

            # 7. Extraer Cuota Mensual de la seccion ART
            cuota_mensual = page.locator('text=Cuota Mensual').locator('..').locator('strong, b, span').first.inner_text()

            browser.close()

            return jsonify({
                "status": "success",
                "aseguradora": "Experta",
                "cuit": cuit,
                "cuota_mensual": cuota_mensual.strip()
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "mensaje": str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
