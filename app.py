# ==============================================================
# 🌿 CRM RINGANA – Versión unificada 2025 (Parte 1/5)
# ==============================================================

import os
import re
import csv
import json
import time
import base64
import shutil
import imaplib
import email
import sqlite3
import difflib
import threading
import subprocess
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename

# ==============================================================
# 🧼 Normalizar nombres de clientes (evitar duplicados)
# ==============================================================

def normalizar(texto):
    """
    Limpia un nombre para poder detectar duplicados incluso si cambia el orden
    de las palabras, acentos, mayúsculas, etc.
    """
    import unicodedata

    # Quitar acentos
    limpio = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

    # Minusculas + limpiar espacios
    limpio = " ".join(limpio.lower().strip().split())

    # Ordenar palabras (importante para nombres en distinto orden)
    palabras = limpio.split()
    palabras.sort()

    return " ".join(palabras)






# ==============================================================
# 🔍 Buscar cliente existente o crearlo si no existe
# ==============================================================

def obtener_cliente_desde_nombre(conn, nombre_original):
    nombre_original = nombre_original.strip()
    nombre_norm = normalizar(nombre_original)

    # Obtener todos los clientes
    clientes = conn.execute("SELECT * FROM clientes").fetchall()

    # Construir diccionario {normalizado: nombre real}
    mapa_normalizados = {
        normalizar(c["nombre"]): c for c in clientes
    }

    # Buscar coincidencia
    if nombre_norm in mapa_normalizados:
        return mapa_normalizados[nombre_norm]

    # Crear nuevo cliente si no existe
    conn.execute(
        "INSERT INTO clientes (nombre, email, telefono, direccion) VALUES (?, '', '', '')",
        (nombre_original,)
    )
    conn.commit()

    return conn.execute(
        "SELECT * FROM clientes WHERE nombre = ?",
        (nombre_original,)
    ).fetchone()


# ==============================================================
# 🔤 Normalización de nombres (global para todo el CRM)
# ==============================================================

def normalizar(texto):
    """Normaliza nombres para evitar duplicados:
    - Quita acentos
    - Pasa a minúsculas
    - Limpia espacios
    - Ordena palabras (ej: 'Almudena Morales Gomez' == 'Gomez Morales Almudena')
    """
    import unicodedata

    # Quitar acentos
    limpio = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

    # Minúsculas + limpiar espacios
    limpio = " ".join(limpio.lower().strip().split())

    # Ordenar palabras (clave para evitar duplicados por invertir nombre/apellidos)
    palabras = limpio.split()
    palabras.sort()

    return " ".join(palabras)


# ==============================================================
# ⚙️ Configuración persistente (modo de aviso)
# ==============================================================

CONFIG_FILE = "config.json"

def cargar_modo_aviso():
    """Carga el modo de aviso actual desde config.json o usa 'calendario' por defecto."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("MODO_AVISO", "calendario")
    return "calendario"

def guardar_modo_aviso(modo):
    """Guarda el modo de aviso seleccionado en config.json."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"MODO_AVISO": modo}, f, ensure_ascii=False, indent=2)

# ==============================================================
# 🚀 Inicialización de Flask
# ==============================================================

app = Flask(__name__)
app.secret_key = "supersecretkey"

from flask import session

@app.before_request
def activar_admin_por_defecto():
    session["rol"] = "admin"


@app.context_processor
def inyectar_modo_aviso():
    return {"MODO_AVISO": MODO_AVISO}

# 📅 Año actual para layout.html
from datetime import datetime

@app.context_processor
def inject_now():
    return {"current_year": datetime.now().year}

# ==============================================================
# ⚙️ Configuración general
# ==============================================================

MODO_PRUEBAS = False
MODO_AVISO = "calendario"   # 🔒 forzado al iniciar

try:
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump({"MODO_AVISO": MODO_AVISO}, f, indent=2, ensure_ascii=False)
    print(f"💡 Modo de aviso forzado a '{MODO_AVISO}' al iniciar.")
except Exception as e:
    print(f"⚠️ No se pudo escribir config.json: {e}")

# ==============================================================
# ✉️ Configuración de correo y SMS
# ==============================================================

EMAIL_REMITENTE = "santfer848@gmail.com"
EMAIL_PASSWORD = "czqudxlrbvvbzaxy"
DESTINATARIO_SMS_FIJO = "630127490"
CALENDARIO_DESTINO = "Ringana"

# ==============================================================
# 📦 Base de datos
# ==============================================================

DB_NAME = "crm_data.sqlite3"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 🔐 ASEGURAR ESQUEMA SIEMPRE
    asegurar_columna_sf_pedido_id(conn)

    return conn


def asegurar_columna_pedido_id():
    conn = get_db_connection()
    try:
        conn.execute("ALTER TABLE pedidos ADD COLUMN pedido_id_ringana TEXT")
        conn.commit()
        print("🆕 Columna pedido_id_ringana añadida a la tabla pedidos.")
    except:
        # Ya existe, ignorar
        pass
    conn.close()

# Ejecutar al iniciar la app
asegurar_columna_pedido_id()


def init_db():
    """Crea las tablas base si no existen."""
    conn = get_db_connection()

    # Clientes
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT,
            telefono TEXT,
            direccion TEXT
        )
    """)

    # Pedidos
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            fecha TEXT,
            producto TEXT,
            regalo TEXT,
            fecha_inicio_producto TEXT,
            interes TEXT,
            puntos REAL,
            total REAL,
            aviso_7dias INTEGER DEFAULT 0,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        )
    """)

    # Productos
    conn.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            categoria TEXT,
            precio REAL
        )
    """)

    # Correos procesados (para evitar duplicados)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emails_procesados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE,
            fecha_procesado TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada correctamente.")


init_db()

def asegurar_columna_sf_pedido_id(conn):
    cursor = conn.cursor()
    cursor.execute("""
        PRAGMA table_info(pedidos)
    """)
    columnas = [col[1] for col in cursor.fetchall()]

    if "sf_pedido_id" not in columnas:
        print("🛠️ Añadiendo columna sf_pedido_id a pedidos...")
        cursor.execute("""
            ALTER TABLE pedidos
            ADD COLUMN sf_pedido_id TEXT
        """)
        conn.commit()


def asegurar_columna_sf_pedido_id(conn):
    cursor = conn.execute("PRAGMA table_info(pedidos)")
    columnas = [col[1] for col in cursor.fetchall()]

    if "sf_pedido_id" not in columnas:
        print("🛠️ Añadiendo columna sf_pedido_id a pedidos...")
        conn.execute("ALTER TABLE pedidos ADD COLUMN sf_pedido_id TEXT")
        conn.commit()


# ==============================================================
# 👥 Inicialización de usuarios CRM
# ==============================================================

def init_users():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            rol TEXT DEFAULT 'usuario',
            activo INTEGER DEFAULT 1
        )
    """)
    conn.commit()

    conn.execute("""
        INSERT OR IGNORE INTO usuarios (nombre, email, rol)
        VALUES 
            ('Almudena Morales', 'amghenar@hotmail.com', 'usuario'),
            ('Santiago Fernández', 'santfer848@gmail.com', 'admin')
    """)
    conn.commit()
    conn.close()
    print("✅ Usuarios CRM inicializados correctamente.")

init_users()


import unicodedata

def normalizar(texto):
    """Convierte un nombre a formato comparable: sin acentos, minúsculas y sin dobles espacios."""
    if not texto:
        return ""
    # Quitar acentos
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    # Pasar a minúsculas
    texto = texto.lower().strip()
    # Unificar espacios
    texto = re.sub(r"\s+", " ", texto)
    return texto

def generar_diccionario_clientes_norm():
    conn = get_db_connection()
    clientes = conn.execute("SELECT nombre FROM clientes").fetchall()
    conn.close()

    dic = {}
    for c in clientes:
        norm = normalizar(c["nombre"])
        dic[norm] = c["nombre"]
    return dic


# ==============================================================
# ✉️ Enviar correo automático
# ==============================================================

