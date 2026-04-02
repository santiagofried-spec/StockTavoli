import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timezone
import streamlit as st

# -----------------------
# Conexión a Supabase cacheada
# -----------------------
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


# -----------------------
# Funciones de insumos
# -----------------------
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
    return supabase.table("insumos").insert(payload).execute()


# -----------------------
# Funciones de movimientos
# -----------------------
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
        insumos_rel = row.get("insumos")
        # Warn if the join returned nothing — could indicate a broken FK
        nombre_insumo = insumos_rel["nombre"] if insumos_rel else "—"
        rows.append({
            "id": row["id"],
            "fecha": row["fecha"],
            "tipo": row["tipo"],
            "insumo": nombre_insumo,
            "cantidad": row["cantidad"],
            "motivo": row["motivo"],
            "usuario": row["usuario"],
        })
    return pd.DataFrame(rows)


def registrar_movimiento(tipo, insumo_id, cantidad, motivo="", usuario="admin"):
    # TODO: replace hardcoded "admin" with the authenticated user once auth is added
    supabase = get_supabase()

    # Fetch only the field we need
    insumo_resp = (
        supabase.table("insumos")
        .select("stock_actual")
        .eq("id", insumo_id)
        .single()
        .execute()
    )
    insumo = insumo_resp.data
    if not insumo:
        raise ValueError("Insumo no encontrado")

    stock_actual = float(insumo["stock_actual"])
    cantidad = float(cantidad)

    if tipo == "compra":
        nuevo_stock = stock_actual + cantidad
    else:
        if cantidad > stock_actual:
            raise ValueError("No puedes descontar más stock del disponible")
        nuevo_stock = stock_actual - cantidad

    # Insert movement first — if this fails, stock is untouched
    supabase.table("movimientos").insert({
        "fecha": datetime.now(timezone.utc).isoformat(),
        "tipo": tipo,
        "insumo_id": insumo_id,
        "cantidad": cantidad,
        "motivo": motivo,
        "usuario": usuario,
    }).execute()

    # Only update stock after the movement is safely recorded
    supabase.table("insumos").update({
        "stock_actual": nuevo_stock
    }).eq("id", insumo_id).execute()
