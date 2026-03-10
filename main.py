import time
import logging
from odoo_client import OdooClient
from notifier import send_notifications

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ACTIVE_SLEEP = 30
MAX_SLEEP = 600
PARAM_KEY = "notificaciones_sku.last_id"


def get_last_id(client):
    try:
        value = client._execute(
            "ir.config_parameter",
            "get_param",
            [PARAM_KEY]
        )
        return int(value) if value else 0
    except Exception as e:
        logger.error(f"Error leyendo last_id desde Odoo: {e}")
        return 0


def save_last_id(client, last_id):
    try:
        client._execute(
            "ir.config_parameter",
            "set_param",
            [PARAM_KEY, str(last_id)]
        )
    except Exception as e:
        logger.error(f"Error guardando last_id en Odoo: {e}")


def main():
    try:
        odoo = OdooClient()
    except Exception as e:
        logger.error(f"❌ Error crítico al conectar con Odoo: {e}")
        return

    logger.info("🚀 Motor de notificaciones iniciado (persistencia en Odoo).")

    # 🔹 Leer last_id UNA sola vez
    last_id = get_last_id(odoo)
    logger.info(f"Estado inicial last_id: {last_id}")

    current_sleep = ACTIVE_SLEEP

    while True:
        try:
            new_products = odoo.get_new_products(last_id)

            if new_products:
                for product in new_products:
                    logger.info(
                        f"🔔 Detectado: {product['name']} "
                        f"(ID: {product['id']})"
                    )

                    send_notifications(product, client=odoo)

                    if product['id'] > last_id:
                        last_id = product['id']

                save_last_id(odoo, last_id)

                logger.info(
                    f"✅ Procesamiento finalizado. "
                    f"Nuevo last_id: {last_id}. "
                    f"Próximo chequeo en {ACTIVE_SLEEP}s."
                )

                current_sleep = ACTIVE_SLEEP

            else:
                current_sleep = min(current_sleep + 60, MAX_SLEEP)
                logger.info(
                    f"😴 Sin novedades. Reintentando en {current_sleep}s..."
                )

        except Exception as e:
            logger.error(f"❌ Error en el ciclo principal: {e}")
            current_sleep = ACTIVE_SLEEP
            time.sleep(60)

        time.sleep(current_sleep)


if __name__ == "__main__":
    main()