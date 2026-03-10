import xmlrpc.client
import os
import logging
from dotenv import load_dotenv

# Carga automática del .env si existe (no rompe en producción)
load_dotenv()

logger = logging.getLogger(__name__)


class OdooClient:
    def __init__(self):
        self.url = os.getenv('ODOO_URL')
        self.db = os.getenv('ODOO_DB')
        self.username = os.getenv('ODOO_USER')
        self.password = os.getenv('ODOO_PASS')

        if not all([self.url, self.db, self.username, self.password]):
            logger.error("❌ Variables Odoo faltantes.")
            raise Exception("Credenciales incompletas")

        # Proxies persistentes
        self.common = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/common",
            allow_none=True
        )

        self.models = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/object",
            allow_none=True
        )

        self.uid = self._authenticate()

    def _authenticate(self):
        try:
            uid = self.common.authenticate(
                self.db,
                self.username,
                self.password,
                {}
            )

            if not uid:
                raise Exception("Autenticación fallida.")

            logger.info("✅ Autenticación Odoo exitosa.")
            return uid

        except Exception as e:
            logger.error(f"Error conectando con Odoo: {e}")
            raise

    def _execute(self, model, method, *args, **kwargs):
        return self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            model,
            method,
            args,
            kwargs
        )

    def get_new_products(self, last_id):
        """
        Devuelve productos con ID mayor al último procesado.
        La lógica de negocio vive en notifier.py
        """

        domain = [['id', '>', last_id]]

        try:
            return self._execute(
                'product.template',
                'search_read',
                [domain],
                {
                    'fields': [
                        'id',
                        'name',
                        'default_code',
                        'list_price',
                        'qty_available',
                        'categ_id',
                        'type',
                        'create_date'
                    ],
                    'order': 'id asc',
                    'limit': 100
                }
            )
        except Exception as e:
            logger.error(f"Error consultando productos: {e}")
            return []