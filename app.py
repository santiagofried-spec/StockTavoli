import streamlit as st
from db import (
    get_insumos, add_insumo, registrar_movimiento, get_movimientos,
    get_recetas, add_receta, get_ingredientes_receta,
    add_ingrediente_receta, delete_ingrediente_receta, registrar_consumo_receta,
    login, logout, get_role, create_user, get_users, delete_user, update_user_role,
)

# -----------------------
# Configuración de la página
# -----------------------
st.set_page_config(page_title="Control de Stock - Tavoli", layout="wide")

# -----------------------
# Auth: login wall
# -----------------------
if "user" not in st.session_state:
    st.session_state.user = None
    st.session_state.role = None

if st.session_state.user is None:
    st.title("Control de Stock — Tavoli")
    st.subheader("Iniciar sesión")
    with st.form("form_login"):
        email = st.text_input("Email")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar")
    if submitted:
        user, error = login(email, password)
        if error:
            st.error("Email o contraseña incorrectos.")
        else:
            role = get_role(user.id)
            if not role:
                st.error("Tu usuario no tiene un rol asignado. Contactá al administrador.")
            else:
                st.session_state.user = user
                st.session_state.role = role
                st.rerun()
    st.stop()  # Nothing below renders if not logged in

# -----------------------
# Shortcuts
# -----------------------
is_admin = st.session_state.role == "admin"
current_user_email = st.session_state.user.email
current_user_id = st.session_state.user.id

# -----------------------
# Inicialización de session_state
# -----------------------
_defaults = {
    "mostrar_form_insumo": False,
    "mostrar_form_compra": False,
    "mostrar_form_salida": False,
    "mostrar_form_consumo": False,
    "mostrar_form_receta": False,
    "mostrar_form_usuario": False,
    "_last_menu": None,
}
for key, val in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# -----------------------
# Helper
# -----------------------
def build_opciones(insumos):
    return {f"{row['nombre']} ({row['unidad']})": row["id"] for _, row in insumos.iterrows()}

# -----------------------
# Sidebar
# -----------------------
st.sidebar.markdown(f"👤 **{current_user_email}**")
st.sidebar.caption(f"Rol: {st.session_state.role}")
if st.sidebar.button("Cerrar sesión"):
    logout()
    st.rerun()

st.sidebar.divider()
st.sidebar.subheader("Acciones rápidas")

# Staff can register consumo
if st.sidebar.button("☕ Registrar consumo"):
    st.session_state["menu"] = "Movimientos"
    st.session_state.mostrar_form_consumo = True
    st.session_state.mostrar_form_compra = False
    st.session_state.mostrar_form_salida = False

# Admin-only actions
if is_admin:
    if st.sidebar.button("➕ Nuevo insumo"):
        st.session_state["menu"] = "Insumos"
        st.session_state.mostrar_form_insumo = True

    if st.sidebar.button("📦 Registrar compra"):
        st.session_state["menu"] = "Movimientos"
        st.session_state.mostrar_form_compra = True
        st.session_state.mostrar_form_salida = False
        st.session_state.mostrar_form_consumo = False

    if st.sidebar.button("📤 Registrar salida/merma"):
        st.session_state["menu"] = "Movimientos"
        st.session_state.mostrar_form_salida = True
        st.session_state.mostrar_form_compra = False
        st.session_state.mostrar_form_consumo = False

    if st.sidebar.button("📋 Nueva receta"):
        st.session_state["menu"] = "Recetas"
        st.session_state.mostrar_form_receta = True

    if st.sidebar.button("👤 Nuevo usuario"):
        st.session_state["menu"] = "Usuarios"
        st.session_state.mostrar_form_usuario = True

st.sidebar.divider()

# -----------------------
# Menú principal
# -----------------------
menu_options = ["Dashboard", "Movimientos"]
if is_admin:
    menu_options = ["Dashboard", "Insumos", "Recetas", "Movimientos", "Usuarios"]

menu = st.sidebar.radio("Navegación", menu_options, key="menu")

