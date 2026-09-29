# OWASP Mobile Top 10 — Curso de Pentesting Móvil

Laboratorio headless de pentesting móvil sobre **Ubuntu 22.04**, pensado para
impartir el curso del **OWASP Mobile Top 10** con demostraciones en vivo.

Todo el entorno se instala con **un único script**, pensado para servidores sin
escritorio (SSH, sin X, sin monitor).

---

## Índice

| Documento | Contenido |
|---|---|
| [`setup-mobile-pentest-lab.sh`](setup-mobile-pentest-lab.sh) | Instalador único del laboratorio |
| [`docs/CLASE1-OWASP-Mobile-Top10.md`](docs/CLASE1-OWASP-Mobile-Top10.md) | **Guion de la Clase 1** (M1, M2, M6) con salidas reales verificadas |
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | Qué se instala, por qué, y qué alternativas se descartaron |
| [`docs/COMANDOS.md`](docs/COMANDOS.md) | Catálogo de todos los comandos del laboratorio |
| [`docs/VERIFICACION.md`](docs/VERIFICACION.md) | Qué se ha probado de verdad y qué no |

---

## Inicio rápido

```bash
git clone git@github.com:isaca0315/owasp-mobile-course.git
cd owasp-mobile-course

# 1) Instalar el laboratorio completo
sudo ./setup-mobile-pentest-lab.sh

# 2) Arrancar MobSF (Docker, puerto 8000)
mobsf-start

# 3) Conectar con la VM Android y activar root
vmconnect
```

Para la **Clase 1**:

```bash
bank-start      # backend de InsecureBankv2 (puerto 8888)
clase1-prep     # instala y configura el móvil (~30 s)
clase1-demo     # repite la demo de M2 y M6
```

El guion completo está en [`docs/CLASE1-OWASP-Mobile-Top10.md`](docs/CLASE1-OWASP-Mobile-Top10.md)
y también se copia al laboratorio tras instalarlo, en
`~/mobile-pentesting-lab/CLASE1-OWASP-Mobile-Top10.md`.

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
| MobSF | **Docker** | Imagen oficial, puerto 8000, proxy interno ligado a `127.0.0.1` |
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

Catálogo completo en [`docs/COMANDOS.md`](docs/COMANDOS.md).

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
| 1337 | Proxy interno de MobSF | **Sólo `127.0.0.1`** |

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

Resumen honesto, en detalle en [`docs/VERIFICACION.md`](docs/VERIFICACION.md):

- **Verificado contra una VM real** (API 27, `x86_64`, root por ADB):
  conectividad, `vmconnect`, instalación de la APK, login real de InsecureBankv2,
  extracción de la base de datos, log de M6 en `logcat`, descifrado de M1→M2,
  y los ayudantes `bank-*`, `clase1-prep` y `clase1-demo`.
- **Verificado estáticamente**: sintaxis, `shellcheck` en nivel `style`, todas
  las URLs y versiones, y los ficheros que el script genera.
- **No verificado de forma integrada**: la instalación completa del script
  sobre un Ubuntu 22.04 limpio, el arranque real de MobSF en Docker y el
  instalador de Burp. Antes de impartir la primera clase, conviene ejecutar el
  script una vez de principio a fin sobre el servidor definitivo.
