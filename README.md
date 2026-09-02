# Cotizador + caja aproximada (web) — INOXIDJOYAS

App web multiusuario. Se pega el pedido del cliente como **texto libre**, se
**cotiza** con el precio del snapshot (tomado de Aspel SAE) y se recomienda la
**caja más chica donde cabe** (aproximado por volumen, sin 3D).

- Corre gratis en **Streamlit Community Cloud**, disponible 24/7 (no depende de
  que tu PC de la oficina esté encendida).
- Protegida con **una contraseña compartida**.
- Los datos son un **snapshot** (`data/snapshot.json`) que refrescas cuando
  cambien precios; la app no se conecta a SAE.

---

## Archivos

| Archivo | Qué es |
|---|---|
| `app.py` | La app (interfaz Streamlit). |
| `logic.py` | Lógica: reconocer pedido + cotizar + recomendar caja. |
| `data/snapshot.json` | Foto del catálogo (productos, medidas, precios, cajas). |
| `refrescar_precios.py` | Se corre en tu PC para regenerar el snapshot desde SAE. |
| `requirements.txt` | Dependencias (las instala Streamlit Cloud solo). |
| `.streamlit/config.toml` | Tema/colores. |
| `.streamlit/secrets.toml.ejemplo` | Modelo del archivo de contraseña (local). |

---

## Probar en tu PC (opcional, antes de subir)

```bash
pip install -r requirements.txt
```

Copia `.streamlit/secrets.toml.ejemplo` a `.streamlit/secrets.toml` y pon una
contraseña. Luego:

```bash
streamlit run app.py
```

Se abre en `http://localhost:8501`.

---

## Subirla GRATIS a internet (una sola vez, ~15 min)

Necesitas 2 cuentas gratis: **GitHub** y **Streamlit Community Cloud**
(el login de Streamlit es con el mismo GitHub).

### 1) Crear cuenta en GitHub
- Ve a https://github.com y regístrate (gratis).

### 2) Subir esta carpeta a un repositorio
Desde esta carpeta (`cotizador-web`):

```bash
git init
git add .
git commit -m "Cotizador web INOXIDJOYAS"
```

Crea un repo nuevo en GitHub (botón **New repository**; puede ser **Private**),
y sigue las instrucciones que te da GitHub para "push an existing repository",
que son del estilo:

```bash
git remote add origin https://github.com/TU_USUARIO/cotizador-web.git
git branch -M main
git push -u origin main
```

> `.streamlit/secrets.toml` NO se sube (está en `.gitignore`): la contraseña se
> pone en Streamlit Cloud, no en el repo.

### 3) Desplegar en Streamlit Community Cloud
- Ve a https://share.streamlit.io e inicia sesión con GitHub.
- **Create app** → **Deploy a public app from GitHub**.
- Repository: tu repo · Branch: `main` · Main file path: `app.py`.
- Antes de darle Deploy, abre **Advanced settings → Secrets** y pega:

  ```toml
  app_password = "la-contraseña-que-quieras"
  ```

- **Deploy**. En 1–2 min te da una URL tipo
  `https://cotizador-web-inoxidjoyas.streamlit.app`.

### 4) Repartir el acceso
- Manda esa URL + la contraseña a las 2–5 personas. Entran desde PC o celular.
- Para cambiar la contraseña: en la app en Streamlit Cloud → **Settings →
  Secrets**, editas `app_password`, guardas. Se reinicia sola.

---

## Refrescar precios (cuando cambien)

Los precios son una foto. Para actualizarlos, en tu **PC de la oficina** (la que
alcanza Aspel SAE):

```bash
python refrescar_precios.py
git add data/snapshot.json
git commit -m "Actualiza precios"
git push
```

La app en la nube se reactualiza sola en ~1 minuto. Mientras tanto, siempre
sirve la última foto buena. (No necesitas hacer esto seguido: son precios de
empaque, que casi no cambian.)

---

## Notas

- Es un **aproximado por volumen**, no un acomodo exacto 3D. Los artículos
  **sin medida** capturada (kits, joyeros) se cotizan pero **no cuentan** para
  el tamaño de caja; la app lo avisa. Si capturas esas medidas en el Excel de
  cajas y refrescas, empezarán a contar.
- El **factor de llenado** (control en la app, 70 % por defecto) modela que la
  caja no se llena al 100 %. Súbelo si empacas apretado, bájalo para holgura.
- Límite del plan gratis de Streamlit: la app "duerme" si nadie la usa por
  mucho rato; el primer acceso del día puede tardar ~30 s en despertar. Para
  2–5 usuarios es irrelevante.