def enviar_correo(destinatario, asunto, mensaje):
    """Envía un correo de aviso o prueba."""
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_REMITENTE
        msg["To"] = destinatario
        msg["Subject"] = asunto
        msg.attach(MIMEText(mensaje, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_REMITENTE, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f"✅ Correo enviado correctamente a {destinatario}")

    except Exception as e:
        print(f"⚠️ Error enviando correo: {e}")

# ==============================================================
# 💬 Enviar SMS desde Mac (AppleScript)
# ==============================================================

def enviar_sms_desde_mac(numero, mensaje):
    """Envía SMS usando la app Mensajes enlazada al iPhone."""
    try:
        subprocess.run([
            "osascript",
            "/Users/santi/Desktop/ringana_sms_desktop.scpt",
            str(numero),
            mensaje
        ], check=True)
        print(f"✅ SMS enviado correctamente a {numero}")
    except Exception as e:
        print(f"⚠️ Error enviando SMS desde Mac: {e}")

# ==============================================================
# Conexion + funciones 
# ==============================================================

from simple_salesforce import Salesforce, SalesforceMalformedRequest

SF_USERNAME = "editiondeveloper@salesforce.com"
SF_PASSWORD = "Ringana2025"
SF_TOKEN = "UIeowZodqc1SiuUq5DUjuxLa"
SF_DOMAIN = "login"   # ⚠️ Producción, NO sandbox

# Conexión a Salesforce
sf = Salesforce(
    username=SF_USERNAME,
    password=SF_PASSWORD,
    security_token=SF_TOKEN,
    domain=SF_DOMAIN
)


# ==============================================================
# 🔵 CREAR / ACTUALIZAR CONTACTO EN SALESFORCE (VERSIÓN FINAL)
# ==============================================================

def upsert_contact(nombre, email, telefono, external_id):
    print("\n🔵 upsert_contact() llamado")
    print("📌 Datos recibidos:", nombre, email, telefono, external_id)

    # --- Separar nombre y apellidos ---
    try:
        partes = nombre.strip().split()
        if len(partes) == 1:
            first_name = partes[0]
            last_name = "Cliente"
        else:
            first_name = partes[0]
            last_name = " ".join(partes[1:])
    except:
        first_name = nombre or "SinNombre"
        last_name = "Cliente"

    # --- Body sin external ID ---
    data = {
        "FirstName": first_name,
        "LastName": last_name,
        "Email": email,
        "Phone": telefono or ""
    }

    try:
        # Intentar upsert
        result = sf.Contact.upsert(f"External_Id__c/{external_id}", data)
        print("🔹 Resultado upsert contacto:", result)

        # Si Salesforce devuelve dict → OK
        if isinstance(result, dict) and "id" in result:
            return result["id"]

        # Si devuelve solo 200 → recuperar el contacto con una consulta
        print("⚠️ Salesforce devolvió solo código 200, recuperando ID...")

        query = f"SELECT Id FROM Contact WHERE External_Id__c = '{external_id}' LIMIT 1"
        res = sf.query(query)

        if res["records"]:
            contact_id = res["records"][0]["Id"]
            print("✅ Contacto encontrado por external id:", contact_id)
            return contact_id

        print("❌ No se pudo recuperar el contacto aunque Salesforce devolvió 200")
        return None

    except Exception as e:
        print(f"❌ ERROR al crear/actualizar Contacto: {e}")
        print("⚠️ Detalle del error:", getattr(e, "content", "Sin más info"))
        return None








def upsert_pedido(contact_id, pedido):
    print("\n🟠 upsert_pedido() llamado")
    print("📌 contact_id recibido:", contact_id)
    print("📌 pedido recibido:", pedido)

    data = {
        "Contact__c": contact_id,
        "Fecha_del_Pedido__c": pedido["fecha"],
        "Total__c": float(pedido["total"]),
        "Puntos__c": float(pedido.get("puntos", 0)),
        "Productos__c": pedido.get("productos", ""),
        "Regalo__c": pedido.get("regalo", "")
    }   


    try:
        result = sf.Pedido_Ringana__c.upsert(
            f"ID_Ringana__c/{pedido['id_ringana']}",
            data
        )

        if isinstance(result, dict) and "id" in result:
            return result["id"]

        # Recuperar ID si Salesforce devolvió solo 200
        res = sf.query(
            f"SELECT Id FROM Pedido_Ringana__c WHERE ID_Ringana__c = '{pedido['id_ringana']}' LIMIT 1"
        )
        if res["records"]:
            return res["records"][0]["Id"]

        return None

    except Exception as e:
        print("❌ ERROR AL ENVIAR PEDIDO A SALESFORCE")
        print("❗ EXCEPCIÓN:", e)
        if hasattr(e, "content"):
            print("⚠️ Detalle API:", e.content)
        return None
    
def normalizar_email(email):
    """
    Normaliza emails para usarlos como External ID en Salesforce.
    Devuelve None si el email no es válido.
    """
    if not email:
        return None

    email = email.strip().lower()

    if "@" not in email:
        return None

    return email




   


def procesar_pedido(pedido):
    print("🔥 procesar_pedido() ha sido llamado")
    print("📦 Pedido recibido:", pedido)

    email_normalizado = normalizar_email(pedido.get("cliente_email"))

    if not email_normalizado:
        raise Exception("❌ El pedido no tiene email válido. No se puede sincronizar.")

    contacto_id = upsert_contact(
        nombre=pedido["cliente_nombre"],
        email=email_normalizado,
        telefono=pedido.get("cliente_telefono", ""),
        external_id=email_normalizado  # 🔑 SIEMPRE ESTE
    )

    print("🧩 Contacto creado/actualizado:", contacto_id)

    pedido_id = upsert_pedido(contacto_id, pedido)
    print("🧾 Pedido creado/actualizado:", pedido_id)

    return pedido_id



def procesar_pedido_sf(pedido):
    print("\n🟠 procesar_pedido_sf() llamado")
    print("📌 Pedido recibido:", pedido)

    # 1️⃣ Asegurar email (OPCIÓN B)
    email = pedido.get("cliente_email")
    if not email or "@" not in email:
        email = f"sin-email-{pedido['id_ringana']}@fake.local"
        print(f"⚠️ Email no válido. Usando email ficticio: {email}")

    # 2️⃣ Upsert contacto
    contact_id = upsert_contact(
        nombre=pedido["cliente_nombre"],
        email=email,
        telefono=pedido.get("cliente_telefono", ""),
        external_id=email
    )

    if not contact_id:
        print("❌ Contacto inválido. Pedido cancelado.")
        return None

    # 3️⃣ Datos del pedido (SIN Name)
    data = {
        "Contact__c": contact_id,
        "Fecha_del_Pedido__c": pedido["fecha"],
        "Total__c": float(pedido.get("total") or 0),
        "Puntos__c": float(pedido.get("puntos") or 0),
        "Productos__c": pedido.get("productos", ""),
        "Regalo__c": pedido.get("regalo", ""),
    }

    try:
        sf.Pedido_Ringana__c.upsert(
            f"ID_Ringana__c/{pedido['id_ringana']}",
            data
        )

        # 4️⃣ 🔑 RECUPERAR EL ID SIEMPRE
        res = sf.query(
            f"SELECT Id FROM Pedido_Ringana__c WHERE ID_Ringana__c = '{pedido['id_ringana']}' LIMIT 1"
        )

        if res["records"]:
            pedido_sf_id = res["records"][0]["Id"]
            print(f"✅ Pedido Salesforce ID: {pedido_sf_id}")
            return pedido_sf_id

        print("❌ Pedido creado pero no se pudo recuperar el ID")
        return None

    except Exception as e:
        print("❌ ERROR enviando pedido a Salesforce")
        print("❗", e)
        print("⚠️ API:", getattr(e, "content", ""))
        return None







# ==============================================================
# 🗓️ Crear archivo .ics (para exportar)
# ==============================================================

def crear_evento_calendario(pedido, cliente):
    """Genera un archivo .ics compatible con Apple Calendar."""
    # 🛑 NO CREAR AVISO PARA Almudena Morales Gomez
    if cliente["nombre"].strip().lower() == "almudena morales gomez":
        print("🔕 Aviso NO generado (cliente excluido): Almudena Morales Gomez")
        return None

    try:
        avisos_dir = os.path.join("static", "avisos")
        os.makedirs(avisos_dir, exist_ok=True)

        fecha_pedido = datetime.strptime(pedido["fecha"], "%Y-%m-%d")
        fecha_aviso = fecha_pedido + timedelta(days=7)

        ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//CRM Ringana//ES
BEGIN:VEVENT
SUMMARY:Seguimiento {cliente['nombre']}
DTSTART:{fecha_aviso.strftime('%Y%m%dT090000Z')}
DTEND:{fecha_aviso.strftime('%Y%m%dT100000Z')}
DESCRIPTION:Producto: {pedido['producto']} | Total: {pedido['total']}€
END:VEVENT
END:VCALENDAR
"""
        ruta = os.path.join(avisos_dir, f"pedido_{pedido['id']}.ics")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(ics)
        print(f"✅ Archivo .ics generado: {ruta}")
        return ruta
    except Exception as e:
        print(f"⚠️ Error creando archivo .ics: {e}")

# ==============================================================
# 🗓️ Agregar evento al calendario de macOS
# ==============================================================

def agregar_evento_calendario_mac(cliente, pedido):
    """Crea un evento en el calendario de macOS “Ringana”."""
    try:
        fecha_pedido = datetime.strptime(pedido["fecha"], "%Y-%m-%d")
        fecha_aviso = fecha_pedido + timedelta(days=7)

        descripcion = (
            f"Cliente: {cliente['nombre']}\\n"
            f"Producto: {pedido['producto']}\\n"
            f"Total: {pedido['total']}€"
        )

        applescript = f"""
        tell application "Calendar"
            set calName to "{CALENDARIO_DESTINO}"
            if not (exists calendar calName) then
                make new calendar with properties {{name:calName}}
            end if

            set fechaAviso to current date
            set fechaAviso to fechaAviso + (({(fecha_aviso - datetime.now()).days}) * days)
            tell calendar calName
                set nuevoEvento to make new event with properties {{summary:"🌿 Seguimiento {cliente['nombre']}", start date:fechaAviso, end date:fechaAviso + 1 * hours, description:"{descripcion}"}}
                tell nuevoEvento
                    make new display alarm at end with properties {{trigger interval:-900}}
                end tell
            end tell
        end tell
        """
        subprocess.run(["osascript", "-e", applescript], check=True)
        print(f"🗓️ Evento añadido al calendario '{CALENDARIO_DESTINO}' ({fecha_aviso.date()})")
    except Exception as e:
        print(f"⚠️ Error al agregar evento: {e}")

# ==============================================================
# 🧹 Limpieza de eventos antiguos en el calendario
# ==============================================================

def limpiar_eventos_antiguos_ringana():
    """Elimina eventos antiguos de más de 5 días."""
    print("🧼 Buscando eventos antiguos de Ringana para eliminar...")
    try:
        fecha_limite = (datetime.now() - timedelta(days=5)).strftime("%d/%m/%Y %H:%M:%S")

        applescript = f'''
        set fecha_limite to date "{fecha_limite}"
        set deletedCount to 0
        tell application "Calendar"
            set ringanaCalendars to every calendar whose name contains "Ringana"
            repeat with c in ringanaCalendars
                tell c
                    set oldEvents to every event whose start date < fecha_limite
                    repeat with e in oldEvents
                        if (summary of e starts with "🌿 Seguimiento") then
                            delete e
                            set deletedCount to deletedCount + 1
                        end if
                    end repeat
                end tell
            end repeat
        end tell
        return deletedCount
        '''
        result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True)
        count = result.stdout.strip()
        print(f"✅ Limpieza completada: 🗑️ {count} eventos eliminados")
    except Exception as e:
        print(f"⚠️ Error al limpiar eventos antiguos: {e}")
# ==============================================================
# 🏠 Página principal (lista de clientes y pedidos)
# ==============================================================

@app.route("/")
def index():
    conn = get_db_connection()
    hoy = datetime.now().date()
    pedidos = conn.execute("SELECT * FROM pedidos WHERE aviso_7dias = 0").fetchall()

    for pedido in pedidos:
        try:
            fecha_pedido = datetime.strptime(pedido["fecha"], "%Y-%m-%d").date()
        except Exception:
            continue

        dias = (hoy - fecha_pedido).days
        print(f"➡️ Pedido {pedido['id']} ({pedido['fecha']}) — {dias} días atrás")

        if dias >= 7:

            # Obtener cliente asociado al pedido
            cliente = conn.execute(
                "SELECT * FROM clientes WHERE id = ?",
                (pedido["cliente_id"],)
            ).fetchone()

            # Si el cliente no existe → saltar
            if cliente is None:
                print(f"⚠️ Cliente no encontrado para pedido {pedido['id']}. Saltando…")
                continue

            # 🛑 EXCLUSIÓN: NO CREAR AVISOS PARA ALMUDENA MORALES GOMEZ
            nombre_normalizado = cliente["nombre"].strip().lower()
            if nombre_normalizado == "almudena morales gomez":
                print(f"⏭️ Aviso omitido para {cliente['nombre']}")
                continue

            # Crear evento calendario
            agregar_evento_calendario_mac(cliente, pedido)

            # Marcar como avisado
            conn.execute(
                "UPDATE pedidos SET aviso_7dias = 1 WHERE id = ?",
                (pedido["id"],)
            )
            conn.commit()

    # Limpiar eventos antiguos
    limpiar_eventos_antiguos_ringana()

    clientes = conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
    conn.close()

    return render_template("clientes.html", clientes=clientes)


# ==============================================================
# ➕ Nuevo cliente
# ==============================================================

@app.route("/nuevo_cliente", methods=["GET", "POST"])
def nuevo_cliente():
    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        email = request.form["email"].strip()
        telefono = request.form["telefono"].strip()
        direccion = request.form["direccion"].strip()

        if not nombre:
            flash("⚠️ El nombre es obligatorio.", "warning")
            return redirect(request.url)

        conn = get_db_connection()
        conn.execute("INSERT INTO clientes (nombre, email, telefono, direccion) VALUES (?, ?, ?, ?)",
                     (nombre, email, telefono, direccion))
        conn.commit()
        conn.close()

        flash("✅ Cliente agregado correctamente.", "success")
        return redirect(url_for("index"))
    return render_template("nuevo_cliente.html")

# ==============================================================
# ✏️ Editar cliente
# ==============================================================

@app.route("/editar_cliente/<int:cliente_id>", methods=["GET", "POST"])
def editar_cliente(cliente_id):
    conn = get_db_connection()
    cliente = conn.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()

    if not cliente:
        flash("⚠️ Cliente no encontrado.", "warning")
        conn.close()
        return redirect(url_for("index"))

    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        email = request.form["email"].strip()
        telefono = request.form["telefono"].strip()
        direccion = request.form["direccion"].strip()

        conn.execute("""
            UPDATE clientes
            SET nombre = ?, email = ?, telefono = ?, direccion = ?
            WHERE id = ?
        """, (nombre, email, telefono, direccion, cliente_id))
        conn.commit()
        conn.close()
        flash("✅ Cliente actualizado correctamente.", "success")
        return redirect(url_for("index"))

    conn.close()
    return render_template("editar_cliente.html", cliente=cliente)

# ==============================================================
# 🗑️ Eliminar cliente
# ==============================================================

@app.route("/cliente/eliminar/<int:cliente_id>", methods=["POST"])
def eliminar_cliente(cliente_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM pedidos WHERE cliente_id = ?", (cliente_id,))
    conn.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
    conn.commit()
    conn.close()
    flash("🗑️ Cliente y sus pedidos eliminados.", "success")
    return redirect(url_for("index"))

@app.route("/cambiar_modo_aviso", methods=["POST"])
def cambiar_modo_aviso():
    nuevo_modo = request.form.get("modo_aviso", "calendario")

    # Guardar en archivo
    guardar_modo_aviso(nuevo_modo)

    # Actualizar variable global
    global MODO_AVISO
    MODO_AVISO = nuevo_modo

    flash(f"🔔 Modo de aviso cambiado a: {nuevo_modo}", "success")
    return redirect(url_for("index"))

@app.route("/eliminar_clientes", methods=["POST"])
def eliminar_clientes():
    ids = request.form.getlist("cliente_ids")

    if not ids:
        flash("⚠️ No has seleccionado ningún cliente.", "warning")
        return redirect(url_for("index"))

    conn = get_db_connection()

    for cid in ids:
        conn.execute("DELETE FROM pedidos WHERE cliente_id = ?", (cid,))
        conn.execute("DELETE FROM clientes WHERE id = ?", (cid,))

    conn.commit()
    conn.close()

    flash(f"🗑️ {len(ids)} cliente(s) eliminados correctamente.", "success")
    return redirect(url_for("index"))

@app.route("/ver_productos")
def ver_productos():
    conn = get_db_connection()
    productos = conn.execute("SELECT * FROM productos ORDER BY nombre").fetchall()
    conn.close()
    return render_template("productos.html", productos=productos)

@app.route("/nuevo_producto", methods=["GET", "POST"])
def nuevo_producto():
    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        categoria = request.form.get("categoria", "").strip()
        precio = request.form.get("precio", "0").replace(",", ".").strip()

        if not nombre:
            flash("⚠️ El nombre del producto es obligatorio.", "warning")
            return redirect(request.url)

        try:
            precio = float(precio)
        except:
            precio = 0.0

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO productos (nombre, categoria, precio)
            VALUES (?, ?, ?)
        """, (nombre, categoria, precio))
        conn.commit()
        conn.close()

        flash("✅ Producto añadido correctamente.", "success")
        return redirect(url_for("ver_productos"))

    return render_template("nuevo_producto.html")