if menu != st.session_state.get("_last_menu"):
    st.session_state.mostrar_form_insumo = False
    st.session_state.mostrar_form_compra = False
    st.session_state.mostrar_form_salida = False
    st.session_state.mostrar_form_consumo = False
    st.session_state.mostrar_form_receta = False
    st.session_state.mostrar_form_usuario = False
st.session_state["_last_menu"] = menu

# -----------------------
# Dashboard
# -----------------------
if menu == "Dashboard":
    st.subheader("Dashboard")
    insumos = get_insumos()
    if insumos.empty:
        st.info("No hay insumos cargados todavía.")
    else:
        total_insumos = len(insumos)
        stock_bajo = len(insumos[insumos["stock_actual"] <= insumos["stock_minimo"]])
        c1, c2 = st.columns(2)
        c1.metric("Cantidad de insumos", total_insumos)
        c2.metric("Insumos con stock bajo", stock_bajo)

        # Staff don't see costs
        cols_dashboard = ["nombre", "categoria", "unidad", "stock_actual", "stock_minimo"]
        if is_admin:
            cols_dashboard.append("costo_unitario")

        st.subheader("Stock actual")
        st.dataframe(insumos[cols_dashboard], use_container_width=True)

        st.subheader("Alertas")
        alertas = insumos[insumos["stock_actual"] <= insumos["stock_minimo"]]
        if alertas.empty:
            st.success("No hay alertas de stock.")
        else:
            st.warning("Hay insumos por debajo del stock mínimo:")
            st.dataframe(
                alertas[["nombre", "stock_actual", "stock_minimo", "unidad"]],
                use_container_width=True,
            )

# -----------------------
# Gestión de Insumos (admin only)
# -----------------------
elif menu == "Insumos":
    if not is_admin:
        st.error("Acceso restringido.")
        st.stop()

    st.subheader("Gestión de insumos")

    if st.session_state.mostrar_form_insumo:
        with st.form("form_insumo"):
            nombre = st.text_input("Nombre del insumo")
            categoria = st.text_input("Categoría")
            unidad = st.selectbox("Unidad", ["g", "kg", "ml", "L", "un"])
            stock_actual = st.number_input("Stock actual", min_value=0.0, value=0.0)
            stock_minimo = st.number_input("Stock mínimo", min_value=0.0, value=0.0)
            costo_unitario = st.number_input("Costo unitario", min_value=0.0, value=0.0)
            proveedor = st.text_input("Proveedor")
            submitted = st.form_submit_button("Agregar insumo")

        if submitted:
            if nombre.strip():
                add_insumo(nombre, categoria, unidad, stock_actual, stock_minimo, costo_unitario, proveedor)
                st.success(f"Insumo '{nombre}' agregado correctamente.")
                st.session_state.mostrar_form_insumo = False
            else:
                st.error("El nombre es obligatorio.")

    st.subheader("Listado de insumos")
    insumos = get_insumos()
    if not insumos.empty:
        st.dataframe(insumos, use_container_width=True)
    else:
        st.info("No hay insumos cargados.")

