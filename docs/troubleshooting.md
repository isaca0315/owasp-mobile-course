# Problemas frecuentes

Síntoma → causa → solución. Todos los casos de aquí se han reproducing en
pruebas reales.

---

## VM Android

### `adb devices` muestra `offline` o nada

**Causa:** `adb root` reinicia el demonio ADB de la VM y **tumba la conexión
TCP**. Es el comportamiento esperado, no un fallo.

```bash
vmconnect
```

El ayudante hace conectar → root → reconectar → resumen. Si lo haces a mano:

```bash
adb connect 172.25.208.100:5555
adb root
sleep 3
adb connect 172.25.208.100:5555
```

### `error: device unauthorized`

**Causa:** la VM no ha aceptado la huella de depuración.

1. Acepta el diálogo en la pantalla de la VM, o
2. Acepta desde el navegador en `http://172.25.208.100:5555`, o
3. Si hay otro servidor ADB en juego: `adb kill-server` y vuelve a conectar.

### `adb root` no da `uid=0(root)`

**Causa:** la imagen no es una build `eng`/`userdebug`.

**Solución:** usa una imagen AOSP sin Play Services. Todo el curso depende de
esto: sin root no hay M2 real, ni MobSF dinámico, ni `frida-server`.

### `INSTALL_FAILED_VERIFICATION_FAILURE`

**Causa:** la verificación de apps por USB está activa (habitual en imágenes de
Android 8.x con Google Play Services).

```bash
adb -s 172.25.208.100:5555 shell settings put global verifier_verify_adb_installs 0
adb -s 172.25.208.100:5555 shell settings put global package_verifier_enable 0
```

`clase1-prep` lo hace automáticamente en el paso 2.

### `adb: no such file or directory` tras instalar

**Causa:** las variables del SDK no están en la shell actual.

```bash
source /etc/profile.d/android-sdk.sh
```

---

## Backend de InsecureBankv2 (Clase 1)

### `bank-start` dice que no arranca

`bank-start` ya diagnostica el caso más frecuente. Si el mensaje es:

```
CAUSA: el puerto 8888 ya esta ocupado por otro proceso.
```

Entonces hay otro servicio escuchando:

```bash
sudo ss -ltnp | grep 8888
```

Suele ser una instancia anterior. Soluciones:

```bash
sudo systemctl stop insecurebankv2-server
bank-start
```

o usar otro puerto:

```bash
bank-start 8889
clase1-prep 8889        # configura la app con ese puerto
```

### El servicio se queda en `failed` y no se recupera solo

**Causa:** el tope de reinicios (`StartLimitBurst=5`) se ha alcanzado. Es
intencionado: antes de ese tope el servicio entraba en bucle y se observaron
**149 reinicios en 5 minutos**, inundando el journal.

```bash
sudo systemctl reset-failed insecurebankv2-server
bank-start
```

### La app hace login pero no se registra nada en el log

**Causa:** el log de M6 sólo se emite cuando el backend responde
`"Correct Credentials"`. Si el backend no está, o la IP guardada en la app no
es la correcta, el login falla en silencio.

```bash
curl -s -X POST -d 'username=dinesh&password=Dinesh@123$' http://127.0.0.1:8888/login
adb -s 172.25.208.100:5555 shell "cat /data/data/com.android.insecurebankv2/shared_prefs/*.xml"
```

La IP guardada debe ser la del servidor, no `127.0.0.1`.

### `no such table: names`

**Causa:** la tabla se crea al iniciar sesión. `clase1-demo` la lista vacía si
todavía nadie ha entrado.

```bash
# entrar en la app con dinesh / Dinesh@123$ y reintentar
```

---

## MobSF

### El contenedor no arranca

```bash
mobsf-logs
docker ps -a | grep mobsf
```

Causas frecuentes:

| Síntoma | Causa |
|---|---|
| `permission denied` sobre el directorio de datos | Propietario incorrecto. El contenedor usa UID 9901 |
| El análisis dinámico falla | Falta `--shm-size=1g` |
| Falla al reanálisis | La imagen no tiene permisos sobre los ficheros subidos |

### MobSF tarda mucho en responder la primera vez

El primer arranque descarga dependencias y migra la base de datos. Puede tardar
varios minutos. Espera a ver `Gunicorn server started` en el log:

```bash
mobsf-logs
```

### El análisis dinámico no encuentra el dispositivo

**Causa:** el contenedor no ve el socket ADB del host. Es una limitación
conocida del montaje por defecto. Para el análisis dinámico hay que usar la
instalación **nativa** (`--no-docker`), que sí tiene acceso al ADB del host.

---

## Burp Suite

### El instalador se queda colgado

**Causa:** `install4j` espera confirmación interactiva. El script pasa `-q`
por esto. Si ocurre, es que se instaló con `--burp-jar`.

### No se abre la ventana de Burp

**Causa:** es un servidor sin escritorio. Se accede por túnel SSH:

```bash
ssh -L 8080:127.0.0.1:8080 usuario@servidor
```

y luego `http://127.0.0.1:8080` en el navegador.

### La VM Android no alcanza el proxy de Burp

```bash
adb -s 172.25.208.100:5555 shell ping -c2 <IP-del-servidor>
```

Si no hay ping, el problema es el cortafuegos, no Burp:

```bash
sudo ufw allow 8080/tcp
```

---

## Frida

### `server version mismatch`

**Causa:** el cliente y el servidor tienen versiones distintas. Deben coincidir
**exactamente**.

```bash
vmconnect frida
```

Imprime la URL y los comandos con la versión correcta ya rellenados.

### `frida-ps` dice `unable to connect`

Casi siempre es que falta root en la VM, o que `frida-server` no está corriendo
dentro:

