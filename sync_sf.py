# sync_sf.py
import os
import sys

# 🔧 Asegurar que se puede importar app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# --------------------------------------------------
# 🌍 Variables de entorno Salesforce
# --------------------------------------------------
SF_USERNAME = os.getenv("SF_USERNAME")
SF_PASSWORD = os.getenv("SF_PASSWORD")
SF_TOKEN = os.getenv("SF_TOKEN")

if not SF_USERNAME or not SF_PASSWORD or not SF_TOKEN:
    raise RuntimeError("❌ Faltan variables de entorno Salesforce")

# --------------------------------------------------
# 🚀 Importar lógica principal desde app.py
# --------------------------------------------------
from app import sincronizar_pedidos_pendientes

# --------------------------------------------------
# ▶️ Punto de entrada
# --------------------------------------------------
if __name__ == "__main__":
    print("🚀 Iniciando sincronización automática con Salesforce…")
    sincronizar_pedidos_pendientes()
    print("✅ Sincronización finalizada")
