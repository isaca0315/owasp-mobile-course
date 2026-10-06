# OWASP Mobile Top 10 — Curso de Análisis de Seguridad Móvil

Laboratorio headless sobre **Ubuntu 24.04**, pensado para impartir el curso del
**OWASP Mobile Top 10** con demostraciones en vivo.

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
| **1** — OWASP Mobile Top 10: M1, M2, M6 | [`docs/clases/clase-1-owasp-mobile-top10.md`](docs/clases/clase-1-owasp-mobile-top10.md) | Guion verificado de extremo a extremo |
| | [`docs/clases/clase-1-evidencia.md`](docs/clases/clase-1-evidencia.md) | Transcripción real de la prueba |
| **2** — OWASP Mobile Top 10: M3, M4, M5, M7 | [`docs/clases/clase-2-owasp-mobile-top10.md`](docs/clases/clase-2-owasp-mobile-top10.md) | Guion verificado de extremo a extremo |
| | [`docs/clases/clase-2-evidencia.md`](docs/clases/clase-2-evidencia.md) | Transcripción real de la prueba |
| | [`docs/clases/mitm-m5.py`](docs/clases/mitm-m5.py) · [`hook-m3-bypass.js`](docs/clases/hook-m3-bypass.js) | Herramientas de M5 y M3 |
| **3** — OWASP Mobile Top 10: M8, M9, M10 | [`docs/clases/clase-3-owasp-mobile-top10.md`](docs/clases/clase-3-owasp-mobile-top10.md) | Guion verificado de extremo a extremo |
| | [`docs/clases/clase-3-evidencia.md`](docs/clases/clase-3-evidencia.md) | Transcripción real: 20 hallazgos y 3 fallos documentados |
| | [`docs/clases/hook-m9-clave.js`](docs/clases/hook-m9-clave.js) · [`prepend-janus.py`](docs/clases/prepend-janus.py) · [`CryptoClass-janus.java`](docs/clases/CryptoClass-janus.java) | Herramientas de M9 y M8 |
| | [`docs/clases/cve-2026-mobile.md`](docs/clases/cve-2026-mobile.md) | Cada hallazgo mapeado a CVE reales de 2026 |
| **4** — Resiliencia: defensa del cliente | [`docs/clases/clase-4-resiliencia.pptx`](docs/clases/clase-4-resiliencia.pptx) | Presentación (18 diapositivas): repaso M1–M10 + MASVS-RESILIENCE |
| | [`docs/clases/clase-4-resiliencia.md`](docs/clases/clase-4-resiliencia.md) | Guion de la sesión · genera la PPTX con [`make-clase4-ppt.py`](docs/clases/make-clase4-ppt.py) |

---

## Requisitos

**Servidor (Ubuntu 24.04)**

- 4 vCPU, 8 GB RAM, 40 GB de disco libre
- `sudo`
- Acceso a Internet
- Docker (lo instala el script si falta)

**VM Android objetivo**

| Requisito | Mínimo | Recomendado |
|---|---|---|
| Android | 8.1 (API 27) | 10.0 (API 29) o superior |
| ABI | `x86_64` | `x86_64` |
| ADB por TCP | Puerto 5555 abierto | Puerto 5555 abierto |
| Root por ADB | `adb root` funciona | `adb root` funciona |
| RAM | 2 GB | 4 GB |
| Disco | 10 GB | 20 GB |
| CPU | 2 vCPU | 4 vCPU |
| Red | Misma L2 que el servidor | Misma L2 que el servidor |
| Verificación USB | Desactivada | Desactivada |
| Play Protect | Desactivado | Desactivado |

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
(`v4.3.2`, la última compatible con Python 3.10; en Ubuntu 24.04 con Python 3.12 puedes usar `v4.5.3` o superior).

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

# Clase 2
python3 docs/clases/mitm-m5.py --port 8080 --target 127.0.0.1:8888 --tamper

# Clase 3 — M9: clave AES en memoria. Adjuntar por PID, NO con -f
sudo apt-get install -y apktool            # necesario para M8 (Fase 0 de la clase)
export PATH="$PATH:/opt/android-sdk/build-tools/33.0.2"   # apksigner y d8
vmconnect frida                            # levanta frida-server en la VM
frida -U -p $(adb shell pidof com.android.insecurebankv2) \
      -l docs/clases/hook-m9-clave.js

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
~/mobile-owasp-lab/
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
sudo rm -rf /etc/mobile-lab ~/mobile-owasp-lab
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
- **Clase 2 verificada de extremo a extremo** contra la misma VM: bypass de
  autenticación por `/devlogin` con la app oficial, cambio de contraseña sin
  contraseña actual, captura de tráfico HTTP en claro con `mitm-m5.py`,
  alteración de respuesta (login fallido → sesión iniciada), bypass con Frida
  sobre `convertStreamToString`, firma v1 / Janus, permisos y configuración del
  manifiesto. Transcripción completa en
  [`docs/clases/clase-2-evidencia.md`](docs/clases/clase-2-evidencia.md).
