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


# -----------------------
# Funciones de recetas
# -----------------------
def get_recetas():
    supabase = get_supabase()
    response = supabase.table("recetas").select("*").order("nombre").execute()
    data = response.data if response.data else []
    return pd.DataFrame(data)


def add_receta(nombre):
    supabase = get_supabase()
    response = supabase.table("recetas").insert({"nombre": nombre}).execute()
    return response.data[0]["id"]


def get_ingredientes_receta(receta_id):
    """Returns ingredients for a recipe joined with insumo name and unit."""
    supabase = get_supabase()
    response = (
        supabase.table("receta_ingredientes")
        .select("id, cantidad, insumo_id, insumos(nombre, unidad)")
        .eq("receta_id", receta_id)
        .execute()
    )
    data = response.data if response.data else []
    rows = []
    for row in data:
        insumo = row.get("insumos") or {}
        rows.append({
            "id": row["id"],
            "insumo_id": row["insumo_id"],
            "insumo": insumo.get("nombre", "—"),
            "unidad": insumo.get("unidad", ""),
            "cantidad": row["cantidad"],
        })
    return pd.DataFrame(rows)


def add_ingrediente_receta(receta_id, insumo_id, cantidad):
    supabase = get_supabase()
    supabase.table("receta_ingredientes").insert({
        "receta_id": receta_id,
        "insumo_id": insumo_id,
        "cantidad": float(cantidad),
    }).execute()


def delete_ingrediente_receta(ingrediente_id):
    supabase = get_supabase()
    supabase.table("receta_ingredientes").delete().eq("id", ingrediente_id).execute()


def registrar_consumo_receta(receta_id, cantidad_vendida, motivo="", usuario="admin"):
    """
    Deducts stock for all ingredients of a recipe multiplied by cantidad_vendida.
    Raises ValueError if any ingredient has insufficient stock before making any changes.
    """
    supabase = get_supabase()
    ingredientes = get_ingredientes_receta(receta_id)
    if ingredientes.empty:
        raise ValueError("La receta no tiene ingredientes cargados.")

    cantidad_vendida = float(cantidad_vendida)

    # --- Pre-flight check: verify all ingredients have enough stock ---
    errores = []
    for _, ing in ingredientes.iterrows():
        resp = (
            supabase.table("insumos")
            .select("nombre, stock_actual")
            .eq("id", ing["insumo_id"])
            .single()
            .execute()
        )
        insumo = resp.data
        if not insumo:
            errores.append(f"Insumo ID {ing['insumo_id']} no encontrado.")
            continue
        necesario = ing["cantidad"] * cantidad_vendida
        if necesario > float(insumo["stock_actual"]):
            errores.append(
                f"{insumo['nombre']}: necesitás {necesario} {ing['unidad']}, "
                f"hay {insumo['stock_actual']} {ing['unidad']}."
            )
    if errores:
        raise ValueError("Stock insuficiente:\n" + "\n".join(errores))

    # --- All good: register movements and deduct stock ---
    fecha = datetime.now(timezone.utc).isoformat()
    for _, ing in ingredientes.iterrows():
        total = ing["cantidad"] * cantidad_vendida
        supabase.table("movimientos").insert({
            "fecha": fecha,
            "tipo": "consumo",
            "insumo_id": ing["insumo_id"],
            "cantidad": total,
            "motivo": motivo,
            "usuario": usuario,
        }).execute()
        resp = (
            supabase.table("insumos")
            .select("stock_actual")
            .eq("id", ing["insumo_id"])
            .single()
            .execute()
        )
        nuevo_stock = float(resp.data["stock_actual"]) - total
        supabase.table("insumos").update({"stock_actual": nuevo_stock}).eq("id", ing["insumo_id"]).execute()


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