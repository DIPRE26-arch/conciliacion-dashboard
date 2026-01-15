import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from io import BytesIO
import plotly.express as px
import hashlib
import datetime
import unicodedata
import re
import os

# =============================
# CONFIGURACIÓN GENERAL
# =============================
st.set_page_config(page_title="Reporte de Pagos", layout="wide")

FOLDER_ID = "1VWq_kfZebHVMmJ64_Zlj4wNy70_NN-_b"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# =============================
# UTILIDADES DE SEGURIDAD
# =============================
def hash_pass(p):
    return hashlib.sha256(p.encode()).hexdigest()

def log_event(msg):
    st.session_state.logs.append(
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}"
    )

# =============================
# ESTADO INICIAL
# =============================
if "users" not in st.session_state:
    st.session_state.users = {
        "WANDER DIPRE": {
            "password": hash_pass("DIPRE.W01"),
            "admin": True
        }
    }

if "logs" not in st.session_state:
    st.session_state.logs = []

if "auth" not in st.session_state:
    st.session_state.auth = False

# =============================
# LOGIN
# =============================
if not st.session_state.auth:
    st.title("🔐 Acceso al sistema")

    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        user = st.session_state.users.get(u)
        if user and user["password"] == hash_pass(p):
            st.session_state.auth = True
            st.session_state.user = u
            log_event(f"Login exitoso: {u}")
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

    st.stop()

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.title("⚙️ Menú")

    if st.button("🔒 Cerrar sesión"):
        log_event(f"Cierre de sesión: {st.session_state.user}")
        st.session_state.auth = False
        st.rerun()

    # =============================
    # ADMINISTRACIÓN DE USUARIOS
    # =============================
    if st.session_state.users[st.session_state.user]["admin"]:
        st.markdown("---")
        st.subheader("👥 Administración de Usuarios")

        # CREAR USUARIO
        with st.expander("➕ Crear usuario"):
            new_user = st.text_input("Usuario nuevo")
            new_pass = st.text_input("Contraseña", type="password")
            is_admin = st.checkbox("Administrador")

            if st.button("Crear usuario"):
                if not new_user or not new_pass:
                    st.error("Usuario y contraseña obligatorios")
                elif new_user in st.session_state.users:
                    st.error("El usuario ya existe")
                else:
                    st.session_state.users[new_user] = {
                        "password": hash_pass(new_pass),
                        "admin": is_admin
                    }
                    log_event(f"Usuario creado: {new_user}")
                    st.success("Usuario creado correctamente")

        # CAMBIAR CONTRASEÑA
        with st.expander("🔑 Cambiar contraseña"):
            sel_user = st.selectbox(
                "Usuario",
                list(st.session_state.users.keys())
            )
            new_pwd = st.text_input("Nueva contraseña", type="password")

            if st.button("Actualizar contraseña"):
                if new_pwd:
                    st.session_state.users[sel_user]["password"] = hash_pass(new_pwd)
                    log_event(f"Contraseña actualizada: {sel_user}")
                    st.success("Contraseña actualizada")
                else:
                    st.error("Contraseña vacía")

        # ELIMINAR USUARIO
        with st.expander("🗑 Eliminar usuario"):
            del_user = st.selectbox(
                "Usuario a eliminar",
                [u for u in st.session_state.users if u != st.session_state.user]
            )

            if st.button("Eliminar usuario"):
                del st.session_state.users[del_user]
                log_event(f"Usuario eliminado: {del_user}")
                st.success("Usuario eliminado")

# =============================
# GOOGLE DRIVE
# =============================
creds = service_account.Credentials.from_service_account_info(
    st.secrets["gdrive"],
    scopes=SCOPES
)
service = build("drive", "v3", credentials=creds)

def listar_archivos(folder_id):
    q = f"'{folder_id}' in parents and trashed=false"
    return service.files().list(
        q=q, fields="files(id,name,mimeType)"
    ).execute().get("files", [])

def leer_excel(file_id):
    data = service.files().get_media(fileId=file_id).execute()
    return pd.read_excel(BytesIO(data))

# =============================
# UTILIDADES DE DATOS
# =============================
def limpiar_texto(t):
    if pd.isna(t):
        return ""
    t = unicodedata.normalize("NFKD", str(t).lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", "", t)

def banco_norm(b):
    b = limpiar_texto(b)
    if "popular" in b:
        return "POPULAR"
    if "reserva" in b:
        return "BANRESERVAS"
    return ""

def money(x):
    return f"$ {x:,.2f}"

# =============================
# CARGA DE EXCEL
# =============================
dfs = []
for f in listar_archivos(FOLDER_ID):
    if f["name"].lower().endswith(".xlsx"):
        df = leer_excel(f["id"])
        df["archivo"] = f["name"]
        dfs.append(df)

if not dfs:
    st.error("No se encontraron archivos Excel en Google Drive")
    st.stop()

df = pd.concat(dfs, ignore_index=True)
df.columns = df.columns.str.lower().str.strip()

df["fecha"] = pd.to_datetime(df.get("fecha"), errors="coerce")
df["monto"] = pd.to_numeric(df.get("monto"), errors="coerce")
df["banco"] = df.get("banco").apply(banco_norm)

# =============================
# HEADER
# =============================
if os.path.exists("logo.png"):
    st.image("logo.png", width=180)

st.title("REPORTE DE PAGOS DE FINANCIAMOTO LA FUENTE, S.R.L")

# =============================
# KPIs
# =============================
k1, k2 = st.columns(2)
k1.metric("💰 Total Pagado", money(df["monto"].sum()))
k2.metric("📄 Total de Pagos", len(df))

# =============================
# FILTROS
# =============================
st.subheader("🔍 Filtros")

c1, c2, c3, c4 = st.columns(4)
f_codigo = c1.text_input("Buscar por Código")
f_prestamo = c2.text_input("Buscar por Préstamo")
f_nombre = c3.text_input("Buscar por Nombre")
f_banco = c4.selectbox("Banco", ["", "POPULAR", "BANRESERVAS"])

df_f = df.copy()

if f_codigo:
    df_f = df_f[df_f.astype(str).apply(lambda x: f_codigo in " ".join(x), axis=1)]
if f_prestamo:
    df_f = df_f[df_f.astype(str).apply(lambda x: f_prestamo in " ".join(x), axis=1)]
if f_nombre:
    df_f = df_f[df_f.astype(str).apply(
        lambda x: f_nombre.lower() in " ".join(x).lower(), axis=1
    )]
if f_banco:
    df_f = df_f[df_f["banco"] == f_banco]

# =============================
# TABLA
# =============================
df_f["monto_fmt"] = df_f["monto"].apply(money)
st.dataframe(df_f, use_container_width=True)

# =============================
# GRÁFICA
# =============================
st.subheader("📊 Pagos por Banco")

chart = df_f.groupby("banco", as_index=False)["monto"].sum()

fig = px.bar(
    chart,
    x="banco",
    y="monto",
    color="banco",
    color_discrete_map={
        "POPULAR": "blue",
        "BANRESERVAS": "orange"
    },
    text_auto=True
)

st.plotly_chart(fig, use_container_width=True)

# =============================
# HISTORIAL
# =============================
st.subheader("🕒 Historial del Sistema")
st.text("\n".join(st.session_state.logs))

