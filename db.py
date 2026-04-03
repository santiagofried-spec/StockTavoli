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


@st.cache_resource
def get_supabase_admin() -> Client:
    """Service role client — only for admin auth operations (create/delete users)."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


# -----------------------
# Auth
# -----------------------
def login(email, password):
    """Returns (user, error_message)."""
    supabase = get_supabase()
    try:
        resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return resp.user, None
    except Exception as e:
        return None, str(e)


def logout():
    supabase = get_supabase()
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    for key in ["user", "role"]:
        st.session_state.pop(key, None)


def get_role(user_id):
    """Returns 'admin', 'staff', or None."""
    supabase = get_supabase()
    try:
        resp = (
            supabase.table("user_roles")
            .select("role")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return resp.data["role"] if resp.data else None
    except Exception:
        return None


def create_user(email, password, role="staff"):
    """Admin creates a new user. Returns (user, error_message)."""
    supabase = get_supabase_admin()
    try:
        resp = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
        })
        user = resp.user
        # Insert role directly — no trigger needed
        supabase.table("user_roles").insert({
            "user_id": user.id,
            "role": role,
        }).execute()
        return user, None
    except Exception as e:
        return None, str(e)


def get_users():
    """Returns list of all users with their roles."""
    supabase = get_supabase_admin()
    try:
        users_resp = supabase.auth.admin.list_users()
        roles_resp = supabase.table("user_roles").select("user_id, role").execute()
        roles = {r["user_id"]: r["role"] for r in (roles_resp.data or [])}
        rows = []
        for u in users_resp:
            rows.append({
                "id": u.id,
                "email": u.email,
                "role": roles.get(u.id, "staff"),
                "created_at": u.created_at,
            })
        return rows
    except Exception:
        return []


def delete_user(user_id):
    supabase = get_supabase_admin()
    supabase.auth.admin.delete_user(user_id)


def update_user_role(user_id, role):
    supabase = get_supabase()
    supabase.table("user_roles").update({"role": role}).eq("user_id", user_id).execute()


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


def registrar_consumo_receta(receta_id, cantidad_vendida, motivo="", usuario=None):
    supabase = get_supabase()
    ingredientes = get_ingredientes_receta(receta_id)
    if ingredientes.empty:
        raise ValueError("La receta no tiene ingredientes cargados.")

    cantidad_vendida = float(cantidad_vendida)

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


def registrar_movimiento(tipo, insumo_id, cantidad, motivo="", usuario=None):
    # TODO: replace hardcoded "admin" with the authenticated user once auth is added
    supabase = get_supabase()

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

    supabase.table("movimientos").insert({
        "fecha": datetime.now(timezone.utc).isoformat(),
        "tipo": tipo,
        "insumo_id": insumo_id,
        "cantidad": cantidad,
        "motivo": motivo,
        "usuario": usuario,
    }).execute()

    supabase.table("insumos").update({
        "stock_actual": nuevo_stock
    }).eq("id", insumo_id).execute()