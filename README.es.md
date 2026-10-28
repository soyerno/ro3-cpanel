# RO3 CPanel (Panel de Administración Marca Blanca)

[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-gold.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Sin dependencias externas](https://img.shields.io/badge/dependencias-0-success.svg)]()

Panel de administración (CPanel) moderno, ligero y personalizable con **marca blanca** para servidores privados de **Ragnarok Online 3 / Ragnarok Origin PC (`RO3Emu`)**.

Diseñado con una estética nórdica oscura inspirada en los paneles clásicos de Ragnarok Online (FluxCP / CeresCP), impulsado por un backend en Python 3 sin librerías externas y una aplicación web interactiva en vanilla JavaScript.

---

## ✨ Características Principales

- **Marca Blanca Total:** Personaliza fácilmente el nombre del servidor, logotipo, subtítulo y pie de página desde `config.json` o variables de entorno `.env` sin modificar el código fuente.
- **Cero Dependencias Externas:** Funciona con la biblioteca estándar de Python 3 (`http.server`, `sqlite3`, `hashlib`, `secrets`), sin necesidad de ejecutar `pip install` ni configurar Node.js.
- **Servidor Web Embebido:** Sirve tanto los archivos estáticos de la interfaz (`public/`) como los endpoints RESTful en un solo proceso.
- **Estética Ragnarok:** Paleta oscura con acentos dorados, distintivos de clases (`Novice`, `Swordman`, `Knight`, `Wizard`, etc.) con sus colores representativos y modales reactivos.
- **Gestión Integral de Cuentas:**
  - **Buscador en Tiempo Real:** Filtro instantáneo por nombre de usuario de la cuenta o nombres de sus personajes.
  - **Filtros y Ordenamiento:** Filtra por cuentas activas, suspendidas/baneadas y ordena por fecha o cantidad de personajes.
  - **Ficha del Jugador:** Información completa con niveles Base/Job, Monedero (Zeny y Diamantes), atributos (`STR, AGI, VIT, INT, DEX, LUK`), coordenadas del mapa y último inicio de sesión.
  - **Gestión de Contraseñas:** Cálculo de hash exacto `PBKDF2-SHA256` (100.000 iteraciones + sal aleatoria de 16 bytes) compatible al 100% con `RO3Emu`. Al actualizar la clave, revoca tokens activos.
  - **Creación de Cuentas:** Registro manual de nuevas cuentas directamente desde la interfaz web.
  - **Suspensión / Baneo:** Bloqueo preventivo de cuentas con registro de motivo y desconexión inmediata de sesiones.
  - **Eliminación Segura:** Confirmación con doble validación de seguridad (con protección contra el borrado de administradores).
  - **Notas del GM:** Anotaciones privadas para Game Masters en cada cuenta.
- **Métricas y Estado en Vivo:** Consulta en tiempo real al endpoint de `RO3Emu` para conocer jugadores en línea, tamaño de la base de datos y copias de seguridad disponibles.
- **Registro de Auditoría:** Historial inmutable que documenta todas las acciones administrativas realizadas.

---

## 🚀 Guía Rápida de Inicio

### 1. Requisitos
- Python 3.10 o superior instalado.
- Acceso a la base de datos SQLite de RO3Emu (`ro3emu.db`).

### 2. Configuración
Copia la plantilla de configuración:

```bash
cp config.example.json config.json
```

Edita `config.json` con los datos de tu servidor y tus credenciales de administrador:

```json
{
  "server_title": "Mi Servidor RO3 - Control Panel",
  "server_subtitle": "Gestión de Cuentas y Servidor",
  "logo_text": "RO3",
  "host": "0.0.0.0",
  "port": 8095,
  "ro3_db_path": "ruta/a/tu/ro3emu.db",
  "ro3_status_url": "http://127.0.0.1:5380/ro3emu/status",
  "admin_users": [
    {
      "username": "admin",
      "password": "TuContraseñaSegura123!"
    }
  ]
}
```

### 3. Puesta en Marcha

**En Windows:**
Doble clic en `run.cmd` o desde terminal:
```cmd
python server.py
```

**En Linux / macOS:**
```bash
chmod +x run.sh
./run.sh
```

**Con Docker:**
```bash
docker compose up -d
```

Abre tu navegador en `http://localhost:8095`.

---

## 🌐 Configuración con Nginx (Proxy Inverso)

Para integrarlo bajo tu dominio (ejemplo: `https://tuservidor.com/admin/`):

```nginx
# Panel de Control Web
location /admin/ {
    proxy_pass http://127.0.0.1:8095/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
}

# API del Panel de Control
location /api/admin/ {
    proxy_pass http://127.0.0.1:8095/api/admin/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_read_timeout 60s;
}
```

---

## 🔒 Arquitectura de Seguridad

1. **Autenticación Estricta:** Solo los usuarios especificados en `admin_users` o cuentas válidas con permisos de GM pueden acceder.
2. **Tokens de Sesión:** Cookies `HttpOnly`, con protección `SameSite=Lax` y tokens criptográficos aleatorios.
3. **Concurrencia SQLite:** Total compatibilidad con el modo WAL (`Write-Ahead Logging`) de SQLite sin bloquear lecturas ni escrituras del emulador.
4. **Trazabilidad:** La tabla `admin_audit_log` guarda cada cambio de clave, baneo, creación o eliminación junto con el usuario admin y la fecha UTC.

---

## 📜 Licencia

Distribuido bajo la [Licencia MIT](LICENSE).
