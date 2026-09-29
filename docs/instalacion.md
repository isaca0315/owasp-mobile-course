# Instalación

Guía de principio a fin. Asume una máquina **Ubuntu 24.04** limpia.

---

## 1. Requisitos previos

| Elemento | Requisito |
|---|---|
| SO | Ubuntu 24.04 (o derivados) |
| CPU / RAM / Disco | 4 vCPU, 8 GB RAM, 40 GB libres |
| Privilegios | `sudo` |
| Red | Salida a Internet y a la VM Android |
| VM Android | Ver más abajo |

### La VM Android

**El instalador no la crea.** Es un componente aparte.

#### Requisitos mínimos

| Requisito | Valor |
|---|---|
| Android | 8.1 (API 27) |
| ABI | `x86_64` |
| ADB por TCP | Puerto 5555 abierto |
| Root por ADB | `adb root` funciona |
| RAM | 2 GB |
| Disco | 10 GB |
| CPU | 2 vCPU |
| Red | Misma L2 que el servidor |
| Verificación USB | Desactivada |
| Play Protect | Desactivado |

#### Requisitos recomendados

| Requisito | Valor |
|---|---|
| Android | 10.0 (API 29) o superior |
| ABI | `x86_64` |
| ADB por TCP | Puerto 5555 abierto |
| Root por ADB | `adb root` funciona |
| RAM | 4 GB |
| Disco | 20 GB |
| CPU | 4 vCPU |
| Red | Misma L2 que el servidor |
| Verificación USB | Desactivada |
| Play Protect | Desactivado |

#### Comprobación rápida antes de instalar nada

```bash
ping -c2 172.25.208.100
adb connect 172.25.208.100:5555
adb root && sleep 3 && adb connect 172.25.208.100:5555
adb devices -l
```

Si `adb root` no responde `uid=0(root)`, **para aquí**: el resto del curso
depende de ello.

---

## 2. Instalar el laboratorio

```bash
git clone git@github.com:isaca0315/owasp-mobile-course.git
cd owasp-mobile-course
sudo ./setup-mobile-pentest-lab.sh
```

Tardará entre 10 y 30 minutos según la velocidad de la red. Las descargas
principales son el SDK de Android, Burp Suite y la imagen de MobSF.

### Instalación mínima

Si sólo quieres las clases estáticas (MobSF, JADX, sin Burp ni Frida):

```bash
sudo ./setup-mobile-pentest-lab.sh --skip-burp --skip-frida --no-upgrade
```

### Opciones

| Opción | Efecto |
|---|---|
| `--no-upgrade` | No ejecuta `apt upgrade` |
| `--no-docker` | No instala Docker; MobSF de forma nativa |
| `--mobsf-native` | Fuerza MobSF nativo aunque haya Docker |
| `--firewall` | Configura UFW con las reglas del laboratorio |
| `--extras` | Herramientas adicionales de análisis |
| `--burp-jar` | Instala Burp desde el JAR, no con `install4j` |
| `--skip-mobsf` / `--skip-jadx` / `--skip-burp` / `--skip-frida` | Omitir componentes |
| `--skip-class1` | Omitir la app y el backend de la Clase 1 |
| `-h`, `--help` | Ayuda |

### Variables de entorno

```bash
sudo ANDROID_VM_IP=10.0.0.50 ANDROID_VM_PORT=5555 ./setup-mobile-pentest-lab.sh
```

| Variable | Por defecto | Significado |
|---|---|---|
| `ANDROID_VM_IP` | `172.25.208.100` | IP de la VM |
| `ANDROID_VM_PORT` | `5555` | Puerto ADB |
| `ANDROID_PLATFORM` | `android-28` | Plataforma del SDK |
| `MOBSF_DOCKER_TAG` | `latest` | Tag de la imagen de MobSF |
| `MOBSF_BIND_ADDR` | `0.0.0.0` | Interfaz de escucha de MobSF (puertos 8000 y 1337). Ponle `127.0.0.1` para no exponerlo a la red |

---

## 3. Comprobación posterior

```bash
# ¿Los servicios están arriba?
systemctl is-active mobsf-server
systemctl is-active insecurebankv2-server

# ¿El laboratorio responde?
mobsf-start
curl -s -X POST -d 'username=dinesh&password=Dinesh@123$' http://127.0.0.1:8888/login
# {"message": "Correct Credentials", "user": "dinesh"}

# ¿La VM responde?
vmconnect
```

Si algo falla, mira [`troubleshooting.md`](troubleshooting.md).

---

## 4. Preparar la Clase 1

```bash
bank-start      # backend de InsecureBankv2 en el puerto 8888
clase1-prep     # instala y configura el móvil (~30 s)
clase1-demo     # repite la demo de M2 y M6
```

El guion de la clase, paso a paso:

- [`clases/clase-1-owasp-mobile-top10.md`](clases/clase-1-owasp-mobile-top10.md)
- [`clases/clase-1-evidencia.md`](clases/clase-1-evidencia.md)

---

## 5. Primer arranque del laboratorio (usuario sin sudo)

El instalador escribe las variables del SDK en `/etc/profile.d/android-sdk.sh`
y en `/etc/bash.bashrc`. Para una **terminal nueva** basta con abrirla. Para la
terminal actual:

```bash
source /etc/profile.d/android-sdk.sh
```

Comprobación:

```bash
adb version
java -version
jadx --version
```

Burp Suite necesita un servidor gráfico, así que se accede por túnel SSH
(ver [`comandos.md`](comandos.md)).

---

## 6. Reinicio del servidor

Si el script avisó de que hace falta reiniciar (actualizaciones del núcleo):

```bash
sudo reboot
```

Los servicios están habilitados con `systemd`, así que MobSF y el backend
arrancan solos.

---

## Instalación sin Docker

Si la política del servidor no permite Docker:

```bash
sudo ./setup-mobile-pentest-lab.sh --no-docker
```

MobSF se instala en un venv de Python, versión **4.3.2** (la última compatible
con Python 3.12 de Ubuntu 24.04). El acceso dinámico a dispositivos **no**
funciona en modo nativo; se documenta en
[`arquitectura.md`](arquitectura.md).
