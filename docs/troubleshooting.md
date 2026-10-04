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

## Clase 3 (M8, M9, M10)

### `apktool: command not found` en mitad de la clase

**Causa:** el instalador solo pone `apktool` con la opción `--extras`, pero la
Clase 3 lo necesita para M8. Una instalación normal se queda sin él.

**Solución:**

```bash
sudo apt-get install -y apktool    # está en los repos de Ubuntu 24.04
apktool --version                  # 2.7.0-dirty
```

El sufijo `-dirty` es normal en el paquete de Debian/Ubuntu y no indica un
problema. El instalador ahora avisa de esto en la verificación final con
`[AVISO] apktool (Clase 3 / M8)`.

### `apksigner: command not found` / `d8: command not found`

**Causa:** vienen con build-tools pero no están en el `PATH`.

**Solución:**

```bash
source /etc/profile.d/android-sdk.sh
export PATH="$PATH:/opt/android-sdk/build-tools/33.0.2"
```

Este `export` **solo vive en la shell actual**. Si abres otra terminal, la Fase 2
se cae con `command not found` en el peor momento. Ponlo al principio de la clase,
no cuando lo necesites.

### El hook de Frida imprime el banner pero no captura nada

Casi siempre es una de estas dos, y las dos las encontré probando, no leyendo:

**1. Estás usando `-f` (spawn) en vez de `-p` (attach).** Con `-f` hay una carrera:
el script se instala cuando el runtime está listo, pero la app puede haber
ejecutado ya su `onCreate`. En InsecureBankv2, `LoginActivity.onCreate`
descifra la credencial guardada, así que con `-f` te pierdes **precisamente** el
evento que querías capturar.

```bash
# mal: pierde el descifrado inicial
frida -U -f com.android.insecurebankv2 -l docs/clases/hook-m9-clave.js

# bien: arranca la app primero y luego se engancha
adb shell am start -n com.android.insecurebankv2/.LoginActivity
frida -U -p $(adb shell pidof com.android.insecurebankv2 | tr -d '\r') \
      -l docs/clases/hook-m9-clave.js
```

**2. El hook no dispara y no da ningún error.** Es el caso clásico de un método
que no existe con el nombre que has puesto. Ojo: aquí el método real se llama
**`aesDeccryptedString`, con doble `c`**. Es una errata del autor de la app.

```bash
# Para comprobar que el método existe antes de culpar a Frida:
grep -oE 'public [a-zA-Z\[\]]+ [a-zA-Z]+\(' \
  ~/mobile-owasp-lab/reports/jadx/InsecureBankv2/sources/com/android/insecurebankv2/CryptoClass.java
```

Si el banner se imprime, el hook **existe** (si el método no estuviera,
`.overload()` lanzaría excepción). Si no captura nada, el problema es de
*cuándo* te enganchaste, no *dónde*.

### El hook no captura: `frida -n` dice `unable to find process with name`

**Causa:** desincronización de la lista de procesos de Frida. El proceso existe
(`adb shell pidof` y `ps` lo ven), pero Frida todavía no lo tiene.

**Solución:** engancha por PID. Nunca falla.

```bash
frida -U -p $(adb shell pidof com.android.insecurebankv2 | tr -d '\r') -l hook.js
```

### La app modificada no entra y creo que el parche falló

Lo más probable es que **el backend esté apagado**. Está documentado a propósito
en la Fase 2, §2.6, y no es un fallo del parche:

```bash
systemctl is-active insecurebankv2-server   # debe decir: active
```

El chequeo de login está **dentro del `try`** que hace la llamada de red, así que
si el servidor no responde la excepción salta antes de llegar al código parcheado.
Los dos `nop` nunca se ejecutan. Los dos «saltos a error» que se parchean están
en `smali`, pero el `try` que los envuelve está en `DoLogin.postData`.

Con el backend encendido y credenciales inventadas, la app parcheada **sí** entra.
Ese es el escenario de demostración, y el guion incluye el `curl` de control que
muestra lo que el servidor responde realmente.

