# Arquitectura del laboratorio

Por qué está montado así y qué alternativas se descartaron.

---

## 1. Principio rector

Un laboratorio de pentesting móvil tiene una restricción que no tiene el de
web: **el objetivo no es un fichero, es un dispositivo conectado por ADB**.

Todo lo que rompa la conectividad entre el host y la VM, o la causa por la
que un alumno no puede conectar, produce una clase que empieza con veinte
minutos de depuración. Por eso el script prioriza la fiabilidad de la
conexión ADB por encima de cualquier otra comodidad.

---

## 2. Android SDK en el host

El SDK se instala **nativo** en `/opt/android-sdk`, no en un contenedor.

El motivo es concreto: `adb` tiene que hablar con la VM por TCP
(`172.25.208.100:5555`). Dentro de un contenedor eso exigiría
`--network host` o reenvío de puertos, además de montar el socket de ADB, y
`adb root` seguiría necesitando reiniciar el demonio en la VM. La
complejidad no aporta nada.

`ANDROID_SDK_DIR`, `ANDROID_HOME` y el `PATH` se exportan desde:

- `/etc/bash.bashrc` (sesiones interactivas)
- `/etc/profile.d/android-sdk.sh` (sesiones de login, servicios)

---

## 3. MobSF en Docker

MobSF es el **único** componente en contenedor, porque es el único con imagen
oficial mantenida.

| Decisión | Valor | Motivo |
|---|---|---|
| Imagen | `opensecurity/mobile-security-framework-mobsf` | Oficial |
| Puerto web | `8000` | Estándar de MobSF |
| Proxy interno | `1337` → `${MOBSF_BIND_ADDR}` | Por defecto `0.0.0.0`, para que el dispositivo alcance el proxy de instrumentación. Antes era sólo `127.0.0.1`; ver la nota de abajo |
| Interfaz de escucha | `MOBSF_BIND_ADDR` (por defecto `0.0.0.0`) | Una sola variable gobierna los dos puertos |
| Datos | Bind mount a `~/mobile-pentesting-lab/mobsf` | Los informes sobreviven a la recreación del contenedor |
| `--add-host` | `host.docker.internal:host-gateway` | El healthcheck de la imagen hace `curl` a ese nombre, que sólo existe en Docker Desktop. Sin esta línea el contenedor se queda en `unhealthy` en Linux aunque sirva correctamente |
| `--shm-size` | `1g` | Los análisis dinámicos se quedan sin `/dev/shm` por defecto y fallan |
| UID | `9901` | Los ficheros de datos del contenedor son de otro usuario |
| Reinicio | `unless-stopped` + `systemd` | Sobrevive a reinicios del servidor |

> [!WARNING]
> **Publicar el puerto 1337 es una decisión de confianza, no un detalle.**
> MobSF lo usa como proxy de instrumentación para el análisis dinámico. Escucharlo
> en `0.0.0.0` lo convierte en un proxy alcanzable desde toda la red del
> laboratorio, que es lo que un alumno necesita para conectar desde el dispositivo
> Android, pero también lo expone a cualquiera que llegue a esa red. El proyecto
> lo tenía atado a `127.0.0.1` de forma deliberada. Si el servidor no está en una
> red de confianza, instálalo con:
>
> ```bash
> MOBSF_BIND_ADDR=127.0.0.1 ./setup-mobile-pentest-lab.sh
> ```

### Fallback nativo

Con `--no-docker` o `--mobsf-native` el script instala MobSF en un venv de
Python. Se fija la **v4.3.2** porque es la última que funciona con Python 3.10
de Ubuntu 22.04; las versiones nuevas requieren 3.11+.

### Autenticación dinámica

El acceso dinámico de MobSF (análisis en vivo) necesita un dispositivo
`adb` accesible **desde el contenedor**. El script lo documenta y ofrece la
comprobación, pero en la configuración por defecto se deja desactivado, porque
el contenedor no ve el socket ADB del host. Para usarlo hay que lanzar el
contenedor con el socket montado o pasar a la instalación nativa.

---

## 4. JADX nativo, sólo CLI por defecto

Se instala el paquete completo (CLI + GUI), pero el flujo del curso usa la
**CLI**:

```bash
jadx app.apk -d salida/
```

Motivo: el servidor es headless. Enseñar con la CLI tiene además una ventaja
pedagógica: se ve el **fichero y la línea exacta** del hallazgo, que es
justamente lo que hay que documentar en un informe.

---

## 5. Burp Suite

Instalador `install4j` desatendido:

```
burpsuite --user-license --install --dir /opt/burpsuite -q
```