@app.route("/editar_producto/<int:id>", methods=["GET", "POST"])
def editar_producto(id):
    conn = get_db_connection()
    producto = conn.execute("SELECT * FROM productos WHERE id = ?", (id,)).fetchone()

    if not producto:
        conn.close()
        flash("⚠️ Producto no encontrado.", "warning")
        return redirect(url_for("ver_productos"))

    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        categoria = request.form.get("categoria", "").strip()
        precio = request.form.get("precio", "0").replace(",", ".").strip()

        if not nombre:
            flash("⚠️ El nombre del producto es obligatorio.", "warning")
            return redirect(request.url)

        try:
            precio = float(precio)
        except:
            precio = 0.0

        conn.execute("""
            UPDATE productos
            SET nombre = ?, categoria = ?, precio = ?
            WHERE id = ?
        """, (nombre, categoria, precio, id))
        conn.commit()
        conn.close()

        flash("✅ Producto actualizado correctamente.", "success")
        return redirect(url_for("ver_productos"))

    conn.close()
    return render_template("editar_producto.html", producto=producto)

@app.route("/eliminar_producto/<int:id>", methods=["POST"])
def eliminar_producto(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM productos WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    flash("🗑️ Producto eliminado correctamente.", "success")
    return redirect(url_for("ver_productos"))





# ==============================================================
# 📦 Pedidos por cliente
# ==============================================================

@app.route("/cliente/<int:cliente_id>/pedidos")
def pedidos_cliente(cliente_id):
    conn = get_db_connection()

    cliente = conn.execute(
        "SELECT * FROM clientes WHERE id = ?", (cliente_id,)
    ).fetchone()

    pedidos_raw = conn.execute(
        "SELECT * FROM pedidos WHERE cliente_id = ? ORDER BY fecha DESC",
        (cliente_id,)
    ).fetchall()

    # Totales
    suma_total = conn.execute(
        "SELECT COALESCE(SUM(total), 0) FROM pedidos WHERE cliente_id = ?",
        (cliente_id,)
    ).fetchone()[0]

    numero_pedidos = conn.execute(
        "SELECT COUNT(*) FROM pedidos WHERE cliente_id = ?",
        (cliente_id,)
    ).fetchone()[0]

    conn.close()

    # Convertir pedidos a diccionarios (para poder modificarlos)
    pedidos = [dict(p) for p in pedidos_raw]

    import re

    # -----------------------------------------------
    # LIMPIEZA DE % + SEPARACIÓN DE REGALOS SAMPLE
    # -----------------------------------------------
    for p in pedidos:

        producto_original = p.get("producto", "") or ""
        partes = [t.strip() for t in producto_original.split(",") if t.strip()]

        productos_limpios = []
        regalos_sample = []

        for item in partes:

            # 🔵 1. Eliminar porcentajes tipo "0,00%"
            item = re.sub(r"\d+,\d+% ?", "", item)

            # 🔵 2. Eliminar códigos Ringana (paréntesis largos)
            item = re.sub(r"\([A-Z0-9\-]{8,}\)", "", item).strip()

            # 🔵 3. Detectar sample → REGALO
            if "sample" in item.lower():
                regalos_sample.append(item)
            else:
                productos_limpios.append(item)

        # Reconstruir campos
        p["producto"] = ", ".join(productos_limpios)

        # Añadir regalos sample al campo REGALO del pedido
        if regalos_sample:
            nuevos_regalos = ", ".join(regalos_sample)

            if p.get("regalo"):
                p["regalo"] = p["regalo"] + ", " + nuevos_regalos
            else:
                p["regalo"] = nuevos_regalos

    # -----------------------------------------------
    # Render final
    # -----------------------------------------------
    return render_template(
        "pedidos_cliente.html",
        cliente=cliente,
        pedidos=pedidos,
        suma_total=suma_total,
        numero_pedidos=numero_pedidos
    )


# ==============================================================
# 📦 Todos los pedidos
# ==============================================================

@app.route("/todos_pedidos")
def todos_pedidos():
    conn = get_db_connection()

    pedidos_raw = conn.execute("""
        SELECT p.*, c.nombre AS cliente_nombre
        FROM pedidos p
        LEFT JOIN clientes c ON p.cliente_id = c.id
        ORDER BY fecha DESC
    """).fetchall()

    conn.close()

    # Convertir para modificar
    pedidos = [dict(p) for p in pedidos_raw]

    import re

    # -----------------------------------------------
    # LIMPIEZA DE % + SEPARACIÓN DE REGALOS SAMPLE
    # -----------------------------------------------
    for p in pedidos:

        producto_original = p.get("producto", "") or ""
        partes = [t.strip() for t in producto_original.split(",") if t.strip()]

        productos_limpios = []
        regalos_sample = []

        for item in partes:

            # 🔵 1. Eliminar porcentajes
            item = re.sub(r"\d+,\d+% ?", "", item)

            # 🔵 2. Eliminar códigos
            item = re.sub(r"\([A-Z0-9\-]{8,}\)", "", item).strip()

            # 🔵 3. Detectar sample
            if "sample" in item.lower():
                regalos_sample.append(item)
            else:
                productos_limpios.append(item)

        # Reconstruir productos
        p["producto"] = ", ".join(productos_limpios)

        # Añadir regalos automáticamente
        if regalos_sample:
            nuevos_regalos = ", ".join(regalos_sample)

            if p.get("regalo"):
                p["regalo"] = p["regalo"] + ", " + nuevos_regalos
            else:
                p["regalo"] = nuevos_regalos

    return render_template("todos_pedidos.html", pedidos=pedidos)




@app.route("/editar_pedido/<int:pedido_id>", methods=["GET", "POST"])
def editar_pedido(pedido_id):
    conn = get_db_connection()
    pedido = conn.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()

    if not pedido:
        conn.close()
        flash("⚠️ Pedido no encontrado.", "warning")
        return redirect(url_for("index"))

    cliente = conn.execute(
        "SELECT * FROM clientes WHERE id = ?",
        (pedido["cliente_id"],)
    ).fetchone()

    if request.method == "POST":
        fecha = request.form["fecha"]
        producto = request.form["producto"]
        regalo = request.form.get("regalo", "")
        interes = request.form.get("interes", "")

        # Capturar fecha inicio producto
        fecha_inicio_producto = request.form.get("fecha_inicio_producto", "").strip()

        # Valores seguros para evitar ValueError
        puntos_raw = request.form.get("puntos", "").strip()
        total_raw = request.form.get("total", "").strip()

        puntos = float(puntos_raw) if puntos_raw else 0.0
        total = float(total_raw) if total_raw else 0.0

        # Checkbox aviso
        aviso_7dias = 1 if "aviso_7dias" in request.form else 0

        conn.execute("""
            UPDATE pedidos
            SET fecha = ?, producto = ?, regalo = ?, fecha_inicio_producto = ?,
                interes = ?, puntos = ?, total = ?, aviso_7dias = ?
            WHERE id = ?
        """, (fecha, producto, regalo, fecha_inicio_producto,
              interes, puntos, total, aviso_7dias, pedido_id))

        conn.commit()
        conn.close()

        flash("✏️ Pedido actualizado correctamente.", "success")
        return redirect(url_for("pedidos_cliente", cliente_id=cliente["id"]))

    conn.close()
    return render_template("editar_pedido.html", pedido=pedido, cliente=cliente)


@app.route("/eliminar_pedido/<int:pedido_id>", methods=["POST"])
def eliminar_pedido(pedido_id):
    conn = get_db_connection()

    # Obtener pedido para saber a qué cliente pertenece
    pedido = conn.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()

    if not pedido:
        conn.close()
        flash("⚠️ Pedido no encontrado.", "warning")
        return redirect(url_for("index"))

    cliente_id = pedido["cliente_id"]

    # Eliminar el pedido
    conn.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))
    conn.commit()
    conn.close()

    flash("🗑️ Pedido eliminado correctamente.", "success")
    return redirect(url_for("pedidos_cliente", cliente_id=cliente_id))


