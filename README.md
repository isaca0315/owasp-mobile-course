# OWASP Mobile Top 10 — Curso de Pentesting Móvil

Laboratorio headless de pentesting móvil sobre **Ubuntu 22.04**, pensado para
impartir el curso del **OWASP Mobile Top 10** con demostraciones en vivo.

Todo el entorno se instala con **un único script**, pensado para servidores sin
escritorio (SSH, sin X, sin monitor).

---

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/instalacion.md`](docs/instalacion.md) | Instalación de principio a fin, requisitos y comprobaciones |
| [`docs/arquitectura.md`](docs/arquitectura.md) | Qué se instala, por qué, y qué alternativas se descartaron |
| [`docs/comandos.md`](docs/comandos.md) | Catálogo de todos los comandos del laboratorio |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Problemas frecuentes: síntoma, causa y solución |
| [`docs/verificacion.md`](docs/verificacion.md) | Qué se ha probado de verdad y qué no |
| [`setup-mobile-pentest-lab.sh`](setup-mobile-pentest-lab.sh) | El instalador |

### Clases

| Clase | Documento | Estado |
|---|---|---|
| **1** — OWASP Mobile Top 10: M1, M2, M6 | [`docs/clases/clase-1-owasp-mobile-top10.md`](docs/clases/clase-1-owasp-mobile-top10.md) | Guion listo, verificado de extremo a extremo |
| | [`docs/clases/clase-1-evidencia.md`](docs/clases/clase-1-evidencia.md) | Transcripción real de la prueba |
| 2 — M3, M5 | *pendiente* | Requiere Burp y `frida-server` |

---

## Requisitos

**Servidor (Ubuntu 22.04)**

- 4 vCPU, 8 GB RAM, 40 GB de disco libre
- `sudo`
- Acceso a Internet
- Docker (lo instala el script si falta)

**VM Android objetivo**

- Android 8.1 (API 27) o superior, ABI `x86_64`
- **ADB accesible por TCP** (por defecto `172.25.208.100:5555`)
- Con acceso root por ADB (imagen AOSP sin Play Protect; ver abajo)

El script **no** instala la VM Android: es un proyecto aparte. Si la VM no
acepta `adb root`, hay que usar una imagen AOSP o desactivar la verificación.

---

## Variables de entorno

Todas tienen valores por defecto razonables y se pueden sobreescribir:

```bash
ANDROID_VM_IP=172.25.208.100    # IP de la VM Android
ANDROID_VM_PORT=5555            # Puerto ADB
ANDROID_PLATFORM=android-28     # Plataforma del SDK a instalar
MOBSF_DOCKER_TAG=latest         # Tag de la imagen de MobSF
MOBSF_BIND_ADDR=0.0.0.0         # Interfaz de escucha de MobSF (1337 y 8000)
```

```bash
sudo ANDROID_VM_IP=10.0.0.50 ./setup-mobile-pentest-lab.sh
```

---

## Opciones del instalador

| Opción | Efecto |
|---|---|
| `--no-upgrade` | No ejecuta `apt upgrade` |
| `--no-docker` | No instala Docker; MobSF de forma nativa (`--mobsf-native`) |
| `--mobsf-native` | Fuerza MobSF nativo aunque haya Docker |
| `--firewall` | Configura UFW con las reglas del laboratorio |
| `--extras` | Instala herramientas adicionales de análisis |
| `--burp-jar` | Instala Burp desde el JAR en vez del instalador `install4j` |
| `--skip-mobsf` / `--skip-jadx` / `--skip-burp` / `--skip-frida` | Omitir componentes |
| `--skip-class1` | Omitir la app y el backend de la Clase 1 |
| `-h`, `--help` | Ayuda |

Ejemplo mínimo para una máquina de prácticas:

```bash
sudo ./setup-mobile-pentest-lab.sh --skip-burp --skip-frida --no-upgrade
```

---

## Qué instala

| Componente | Cómo | Notas |
|---|---|---|
| Android SDK | Nativo | Command line tools 13114758, `platform-tools`, `build-tools;33.0.2` |
| MobSF | **Docker** | Imagen oficial, puerto 8000, todo en `0.0.0.0` (`MOBSF_BIND_ADDR`) |
| JADX | Nativo | CLI `jadx` y `jadx-gui` (1.5.6) |
| Burp Suite Community | Nativo | Instalador `install4j` desatendido, puerto 8080 |
| Frida | Nativo | `frida-tools` en el servidor; `frida-server` se instala en la VM |
| InsecureBankv2 + backend | Nativo | App objetivo y backend de la Clase 1 |
| Utilidades | Nativo | `sqlite3`, `nmap`, `curl`, `jq`, `tree`, `file`, `less`, … |

### Por qué MobSF va en Docker y el resto no

MobSF tiene imagen oficial mantenida, así que es el único componente que se
externaliza. El SDK de Android, JADX, Burp y Frida **no** tienen imágenes
oficiales fiables, y ADB tiene que permanecer en el host para hablar con la VM
por TCP: dentro de un contenedor no functionaría sin `network_mode: host` y
montar el socket, lo que añade complejidad sin ganancia.

Con `--no-docker` el script instala MobSF de forma nativa en un venv
(`v4.3.2`, la última compatible con Python 3.10 de Ubuntu 22.04).

---

## Comandos habituales

```bash
# MobSF
mobsf-start            mobsf-stop            mobsf-logs
sudo systemctl status mobsf-server