### `INSTALL_FAILED_UPDATE_INCOMPATIBLE` al instalar la APK modificada

**Causa:** esperado. La APK modificada la firma `CN=Attacker`, que no coincide
con `CN=Dinesh Shetty` de la instalada. Android rechaza actualizar un paquete
firmado con una clave distinta.

```bash
adb uninstall com.android.insecurebankv2
adb install InsecureBankv2_mod2_signed.apk
```

Y recuerda reinstalar la original al terminar (§2.9 de la clase), o la siguiente
sesión empezará sobre un estado inesperado.

### La instalación de la APK Janus falla con `FileNotFoundException`

**No es un fallo tuyo. Está documentado como resultado esperado.** El ataque
consigue que la firma v1 siga siendo válida (`apksigner verify` lo confirma) con
856 bytes ajenos prependidos, pero Android 8.1 lo bloquea al instalar:

```
INSTALL_PARSE_FAILED_UNEXPECTED_EXCEPTION: Failed to parse ...: AndroidManifest.xml
W PackageParser: java.io.FileNotFoundException: AndroidManifest.xml
```

NVD documenta CVE-2017-13156 hasta Android **8.0**; nuestra VM es **8.1.0**.
Es exactamente el límite del rango documentado. La clase lo explica en §2.8: el
esquema v1 es realmente débil, y el trabajo está en decirlo con precisión en vez
de en celebar un exploit que aquí no completa.

### `adb push` de las preferencias y la app vuelve a `FilePref`

**Causa:** el fichero empujado queda propiedad de `root` y la app corre como
`u0_a75`, así que no puede leerlo. La app cae a `FilePref` con el valor por
defecto `10.0.2.2`.

**Solución:** configúralo a mano en la pantalla, que sí funciona:

```
Server IP:   -> 172.25.208.104   (campo en [138,92][632,129])
Server Port: -> 8888             (campo en [138,163][632,200])
Submit:                           (botón  en [4,252][636,314])
```

### `content delete` falla con `no such column: injectado`

**Causa:** sin comillas internas, el shell las elimina y `content delete`
interpreta el valor como nombre de columna en vez de como valor.

```bash
# mal: DELETE FROM names WHERE name=injectado
adb shell content delete --uri "$U" --where "name='injectado'"

# bien
adb shell "content delete --uri \"$U\" --where \"name='injectado'\""
```

### `Could not find provider: com.android.insecurebankv2.provider.trackuser`

**Causa:** el authority **es el nombre completo de la clase**, no una ruta
inventada con la palabra `provider`.

```bash
# mal
content://com.android.insecurebankv2.provider.trackuser/

# bien
content://com.android.insecurebankv2.TrackUserContentProvider/trackerusers
```

Sácalo siempre del manifest, no del nombre del paquete:

```bash
grep -oE 'android:authorities="[^"]*"' AndroidManifest.xml
```

### `aapt: Could not extract resource: /prebuilt/linux/aapt_64`

**No es un error.** El paquete de Ubuntu de `apktool` está compilado para otra
arquitectura y cae a su `aapt` embebido. Es un aviso `W:` y la construcción de
la APK **funciona**. Si ves este aviso y la línea siguiente es
`I: Built apk into: ...`, todo está bien.

### El aviso de `d8` sobre `class file version >= 56`

**No es un error.** `javac 17` genera bytecode que `d8` no reconoce
oficialmente, pero el DEX resultante es válido:

```bash
file classes.dex     # Dalvik dex file version 035
```

### `pkill -f` me ha matado la terminal

**Causa:** `pkill -f <patrón>` compara contra la **línea de comandos completa**,
y tu propia shell contiene el patrón. Se mata a sí misma.

**Solución:** localiza el PID y mata solo ese PID:

```bash
FP=$(ps -eo pid,args | grep -F 'hook-m9-clave.js' | grep -v grep | awk '{print $1}' | head -1)
[ -n "$FP" ] && kill "$FP"
```

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
