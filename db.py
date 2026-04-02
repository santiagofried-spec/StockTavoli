import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timezone

# -----------------------------
# Conexión a Supabase
# -----------------------------
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# -----------------------------
# Funciones de la base
# -----------------------------
def get_insumos():
    supabase = get_supabase()
    response = supabase.table("insumos").select("*").order("nombre").execute()
    data = response.data if response.data else []
    return pd.DataFrame(data)

def add_insumo(nombre, categoria, unidad, stock_actual, stock_minimo, costo_unitario, proveedor):
    supabase = get_supabase()
    payload = {
        "nombre": nombre,
        "categoria": categoria,
        "unidad": unidad,
        "stock_actual": stock_actual,
        "stock_minimo": stock_minimo,
        "costo_unitario": costo_unitario,
        "proveedor": proveedor
    }
    supabase.table("insumos").insert(payload).execute()

def get_movimientos():
    supabase = get_supabase()
    response = (
        supabase
        .table("movimientos")
        .select("id, fecha, tipo, cantidad, motivo, usuario, insumo_id, insumos(nombre)")
        .order("fecha", desc=True)
        .execute()
    )
    data = response.data if response.data else []

    rows = []
    for row in data:
        nombre_insumo = row["insumos"]["nombre"] if row.get("insumos") else None
        rows.append({
            "id": row["id"],
            "fecha": row["fecha"],
            "tipo": row["tipo"],
            "insumo": nombre_insumo,
            "cantidad": row["cantidad"],
            "motivo": row["motivo"],
            "usuario": row["usuario"]
        })
    return pd.DataFrame(rows)

def registrar_movimiento(tipo, insumo_id, cantidad, motivo="", usuario="admin"):
    supabase = get_supabase()

    # Traer insumo
    insumo_resp = supabase.table("insumos").select("*").eq("id", insumo_id).single().execute()
    insumo = insumo_resp.data
    if not insumo:
        st.error("Insumo no encontrado")
        return

    stock_actual = float(insumo["stock_actual"])
    cantidad = float(cantidad)

    if tipo == "compra":
        nuevo_stock = stock_actual + cantidad
    else:  # venta / uso
        if cantidad > stock_actual:
            st.error("No puedes descontar más stock del disponible")
            return
        nuevo_stock = stock_actual - cantidad

    # Registrar movimiento
    supabase.table("movimientos").insert({
        "fecha": datetime.now(timezone.utc).isoformat(),
        "tipo": tipo,
        "insumo_id": insumo_id,
        "cantidad": cantidad,
        "motivo": motivo,
        "usuario": usuario
    }).execute()

    # Actualizar stock
    supabase.table("insumos").update({
        "stock_actual": nuevo_stock
    }).eq("id", insumo_id).execute()
    st.success(f"Movimiento '{tipo}' registrado correctamente")

# -----------------------------
# Estado inicial
# -----------------------------
if "insumo_agregado" not in st.session_state:
    st.session_state.insumo_agregado = False
if "movimiento_registrado" not in st.session_state:
    st.session_state.movimiento_registrado = False

# -----------------------------
# Interfaz de la app
# -----------------------------
st.title("💼 Inventario de Insumos")

# --- Agregar Insumo ---
st.subheader("Agregar nuevo insumo")
with st.form("form_agregar_insumo"):
    nombre = st.text_input("Nombre")
    categoria = st.text_input("Categoría")
    unidad = st.text_input("Unidad")
    stock_actual = st.number_input("Stock actual", min_value=0)
    stock_minimo = st.number_input("Stock mínimo", min_value=0)
    costo_unitario = st.number_input("Costo unitario", min_value=0.0, format="%.2f")
    proveedor = st.text_input("Proveedor")
    submitted = st.form_submit_button("Agregar insumo")
    
    if submitted and not st.session_state.insumo_agregado:
        add_insumo(nombre, categoria, unidad, stock_actual, stock_minimo, costo_unitario, proveedor)
        st.session_state.insumo_agregado = True
        st.success(f"Insumo '{nombre}' agregado correctamente")

# --- Registrar Movimiento ---
st.subheader("Registrar movimiento")
insumos_df = get_insumos()
if not insumos_df.empty:
    with st.form("form_registrar_movimiento"):
        insumo_id = st.selectbox("Insumo", options=insumos_df["id"], format_func=lambda x: insumos_df.loc[insumos_df["id"]==x, "nombre"].values[0])
        tipo = st.selectbox("Tipo", ["compra", "uso"])
        cantidad = st.number_input("Cantidad", min_value=0.0, format="%.2f")
        motivo = st.text_input("Motivo")
        submitted_mov = st.form_submit_button("Registrar movimiento")

        if submitted_mov and not st.session_state.movimiento_registrado:
            registrar_movimiento(tipo, insumo_id, cantidad, motivo)
            st.session_state.movimiento_registrado = True

# --- Ver Inventario ---
st.subheader("Inventario actual")
st.dataframe(get_insumos())

# --- Ver Movimientos ---
st.subheader("Historial de movimientos")
st.dataframe(get_movimientos())