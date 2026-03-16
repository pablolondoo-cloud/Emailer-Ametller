# 🚀 Guía de configuración — RPA Rutas Ametller Origen

## ¿Qué hace este sistema?
Cada día a las **20:00h (hora España)**, GitHub Actions:
1. Hace login en `control.instaleap.io`
2. Descarga las rutas del día via API
3. Genera un Excel con las columnas: Route Number, Job Number, Stop, Delivery From, Delivery To
4. Envía el Excel por email a las personas configuradas

---

## PASO 1 — Crear el repositorio en GitHub

1. Ve a [github.com](https://github.com) e inicia sesión (o crea cuenta gratis)
2. Haz clic en **"New repository"** (botón verde arriba a la derecha)
3. Configura así:
   - **Repository name:** `ametller-rutas-rpa`
   - **Visibility:** ✅ **Private** (muy importante — contiene código con acceso a la API)
   - Marca ✅ **Add a README file**
4. Haz clic en **"Create repository"**

---

## PASO 2 — Subir los archivos

En tu repositorio recién creado, sube estos 4 archivos:

| Archivo | Dónde ponerlo |
|---------|--------------|
| `fetch_routes.py` | raíz del repositorio |
| `send_email.py` | raíz del repositorio |
| `requirements.txt` | raíz del repositorio |
| `rutas_diarias.yml` | dentro de la carpeta `.github/workflows/` |

**Para crear la carpeta `.github/workflows/`:**
1. Haz clic en **"Add file" → "Create new file"**
2. En el nombre escribe: `.github/workflows/rutas_diarias.yml`
3. GitHub creará automáticamente las carpetas
4. Pega el contenido del archivo `rutas_diarias.yml`
5. Haz clic en **"Commit changes"**

Repite para los otros 3 archivos (estos van directamente en la raíz).

---

## PASO 3 — Configurar los Secrets (credenciales seguras)

Los Secrets son variables encriptadas que GitHub guarda de forma segura. El código nunca verá las contraseñas directamente.

1. En tu repositorio, ve a **Settings** (pestaña superior)
2. En el menú izquierdo: **Secrets and variables → Actions**
3. Haz clic en **"New repository secret"** y añade estos 4 secrets:

| Secret Name | Valor |
|-------------|-------|
| `PORTAL_EMAIL` | `AutomatizacionemailsRutas@instaleap.com` |
| `PORTAL_PASSWORD` | `AutomatizacionemailsRutas1?` |
| `GMAIL_USER` | tu cuenta Gmail (ej: `pablo@gmail.com`) |
| `GMAIL_APP_PASS` | el App Password de Gmail (ver Paso 4) |
| `EMAIL_TO` | emails separados por coma (ej: `pablo@empresa.com,ana@empresa.com`) |

---

## PASO 4 — Crear Gmail App Password

> ⚠️ Necesitas tener la **verificación en 2 pasos activada** en tu cuenta Gmail.

1. Ve a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. En "Seleccionar app" elige **"Correo"**
3. En "Seleccionar dispositivo" elige **"Otro"** y escribe `GitHub Actions`
4. Haz clic en **"Generar"**
5. Copia el código de **16 caracteres** que aparece → ese es tu `GMAIL_APP_PASS`

---

## PASO 5 — Probar manualmente

Una vez subidos los archivos y configurados los secrets:

1. Ve a la pestaña **Actions** de tu repositorio
2. En el menú izquierdo verás **"📦 Rutas Diarias - Ametller Origen"**
3. Haz clic en **"Run workflow"** → **"Run workflow"** (botón verde)
4. Espera ~1 minuto y verás si todo funciona ✅ o si hay algún error ❌

Si hay error, haz clic en el job fallido para ver los logs y dímelos — lo resolveremos.

---

## Estructura final del repositorio

```
ametller-rutas-rpa/
├── .github/
│   └── workflows/
│       └── rutas_diarias.yml   ← Programación y orquestación
├── fetch_routes.py             ← Login + API + Excel
├── send_email.py               ← Envío de email
├── requirements.txt            ← Dependencias Python
└── README.md
```

---

## Horario de ejecución

El workflow se ejecuta automáticamente:
- **Cada día a las 19:00 UTC = 20:00h hora España**
- El cron configurado es: `0 19 * * *`

> En verano (horario CEST = UTC+2), serían las 21:00h. Si quieres ajustarlo a verano/invierno automáticamente, dímelo.

---

## Preguntas frecuentes

**¿Es gratuito?**
Sí. GitHub Actions ofrece 2.000 minutos/mes gratis en repositorios privados. Este workflow usa ~2 minutos por ejecución = ~60 minutos/mes. Muy por debajo del límite.

**¿Mis credenciales están seguras?**
Sí. Los Secrets de GitHub están encriptados y nunca aparecen en los logs ni en el código.

**¿Qué pasa si no hay rutas ese día?**
El script detecta que no hay datos, no genera Excel y no envía email (evita emails vacíos).
