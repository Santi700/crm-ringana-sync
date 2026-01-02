# sync_sf.py
import os
import sys
import hashlib

# 🔧 Asegurar que se puede importar app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# --------------------------------------------------
# 🌍 Variables de entorno Salesforce
# --------------------------------------------------
SF_USERNAME = (os.getenv("SF_USERNAME") or "").strip()
SF_PASSWORD = (os.getenv("SF_PASSWORD") or "").strip()
SF_TOKEN    = (os.getenv("SF_TOKEN") or "").strip()
SF_DOMAIN   = (os.getenv("SF_DOMAIN", "login") or "").strip()

if not all([SF_USERNAME, SF_PASSWORD, SF_TOKEN]):
    raise RuntimeError("❌ Faltan variables de entorno Salesforce")

# --------------------------------------------------
# 🔍 Fingerprint seguro (NO muestra secretos)
# --------------------------------------------------
def fp(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:8]

print("DEBUG SF_USERNAME FP:", fp(SF_USERNAME))
print("DEBUG SF_PASSWORD FP:", fp(SF_PASSWORD))
print("DEBUG SF_TOKEN FP:", fp(SF_TOKEN))
print("DEBUG SF_DOMAIN:", SF_DOMAIN)
print("DEBUG PASSWORD LEN:", len(SF_PASSWORD))
print("DEBUG TOKEN LEN:", len(SF_TOKEN))

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

