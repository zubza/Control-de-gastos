import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text

st.set_page_config(page_title="Gestión Financiera", layout="wide", page_icon="🏦")

# 1. CONEXIÓN A NEON
try:
    conn = st.connection("neon", type="sql")
except Exception as e:
    st.error("⚠️ Error de conexión. Verifica tu archivo .streamlit/secrets.toml")
    st.stop()

st.title("🏦 Dashboard de Finanzas Personales")

# Creamos las pestañas de navegación superior
tab1, tab2, tab3 = st.tabs(["📊 Balance y Gráficos", "💰 Ingresar Movimientos", "📝 Cosas por Pagar"])

# ==========================================
# PESTAÑA 2: INGRESOS Y GASTOS (Formularios)
# ==========================================
with tab2:
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("💵 Registrar Sueldo")
        with st.form("form_sueldo", clear_on_submit=True):
            mes_s = st.date_input("Mes del Sueldo").replace(day=1)
            monto_s = st.number_input("Monto Sueldo Líquido ($)", min_value=0, step=10000)
            if st.form_submit_button("Guardar Sueldo"):
                if monto_s > 0:
                    query = text("INSERT INTO ingresos (mes, monto) VALUES (:m, :v) ON CONFLICT (mes) DO UPDATE SET monto = EXCLUDED.monto")
                    with conn.session as s:
                        s.execute(query, {"m": mes_s, "v": monto_s})
                        s.commit()
                    st.success("Sueldo guardado exitosamente.")
                    st.rerun()

    with col_b:
        st.subheader("💸 Registrar Gasto Realizado")
        with st.form("form_gastos", clear_on_submit=True):
            mes_g = st.date_input("Mes del Gasto").replace(day=1)
            cat_g = st.selectbox("Categoría", ["Luz", "Agua", "Gas", "Dividendo", "Internet", "Celular", "Feria (Verduras)", "Carne", "Supermercado", "Colaciones Niños", "Otros"])
            monto_g = st.number_input("Monto Pagado ($)", min_value=0, step=1000)
            if st.form_submit_button("Guardar Gasto"):
                if monto_g > 0:
                    with conn.session as s:
                        s.execute(text("INSERT INTO gastos_familiares (mes, categoria, monto) VALUES (:m, :c, :v)"), {"m": mes_g, "c": cat_g, "v": monto_g})
                        s.commit()
                    st.success(f"Gasto de {cat_g} guardado.")
                    st.rerun()

# ==========================================
# PESTAÑA 3: COSAS POR PAGAR (To-Do List)
# ==========================================
with tab3:
    st.subheader("📌 Cuentas Pendientes (Aún no pagadas)")
    with st.form("form_pendientes", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        desc_p = c1.text_input("Descripción (ej: Patente, Seguro)")
        monto_p = c2.number_input("Monto Estimado ($)", min_value=0, step=1000)
        limite_p = c3.date_input("Fecha Límite de Pago")
        if st.form_submit_button("Agregar a la lista"):
            if monto_p > 0 and desc_p:
                with conn.session as s:
                    s.execute(text("INSERT INTO pendientes (descripcion, monto, fecha_limite) VALUES (:d, :m, :f)"), {"d": desc_p, "m": monto_p, "f": limite_p})
                    s.commit()
                st.success("Añadido a cuentas por pagar.")
                st.rerun()
    
    # Mostrar la tabla de pendientes
    try:
        pendientes = conn.query("SELECT id, descripcion, monto, fecha_limite FROM pendientes WHERE pagado = FALSE ORDER BY fecha_limite ASC", ttl=0)
        if not pendientes.empty:
            st.dataframe(pendientes, use_container_width=True, hide_index=True)
        else:
            st.info("¡Excelente! No tienes cuentas pendientes por ahora.")
    except Exception as e:
        st.warning("Crea la tabla 'pendientes' en Neon para ver esta lista.")

# ==========================================
# PESTAÑA 1: BALANCE Y GRÁFICOS VISUALES
# ==========================================
with tab1:
    try:
        # 1. Traer datos para los KPIs superiores
        df_ingreso = conn.query("SELECT monto FROM ingresos ORDER BY mes DESC LIMIT 1", ttl=0)
        df_gastos_mes = conn.query("SELECT SUM(monto) as total FROM gastos_familiares WHERE mes = (SELECT MAX(mes) FROM ingresos)", ttl=0)
        df_pend = conn.query("SELECT SUM(monto) as total FROM pendientes WHERE pagado = FALSE", ttl=0)

        sueldo = int(df_ingreso['monto'].iloc[0]) if not df_ingreso.empty else 0
        gastado = int(df_gastos_mes['total'].iloc[0]) if not df_gastos_mes.empty and pd.notna(df_gastos_mes['total'].iloc[0]) else 0
        por_pagar = int(df_pend['total'].iloc[0]) if not df_pend.empty and pd.notna(df_pend['total'].iloc[0]) else 0
        
        quedan = sueldo - gastado
        proyectado = sueldo - gastado - por_pagar

        # Tarjetas de Resumen
        m1, m2, m3 = st.columns(3)
        m1.metric("Sueldo Ingresado", f"${sueldo:,.0f}")
        m2.metric("Ya Gastado (Mes Actual)", f"${gastado:,.0f}", delta=f"-{gastado}", delta_color="inverse")
        m3.metric("Saldo Disponible (En Cuenta)", f"${quedan:,.0f}")
        
        if por_pagar > 0:
            st.warning(f"🚨 **Proyección:** Tienes **${por_pagar:,.0f}** en cuentas por pagar. Si las pagas todas, llegarás a fin de mes con **${proyectado:,.0f}**.")
        else:
            st.success("✅ No tienes deudas pendientes registradas.")

        st.markdown("---")
        st.subheader("📈 Análisis Visual Histórico")

        # 2. Traer datos para los GRÁFICOS
        df_historico = conn.query("SELECT mes, categoria, monto FROM gastos_familiares ORDER BY mes ASC", ttl=0)

        if not df_historico.empty:
            df_historico['mes'] = pd.to_datetime(df_historico['mes'])
            
            col_izq, col_der = st.columns([2, 1])
            
            with col_izq:
                st.markdown("**Evolución del Gasto por Categoría**")
                evolucion = df_historico.groupby(['mes', 'categoria'])['monto'].sum().reset_index()
                fig_area = px.area(evolucion, x='mes', y='monto', color='categoria', 
                                   color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_area.update_layout(height=350, xaxis_title="", yaxis_title="Monto ($)", margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_area, use_container_width=True)
                
            with col_der:
                st.markdown("**Distribución Total**")
                distribucion = df_historico.groupby('categoria')['monto'].sum().reset_index()
                fig_pie = px.pie(distribucion, values='monto', names='categoria', hole=0.4)
                fig_pie.update_layout(height=350, showlegend=False, margin=dict(l=0, r=0, t=30, b=0))
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Ingresa tu primer gasto en la pestaña 'Ingresar Movimientos' para ver los gráficos.")
            
    except Exception as e:
        st.info("Las tablas aún no están creadas en Neon o están vacías.")