```bash
adb -s 172.25.208.100:5555 shell '/data/local/tmp/frida-server-android-x86_64 &'
```

### `unrecognized arguments: --no-pause`

**Causa:** el flag `--no-pause` **se eliminó en Frida 16**. En las versiones
actuales la app se reanuda sola al cargar el script.

**Solución:** quita el flag:

```bash
frida -U -f com.android.insecurebankv2 -l docs/clases/hook-m3-bypass.js
```

Para dejar el proceso parado, el flag es `--pause`.

---

## Clase 2 (M3, M4, M5, M7)

### El proxy del sistema no captura nada y el log sale vacío

**Síntoma:** el móvil tiene el proxy configurado, haces login, pero
`mitm-m5.py` no muestra ni una línea.

**Causa:** casi siempre bufferización. Python bloquea stdout en bloques de 4–8
KB cuando la salida no es una terminal, así que con `nohup … > log` los
mensajes se quedan en el buffer y no aparecen. El proxy está funcionando; el
log aún no se ha escrito.

**Solución:** `mitm-m5.py` ya fuerza `line_buffering`, así que si te pasa es que
estás ejecutando una copia antigua. Y para verlo sin buffering:

```bash
python3 -u docs/clases/mitm-m5.py --port 8080 --target 127.0.0.1:8888
```

Comprueba que el proxy captura peticiones localmente antes de culpar a la app:

```bash
curl -s -x http://127.0.0.1:8080 -X POST -d 'username=dinesh&password=Dinesh@123$' \
     http://172.25.208.104:8888/login
```

### El móvil se queda sin red después de la fase M5

**Causa:** el proxy sigue configurado en el dispositivo.

```bash
adb -s 172.25.208.100:5555 shell settings put global http_proxy :0
adb -s 172.25.208.100:5555 shell am force-stop com.android.insecurebankv2
```

Conviene dejarlo así **siempre** al terminar la fase, o el móvil parece averiado
en la siguiente.

### La fase de login «no hace nada»

**Causa:** casi siempre que el backend está parado. Sin respuesta del backend no
hay pantalla de error útil.

```bash
bank-status
```

### No encuentro la contraseña en el log del backend

**Causa (trampa real):** el backend **sí** la registra (`app.py:85`,
`print(newpassword)`), pero **no lo verás en `journalctl`** mientras el buffer de
Python no se llene. Python bloquea stdout cuando no hay terminal, así que los
mensajes llegan al journal a trozos.

**No concluyas que el backend no loguea.** Para verlo en vivo:

```bash
cd ~/mobile-owasp-lab/tools/InsecureBankv2Server
PYTHONUNBUFFERED=1 venv/bin/python app.py --port 8888
```

### El login con `devadmin` funciona en el curl pero no en la app

No es un error: es el objetivo de la fase. En la app hay que escribir
exactamente `devadmin` en el campo de usuario, porque la decisión de endpoint se
toma en el cliente comparando esa cadena (`DoLogin.java:103`). Cualquier otro
nombre va a `/login`, que sí valida la contraseña.

Si `devadmin` + cualquier clave no entra, comprueba primero que el backend está
activo y que la app apunta a la IP correcta:

```bash
adb -s 172.25.208.100:5555 shell \
  "cat /data/data/com.android.insecurebankv2/shared_prefs/com.android.insecurebankv2_preferences.xml"
```

### La demo de MITM no deja entrar a la app

**Causa:** si alteraste la respuesta sustituyendo `Wrong` por `Correct`, la app
recibe `Correct Password`, y eso **no** contiene la cadena que busca
(`"Correct Credentials"`, `DoLogin.java:114`). La app se queda en
`WrongLogin` sin avisar.

**Solución:** falsificar la respuesta completa, que es lo que hace `--tamper`:

```bash
python3 docs/clases/mitm-m5.py --port 8080 --target 127.0.0.1:8888 --tamper
```

### Burp no arranca en el servidor

**Causa:** es una aplicación Swing y el servidor es headless. Sin Xvfb no hay
display, y el lanzador `/usr/local/bin/burpsuite` directamente no existe: el
binario real está en `/opt/burpsuite/app`.

**Solución:** usa `docs/clases/mitm-m5.py`, que cubre la fase M5 sin escritorio.
El procedimiento con Burp está en el Anexo C del guion de la Clase 2.

---

## Instalador

### `adb` o `java` no se encuentran tras instalar

```bash
source /etc/profile.d/android-sdk.sh
```

Si persiste, el bloque no se escribió en `/etc/bash.bashrc` (puede que ya
existiera con otro marcador). Comprueba:

```bash
grep -A6 "ANDROID_SDK" /etc/bash.bashrc
```

### Reejecutar el instalador

Se puede repetir sin miedo: comprueba qué falta antes de instalar, y las
variables de entorno se escriben una sola vez.

```bash
sudo ./setup-mobile-pentest-lab.sh
```

### Desinstalar todo

```bash
sudo systemctl disable --now mobsf-server insecurebankv2-server
sudo rm -f /usr/local/bin/{mobsf-*,bank-*,clase1-*,vmconnect}
sudo rm -f /etc/systemd/system/{mobsf,insecurebankv2}-*.service
sudo systemctl daemon-reload
sudo rm -rf /etc/mobile-lab ~/mobile-owasp-lab
adb -s 172.25.208.100:5555 uninstall com.android.insecurebankv2
```

---

## Diagnóstico general

```bash
# Estado de todos los servicios del laboratorio
systemctl list-units | grep -E 'mobsf|insecurebank'

# Logs en vivo
sudo journalctl -u mobsf-server -f
sudo journalctl -u insecurebankv2-server -f

# Configuración guardada
cat /etc/mobile-lab/lab.env

# Puertos del laboratorio
ss -ltnp | grep -E '8000|8080|8888|5555|1337'
```
