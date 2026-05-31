# Solvy — Guía de Setup

**Solvy** es el agente virtual de BancoSol. Atiende clientes por WhatsApp, diagnostica problemas usando una base de conocimiento de 240 artículos, y escala casos al equipo de soporte humano (SolvyCall) cuando es necesario. Corre completamente self-hosted: sin dependencias de servicios de terceros salvo el modelo de lenguaje.

---

## Tabla de contenidos

1. [Prerequisitos](#1-prerequisitos)
2. [Preparar la base de conocimiento](#2-preparar-la-base-de-conocimiento)
3. [Configurar el entorno](#3-configurar-el-entorno)
4. [Levantar la infraestructura](#4-levantar-la-infraestructura)
5. [Conectar WhatsApp (escanear QR)](#5-conectar-whatsapp-escanear-qr)
6. [Iniciar el agente](#6-iniciar-el-agente)
7. [Verificar que todo funciona](#7-verificar-que-todo-funciona)
8. [Modo presentación (todos los números)](#8-modo-presentación-todos-los-números)
9. [Uso diario](#9-uso-diario)
10. [Solución de problemas](#10-solución-de-problemas)

---

## 1. Prerequisitos

Instalá estas dos herramientas antes de continuar. Ambas tienen instalador gráfico.

| Herramienta | Versión mínima | Descarga |
|---|---|---|
| Docker Desktop | 4.x | https://www.docker.com/products/docker-desktop |
| Python | 3.11 | https://www.python.org/downloads/ |

> **Python en Windows:** durante la instalación, activar la opción **"Add Python to PATH"** antes de hacer clic en Install Now.

También necesitás tener a mano:

- **API Key de OpenRouter** (`sk-or-v1-...`) — el equipo puede proveer una, o creá una cuenta en https://openrouter.ai
- **Carpeta `Problemas\`** del Knowledge Base de BancoSol — los 240 archivos `PROB-*.md`. Anotá la ruta completa donde la guardás.

---

## 2. Preparar la base de conocimiento

El agente no inventa respuestas: lee una carpeta de artículos en formato Markdown y los usa para diagnosticar y resolver problemas. Sin esta carpeta, el agente arranca pero no puede ayudar a ningún cliente.

### Qué es y cómo funciona

La base de conocimiento es simplemente **una carpeta con archivos `.md`** nombrados `PROB-001.md`, `PROB-002.md`, etc. Cada archivo describe un problema específico: qué lo causa, cómo detectarlo y cómo resolverlo.

Al iniciar, el agente indexa todos los archivos en memoria. Cuando un cliente reporta un código de error, el agente busca el artículo correspondiente y le explica los pasos de solución al cliente por WhatsApp.

### Opción A — Usar la base de conocimiento existente de BancoSol

Si tenés acceso a la carpeta `Problemas\` del playbook de BancoSol (los 240 archivos `PROB-*.md`), copiala a cualquier ubicación de tu máquina. Por ejemplo:

```
C:\solvy-kb\Problemas\
```

Luego apuntá `OBSIDIAN_KB_PATH` a esa carpeta en el `.env` (ver Paso 3).

### Opción B — Crear tu propia base de conocimiento

Si querés adaptar el agente a otro banco u organización, creá una carpeta vacía y poblala con tus propios artículos siguiendo este formato:

**Nombre del archivo:** `PROB-001.md` (numeración correlativa, tres dígitos)

**Estructura del archivo:**

```markdown
# Título descriptivo del problema

**Keywords:** palabra1 palabra2 palabra3 nombreapp bancoxyz autenticacion

---
producto: AppSol
categoria: Autenticación
severidad: S2
---

## Cuándo usar este manual
- Señal principal: descripción de cuándo aparece este problema.
- Validaciones específicas: qué revisar en el dispositivo o cuenta del cliente.

## Pasos de Solución
1. Primer paso para resolverlo.
2. Segundo paso.
3. Tercer paso si aplica.

## Resultado esperado
El cliente puede volver a operar normalmente luego de seguir los pasos indicados.
```

**Campos obligatorios** que el agente lee activamente:

| Campo | Dónde va | Para qué sirve |
|---|---|---|
| `# Título` | Primera línea | Nombre del problema que se muestra al cliente |
| `**Keywords:**` | Línea 3 | Búsqueda por palabras clave |
| `producto:` | Frontmatter | Filtra artículos por aplicación del cliente |
| `- Señal principal:` | Sección "Cuándo usar" | Contexto que se envía al LLM para generar respuesta |
| `- Validaciones específicas:` | Sección "Cuándo usar" | Ídem |
| `## Resultado esperado` | Sección propia | Ídem |

**Valores válidos para `producto:`**

| Valor en el artículo | Aplicación que reporta el cliente |
|---|---|
| `AppSol` | AppSol |
| `Altoke` | Al Toque |
| `Banca Web` | SolNet |

> Si usás otro nombre de producto, el agente igualmente funciona pero no puede filtrar artículos por app y usará toda la base de conocimiento en la búsqueda.

### ¿Cuántos artículos necesito para una demo?

Con **5 a 10 artículos** bien escritos el agente ya demuestra su capacidad de búsqueda y resolución. No es necesario tener los 240 para una presentación.

---

## 3. Configurar el entorno

Dentro de la carpeta `agent\` hay un archivo `.env` con todas las variables del sistema. Abrilo con cualquier editor de texto y completá los campos marcados:

```env
# ── Infraestructura (no tocar) ──────────────────────────────────
EVOLUTION_URL=http://localhost:8080
EVOLUTION_API_KEY=change-me-before-production
EVOLUTION_INSTANCE=banco-prueba

# ── LLM ─────────────────────────────────────────────────────────
OPENROUTER_API_KEY=sk-or-v1-...          ← reemplazá con tu clave
LLM_MODEL=openrouter/owl-alpha

# ── Knowledge Base ───────────────────────────────────────────────
OBSIDIAN_KB_PATH=C:\ruta\a\tu\carpeta\Problemas   ← ruta completa a los PROB-*.md

# ── Control de acceso ────────────────────────────────────────────
ALLOWED_NUMBERS=591XXXXXXXXX,591XXXXXXXXX   ← números habilitados, con código de país, sin +
SUPPORT_NUMBER=591XXXXXXXXX                 ← número del SolvyCall que recibe escaladas

# ── Comportamiento ───────────────────────────────────────────────
AGENT_PORT=3000
INACTIVITY_HOURS=24

# ── Integración con sistema principal (opcional) ─────────────────
BASE_URL=           ← URL base del backend Java (ej: https://api.solvy.com)
CASE_STATUS_URL=    ← URL que verán los clientes para consultar su caso
```

> **`EVOLUTION_API_KEY`** — podés dejarlo como `change-me-before-production` para desarrollo local. Si querés una clave personalizada, cambiala **antes** de levantar Docker por primera vez; después necesitarías recrear los contenedores.

---

## 4. Levantar la infraestructura

Desde la raíz del proyecto, abrí una terminal y ejecutá:

```powershell
docker compose up -d
```

Esto levanta tres contenedores:

| Servicio | Puerto | Descripción |
|---|---|---|
| Evolution API | 8080 | Bridge de WhatsApp |
| PostgreSQL | 5432 | Base de datos de Evolution |
| Redis | 6379 | Caché de sesiones |

La primera vez descarga las imágenes (puede tardar 2-3 minutos). Las siguientes veces arranca en segundos.

Verificá que los tres estén corriendo:

```powershell
docker compose ps
```

Todos deben aparecer con estado `Up`.

---

## 5. Conectar WhatsApp (escanear QR)

Este es el único paso manual: vincular el número de WhatsApp del bot.

### Registrar la instancia y el webhook

Desde la carpeta `agent\`, ejecutá una sola vez:

```powershell
cd agent
pip install -r requirements.txt
python setup_webhook.py
```

Esto crea la instancia en Evolution API y configura el webhook que conecta los mensajes entrantes con el agente Python.

### Escanear el QR

1. Abrí el Manager de Evolution en el navegador:
   ```
   http://localhost:8080/manager
   ```

2. En el campo **API KEY** ingresá el valor de `EVOLUTION_API_KEY` de tu `.env`.

3. En el panel izquierdo hacé clic en la instancia **`banco-prueba`** → **Connect**.

4. Aparece un QR. Escanealo con el teléfono que será el número del bot:
   - WhatsApp → Menú (⋮) → **Dispositivos vinculados** → **Vincular un dispositivo**
   - Apuntá la cámara al QR

5. Cuando el estado cambie a **`open`** o **`connected`**, el QR desaparece. Listo.

> El teléfono sigue funcionando normalmente; el bot actúa como un dispositivo adicional (igual que WhatsApp Web).

> **QR expirado:** tenés ~60 segundos para escanearlo. Si expira, hacé clic en **Reconnect** o recargá la página.

---

## 6. Iniciar el agente

Con la infraestructura corriendo y el QR escaneado, iniciá el agente:

```powershell
cd agent
python main.py
```

Deberías ver:

```
[KB] Índice cargado: 240 artículos desde C:\...\Problemas
INFO:     Uvicorn running on http://0.0.0.0:3000 (Press CTRL+C to quit)
```

> **Dejá esta ventana abierta.** El agente se detiene si cerrás la consola.

---

## 7. Verificar que todo funciona

1. Desde un número habilitado en `ALLOWED_NUMBERS`, mandá un mensaje al número del bot.
2. El bot responde con el saludo de Solvy en pocos segundos.
3. En la consola debería aparecer:
   ```
   [Solvy] 591XXXXXXXXX | initial | 'hola'
   ```

---

## 8. Modo presentación (todos los números)

Para que cualquier número pueda usar el bot durante la presentación, cambiá en `agent\.env`:

```env
ALLOWED_NUMBERS=*
```

Reiniciá el agente (Ctrl+C y volvé a correr `python main.py`). A partir de ese momento cualquier chat directo (no grupos) recibe respuesta.

> Para volver a modo restringido, reemplazá `*` por la lista de números autorizados y reiniciá.

---

## 9. Uso diario

Cada vez que retomes el trabajo necesitás dos cosas corriendo en paralelo:

### Levantar contenedores Docker

```powershell
docker compose up -d
```

O verificá en Docker Desktop que `postgres`, `redis` y `evolution` estén en verde.

### Iniciar el agente

```powershell
cd agent
python main.py
```

### Apagar todo al terminar

```powershell
docker compose down
```

---

## 10. Solución de problemas

### `setup.ps1` o scripts no se ejecutan: "no se puede cargar el archivo"

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### El QR no aparece en el Manager

```powershell
docker compose ps                          # verificar que los 3 contenedores están Up
docker compose logs evolution --tail 50   # ver errores de Evolution
```

Evolution hace migraciones de DB la primera vez — esperá 30 segundos antes de intentar.

### El bot no responde aunque el QR está escaneado

Verificá en orden:

1. **¿El agente Python está corriendo?** — debe haber una consola con `python main.py` activa.
2. **¿Tu número está habilitado?** — revisá `ALLOWED_NUMBERS` en `agent\.env` (o usá `*` para modo presentación).
3. **¿El webhook está registrado?** — desde `agent\` ejecutá `python setup_webhook.py` nuevamente.
4. **¿Evolution puede alcanzar al agente?** — el webhook apunta a `http://host.docker.internal:3000/webhook`. Verificá que el agente esté en el puerto de `AGENT_PORT`.

### "Module not found" al correr main.py

```powershell
cd agent
pip install -r requirements.txt
```

### El agente cargó 0 artículos del KB

```
[KB] WARN: ruta no encontrada: C:\...
```

La ruta en `OBSIDIAN_KB_PATH` no existe o está mal escrita. Verificá que apunte directamente a la carpeta que contiene los archivos `PROB-*.md`.

### Los contenedores se caen o no levantan

```powershell
docker compose logs          # errores de todos los servicios
docker compose logs postgres --tail 50
```

### El bot responde lento

Normal en la primera respuesta de cada sesión (3-8 segundos por el LLM). Si tarda más de 15 segundos de forma consistente, revisá tu conexión y el estado de OpenRouter en https://status.openrouter.ai

### Reiniciar todo desde cero

```powershell
docker compose down -v
Remove-Item agent\conversation_state.json -ErrorAction SilentlyContinue
docker compose up -d
```

Esperá 30 segundos, luego:

```powershell
cd agent
python setup_webhook.py
```

Después volvé a escanear el QR (Paso 4).
