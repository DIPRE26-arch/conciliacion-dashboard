import os
import pandas as pd
import streamlit as st
from datetime import date
import plotly.express as px

# =============================
# CONFIGURACIÓN
# =============================
st.set_page_config(page_title="Conciliación de Pagos", layout="wide")

RUTA_EXCEL = r"C:\Users\CONFIGURACION\Desktop\Conciliacion_Pagos\Excel"
RUTA_USUARIOS = r"C:\Users\CONFIGURACION\Desktop\Conciliacion_Pagos\usuarios.xlsx"

PERMISOS = ["Editar Datos", "Crear Usuarios", "Modificar Usuarios", "Asignar Permisos", "Acceso Reportes"]

# =============================
# FUNCIONES USUARIOS
# =============================
USUARIOS = {}

def guardar_usuarios_excel():
    df = pd.DataFrame([
        {"usuario": u, "password": v["password"], "permisos": ",".join(v["permisos"])}
        for u,v in USUARIOS.items()
    ])
    df.to_excel(RUTA_USUARIOS, index=False)

def cargar_usuarios_excel():
    global USUARIOS
    if os.path.exists(RUTA_USUARIOS):
        df = pd.read_excel(RUTA_USUARIOS)
        USUARIOS = {}
        for _, row in df.iterrows():
            USUARIOS[row["usuario"]] = {
                "password": row["password"],
                "permisos": row["permisos"].split(",") if pd.notna(row["permisos"]) else []
            }
    else:
        # Usuario administrador inicial
        USUARIOS["WANDER"] = {"password":"DIPRE.W01", "permisos": PERMISOS}
        guardar_usuarios_excel()

cargar_usuarios_excel()

# =============================
# LOGIN SIMPLE
# =============================
if "usuario" not in st.session_state:
    st.session_state.usuario = None

def login():
    st.title("🔐 Acceso al Dashboard")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        if u in USUARIOS and USUARIOS[u]["password"] == p:
            st.session_state.usuario = u
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

if st.session_state.usuario is None:
    login()
    st.stop()

# =============================
# CARGA DE EXCEL CON FECHAS
# =============================
@st.cache_data(ttl=5)
def cargar_datos():
    lista = []

    if not os.path.exists(RUTA_EXCEL):
        st.error(f"No existe la ruta: {RUTA_EXCEL}")
        st.stop()

    archivos = os.listdir(RUTA_EXCEL)

    meses = {
        "enero": "01","febrero": "02","marzo": "03","abril": "04",
        "mayo": "05","junio": "06","julio": "07","agosto": "08",
        "septiembre": "09","octubre": "10","noviembre": "11","diciembre": "12"
    }

    for archivo in archivos:
        if archivo.lower().endswith((".xlsx", ".xls")) and not archivo.startswith("~$"):
            try:
                ruta = os.path.join(RUTA_EXCEL, archivo)
                df = pd.read_excel(ruta)
                df.columns = df.columns.str.strip().str.lower()

                # Fecha
                if "fecha" in df.columns:
                    temp = df["fecha"].astype(str).str.upper().str.replace(" DE ", " ", regex=False)
                    temp = temp.str.lower()
                    for nombre, numero in meses.items():
                        temp = temp.str.replace(nombre, numero, regex=False)
                    df["fecha"] = pd.to_datetime(temp, dayfirst=True, errors="coerce")

                # Monto
                if "monto" in df.columns:
                    df["monto"] = df["monto"].astype(str).str.replace("$","",regex=False).str.replace(",","",regex=False)
                    df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0)

                # Unificar bancos
                if "banco" in df.columns:
                    df["banco"] = df["banco"].str.upper()
                    df["banco"] = df["banco"].replace({
                        "RESERVA": "BANRESERVAS",
                        "RESERVAS": "BANRESERVAS",
                        "BAN RESERVAS": "BANRESERVAS",
                        "BANRESERVAS": "BANRESERVAS",
                        "POPULAR": "POPULAR"
                    })

                lista.append(df)

            except Exception as e:
                st.warning(f"Error leyendo {archivo}: {e}")

    if not lista:
        st.error("❌ No se encontraron archivos Excel válidos en la carpeta")
        st.stop()

    return pd.concat(lista, ignore_index=True)

df = cargar_datos()

# =============================
# PANEL ADMINISTRADOR (solo WANDER)
# =============================
def panel_admin():
    st.header("⚙️ Panel de Administración - WANDER")
    accion = st.selectbox("Selecciona acción", ["Usuarios", "Editar Datos"])

    if accion == "Usuarios":
        st.subheader("Gestionar Usuarios")
        usuario_sel = st.selectbox("Selecciona usuario", list(USUARIOS.keys()))

        # Cambiar contraseña
        nueva_pass = st.text_input("Nueva contraseña", type="password", key="pass_mod")
        if st.button("Actualizar contraseña", key="btn_pass"):
            if nueva_pass:
                USUARIOS[usuario_sel]["password"] = nueva_pass
                guardar_usuarios_excel()
                st.success(f"Contraseña de {usuario_sel} actualizada.")

        # Cambiar permisos
        permisos_actuales = USUARIOS[usuario_sel]["permisos"]
        permisos_sel = st.multiselect("Permisos", PERMISOS, default=permisos_actuales, key="perm_mod")
        if st.button("Actualizar permisos", key="btn_perm"):
            USUARIOS[usuario_sel]["permisos"] = permisos_sel
            guardar_usuarios_excel()
            st.success(f"Permisos de {usuario_sel} actualizados.")

        # Crear nuevo usuario
        st.subheader("Crear Nuevo Usuario")
        nuevo_usuario = st.text_input("Nombre de usuario", key="new_user")
        nueva_pass_nuevo = st.text_input("Contraseña", type="password", key="new_pass")
        permisos_nuevo = st.multiselect("Permisos", PERMISOS, default=["Acceso Reportes"], key="perm_new")
        if st.button("Crear Usuario", key="btn_new"):
            if nuevo_usuario and nueva_pass_nuevo:
                if nuevo_usuario in USUARIOS:
                    st.warning("El usuario ya existe")
                else:
                    USUARIOS[nuevo_usuario] = {"password": nueva_pass_nuevo, "permisos": permisos_nuevo}
                    guardar_usuarios_excel()
                    st.success(f"Usuario {nuevo_usuario} creado.")

    elif accion == "Editar Datos":
        st.subheader("Editar Pagos")
        st.info("Selecciona celdas y modifica valores. Los cambios se guardarán en Excel.")

        df_edit = st.data_editor(df, use_container_width=True)
        if st.button("Guardar cambios en Excel", key="guardar_excel"):
            ruta_guardado = os.path.join(RUTA_EXCEL, "Conciliacion_Pagos_Actualizado.xlsx")
            df_edit.to_excel(ruta_guardado, index=False)
            st.success(f"Cambios guardados en {ruta_guardado}")