# -----------------------
# Recetas (admin only)
# -----------------------
elif menu == "Recetas":
    if not is_admin:
        st.error("Acceso restringido.")
        st.stop()

    st.subheader("Gestión de recetas")
    insumos = get_insumos()

    if st.session_state.mostrar_form_receta:
        if "receta_ingredientes_temp" not in st.session_state:
            st.session_state.receta_ingredientes_temp = []

        st.markdown("#### Nueva receta")
        nombre_receta = st.text_input("Nombre de la receta", key="input_nombre_receta")

        if not insumos.empty:
            opciones = build_opciones(insumos)
            with st.form("form_add_ing_new", clear_on_submit=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                ing_label = col1.selectbox("Insumo", list(opciones.keys()))
                ing_cantidad = col2.number_input("Cantidad", min_value=0.01, value=1.0)
                if col3.form_submit_button("➕ Añadir"):
                    st.session_state.receta_ingredientes_temp.append({
                        "insumo_id": opciones[ing_label],
                        "label": ing_label,
                        "cantidad": ing_cantidad,
                    })

        if st.session_state.receta_ingredientes_temp:
            st.markdown("**Ingredientes agregados:**")
            to_delete = None
            for i, ing in enumerate(st.session_state.receta_ingredientes_temp):
                c1, c2 = st.columns([5, 1])
                c1.write(f"• {ing['label']} — {ing['cantidad']}")
                if c2.button("🗑", key=f"del_temp_{i}"):
                    to_delete = i
            if to_delete is not None:
                st.session_state.receta_ingredientes_temp.pop(to_delete)
        else:
            st.caption("Todavía no agregaste ingredientes.")

        col_save, col_cancel = st.columns([1, 1])
        if col_save.button("💾 Guardar receta", key="btn_guardar_receta"):
            if not nombre_receta.strip():
                st.error("El nombre es obligatorio.")
            elif not st.session_state.receta_ingredientes_temp:
                st.error("Agregá al menos un ingrediente.")
            else:
                receta_id = add_receta(nombre_receta.strip())
                for ing in st.session_state.receta_ingredientes_temp:
                    add_ingrediente_receta(receta_id, ing["insumo_id"], ing["cantidad"])
                st.success(f"Receta '{nombre_receta}' guardada.")
                st.session_state.receta_ingredientes_temp = []
                st.session_state.mostrar_form_receta = False
                st.rerun()

        if col_cancel.button("Cancelar", key="btn_cancelar_receta"):
            st.session_state.receta_ingredientes_temp = []
            st.session_state.mostrar_form_receta = False
            st.rerun()

        st.divider()

    recetas = get_recetas()
    if recetas.empty:
        st.info("No hay recetas cargadas. Usá el botón '📋 Nueva receta' para crear una.")
    else:
        accion = st.session_state.pop("_receta_accion", None)
        if accion:
            if accion["tipo"] == "add":
                add_ingrediente_receta(accion["receta_id"], accion["insumo_id"], accion["cantidad"])
            elif accion["tipo"] == "delete":
                delete_ingrediente_receta(accion["ing_id"])

        for _, receta in recetas.iterrows():
            with st.expander(f"**{receta['nombre']}**", expanded=False):
                ingredientes = get_ingredientes_receta(receta["id"])

                if not ingredientes.empty:
                    for _, ing in ingredientes.iterrows():
                        c1, c2 = st.columns([5, 1])
                        c1.write(f"• {ing['insumo']} — {ing['cantidad']} {ing['unidad']}")
                        if c2.button("🗑", key=f"del_ing_{ing['id']}"):
                            st.session_state["_receta_accion"] = {"tipo": "delete", "ing_id": ing["id"]}
                else:
                    st.caption("Sin ingredientes todavía.")

                if not insumos.empty:
                    st.markdown("**Agregar ingrediente:**")
                    opciones = build_opciones(insumos)
                    with st.form(f"form_add_ing_{receta['id']}", clear_on_submit=True):
                        col1, col2, col3 = st.columns([3, 1, 1])
                        ing_label = col1.selectbox("Insumo", list(opciones.keys()))
                        ing_qty = col2.number_input("Cantidad", min_value=0.01, value=1.0)
                        if col3.form_submit_button("➕ Añadir"):
                            st.session_state["_receta_accion"] = {
                                "tipo": "add",
                                "receta_id": receta["id"],
                                "insumo_id": opciones[ing_label],
                                "cantidad": ing_qty,
                            }

# -----------------------
# Movimientos
# -----------------------
elif menu == "Movimientos":

    # Consumo — available to all roles
    if st.session_state.mostrar_form_consumo:
        st.subheader("Registrar consumo")
        recetas = get_recetas()
        if recetas.empty:
            st.info("No hay recetas cargadas. Pedile al administrador que cree una.")
        else:
            with st.form("form_consumo"):
                opciones_recetas = {row["nombre"]: row["id"] for _, row in recetas.iterrows()}
                receta_label = st.selectbox("Receta", list(opciones_recetas.keys()))
                cantidad_vendida = st.number_input("Cantidad vendida", min_value=1, value=1, step=1)
                motivo = st.text_input("Nota (opcional)")
                submitted = st.form_submit_button("Registrar consumo")

            if submitted:
                try:
                    registrar_consumo_receta(
                        opciones_recetas[receta_label],
                        cantidad_vendida,
                        motivo=motivo or receta_label,
                        usuario=current_user_id,
                    )
                    st.success(f"Consumo de {cantidad_vendida}x {receta_label} registrado.")
                    st.session_state.mostrar_form_consumo = False
                except ValueError as e:
                    st.error(str(e))
        st.divider()

    # Compra — admin only
    if is_admin and st.session_state.mostrar_form_compra:
        st.subheader("Registrar compra")
        insumos = get_insumos()
        if insumos.empty:
            st.info("Primero debes cargar insumos.")
        else:
            with st.form("form_compra"):
                opciones = build_opciones(insumos)
                insumo_label = st.selectbox("Selecciona un insumo", list(opciones.keys()))
                cantidad = st.number_input("Cantidad comprada", min_value=0.01, value=1.0)
                motivo = st.text_input("Proveedor / detalle")
                submitted = st.form_submit_button("Registrar compra")

            if submitted:
                try:
                    registrar_movimiento("compra", opciones[insumo_label], cantidad, motivo, usuario=current_user_id)
                    st.success("Compra registrada correctamente.")
                    st.session_state.mostrar_form_compra = False
                except Exception as e:
                    st.error(str(e))
        st.divider()

    # Salida/merma — admin only
    if is_admin and st.session_state.mostrar_form_salida:
        st.subheader("Registrar salida / merma")
        insumos = get_insumos()
        if insumos.empty:
            st.info("Primero debes cargar insumos.")
        else:
            with st.form("form_salida"):
                opciones = build_opciones(insumos)
                tipo = st.selectbox("Tipo de salida", ["merma", "consumo", "ajuste"])
                insumo_label = st.selectbox("Selecciona un insumo", list(opciones.keys()))
                cantidad = st.number_input("Cantidad a descontar", min_value=0.01, value=1.0)
                motivo = st.text_input("Motivo")
                submitted = st.form_submit_button("Registrar salida")

            if submitted:
                try:
                    registrar_movimiento(tipo, opciones[insumo_label], cantidad, motivo, usuario=current_user_id)
                    st.success("Salida registrada correctamente.")
                    st.session_state.mostrar_form_salida = False
                except Exception as e:
                    st.error(str(e))
        st.divider()

    st.subheader("Historial de movimientos")
    movimientos = get_movimientos()
    if movimientos.empty:
        st.info("No hay movimientos registrados.")
    else:
        st.dataframe(movimientos, use_container_width=True)

# -----------------------
# Usuarios (admin only)
# -----------------------
elif menu == "Usuarios":
    if not is_admin:
        st.error("Acceso restringido.")
        st.stop()

    st.subheader("Gestión de usuarios")

    if st.session_state.mostrar_form_usuario:
        with st.form("form_nuevo_usuario"):
            new_email = st.text_input("Email")
            new_password = st.text_input("Contraseña", type="password")
            new_role = st.selectbox("Rol", ["staff", "admin"])
            submitted = st.form_submit_button("Crear usuario")

        if submitted:
            if new_email.strip() and new_password.strip():
                user, error = create_user(new_email.strip(), new_password.strip(), new_role)
                if error:
                    st.error(f"Error: {error}")
                else:
                    st.success(f"Usuario '{new_email}' creado como {new_role}.")
                    st.session_state.mostrar_form_usuario = False
            else:
                st.error("Email y contraseña son obligatorios.")
        st.divider()

    users = get_users()
    if not users:
        st.info("No se pudieron cargar los usuarios.")
    else:
        st.markdown(f"**{len(users)} usuario(s) registrado(s)**")
        for u in users:
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            c1.write(u["email"])
            c2.write(u["role"])
            # Role toggle
            new_role = "admin" if u["role"] == "staff" else "staff"
            if u["id"] != current_user_id:  # can't change own role
                if c3.button(f"→ {new_role}", key=f"role_{u['id']}"):
                    update_user_role(u["id"], new_role)
                    st.rerun()
                if c4.button("🗑 Eliminar", key=f"del_user_{u['id']}"):
                    delete_user(u["id"])
                    st.rerun()
            else:
                c3.caption("(vos)")