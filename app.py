"""Cotizador + caja aproximada (web) - INOXIDJOYAS.

App multiusuario: se pega el pedido del cliente como texto libre, se cotiza con
el precio del snapshot (tomado de Aspel SAE) y se recomienda la caja mas chica
donde cabe (aproximado volumetrico, sin 3D).

Deploy gratis en Streamlit Community Cloud. Ver README.md.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

import logic

st.set_page_config(page_title="Cotizador de cajas - INOXIDJOYAS",
                   page_icon="📦", layout="wide")


# ----------------------------------------------------------------- login
def check_password() -> bool:
    """Login simple por contraseña compartida (st.secrets['app_password'])."""
    if st.session_state.get("auth_ok"):
        return True

    correcta = st.secrets.get("app_password", "inoxid2026")  # fallback local

    def _validar():
        st.session_state["auth_ok"] = (st.session_state.get("pw_in", "") == correcta)

    st.markdown("### 🔒 Acceso")
    st.text_input("Contraseña", type="password", key="pw_in", on_change=_validar)
    entrar = st.button("Entrar", type="primary")
    if entrar:
        _validar()
    if st.session_state.get("auth_ok"):
        st.session_state.pop("pw_in", None)
        st.rerun()
    if st.session_state.get("auth_ok") is False:
        st.error("Contraseña incorrecta.")
    st.caption("Pide la contraseña al administrador.")
    return False


if not check_password():
    st.stop()


# ----------------------------------------------------------------- datos
@st.cache_data(show_spinner=False)
def _cargar():
    return logic.cargar()


cat = _cargar()


def _fecha_snapshot(iso: str) -> str:
    try:
        return dt.datetime.fromisoformat(iso).strftime("%d/%b/%Y %H:%M")
    except Exception:
        return iso or "-"


# ----------------------------------------------------------------- encabezado
st.title("📦 Cotizador + caja aproximada")
st.caption(f"INOXIDJOYAS · {len(cat.products)} productos · {len(cat.boxes)} cajas · "
           f"precios del **{_fecha_snapshot(cat.generado)}**")

with st.expander("¿Cómo funciona? (leer una vez)"):
    st.markdown(
        "1. **Pega el pedido** del cliente en el cuadro (una línea por renglón).\n"
        "2. Ajusta el **factor de llenado** si quieres (70 % = típico).\n"
        "3. Clic en **Cotizar**.\n\n"
        "Reconoce cada renglón por **clave** (ej. `PA01`) o por **descripción** "
        "(ej. `caja dura brazalete x3`). Cotiza con el precio del snapshot y sugiere "
        "la caja más chica donde cabe.\n\n"
        "Cantidades válidas: `2 PA01`, `PA01 x10`, `x3`, `3 pzas`.\n\n"
        "⚠️ Es un **aproximado por volumen**, no un acomodo exacto 3D. Los artículos "
        "**sin medida** (kits, joyeros) se cotizan pero no cuentan para el tamaño de caja."
    )

col_in, col_out = st.columns([1, 1], gap="large")

EJEMPLO = ("2 PA01\n"
           "caja dura brazalete x3\n"
           "5 bolsa liston rosa\n"
           "PC01 x10\n"
           "1 joyero rosa mod2")

with col_in:
    st.subheader("Pedido")
    texto = st.text_area("Pega aquí el pedido (una línea por renglón)",
                         value="", height=280, placeholder=EJEMPLO, key="pedido_txt")
    c1, c2 = st.columns([1, 1])
    with c1:
        factor = st.slider("Factor de llenado", min_value=0.40, max_value=0.95,
                           value=0.70, step=0.05,
                           help="% útil de la caja. 70 % = típico. Súbelo si empacas "
                                "apretado, bájalo para más holgura.")
    with c2:
        st.write("")
        st.write("")
        procesar = st.button("🧮 Cotizar", type="primary", use_container_width=True)

if procesar and texto.strip():
    lineas, res = logic.cotizar(texto, cat, factor)

    with col_out:
        st.subheader("Resultado")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total", f"${res.total_importe:,.2f}")
        m2.metric("Piezas", res.total_piezas)
        m3.metric("Caja sugerida", res.caja if len(res.caja) < 16 else "ver abajo")

        st.markdown(f"### 📦 Caja recomendada: **{res.caja}**")
        sub = []
        if res.ocupacion is not None:
            sub.append(f"ocupación aprox. **{res.ocupacion:.0%}** del volumen interior")
        if res.alternativa:
            sub.append(f"alternativa: {res.alternativa}")
        if sub:
            st.caption(" · ".join(sub))

        for a in res.avisos:
            st.warning(a)

    # tabla de renglones (ancho completo abajo)
    st.divider()
    st.subheader("Detalle del pedido")
    filas, colores = [], []
    for ln in lineas:
        if not ln.matched:
            colores.append("background-color: #f8cbcb")   # rojo: no reconocida
        elif not ln.tiene_medidas:
            colores.append("background-color: #ffe6e6")   # rosa: sin medida
        else:
            colores.append("")
        filas.append({
            "Cant": ln.qty,
            "Clave": ln.clave or "—",
            "Artículo": ln.articulo or f"⚠️ NO RECONOCIDA: {ln.raw}",
            "Medida": "sin medida" if (ln.matched and not ln.tiene_medidas)
                      else ("sí" if ln.matched else "—"),
            "Precio": f"${ln.precio:,.2f}" if ln.precio is not None else "—",
            "Importe": f"${ln.importe:,.2f}" if ln.matched else "—",
        })
    vis = pd.DataFrame(filas)

    def _estilo(row):
        return [colores[row.name]] * len(row)

    st.dataframe(vis.style.apply(_estilo, axis=1),
                 use_container_width=True, hide_index=True)

    # descargar cotizacion
    csv = vis.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Descargar cotización (CSV)", data=csv,
                       file_name="cotizacion.csv", mime="text/csv")

elif procesar:
    with col_out:
        st.info("Pega un pedido en el cuadro de la izquierda.")

with st.sidebar:
    st.header("Catálogo")
    st.caption(f"Snapshot: {_fecha_snapshot(cat.generado)}")
    if not cat.sae_ok:
        st.warning("El snapshot se generó sin conexión a SAE (precios pueden faltar).")
    st.dataframe(
        pd.DataFrame([{"Clave": p["clave"], "Artículo": p["articulo"],
                       "Precio": p.get("precio")} for p in cat.products]),
        use_container_width=True, hide_index=True, height=360,
    )
    st.divider()
    st.caption("Cajas disponibles")
    st.dataframe(
        pd.DataFrame([{"Caja": b["nombre"], "Interior (cm)":
                       f"{b['int_l']}×{b['int_w']}×{b['int_h']}"} for b in cat.boxes]),
        use_container_width=True, hide_index=True, height=240,
    )