@app.route("/limpiar_porcentajes")
def limpiar_porcentajes():
    import re

    conn = get_db_connection()
    pedidos = conn.execute("SELECT id, producto FROM pedidos").fetchall()

    for p in pedidos:
        if p["producto"]:
            limpio = re.sub(r"\d+,\d+% ?", "", p["producto"]).strip()
            conn.execute("UPDATE pedidos SET producto = ? WHERE id = ?", (limpio, p["id"]))

    conn.commit()
    conn.close()

    return "✔️ Limpieza completada. Todos los porcentajes eliminados."

@app.route("/limpiar_importe_iva")
def limpiar_importe_iva():
    import re

    conn = get_db_connection()
    pedidos = conn.execute("SELECT id, producto FROM pedidos").fetchall()

    for p in pedidos:
        prod = p["producto"] or ""

        # Eliminar cualquier variante:
        # - Importe incl. IVA
        # - Importe incl IVA
        # - Importe del IVA
        # - con o sin EUROS detrás
        prod_limpio = re.sub(
            r"(importe\s+incl\.?\s*iva.*?$)|(importe\s+del\s+iva.*?$)",
            "",
            prod,
            flags=re.IGNORECASE
        ).strip(" ,")

        conn.execute(
            "UPDATE pedidos SET producto = ? WHERE id = ?",
            (prod_limpio, p["id"])
        )

    conn.commit()
    conn.close()

    flash("🧼 Eliminado cualquier texto relacionado con 'Importe IVA' de todos los productos.", "success")
    return redirect(url_for("index"))