# =============================
# SIDEBAR Y FILTROS
# =============================
with st.sidebar:
    st.markdown(f"👤 **Usuario:** {st.session_state.usuario}")
    if st.button("👁️ Actualizar"):
        st.cache_data.clear()
        st.rerun()
    st.markdown("## 🔎 Filtros")

df_f = df.copy()

# -----------------------------
# FILTROS INDEPENDIENTES
# -----------------------------
mask_fecha = pd.Series(True, index=df_f.index)
usar_fecha = st.sidebar.checkbox("Filtrar por fecha")
if usar_fecha and "fecha" in df_f.columns:
    rango = st.sidebar.date_input("Rango de fechas", value=(date(2026,1,1), date.today()))
    if len(rango) == 2:
        mask_fecha = (df_f["fecha"] >= pd.to_datetime(rango[0])) & (df_f["fecha"] <= pd.to_datetime(rango[1]))

mask_banco = pd.Series(True, index=df_f.index)
if "banco" in df_f.columns:
    banco_sel = st.sidebar.multiselect("Banco", sorted(df_f["banco"].unique()))
    if banco_sel:
        mask_banco = df_f["banco"].isin(banco_sel)

mask_codigo = pd.Series(True, index=df_f.index)
codigo_buscar = st.sidebar.text_input("Buscar por Código")
if codigo_buscar:
    mask_codigo = df_f["codigo"].astype(str).str.contains(codigo_buscar, case=False, na=False)

mask_nombre = pd.Series(True, index=df_f.index)
nombre_buscar = st.sidebar.text_input("Buscar por Nombre")
if nombre_buscar:
    mask_nombre = df_f["nombre"].astype(str).str.contains(nombre_buscar, case=False, na=False)

mask_prestamo = pd.Series(True, index=df_f.index)
prestamo_buscar = st.sidebar.text_input("Buscar por Préstamo")
if prestamo_buscar:
    mask_prestamo = df_f["prestamo"].astype(str).str.contains(prestamo_buscar, case=False, na=False)

# NUEVO: Filtro por oficial
mask_oficial = pd.Series(True, index=df_f.index)
if "oficial" in df_f.columns:
    oficial_sel = st.sidebar.multiselect("Oficial", sorted(df_f["oficial"].dropna().unique()))
    if oficial_sel:
        mask_oficial = df_f["oficial"].isin(oficial_sel)

# Aplicar todos los filtros
df_f = df_f[mask_fecha & mask_banco & mask_codigo & mask_nombre & mask_prestamo & mask_oficial]

# =============================
# FORMATO
# =============================
if "monto" in df_f.columns:
    df_f["monto_$"] = df_f["monto"].apply(lambda x: f"${x:,.2f}")
if "fecha" in df_f.columns:
    df_f["fecha"] = df_f["fecha"].dt.strftime("%d/%m/%Y")

# =============================
# DASHBOARD
# =============================
st.title("📊 Conciliación de Pagos")

c1, c2 = st.columns(2)
if "monto" in df_f.columns:
    c1.metric("💰 Total Pagado", f"${df_f['monto'].sum():,.2f}")
c2.metric("📄 Registros", len(df_f))

cols_mostrar = [col for col in ["fecha","nombre","codigo","prestamo","banco","oficial","monto_$"] if col in df_f.columns]
st.dataframe(df_f[cols_mostrar], use_container_width=True)

# =============================
# GRÁFICOS DINÁMICOS
# =============================
if "banco" in df_f.columns and "monto" in df_f.columns:
    df_graf = df_f.groupby("banco")["monto"].sum().reset_index()
    fig = px.bar(
        df_graf,
        x="banco",
        y="monto",
        text="monto",
        color="banco",
        color_discrete_map={"BANRESERVAS":"#FF7F50", "POPULAR":"#1F77B4"},
        title="💰 Total Pagos por Banco (Filtros aplicados)"
    )
    st.plotly_chart(fig, use_container_width=True)

# =============================
# PANEL ADMIN WANDER
# =============================
if st.session_state.usuario == "WANDER":
    st.markdown("---")
    panel_admin()

# =============================
# CERRAR SESIÓN
# =============================
with st.sidebar:
    st.markdown("---")
    if st.button("Cerrar sesión"):
        st.session_state.clear()
        st.rerun()
