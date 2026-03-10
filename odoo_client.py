import os
import logging
import requests
from dotenv import load_dotenv

# Carga .env si existe (no afecta producción)
load_dotenv()

logger = logging.getLogger(__name__)


class OdooClient:
    def __init__(self):
        self.url = os.getenv("ODOO_URL")
        self.db = os.getenv("ODOO_DB")
        self.username = os.getenv("ODOO_USER")
        self.password = os.getenv("ODOO_PASS")

        if not all([self.url, self.db, self.username, self.password]):
            logger.error("❌ Variables Odoo faltantes.")
            raise Exception("Credenciales Odoo incompletas")

        self.uid = self._authenticate()

    # ==========================================================
    # JSON RPC BASE
    # ==========================================================

    def _json_rpc(self, service, method, *args):
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": service,
                "method": method,
                "args": args,
            },
            "id": 1,
        }

        try:
            response = requests.post(
                f"{self.url}/jsonrpc",
                json=payload,
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            if "error" in result:
                raise Exception(result["error"])

            return result.get("result")

        except Exception as e:
            logger.error(f"❌ Error JSON-RPC: {e}")
            raise

    # ==========================================================
    # AUTH
    # ==========================================================

    def _authenticate(self):
        uid = self._json_rpc(
            "common",
            "login",
            self.db,
            self.username,
            self.password
        )

        if not uid:
            raise Exception("Autenticación fallida en Odoo.")

        logger.info("✅ Autenticación Odoo exitosa.")
        return uid

    # ==========================================================
    # EXECUTE GENERICO
    # ==========================================================

    def execute(self, model, method, *args, **kwargs):
        return self._json_rpc(
            "object",
            "execute_kw",
            self.db,
            self.uid,
            self.password,
            model,
            method,
            args,
            kwargs
        )

    # ==========================================================
    # PRODUCTOS NUEVOS
    # ==========================================================

    def get_new_products(self, last_id):
        domain = [['id', '>', last_id]]

        try:
            return self.execute(
                'product.template',
                'search_read',
                domain,
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
            logger.error(f"❌ Error consultando productos: {e}")
            return []