# VM Android
vmconnect              # conectar + root + resumen
vmconnect frida        # URL y comandos de frida-server para ESTA VM

# Clase 1
bank-start             bank-stop             bank-status
clase1-prep            clase1-demo

# Servicio
sudo journalctl -u mobsf-server -f
docker ps | docker logs -f mobsf
```

Catálogo completo en [`docs/comandos.md`](docs/comandos.md).

---

## Seguridad

### El proxy de MobSF

MobSF incluye un proxy integrado. El script lo ata **sólo a `127.0.0.1`**, a
propósito: publicarlo convertiría el servidor en un proxy abierto que cualquier
alumno podría usar para Pivotar a otras máquinas de la red.

### Credenciales por defecto

| Servicio | Usuario | Contraseña |
|---|---|---|
| MobSF | `mobsf` | `mobsf` |

Cámbialas antes de usar el laboratorio con datos reales.

### Puertos expuestos

| Puerto | Servicio | Acceso |
|---|---|---|
| 8000 | MobSF | Red del laboratorio |
| 8080 | Proxy de Burp | `0.0.0.0` (para que la VM lo alcance) |
| 8888 | Backend InsecureBankv2 | Red del laboratorio |
| 1337 | Proxy interno de MobSF | `MOBSF_BIND_ADDR` (por defecto `0.0.0.0`) |

### Claves SSH

**Este repositorio nunca debe contener claves privadas.** El `.gitignore`
excluye `id_*`, `*.pem`, `*.key`, `.ssh/`, `.env` y friends. Si alguna vez se
cuela una llave, hay que **rotarla**, no sólo borrarla del historial: git
conserva los objetos en todos los commits aunque los elimines después.

---

## Estructura del laboratorio instalado

```
~/mobile-pentesting-lab/
├── apps/apk/                  APKs de práctica
├── reports/
│   ├── jadx/                  descompilaciones
│   ├── mobsf/                 informes de MobSF
│   └── burp/                  exportaciones de Burp
├── tools/InsecureBankv2Server/ backend de la Clase 1 (venv propio)
├── notes/                     notas de clase
├── mobsf/                     datos persistentes del contenedor
└── CLASE1-OWASP-Mobile-Top10.md
```

Ficheros de configuración en el sistema:

| Ruta | Contenido |
|---|---|
| `/etc/mobile-lab/lab.env` | Variables compartidas con los ayudantes |
| `/etc/systemd/system/mobsf-server.service` | Servicio de MobSF |
| `/etc/systemd/system/insecurebankv2-server.service` | Backend de la Clase 1 |
| `/usr/local/bin/{mobsf,bank,clase1,vmconnect}*` | Ayudantes |
| `/etc/profile.d/android-sdk.sh` | Variables del SDK para las shells de login |

---

## Desinstalación

```bash
sudo systemctl disable --now mobsf-server insecurebankv2-server
sudo rm -f /usr/local/bin/{mobsf-*,bank-*,clase1-*,vmconnect}
sudo rm -f /etc/systemd/system/{mobsf,insecurebankv2}-*.service
sudo systemctl daemon-reload
sudo rm -rf /etc/mobile-lab ~/mobile-pentesting-lab
```

Para quitar la app del móvil:

```bash
adb -s 172.25.208.100:5555 uninstall com.android.insecurebankv2
```

---

## Estado de verificación

Resumen honesto, en detalle en [`docs/verificacion.md`](docs/verificacion.md):

- **Clase 1 verificada de extremo a extremo** contra una VM real (API 27,
  `x86_64`, root por ADB) y con `systemd` real: instalación de los componentes,
  `bank-start`, `clase1-prep`, login real de InsecureBankv2, log de M6 en
  `logcat`, extracción y lectura de la base de datos, `SharedPreferences`,
  descompilación con JADX y descifrado M1→M2. Transcripción completa en
  [`docs/clases/clase-1-evidencia.md`](docs/clases/clase-1-evidencia.md).
- **Corregido durante esa prueba:** el backend entraba en un bucle de 149
  reinicios si el puerto 8888 estaba ocupado. Ahora lleva tope de reinicios,
  aviso previo y diagnóstico. Verificado reproducciendo el fallo.
- **Verificado estáticamente**: sintaxis, `shellcheck` en nivel `style`, todas
  las URLs y versiones, y los ficheros que el script genera.
- **No verificado de forma integrada**: la instalación completa del script
  sobre un Ubuntu 22.04 limpio, el arranque real de MobSF en Docker y el
  instalador de Burp. Antes de impartir la primera clase, conviene ejecutar el
  script una vez de principio a fin sobre el servidor definitivo.