# ==============================================================
# ➕ Nuevo pedido
# ==============================================================

import re

def to_float(valor):
    """Convierte valores vacíos o inválidos a 0.0"""
    try:
        return float(valor.replace(",", "."))
    except:
        return 0.0


@app.route("/nuevo_pedido/<int:cliente_id>", methods=["GET", "POST"])
def nuevo_pedido(cliente_id):
    conn = get_db_connection()
    cliente = conn.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
    conn.close()

    if not cliente:
        flash("⚠️ Cliente no encontrado.", "warning")
        return redirect(url_for("index"))

    if request.method == "POST":
        fecha = request.form.get("fecha", "")
        producto = request.form.get("productos_seleccionados", "").strip()

        # 🔥 Limpieza automática → eliminar 00% o porcentajes de cualquier tipo
        producto = re.sub(r"\d+,\d+% ?", "", producto).strip()

        regalo = request.form.get("regalo", "")
        interes = request.form.get("interes", "")
        puntos = to_float(request.form.get("puntos", "0"))
        total = to_float(request.form.get("total", "0"))

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO pedidos (cliente_id, fecha, producto, regalo, interes, puntos, total)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cliente_id, fecha, producto, regalo, interes, puntos, total))

        conn.commit()
        conn.close()

        flash("✅ Pedido añadido correctamente.", "success")
        return redirect(url_for("pedidos_cliente", cliente_id=cliente_id))

    return render_template("nuevo_pedido.html", cliente=cliente)



# ==============================================================
# 📄 Detalle de un pedido
# ==============================================================

@app.route("/pedido/<int:pedido_id>")
def pedido_detalle(pedido_id):

    conn = get_db_connection()
    pedido_raw = conn.execute(
        "SELECT * FROM pedidos WHERE id = ?", (pedido_id,)
    ).fetchone()
    conn.close()

    if not pedido_raw:
        return "Pedido no encontrado", 404

    pedido = dict(pedido_raw)

    import re

    # ------------------------------------------
    # LIMPIEZA DE PRODUCTO + DETECCIÓN DE SAMPLE
    # ------------------------------------------
    producto_original = pedido.get("producto", "") or ""

    partes = [t.strip() for t in producto_original.split(",") if t.strip()]

    productos_limpios = []
    regalos_sample = []

    for item in partes:

        # 1. Eliminar porcentajes
        item = re.sub(r"\d+,\d+% ?", "", item)

        # 2. Eliminar códigos tipo (S9GJ-KFJHLZ-GXLQ)
        item = re.sub(r"\([A-Z0-9\-]{8,}\)", "", item).strip()

        # 3. Clasificar si es sample → regalo
        if "sample" in item.lower():
            regalos_sample.append(item)
        else:
            productos_limpios.append(item)

    # Guardar producto limpio
    pedido["producto"] = ", ".join(productos_limpios)

    # Regalo automático
    if regalos_sample:
        nuevos = ", ".join(regalos_sample)
        if pedido.get("regalo"):
            pedido["regalo"] = pedido["regalo"] + ", " + nuevos
        else:
            pedido["regalo"] = nuevos

    return render_template("pedido_detalle.html", pedido=pedido)



# ==============================================================
# 🔍 Buscar pedidos por producto
# ==============================================================

@app.route("/buscar_producto")
def buscar_producto():
    query = request.args.get("q", "").strip()
    conn = get_db_connection()
    if query:
        resultados = conn.execute("""
            SELECT p.id, p.fecha, p.producto, c.nombre AS cliente, p.total
            FROM pedidos p
            JOIN clientes c ON c.id = p.cliente_id
            WHERE LOWER(p.producto) LIKE LOWER(?)
            ORDER BY p.fecha DESC
        """, (f"%{query}%",)).fetchall()
    else:
        resultados = []
    conn.close()
    return render_template("buscar_producto.html", resultados=resultados, query=query)

from email.header import decode_header

def texto_header(valor):
    """Convierte un header (Subject/From) en texto seguro."""
    if not valor:
        return ""
    try:
        partes = decode_header(valor)
        texto, cod = partes[0]
        if isinstance(texto, bytes):
            return texto.decode(cod or "utf-8", errors="ignore")
        return texto
    except:
        return str(valor)

# ==============================================================
# 📬 Revisión automática de correos desde Gmail (IMAP)
# ==============================================================

GMAIL_USER = "santfer848@gmail.com"
GMAIL_PASS = "dyxtsxyzbwvwmdpq"   # contraseña de aplicación correcta
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993