El flag `-q` es imprescindible: sin él, `install4j` espera una respuesta por
consola y el script se queda colgado indefinidamente en un servidor sin
terminal.

Burp arranca **sin autoarranque** a propósito: es una app de escritorio, y en
un servidor lo normal es tunelizar el puerto 8080 por SSH y usarla desde el
navegador del alumno:

```bash
ssh -L 8080:127.0.0.1:8080 usuario@servidor
```

Alternativa con X11 sobre SSH si el alumno tiene un servidor gráfico.

El proxy se ata a `0.0.0.0` porque la VM Android necesita alcanzarlo: es
justo el escenario de **M5 (comunicación insegura)**, interceptar el tráfico
de la app.

---

## 6. Frida

El **cliente** (`frida-tools`) va al servidor. El **servidor**
(`frida-server`) se instala dentro de la VM, y eso hay que hacerlo a mano
porque:

- La versión del cliente y la del servidor deben coincidir **exactamente**.
- El binario correcto depende de la ABI de la VM.

Por eso `vmconnect frida` detecta la ABI y la versión del cliente, e imprime
los comandos ya rellenados. El servidor Android-x86 suele exigir root; la VM
lo da por `adb root`.

---

## 7. VM Android

**No la instala este script.** Es un componente independiente, y la imagen
concreta depende de lo que se quiera demostrar.

Requisitos que sí deben cumplirse:

| Requisito | Por qué |
|---|---|
| ADB por TCP, puerto 5555 | Canal de trabajo de todo el curso |
| `adb root` funciona | Sin root no hay M2 real, ni MobSF dinámico, ni frida-server |
| API 27 o superior | Recomendado; el instalador avisa si la app pide una plataforma que no está |
| Sin verificación de apps por USB | Si no, `adb install` falla con `INSTALL_FAILED_VERIFICATION_FAILURE` |

Este último punto no es trivial: las imágenes de Android 8.x con Google
Play Services la traen activada. `clase1-prep` la desactiva automáticamente.

---

## 8. Clase 1 — InsecureBankv2

App objetivo del primer bloque del curso, registrada por OWASP MASTG como
**MASTG-APP-0010**.

### El problema del backend

InsecureBankv2 **no tiene servidor embebido**. La IP y el puerto se leen de
`SharedPreferences`, y el login falla si no hay nada escuchando. Peor: el
`Log.d` de M6 sólo se emite cuando el servidor responde
`"Correct Credentials"`. **Sin backend, la mitad de la clase no se puede
demostrar.**

El backend oficial (`AndroLabServer`) es **Python 2**: usa `print` como
sentencia y mezcla tabuladores con espacios, así que no compila en Python 3.10.
El instalador lo porta automáticamente:

| Cambio | Motivo |
|---|---|
| `expandtabs(8)` | La mezcla tab/espacio es un `TabError` en Python 3 |
| `print x` → `print(x)` | `print` pasó a ser función en Python 3 |
| `simplejson` → `json` | Dependencia innecesaria en 3.10 |
| `convert_unicode` eliminado | SQLAlchemy 2.x lo quitaron |
| `autocommit=False` eliminado | SQLAlchemy 2.x lo eliminó |
| Bloque `__main__` reescrito | El original dependía de `web.py`, que no se usa |
| `import web` eliminado | Módulo no usado |

El resultado es un servicio `systemd` en el puerto 8888, en su propio venv,
que no toca el Python del sistema.

### Por qué una app tan rota para la Clase 1

Porque cubre **tres categorías del OWASP Mobile Top 10 encadenadas**, que es
justo lo que se quiere enseñar en una introducción:

- **M1** → clave AES hardcodeada en el código (`CryptoClass.java:22`)
- **M2** → base de datos SQLite sin cifrar (`mydb`, tabla `names`)
- **M6** → usuario y contraseña en el log del sistema (`DoLogin.java:115`)

Y además **M1 rompe M2**: la contraseña que la app guarda "protegida" como
`superSecurePassword` se descifra con la clave de M1. Eso permite cerrar la
clase con la cadena completa, que es más útil que tres hallazgos sueltos.

---

## 9. Idempotencia y re-ejecución

El script está pensado para **poder repetirse**:

- Cada instalación comprueba si el paquete ya está (`dpkg-query`).
- Las descargas verifican tamaño y se reintentan 3 veces.
- Las variables de entorno se escriben una sola vez (marcador en el fichero).
- Los servicios se reinician en lugar de crearse a ciegas.

Ejecutarlo dos veces no debe romper nada, que es lo que uno descubre a mitad de
una clase si no se puede.
