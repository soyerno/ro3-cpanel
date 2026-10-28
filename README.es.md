<p align="center">
  <img src="docs/assets/hero.svg" alt="RO3 CPanel: Panel de Administración Web para RO3Emu" width="100%">
</p>

<p align="center">
  <a href="#inicio-rápido-en-tres-pasos"><img src="docs/assets/button-quickstart.svg" alt="Inicio Rápido" height="44"></a>
  &nbsp;
  <a href="#por-qué-ro3-cpanel"><img src="docs/assets/button-features.svg" alt="Características" height="44"></a>
  &nbsp;
  <a href="https://github.com/aethai/ro3emu-server"><img src="docs/assets/button-ro3emu.svg" alt="Servidor RO3Emu" height="44"></a>
</p>

<p align="center">
  <a href="https://github.com/soyerno/ro3-cpanel/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/soyerno/ro3-cpanel/ci.yml?branch=main&label=pruebas&color=d8b46a&labelColor=1b2740" alt="Pruebas"></a>
  <img src="https://img.shields.io/badge/python-3.10+-3fb950?labelColor=1b2740" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/dependencias-0-3fb950?labelColor=1b2740" alt="Sin dependencias externas">
  <a href="https://github.com/aethai/ro3emu-server"><img src="https://img.shields.io/badge/compañero-RO3Emu-d8b46a?labelColor=1b2740" alt="Compañero para RO3Emu"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licencia-MIT-8b949e?labelColor=1b2740" alt="Licencia MIT"></a>
</p>

Panel de administración (CPanel) moderno, ligero y personalizable con **marca blanca** para servidores privados de **Ragnarok Online 3 / Ragnarok Origin PC (`RO3Emu`)** ([aethai/ro3emu-server](https://github.com/aethai/ro3emu-server)).

Inspirado en los paneles clásicos de Ragnarok Online (FluxCP / CeresCP), desarrollado con una cuidada estética nórdica oscura, cero dependencias externas en Python y una interfaz SPA en vanilla JavaScript.

---

## Por qué RO3 CPanel

<table>
  <tr>
    <td width="50%" valign="top"><b>Marca blanca inmediata</b><br>Personaliza todo el panel para tu servidor privado en segundos. El título, subtítulo, logotipo y textos se configuran desde <code>config.json</code> o <code>.env</code> sin modificar el frontend.</td>
    <td width="50%" valign="top"><b>Cero dependencias externas</b><br>Funciona en Python 3.10+ estándar (<code>http.server</code>, <code>sqlite3</code>, <code>hashlib</code>). Sin <code>pip install</code>, sin Node.js, sin paquetes npm que auditar.</td>
  </tr>
  <tr>
    <td width="50%" valign="top"><b>Compatibilidad 1:1 con RO3Emu</b><br>El cálculo de contraseñas replica exactamente el algoritmo PBKDF2-SHA256 (100.000 iteraciones + sal de 16 bytes). Al suspender o cambiar claves, las sesiones del juego se revocan de inmediato.</td>
    <td width="50%" valign="top"><b>Gestión integral de cuentas</b><br>Buscador en tiempo real, fichas detalladas de personajes (Lv Base/Job, estadísticas, Zeny, Diamantes, coordenadas), creación de cuentas, reseteo de claves y auditoría.</td>
  </tr>
</table>

---

## Inicio rápido en tres pasos

| Paso | Acción |
|:---:|---|
| **1** | **Clona el repositorio:**<br><code>git clone https://github.com/soyerno/ro3-cpanel.git</code><br><code>cd ro3-cpanel</code> |
| **2** | **Configura tu servidor:**<br><code>cp config.example.json config.json</code><br>Indica la ruta hacia tu <code>ro3emu.db</code> y define tu usuario y contraseña de administrador. |
| **3** | **Inicia el panel:**<br>Windows: <code>run.cmd</code> &nbsp;·&nbsp; Linux: <code>./run.sh</code> &nbsp;·&nbsp; Docker: <code>docker compose up -d</code><br>Ingresa en tu navegador a <a href="http://localhost:8095">http://localhost:8095</a>. |

---

## Arquitectura e Integración

RO3 CPanel se ejecuta como un servicio autónomo conectado a la base de datos de `RO3Emu`:

```
[Navegador Web]
    │  (HTTP / HTTPS)
    ▼
[Nginx / Proxy Inverso] (Opcional)
    │  (Puerto 8095)
    ▼
[RO3 CPanel (server.py)]
    ├── Servidor SPA Integrado (public/index.html, admin.css, admin.js)
    ├── Endpoints REST API (/api/admin/*)
    ├── SQLite Concurrente (WAL) ──► [ro3emu.db]
    └── Ping de Estado en Vivo  ──► [Servidor RO3Emu (Puerto 5380)]
```

---

## Rankings

La pestaña **🏆 Rankings** muestra clasificaciones de solo lectura y paginadas. Los personajes eliminados (`deleted_time != 0`) siempre quedan excluidos.

```
GET /api/admin/rankings?type=level|zeny|power|guilds&limit=20&page=1
```

| `type` | Orden | `value` |
|---|---|---|
| `level` (por defecto) | Nivel base, luego nivel de job, luego EXP base | Nivel base |
| `zeny` | Zeny en posesión (ítem de moneda `1` en `role.currency`) | Cantidad de Zeny |
| `power` | Poder de leaderboard guardado por RO3Emu en `role.emblems` (`Power.CurrentNormal + Power.CurrentSeason`) | Poder total |
| `guilds` | Miembros activos, luego suma del nivel base de los miembros | Cantidad de miembros |

- `limit` vale `20` por defecto y se acota a `1..100`; `page` empieza en `1`. Cada fila incluye su `rank` global.
- Las filas de personajes incluyen `id`, `name`, `account`, `career`, `career_name`, `level` y `job_level`; las de clanes incluyen `id`, `name`, `member_count` y `total_level`.
- `power` lista solo personajes cuyo poder ya fue publicado al menos una vez por el servidor de juego; los blobs que no se pueden interpretar se omiten.
- `zeny` y `power` se decodifican en Python con una sola pasada sobre los personajes no eliminados (cargando solo las columnas necesarias), por lo que su costo crece con la cantidad de personajes.
- En bases sin las tablas `guild` / `guild_member`, `type=guilds` devuelve una lista vacía con `"available": false` en lugar de un error.
- Un `type` desconocido devuelve `400`. El endpoint requiere una sesión de administrador autenticada, igual que el resto de las lecturas `/api/admin/*`.

---

## Guías de Documentación

- [Guía de Alojamiento y Despliegue](docs/guide/hosting.md) (Tareas programadas de Windows, Linux systemd, Docker, Nginx, Cloudflare)
- [Guía de Personalización de Marca Blanca](docs/guide/white-label.md) (Temas, textos, logotipo y rutas)
- [Arquitectura de Seguridad](docs/guide/security.md) (Hashes PBKDF2, cookies HttpOnly, registro de auditoría)
- [Guía de Pruebas Automatizadas](docs/guide/testing.md) (Ejecución del test suite con unittest)

---

## Contribuir

¡Las contribuciones son bienvenidas! Consulta [AGENTS.md](AGENTS.md) y [CONTRIBUTING.md](CONTRIBUTING.md) para conocer las pautas de estilo, la regla de cero dependencias y el flujo de Pull Requests.

---

## Licencia

Distribuido bajo la [Licencia MIT](LICENSE).