def revisar_correos():
    """Lee correos NO leídos de Gmail y procesa pedidos Ringana."""

    try:
        print("📨 Revisando nuevos correos en Gmail...")

        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(GMAIL_USER, GMAIL_PASS)

        # 1️⃣ Seleccionar la carpeta INBOX
        status, _ = mail.select("INBOX")

        if status != "OK":
            print("❌ Error al abrir INBOX")
            return

        # 2️⃣ Buscar SOLO correos NO leídos
        status, data = mail.search(None, '(UNSEEN)')

        if status != "OK":
            print("❌ Error buscando correos.")
            return

        mail_ids = data[0].split()

        if not mail_ids:
            print("📭 No hay nuevos correos.")
            return

        print(f"🔍 {len(mail_ids)} correos nuevos encontrados. Procesando...\n")

        for num in mail_ids:
            _, msg_data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            asunto = (msg["subject"] or "").lower()
            cuerpo = ""

            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        cuerpo += part.get_payload(decode=True).decode(errors="ignore")
            else:
                cuerpo = msg.get_payload(decode=True).decode(errors="ignore")

            # -----------------------------------------
            # 📦 ¿Es correo con pedido Ringana?
            # -----------------------------------------
            if (
                "ringana" in asunto
                or "pedido" in asunto
                or "order" in asunto
                or "pedido" in cuerpo.lower()
            ):
                print("🧾 Pedido detectado. Procesando...")
                procesar_pedido_ringana(cuerpo)
            else:
                print("➡️ Correo ignorado:", asunto)

            # 4️⃣ Marcar como leído SIEMPRE
            mail.store(num, '+FLAGS', '\\Seen')

        mail.close()
        mail.logout()
        print("✅ Revisión Gmail completada correctamente.\n")

    except Exception as e:
        print(f"❌ Error revisando Gmail: {e}")








        import unicodedata

def normalizar(nombre):
    """Normaliza nombres eliminando tildes, espacios,
       pasando a minúsculas y ordenando las palabras."""
    
    # Quitar tildes
    nombre = ''.join(
        c for c in unicodedata.normalize("NFD", nombre)
        if unicodedata.category(c) != "Mn"
    )

    # Minúsculas
    nombre = nombre.lower().strip()

    # Quitar caracteres raros
    for ch in [",", ".", "(", ")", ";", ":"]:
        nombre = nombre.replace(ch, " ")

    # Eliminar múltiples espacios
    palabras = [p for p in nombre.split() if p]

    # Ordenar palabras → CLAVE para evitar duplicados
    palabras_ordenadas = sorted(palabras)



    return " ".join(palabras_ordenadas)



