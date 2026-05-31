# Solvy — BancoSol Agent · Guía de Setup

## Tabla de contenidos

1. [Prerequisitos](#1-prerequisitos)
2. [Obtener el ZIP y extraerlo](#2-obtener-el-zip-y-extraerlo)
3. [Ejecutar el script de setup](#3-ejecutar-el-script-de-setup)
4. [Escanear el QR de WhatsApp ← paso de interfaz](#4-escanear-el-qr-de-whatsapp--paso-de-interfaz)
5. [Iniciar el agente Python](#5-iniciar-el-agente-python)
6. [Verificar que todo funciona](#6-verificar-que-todo-funciona)
7. [Uso diario](#7-uso-diario)
8. [Agregar o quitar números autorizados](#8-agregar-o-quitar-números-autorizados)
9. [Solución de problemas](#9-solución-de-problemas)

---

## 1. Prerequisitos

Instala estas herramientas **antes** de correr el script. Cada una tiene un instalador gráfico.

| Herramienta | Versión mínima | Link |
|---|---|---|
| Docker Desktop | 4.x | https://www.docker.com/products/docker-desktop |
| Python | 3.11 | https://www.python.org/downloads/ |

> **Python en Windows:** Durante la instalación, tildar la opción **"Add Python to PATH"** antes de hacer clic en Install Now.

También necesitás tener a mano:

- **API Key de OpenRouter** — pedisela al equipo o creá una cuenta en https://openrouter.ai
- **Carpeta `Problemas\`** del Knowledge Base de BancoSol (los 240 archivos `PROB-*.md`). Copiala en algún lugar de tu máquina y recordá la ruta completa.

---

## 2. Obtener el ZIP y extraerlo

1. Recibís el archivo `solvy-bancosol-YYYY-MM-DD.zip` del equipo.
2. Click derecho → **Extraer todo...** → elegí la carpeta destino (ejemplo: `C:\proyectos\solvy`).
3. Abrí esa carpeta. Debe contener:

```
solvy/
├── docker-compose.yml
├── setup.ps1
├── SETUP.md          ← este archivo
└── agent/
    ├── agent.py
    ├── main.py
    ├── requirements.txt
    ├── .env.example   ← plantilla de configuración
    └── ... (resto de archivos .py)
```

---

## 3. Ejecutar el script de setup

> Este paso hace todo lo de consola: levanta Docker, instala deps de Python, y registra la instancia en Evolution API.

1. Abrí **PowerShell** como administrador.
   - Buscá "PowerShell" en el menú inicio → Click derecho → **Ejecutar como administrador**.

2. Navega a la carpeta del proyecto:
   ```powershell
   cd C:\proyectos\solvy
   ```

3. Permitir la ejecución del script (solo la primera vez):
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
   ```
   Escribí `S` o `A` cuando pregunte.

4. Ejecutá el script:
   ```powershell
   .\setup.ps1
   ```

5. El script te va a pedir los siguientes datos uno por uno:

   | Campo | Descripción |
   |---|---|
   | Evolution API Key | Podés aceptar la que genera el script (recomendado) |
   | OpenRouter API Key | Tu `sk-or-v1-...` de openrouter.ai |
   | Números autorizados | Los números de WhatsApp del bot, con código de país, sin `+` |
   | Número de soporte | El número del SolvyCall que recibe casos derivados |
   | Ruta al KB | Ruta completa a tu carpeta `Problemas\` |
   | Puerto del agente | Dejar en `3000` salvo que ese puerto esté ocupado |
   | Horas de inactividad | Dejar en `24` |

6. El script va a tardar **1-2 minutos** mientras Docker descarga las imágenes la primera vez. Las siguientes veces es casi instantáneo.

7. Si todo va bien, ves al final:

   ```
   ── TODO LISTO ────────────────────
     PostgreSQL  →  localhost:5432
     Redis       →  localhost:6379
     Evolution   →  http://localhost:8080
     Manager UI  →  http://localhost:8080/manager
   ```

---

## 4. Escanear el QR de WhatsApp ← paso de interfaz

Este es el único paso que **no se puede automatizar**: necesitás conectar el número de WhatsApp del bot a Evolution API escaneando un código QR, igual que cuando conectás WhatsApp Web.

### Instrucciones paso a paso

1. **Abrí el Manager de Evolution** en el navegador:
   ```
   http://localhost:8080/manager
   ```

2. Aparece la interfaz de Evolution API Manager. En el campo **API KEY** (arriba a la derecha o en el login), ingresá la clave que te mostró el script al final.

   > Si no la recordás, la encontrás en `agent\.env`, línea `EVOLUTION_API_KEY=...`

3. En el panel izquierdo vas a ver la instancia **`banco-prueba`**. Hacé clic en ella.

4. Hacé clic en el botón **Connect** (o el ícono de QR/conectar).

5. Aparece un código QR. **Escanealo con el teléfono que va a ser el número del bot:**
   - Abrí WhatsApp en ese teléfono.
   - Menú (tres puntos) → **Dispositivos vinculados** → **Vincular un dispositivo**.
   - Apuntá la cámara al QR.

6. Cuando el escaneo sea exitoso, el estado de la instancia cambia a **`open`** o **`connected`** y el QR desaparece.

   > **Importante:** El teléfono que escaneaste va a quedar vinculado como "dispositivo adicional" en WhatsApp (como WhatsApp Web). Puede seguir usándose normalmente desde el teléfono.

### Si el QR expira

Tenés unos 60 segundos para escanearlo. Si expira, actualizá la página o hacé clic en **Reconnect** / **New QR** para generar uno nuevo.

---

## 5. Iniciar el agente Python

Una vez que el QR está escaneado, iniciá el agente:

```powershell
cd C:\proyectos\solvy\agent
python main.py
```

Deberías ver algo así:

```
[KB] Índice cargado: 240 artículos desde C:\...\Problemas
INFO:     Started server process [XXXXX]
INFO:     Uvicorn running on http://0.0.0.0:3000 (Press CTRL+C to quit)
```

> **Dejá esta ventana abierta.** El agente se detiene si cerrás la consola.

---

## 6. Verificar que todo funciona

1. Desde uno de los números autorizados, enviá un mensaje al número del bot en WhatsApp.
2. El bot debe responder con el saludo de Solvy en pocos segundos.
3. En la consola donde corre `main.py` deberían aparecer líneas de log como:
   ```
   [Solvy] 5916xxxxxxx | initial | 'hola'
   ```

Si no responde, revisá primero la sección [Solución de problemas](#9-solución-de-problemas).

---

## 7. Uso diario

Cada vez que vayas a trabajar con el agente necesitás **dos cosas corriendo**:

### A) Levantar los contenedores Docker

```powershell
cd C:\proyectos\solvy
docker compose up -d
```

O simplemente abrí Docker Desktop y verificá que los tres contenedores (`postgres`, `redis`, `evolution`) están en verde.

### B) Iniciar el agente Python

```powershell
cd C:\proyectos\solvy\agent
python main.py
```

### Apagar todo al terminar

```powershell
cd C:\proyectos\solvy
docker compose down
```

> No es estrictamente necesario apagar los contenedores (están configurados con `restart: unless-stopped`), pero si Docker Desktop está configurado para arrancar con Windows van a estar siempre activos.

---

## 8. Agregar o quitar números autorizados

El agente solo responde a los números listados en `agent\.env`. Para agregar o quitar:

1. Abrí `agent\.env` con cualquier editor de texto (Notepad, VSCode, etc.).
2. Editá la línea `ALLOWED_NUMBERS`:
   ```
   ALLOWED_NUMBERS=59160879844,59175572528,59170870580
   ```
   Separá los números con coma, sin espacios, con código de país pero sin `+`.
3. Guardá el archivo.
4. **Reiniciá el agente** (Ctrl+C en la consola y volvé a correr `python main.py`).

---

## 9. Solución de problemas

### El script setup.ps1 falla con "no se puede cargar el archivo"

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### El QR no aparece en el Manager

- Verificá que los contenedores estén corriendo: `docker compose ps`
- Revisá los logs de Evolution: `docker compose logs evolution --tail 50`
- Esperá 30 segundos más — al arrancar por primera vez hace migraciones de DB que tardan.

### El bot no responde aunque el QR está escaneado

Verificá en orden:

1. **¿El agente Python está corriendo?** — Debe haber una consola con `python main.py` activa.
2. **¿Tu número está en `ALLOWED_NUMBERS`?** — Revisá `agent\.env`.
3. **¿El webhook está registrado?** — Volvé a correr `python setup_webhook.py` desde la carpeta `agent\`.
4. **¿Evolution puede llegar al agente?** — El webhook apunta a `http://host.docker.internal:3000/webhook`. Verificá que el agente esté en el puerto correcto.

### "Module not found" al correr main.py

```powershell
cd C:\proyectos\solvy\agent
pip install -r requirements.txt
```

### Los contenedores se caen solos

```powershell
docker compose logs      # ver errores de todos los servicios
docker compose logs evolution --tail 100   # solo Evolution
```

### El bot responde lento

Normal en la primera respuesta de cada sesión (el modelo tarda 3-8 segundos). Si tarda más de 15 segundos consistentemente, revisá tu conexión y el estado de OpenRouter en https://status.openrouter.ai

### Reiniciar todo desde cero

```powershell
cd C:\proyectos\solvy
docker compose down -v        # elimina contenedores Y volúmenes (borra la DB)
Remove-Item agent\conversation_state.json -ErrorAction SilentlyContinue
docker compose up -d
# Esperar 30s y luego:
cd agent
python setup_webhook.py
```

Después volvé a escanear el QR (Paso 4).
