import smtplib
import os
import logging
import pytz
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# ==========================================================
# CREACIÓN DE ACTIVIDAD EN ODOO (JSON-RPC)
# ==========================================================

def create_odoo_activity(client, product_id, product_name):
    try:
        # Buscar tipo estándar (Por hacer / To Do)
        activity_type = client.execute(
            'mail.activity.type',
            'search',
            [['category', '=', 'default']],
            limit=1
        )

        if not activity_type:
            raise Exception("No existe tipo de actividad default en esta base")

        activity_type_id = activity_type[0]

        model_id = client.execute(
            'ir.model',
            'search',
            [['model', '=', 'product.template']],
            limit=1
        )[0]

        activity_vals = {
            'res_id': product_id,
            'res_model_id': model_id,
            'activity_type_id': activity_type_id,
            'summary': f'Completar producto creado: {product_name}',
            'note': '<p>Producto detectado automáticamente.</p>',
            'date_deadline': datetime.now().strftime('%Y-%m-%d'),
            'user_id': 17836,
        }

        result = client.execute(
            'mail.activity',
            'create',
            activity_vals
        )

        logger.info(f"   -> ✅ Actividad creada (ID: {result})")

    except Exception:
        logger.exception("   -> ❌ Error creando actividad:")


# ==========================================================
# NOTIFICACIÓN PRINCIPAL
# ==========================================================

def send_notifications(product, client=None):
    p_name = product.get('name', 'Sin nombre')

    # 1️⃣ FILTRO DE TIPO
    if product.get('type') != 'consu':
        logger.info(f"🚫 Saltando {p_name}: No es tipo 'consu'.")
        return

    # 2️⃣ FILTRO DE CATEGORÍA
    categoria_info = product.get('categ_id')
    if categoria_info and isinstance(categoria_info, list):
        nombre_cat = categoria_info[1].upper()
        if nombre_cat.startswith("REPUESTOS") or nombre_cat.startswith("OUTLET"):
            logger.info(f"🚫 Saltando {p_name}: Categoría excluida ({nombre_cat}).")
            return

    # 3️⃣ FILTRO DE FECHA (HOY ARG)
    create_date = product.get('create_date')
    if not create_date:
        logger.info(f"🚫 Saltando {p_name}: Sin create_date.")
        return

    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    hoy = datetime.now(tz).strftime('%Y-%m-%d')
    fecha_prod = create_date.split(' ')[0]

    if fecha_prod != hoy:
        logger.info(f"🚫 Saltando {p_name}: Fecha antigua ({fecha_prod}).")
        return

    # 4️⃣ FILTRO DE PRECIO
    precio = product.get('list_price', 0.0)
    if precio <= 1.0:
        logger.info(f"🚫 Saltando {p_name}: Precio inválido (${precio}).")
        return

    # ======================================================
    # PRODUCTO VÁLIDO
    # ======================================================

    logger.info(f"🚀 Procesando notificación para: {p_name}")

    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASSWORD')
    recipient = os.getenv('EMAIL_RECIPIENT')
    odoo_url = os.getenv('ODOO_URL')

    if not all([smtp_server, smtp_port, smtp_user, smtp_pass, recipient, odoo_url]):
        logger.error("❌ Variables SMTP/ENV faltantes.")
        return

    try:
        smtp_port = int(smtp_port)
        stock = product.get('qty_available', 0.0)

        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = recipient
        msg['Subject'] = f"📦 NUEVO PRODUCTO: {p_name}"

        body = f"""Hola,

Se ha detectado un nuevo producto con precio establecido:

• Nombre: {p_name}
• SKU: {product.get('default_code') or 'N/A'}
• Precio: ${precio:,.2f}
• Stock: {stock}

Ver en Odoo:
{odoo_url}/web#id={product['id']}&model=product.template&view_type=form

Saludos,
Sistema de Automatización.
"""

        msg.attach(MIMEText(body, 'plain'))

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
            server.starttls()

        server.login(smtp_user, smtp_pass)
        recipients = [r.strip() for r in recipient.split(',')]
        server.sendmail(smtp_user, recipients, msg.as_string())
        server.quit()

        logger.info("   -> ✅ Mail enviado correctamente.")

    except Exception as e:
        logger.error(f"   -> ❌ Error SMTP: {e}")
        return

    # Crear actividad solo si el mail salió bien
    if client:
        create_odoo_activity(client, product['id'], p_name)