- **Clase 3 verificada de extremo a extremo** contra la misma VM: clave AES e IV
  embebidos leídos con JADX, **contraseña en claro capturada en vivo con Frida**
  en los dos sentidos (cifrado y descifrado), parche de smali que elimina la
  validación de login, APK re-firmada por `CN=Attacker` con v2+v3, renombrado de
  la app, `/devlogin`, **bypass de autenticación lanzando una actividad
  exportada**, receptor exportado que **exfiltra la contraseña por SMS**, y un
  `ContentProvider` sin permisos que permite **leer e inyectar** filas desde
  fuera. Transcripción completa en
  [`docs/clases/clase-3-evidencia.md`](docs/clases/clase-3-evidencia.md).
- **La Clase 3 documenta también lo que no funcionó**, porque es lo más útil:
  con el backend caído la app parcheada *no* entra (el chequeo está dentro del
  `try` de red), y el intento **Janus** pasa la verificación de firma v1 pero
  Android 8.1 rechaza la instalación. Este último resultado coincide exactamente
  con el rango de versiones que NVD documenta para CVE-2017-13156.
- **11 de los 20 hallazgos de la Clase 3 se demostraron sin instrumentación**,
  solo con `adb shell` y `curl`.
- **Conexión con el panorama actual:** cada hallazgo se mapea a vulnerabilidades
  reales publicadas en 2026 — CVE-2026-33362, CVE-2026-28626, CVE-2026-0047 y
  los boletines de AOSP — en [`docs/clases/cve-2026-mobile.md`](docs/clases/cve-2026-mobile.md).
- **Corregido durante esas pruebas:** el backend entraba en un bucle de 149
  reinicios si el puerto 8888 estaba ocupado. Ahora lleva tope de reinicios,
  aviso previo y diagnóstico. Verificado reproducciendo el fallo.
- **Segunda pasada de la Clase 3, ejecutada como alumno:** los **49 bloques**
  `bash` del guion se concatenaron y se corrieron encadenados en una sola
  terminal, desde el laboratorio reinstalado. Salieron **18 fallos**, todos de
  estado o de rutas —desde un `cd` que rompía tres secciones hasta un `grep` que
  no capturaba los dígitos de `aes256encrypt`, pasando por un `sed` que nunca se
  recompilaba—. Corregidos, la pasada final da `0`. El detalle está en
  [`docs/verificacion.md`](docs/verificacion.md) §10-bis.
- **Los 15 CVE del documento extra, contrastados uno a uno contra NVD** el
  2026-10-04: todos existen. Dos correcciones salieron de ahí (CWE-321 en lugar
  de CWE-798 para CVE-2026-33362, y la distinción entre la severidad «Crítica»
  de Google y el CVSS real de NVD). Ver §10-ter del mismo documento.
- **Re-verificación de la Clase 3 el 2026-10-06** (víspera de impartirla): otra
  vez 49/49 bloques en verde, Frida real en los dos sentidos y todas las salidas
  contrastadas. Sin regresiones; el único hallazgo fue operativo (la VM arrancó
  sin `frida-server` corriendo). Ver §10-bis de
  [`docs/verificacion.md`](docs/verificacion.md).
- **Clase 4 (resiliencia)**: cierra el curso con un repaso del Top 10 y el grupo
  **MASVS-RESILIENCE** de OWASP MASVS. Es material de repaso y defensa —no un
  ataque nuevo— y así se documenta en su
  [anexo B](docs/clases/clase-4-resiliencia.md#anexo-b--lo-que-no-está-verificado).
- **Verificado estáticamente**: sintaxis, `shellcheck` en nivel `style`, todas
  las URLs y versiones, y los ficheros que el script genera.
- **No verificado de forma integrada**: la instalación completa del script
  sobre un Ubuntu 24.04 limpio, el arranque real de MobSF en Docker y el
  instalador de Burp. Antes de impartir la primera clase, conviene ejecutar el
  script una vez de principio a fin sobre el servidor definitivo.