def procesar_pedido_ringana(cuerpo_email, id_pedido_ringana=None):
    import re
    import unicodedata
    import difflib

    conn = get_db_connection()

    # -----------------------------------------
    # 1️⃣ Extraer fecha del pedido
    # -----------------------------------------
    fecha_match = re.search(r"Fecha:\s*(\d{2}\.\d{2}\.\d{4})", cuerpo_email)
    if fecha_match:
        fecha_pedido = datetime.strptime(fecha_match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
    else:
        fecha_pedido = datetime.now().strftime("%Y-%m-%d")

    # -----------------------------------------
    # 2️⃣ Separar pedidos del correo (MEJORADO)
    #    - Si no encuentra ninguno, tratamos TODO el correo como 1 pedido
    # -----------------------------------------
    partes = re.split(r"(?im)^\s*pedido\s+([A-Z0-9\-]+)\s*$", cuerpo_email)
    num_pedidos = len(partes) // 2
    print(f"📄 Se detectaron {num_pedidos} pedidos en este correo.")

    if num_pedidos == 0:
        # Modo “fallback”: 1 correo = 1 pedido
        print("ℹ️ No se encontró 'pedido XXX' al inicio de ninguna línea; "
              "procesaré TODO el correo como un solo pedido.")
        partes = ["", "", cuerpo_email]

    for idx in range(1, len(partes), 2):

        id_detectado = partes[idx].strip()
        bloque = partes[idx + 1]

        # Si no hemos detectado ID en el cuerpo, usamos el que venga como parámetro (si existe)
        if not id_detectado and id_pedido_ringana:
            id_detectado = id_pedido_ringana

        print(f"\n📦 Procesando pedido {id_detectado or '(sin ID)'}")

        # -----------------------------------------
        # 3️⃣ Buscar nombre del cliente
        # -----------------------------------------
        lineas = bloque.splitlines()
        cliente_nombre = None

        for i, linea in enumerate(lineas):
            if "Dirección de facturación" in linea:

                posible = linea.replace("Dirección de facturación:", "").strip()
                if posible and not re.search(r"\d", posible):
                    cliente_nombre = posible
                    break

                if i + 1 < len(lineas):
                    siguiente = lineas[i + 1].strip()
                    if siguiente and not re.search(r"\d", siguiente):
                        cliente_nombre = siguiente
                    break

        if not cliente_nombre:
            print("⚠️ No se pudo extraer nombre del cliente. Pedido ignorado.")
            continue

        # -----------------------------------------
        # 4️⃣ Normalizar y buscar cliente existente
        # -----------------------------------------
        def normalizar(nombre):
            nombre = ''.join(
                c for c in unicodedata.normalize("NFD", nombre)
                if unicodedata.category(c) != "Mn"
            )
            nombre = nombre.lower().strip()
            for ch in [",", ".", "(", ")", ";", ":"]:
                nombre = nombre.replace(ch, " ")
            palabras = sorted([p for p in nombre.split() if p])
            return " ".join(palabras)

        cliente_normal = normalizar(cliente_nombre)

        clientes_db = conn.execute("SELECT nombre FROM clientes").fetchall()
        mapa = {normalizar(c["nombre"]): c["nombre"] for c in clientes_db}

        match = difflib.get_close_matches(cliente_normal, mapa.keys(), n=1, cutoff=0.8)

        if match:
            cliente_final = mapa[match[0]]
        else:
            conn.execute("INSERT INTO clientes (nombre) VALUES (?)", (cliente_nombre,))
            conn.commit()
            cliente_final = cliente_nombre

        cliente = conn.execute(
            "SELECT * FROM clientes WHERE nombre=?",
            (cliente_final,)
        ).fetchone()

        # -----------------------------------------
        # 5️⃣ Evitar duplicado por ID Ringana (si tenemos id_detectado)
        # -----------------------------------------
        if id_detectado:
            repetido = conn.execute(
                "SELECT id FROM pedidos WHERE pedido_id_ringana=?",
                (id_detectado,)
            ).fetchone()
            if repetido:
                print(f"⏭️ Pedido {id_detectado} ya existe en SQLite. Omitido.")
                continue

        # -----------------------------------------
        # 6️⃣ EXTRAER PRODUCTOS — NUEVA LÓGICA COMPLETA
        # -----------------------------------------
        productos = []

        for linea in bloque.splitlines():
            linea = linea.strip()
            if not linea:
                continue

            # ❌ Saltar líneas no válidas
            if any(x in linea for x in [
                "Importe incl", "Importe del IVA", "Estatus", "Dirección",
                "Modalidad de pago", "Gastos de envío", "Forma de envío"
            ]):
                continue

            # ✔ Detectar línea de producto Ringana
            m = re.match(r"^([A-Z0-9\-]+)\s+(.+?)\s+EUR\s+([-0-9.,]+)", linea)
            if m:
                codigo = m.group(1)
                nombre = m.group(2).strip()
                precio = m.group(3).strip()
                productos.append((nombre, precio))

        if not productos:
            print("⚠️ No se detectaron productos válidos en este bloque.")
            continue

        # -----------------------------------------
        # 7️⃣ Separar regalos y productos normales
        # -----------------------------------------
        regalo = ""
        productos_limpios = []

        for nombre, precio in productos:

            precio_str = precio.replace(" ", "")

            # SAMPLE → regalo
            if "sample" in nombre.lower():
                regalo += nombre + ", "
                continue

            # Precio negativo → regalo
            if precio_str.startswith("-"):
                regalo += nombre + ", "
                continue

            productos_limpios.append(nombre)

        productos_texto = ", ".join(productos_limpios)
        regalo = regalo.rstrip(", ")

        # -----------------------------------------
        # 8️⃣ Extraer total del pedido
        # -----------------------------------------
        total_match = re.search(
            r"Importe incl\.? IVA\s*EUR\s*([-0-9.,]+)",
            bloque
        )
        total = float(total_match.group(1).replace(".", "").replace(",", ".")) if total_match else 0.0

        # -----------------------------------------
        # 9️⃣ Evitar duplicados por contenido
        # -----------------------------------------
        repetido = conn.execute("""
            SELECT id FROM pedidos
            WHERE cliente_id=? AND fecha=? AND producto=? AND ABS(total - ?) < 0.01
        """, (cliente["id"], fecha_pedido, productos_texto, total)).fetchone()

        if repetido:
            print(f"⏭️ Pedido duplicado encontrado (mismo cliente, fecha, productos y total). Omitido.")
            continue

        # -----------------------------------------
        # 🔟 GUARDAR PEDIDO EN SQLITE
        # -----------------------------------------
        productos_texto = re.sub(r"\d+,\d+% ?", "", productos_texto).strip()
        productos_texto = productos_texto.replace("Importe incl. IVA", "").strip(" ,")

        conn.execute("""
            INSERT INTO pedidos (cliente_id, fecha, producto, total, regalo, pedido_id_ringana)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            cliente["id"],
            fecha_pedido,
            productos_texto,
            total,
            regalo or None,
            id_detectado
        ))

        conn.commit()

        print(f"✅ Pedido guardado en SQLite: {cliente_final} | {productos_texto} | Total {total} € | Regalo: {regalo}")

        from unidecode import unidecode

        # -----------------------------------------
        # 🔄 11️⃣ ENVIAR AUTOMÁTICAMENTE A SALESFORCE
        # -----------------------------------------

        # 1️⃣ Generar ID Ringana válido (si no existe)
        id_ringana_final = id_detectado or f"MAIL-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 2️⃣ Email seguro para Salesforce (sin acentos, sin espacios, minúsculas)
        email_safe = unidecode(cliente_final.lower().replace(" ", "-"))
        email_final = f"{email_safe}@fake.com"

        pedido_sf = {
            "id_ringana": id_ringana_final,
            "fecha": fecha_pedido,
            "total": total,
            "puntos": 0,
            "productos": productos_texto,
            "regalo": regalo,
            "cliente_nombre": cliente_final,
            "cliente_email": email_final,
            "cliente_telefono": ""
        }

        try:
            procesar_pedido_sf(pedido_sf)
            print("🚀 Pedido enviado a Salesforce correctamente.")
        except Exception as e:
            print("❌ Error al enviar pedido a Salesforce:", e)

        conn.close()




# ==============================================================
# 🧹 Limpieza manual de correos procesados (solo Admin)
# ==============================================================

@app.route("/limpiar_emails_procesados", methods=["POST"])
def limpiar_emails_procesados():
    """Permite al administrador borrar todos los registros de correos ya procesados."""
    try:
        conn = get_db_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emails_procesados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                fecha_procesado TEXT
            )
        """)
        conn.execute("DELETE FROM emails_procesados")
        conn.commit()
        conn.close()
        flash("🧹 Todos los correos procesados han sido eliminados correctamente.", "success")
        print("🧹 Limpieza manual ejecutada por administrador.")
    except Exception as e:
        flash(f"❌ Error al limpiar correos procesados: {e}", "danger")
    return redirect(url_for("index"))


# ==============================================================
# Extraer Productos
# ==============================================================

def extraer_productos_del_bloque(bloque):
    productos = []
    lineas = [l.strip() for l in bloque.splitlines() if l.strip()]

    for linea in lineas:
        m = re.match(r"^([A-Z0-9]+)\s+(.+?)\s+EUR\s+[\d.,]+\s+.+?\s+EUR\s+([\d.,]+)$", linea)
        if m:
            codigo = m.group(1)
            nombre = m.group(2).strip()
            total_str = m.group(3)

            try:
                total = float(total_str.replace(".", "").replace(",", "."))
            except:
                total = 0.0

            productos.append((f"{nombre}", total))

    return productos




# ==============================================================
# 🧾 Revisión manual de correos (Gmail + Hotmail)
# ==============================================================

@app.route("/revisar_correos")
def revisar_correos():
    try:
        revisar_gmail()
        flash("📬 Revisión manual de correos Gmail completada.", "success")
    except Exception as e:
        flash(f"⚠️ Error revisando correos Gmail: {e}", "danger")
    return redirect(url_for("index"))





# ==============================================================
# 📬 Función REAL revisar_hotmail() (NO existía en tu archivo)
# ==============================================================

def revisar_gmail():
    """Lee correos desde Gmail usando IMAP y procesa pedidos Ringana."""
    try:
        print("📨 Revisando Gmail…")

        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(GMAIL_USER, GMAIL_PASS)

        # 1️⃣ Intentar entrar en la carpeta real "Pedidos Ringana"
        status, _ = mail.select('"Pedidos RINGANA"')

        if status == "OK":
            print("📂 Carpeta usada: Pedidos RINGANA")
        else:
            print("⚠️ Carpeta 'Pedidos RINGANA' NO encontrada. Usando INBOX.")
            mail.select("INBOX")

        # 2️⃣ Buscar correos NO leídos
        _, data = mail.search(None, "UNSEEN")
        ids = data[0].split()

        print(f"🔎 Correos NO LEÍDOS ENCONTRADOS: {len(ids)}")

        if not ids:
            print("📭 No hay nuevos correos.")
            return

        for num in ids:
            _, msg_data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            cuerpo = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        cuerpo += part.get_payload(decode=True).decode(errors="ignore")
            else:
                cuerpo = msg.get_payload(decode=True).decode(errors="ignore")

            print("🧾 Procesando un correo…")
            procesar_pedido_ringana(cuerpo)

            # Marcar como leído
            mail.store(num, '+FLAGS', '\\Seen')

        mail.logout()
        print("✅ Revisión Gmail finalizada.")

    except Exception as e:
        print(f"❌ Error leyendo Gmail: {e}")


# ==============================================================
# 🔄 SINCRONIZAR PEDIDOS PENDIENTES CON SALESFORCE
# ==============================================================

def sincronizar_pedidos_pendientes():
    print("\n🔄 Buscando pedidos pendientes para sincronizar con Salesforce...")

    conn = get_db_connection()

    pedidos = conn.execute("""
        SELECT p.*,
               c.nombre AS cliente_nombre,
               c.email AS cliente_email,
               c.telefono AS cliente_telefono
        FROM pedidos p
        JOIN clientes c ON c.id = p.cliente_id
        WHERE p.sf_pedido_id IS NULL
    """).fetchall()


    if not pedidos:
        print("✅ No hay pedidos pendientes.")
        conn.close()
        return

    for p in pedidos:
        try:
            pedido_sf = {
                "id_ringana": p["pedido_id_ringana"] or f"MANUAL-{p['id']}",
                "fecha": p["fecha"],
                "total": p["total"] or 0,
                "puntos": p["puntos"] or 0,
                "productos": p["producto"] or "",
                "regalo": p["regalo"] or "",
                "cliente_nombre": p["cliente_nombre"],
                "cliente_email": p["cliente_email"],  # puede ser None
                "cliente_telefono": p["cliente_telefono"] or ""
            }

            sf_id = procesar_pedido_sf(pedido_sf)

            if sf_id:
                conn.execute(
                    "UPDATE pedidos SET sf_pedido_id = ? WHERE id = ?",
                    (sf_id, p["id"])
                )
                conn.commit()
                print(f"✅ Pedido {p['id']} sincronizado → {sf_id}")
            else:
                print(f"⚠️ Pedido {p['id']} no sincronizado")

        except Exception as e:
            print(f"❌ Error pedido {p['id']}:", e)

    conn.close()
    print("🎉 Sincronización completada.")




# ==============================================================
# 🔄 SINCRONIZAR PEDIDOS MANUALES (NO ENVIADOS A SALESFORCE)
# ==============================================================

@app.route("/sincronizar_pedidos_sf", methods=["POST"])
def sincronizar_pedidos_sf():
    conn = get_db_connection()

    # 1️⃣ Seleccionar solo pedidos NO sincronizados
    pedidos = conn.execute("""
        SELECT *
        FROM pedidos
        WHERE sf_pedido_id IS NULL
    """).fetchall()

    if not pedidos:
        conn.close()
        flash("🎉 No hay pedidos pendientes de sincronizar.", "success")
        return redirect(url_for("index"))

    sincronizados = 0

    for p in pedidos:
        # Obtener cliente
        cliente = conn.execute("""
            SELECT *
            FROM clientes
            WHERE id = ?
        """, (p["cliente_id"],)).fetchone()

        if not cliente:
            print(f"⚠️ Pedido {p['id']} sin cliente asociado. Saltado.")
            continue

        print(f"\n🔄 SINCRONIZANDO PEDIDO {p['id']}...")

        # Enviar contacto
        contact_id = upsert_contact(
            cliente["nombre"],
            cliente["email"],
            cliente["telefono"],
            cliente["email"]
        )

        contact_id = upsert_contact(...)

        if not contact_id:
            log_error(f"Pedido {pedido_id} cancelado: contacto inválido")
            continue  # ← NO crear pedido


        # Crear cuerpo del pedido para SF
        data_pedido = {
            "Contact__c": contact_id,
            "Fecha_del_Pedido__c": p["fecha"],
            "Puntos__c": float(p["puntos"] or 0.0),
            "Total__c": float(p["total"] or 0.0),
            "Productos__c": p["producto"] or "",
            "Regalo__c": p["regalo"] or ""
        }

        try:
            result = sf.Pedido_Ringana__c.upsert(
                f"ID_Ringana__c/{p['pedido_id_ringana'] or p['id']}",
                data_pedido
            )

            # Salesforce devuelve dict o código
            if isinstance(result, dict):
                sf_id = result.get("id")
            else:
                # Recuperar id si no vino el dict
                rec = sf.query(
                    f"SELECT Id FROM Pedido_Ringana__c WHERE ID_Ringana__c = '{p['pedido_id_ringana'] or p['id']}'"
                )
                sf_id = rec["records"][0]["Id"] if rec["totalSize"] > 0 else None

            if sf_id:
                conn.execute("""
                    UPDATE pedidos
                    SET sf_pedido_id = ?
                    WHERE id = ?
                """, (sf_id, p["id"]))
                conn.commit()

                sincronizados += 1
                print(f"✅ Pedido {p['id']} sincronizado correctamente: {sf_id}")
            else:
                print(f"❌ No se pudo obtener ID Salesforce para pedido {p['id']}.")

        except Exception as e:
            print(f"❌ Error enviando pedido {p['id']} a Salesforce:", e)
            continue

    conn.close()
    flash(f"🔄 Sincronización completada. {sincronizados} pedidos enviados.", "success")
    return redirect(url_for("index"))





# ==============================================================
# 🔄 Revisión automática del correo cada 5 minutos
# ==============================================================

def iniciar_revisor_correo():

    import threading, time

    def loop():
        while True:
            try:
                revisar_gmail()      # puedes cambiarlo a revisar_hotmail()
            except Exception as e:
                print(f"⚠️ Error en el revisor automático: {e}")
            time.sleep(300)

    hilo = threading.Thread(target=loop, daemon=True)
    hilo.start()

    print("🕒 Revisión automática activada cada 5 minutos.")


# ==============================================================
# 🗑️ Borrar todos los pedidos
# ==============================================================

@app.route("/borrar_todos_pedidos", methods=["POST"])
def borrar_todos_pedidos():
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM pedidos")
        conn.commit()
        conn.close()
        flash("🗑️ Todos los pedidos han sido eliminados correctamente.", "success")
    except Exception as e:
        flash(f"⚠️ Error al eliminar pedidos: {e}", "danger")
    return redirect(url_for("index"))

# ==============================================================
# 🔄 REPROCESAR PEDIDOS HISTÓRICOS (SAMPLE + negativos)
# ==============================================================

@app.route("/reprocesar_pedidos_historicos", methods=["POST"])
def reprocesar_pedidos_historicos():
    import re
    conn = get_db_connection()
    pedidos = conn.execute("SELECT id, producto, regalo FROM pedidos").fetchall()

    for p in pedidos:

        producto = p["producto"] or ""
        regalo = p["regalo"] or ""

        # Limpieza inicial
        producto = producto.replace("Importe incl. IVA", "")
        producto = re.sub(r"\d+,\d+% ?", "", producto)  # porcentajes
        producto = re.sub(r"\([A-Z0-9\-]{8,}\)", "", producto)  # códigos Ringana

        partes = [x.strip() for x in producto.split(",") if x.strip()]

        productos_limpios = []
        regalos_detectados = []

        for item in partes:

            # SAMPLE → regalo
            if "sample" in item.lower():
                regalos_detectados.append(item)
                continue

            # Precios negativos → regalo
            if re.search(r"(-\s*\d+,\d+)", item):
                regalos_detectados.append(item)
                continue

            productos_limpios.append(item)

        producto_final = ", ".join(productos_limpios)
        regalo_final = ", ".join(filter(None, [regalo] + regalos_detectados)).strip(", ")

        conn.execute("""
            UPDATE pedidos
            SET producto = ?, regalo = ?
            WHERE id = ?
        """, (producto_final, regalo_final, p["id"]))

    conn.commit()
    conn.close()

    flash("✔ Todos los pedidos han sido reprocesados correctamente.", "success")
    return redirect(url_for("index"))

@app.route("/limpiar_porcentajes_global", methods=["POST"])
def limpiar_porcentajes_global():
    import re

    conn = get_db_connection()
    pedidos = conn.execute("SELECT id, producto, regalo FROM pedidos").fetchall()

    for p in pedidos:
        prod = p["producto"] or ""
        reg = p["regalo"] or ""

        prod_clean = re.sub(r"\d+,\d+% ?", "", prod).strip()
        reg_clean = re.sub(r"\d+,\d+% ?", "", reg).strip()

        conn.execute("""
            UPDATE pedidos
            SET producto = ?, regalo = ?
            WHERE id = ?
        """, (prod_clean, reg_clean, p["id"]))

    conn.commit()
    conn.close()

    flash("✔ Porcentajes eliminados globalmente.", "success")
    return redirect(url_for("index"))


@app.route("/reprocesar_regalos", methods=["POST"])
def reprocesar_regalos():
    import re

    conn = get_db_connection()
    pedidos = conn.execute("SELECT id, producto, regalo FROM pedidos").fetchall()

    for p in pedidos:

        producto_raw = p["producto"] or ""
        regalo_raw = p["regalo"] or ""

        partes = [t.strip() for t in producto_raw.split(",") if t.strip()]

        productos_limpios = []
        nuevos_regalos = []

        for item in partes:
            if "sample" in item.lower():
                nuevos_regalos.append(item)
                continue

            if re.search(r"-\s*\d+,\d+", item):
                nuevos_regalos.append(item)
                continue

            productos_limpios.append(item)

        producto_final = ", ".join(productos_limpios)

        regalo_final = regalo_raw.strip()
        if nuevos_regalos:
            nuevos = ", ".join(nuevos_regalos)
            if regalo_final:
                regalo_final = regalo_final + ", " + nuevos
            else:
                regalo_final = nuevos

        conn.execute("""
            UPDATE pedidos
            SET producto = ?, regalo = ?
            WHERE id = ?
        """, (producto_final, regalo_final, p["id"]))

    conn.commit()
    conn.close()

    flash("🎁 Regalos actualizados correctamente.", "success")
    return redirect(url_for("index"))




# ==============================================================
# 🚀 Iniciar servidor Flask
# ==============================================================

if __name__ == "__main__":
    import webbrowser, threading, time, os

    def abrir_navegador():
        if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            time.sleep(2)
            webbrowser.open("http://127.0.0.1:5050/")

    threading.Thread(target=abrir_navegador, daemon=True).start()

    iniciar_revisor_correo()

    app.run(host="0.0.0.0", port=5050, debug=True)
