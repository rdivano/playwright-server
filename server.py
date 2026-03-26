from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import os

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


@app.route('/experta/login', methods=['POST'])
def experta_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"status": "error", "mensaje": "username y password requeridos"}), 400

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Ir al login de Experta
            page.goto('https://www.experta.com.ar/ARTServicio/ART/Transaccion/LoginInput.lnk', wait_until='networkidle')

            # Completar credenciales
            page.fill('input[name="usuario"]', username)
            page.fill('input[name="clave"]', password)
            page.click('input[type="submit"], button[type="submit"]')

            # Esperar que cargue el dashboard
            page.wait_for_load_state('networkidle')

            # Hacer click en Cotizador
            page.click('text=Cotizador')

            # Esperar que cargue la pagina del cotizador
            page.wait_for_load_state('networkidle')

            url_actual = page.url
            titulo = page.title()

            browser.close()

            return jsonify({
                "status": "success",
                "url": url_actual,
                "titulo": titulo
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "mensaje": str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
