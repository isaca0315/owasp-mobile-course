# Bitácora de verificación

Qué se ha comprobado **de verdad** contra un sistema real, y qué no.

Este documento existe para que nadie dé por hecho algo que no se ha probado.
En una clase en vivo, un comando que no funciona cuesta más que un bug en el
código: rompe el ritmo y la credibilidad.

---

## Entorno de pruebas

| Dato | Valor |
|---|---|
| Servidor de pruebas | `172.25.208.104/24` (misma subred que la VM) |
| VM Android | `172.25.208.100:5555` |
| SO de la VM | Android 8.1.0, **API 27** |
| ABI | `x86_64` |
| Dispositivo | `Standard PC (i440FX + PIIX, 1996)` |
| ADB | `1.0.41` |
| Servidor (host) | Ubuntu, `bash` + `shellcheck` |

---

## 1. Conectividad — VERIFICADO

| Prueba | Resultado |
|---|---|
| `ping` host → VM | 0% pérdida, ~1.4 ms, **TTL 64** (L2 directo, sin router) |
| `adb connect 172.25.208.100:5555` | Correcto |
| `adb devices -l` | `device product:android_x86_64` |
| `adb root` | Funciona → `uid=0(root)` |
| VM → host (`172.25.208.104`) | 0% pérdida: el proxy de Burp en `0.0.0.0:8080` será alcanzable |
| VM → internet | Funciona (ping a `8.8.8.8`) |
| Escaneo de puertos de la VM (1-1024 + comunes) | **Sólo el 5555 abierto** |
| `adb push` a `/data/local/tmp` + `chmod` | Funciona (ruta de `frida-server`) |

### Nota sobre ADB

Una sonda escrita a mano en Python concluyó que el 5555 "no era un adbd
funcional" (aceptaba y cerraba sin banner). **Era falso**: el `adb` real conecta
sin problema. `adbd` no siempre envía banner al establecer la conexión; el
cliente real sí negocia correctamente.

Conclusión: **nunca concluir que ADB está roto a partir de una sonda casera.**
Usar el `adb` real.

---

## 2. Instalación de InsecureBankv2 — VERIFICADO

| Prueba | Resultado |
|---|---|
| Descarga de la APK (3.462.429 bytes) | Correcta, SHA-256 verificado |
| `adb install` | **Falla** con `INSTALL_FAILED_VERIFICATION_FAILURE` |
| Tras `settings put global verifier_verify_adb_installs 0` | `Success` |
| Arranque de la app | Correcto, llega a `LoginActivity` |

El fallo de verificación **no es exótico**: las imágenes de Android 8.x traen la
verificación de apps por USB activada, y bloquea cualquier APK por ADB.
`clase1-prep` lo desactiva en el paso 2 por este motivo.

---

## 3. Análisis estático con JADX — VERIFICADO

Descompilación completa con JADX 1.5.6. **Todos los hallazgos del guion se
contrastaron con el código real**, y tres de ellos resultaron ser incorrectos.

| Lo que decía el guion | Lo que hay realmente |
|---|---|
| `adb pull .../databases/insecurebank.db` | La BD se llama **`mydb`**, tabla `names` |
| `public static final String SECRET_KEY` | `String key = "This is the super secret key 123";` (`:22`) |
| El log imprime "un token de sesión" | Imprime **usuario y contraseña** en claro (`:115`) |
| (no mencionado) | **Falta el backend entero**: la app no tiene servidor embebido |

Referencias exactas:

```
CryptoClass.java:22                     String key = "This is the super secret key 123";
CryptoClass.java:23                     byte[] ivBytes = {0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};
TrackUserContentProvider.java:19        DATABASE_NAME = "mydb"
DoLogin.java:115                        Log.d("Successful Login:", ", account=" + user + ":" + pass)
```

### Hallazgo adicional no previsto

`CryptoClass.java:23` usa un **IV de 16 ceros**. En modo CBC, un IV constante
anula la confidencialidad. No aparece en la mayoría de guías de esta app.

---

## 4. Backend de InsecureBankv2 — VERIFICADO

El backend oficial (`AndroLabServer`) **es Python 2** y no arranca en Ubuntu
24.04. Errores reales encontrados:

```
SyntaxError: Missing parentheses in call to 'print'
TabError: inconsistent use of tabs and spaces
TypeError: Invalid argument(s) 'convert_unicode' sent to create_engine()
ModuleNotFoundError: No module named 'web'
```

Portado y verificado:

| Prueba | Resultado |
|---|---|
| Los tres `.py` compilan en Python 3 | Correcto |
| El backend arranca | `InsecureBankv2 backend escuchando en 0.0.0.0:8888` |
| `POST /login` con credenciales correctas | `{"message": "Correct Credentials", "user": "dinesh"}` |
| `POST /devlogin` con `devadmin` | `Correct Credentials` |
| La VM Android alcanza el backend | Sí |

Credenciales sembradas en la base de datos del backend:

```
dinesh / Dinesh@123$      jack / Jack@123$      devadmin / devadmin
```

---

## 5. M2 y M6 en la VM — VERIFICADO EN DIRECTO

Login real completado desde el dispositivo, con el backend en marcha.

**M6 — logcat:**

```
D Successful Login:: , account=dinesh:Dinesh@123$
```

**M2 — base de datos extraída:**

```
$ adb pull /data/data/com.android.insecurebankv2/databases/mydb .
$ sqlite3 -header -column mydb "select * from names;"
id  name
--  ------
1   dinesh
```

**M2 — credenciales guardadas:**

```
"serverip           = 172.25.208.104
"serverport         = 8888
"superSecurePassword = DTrW2VXjSoFdg0e61fHxJg==
"EncryptedUsername  = ZGluZXNo
```

### Cadena M1 → M2

Descifrando `superSecurePassword` con la clave hardcodeada de M1 y el IV de
ceros:

```python
AES.new(b"This is the super secret key 123", AES.MODE_CBC, b"\x00"*16) \
   .decrypt(base64.b64decode("DTrW2VXjSoFdg0e61fHxJg=="))
# -> Dinesh@123$
```

`EncryptedUsername` sólo está en **Base64**, ni siquiera cifrado:
`base64.b64decode("ZGluZXNo")` → `dinesh`.

---

## 6. Ayudantes generados — VERIFICADO

| Comprobación | Resultado |
|---|---|
| `bash -n` sobre cada fichero generado | Correcto |
| `vmconnect` ejecutado contra la VM real | Conecta, root, detecta API 27 / `x86_64` |
| `vmconnect frida` | Genera la URL y los comandos de `frida-server` correctos |
| `bank-start` / `bank-stop` / `bank-status` | Correctos |
| Backend portado por el script, arrancado de cero | Arranca y autentica |
| `clase1-prep` ejecutado desde cero (app desinstalada) | Instala, configura y abre el login |
| `clase1-demo` | Extrae la BD, muestra el logcat y guarda informes |
| Runbook generado por el script | Idéntico al fuente; el bloque de descifrado se ejecutó y devolvió `Dinesh@123$` |

### Errores encontrados y corregidos durante la verificación

| Error | Causa | Corrección |
|---|---|---|
| `vmconnect` se generaba **vacío** | Heredoc sin comillas: el shell expandía `$(...)` al generar el fichero | Heredoc entrecomillado + fichero de configuración `lab.env` |
| `get-state` fallaba con `adb` real | Algunas versiones anteponen líneas de aviso antes del estado | `tr -d '\r' \| tail -n1` |
| `database.py` no se descargaba | Pesa 727 B y `fetch` exigía >1024 | `fetch` acepta un tamaño mínimo |
| `clase1-prep` buscaba la APK en `/root` | Con `sudo`, `$HOME` cambia | Lee `LAB_DIR` de `/etc/mobile-lab/lab.env` |
| `info` no existía | La función del script es `log` | Corregido |
| `Status: unbound variable` en pruebas | Artefacto del arnés de prueba, no del script | — |

---

## 7. Segunda ejecución completa de la clase — VERIFICADO

El 29 de septiembre de 2026 se repitió la clase entera de principio a fin con
`systemd` real en el servidor. Transcripción completa en
[`clases/clase-1-evidencia.md`](clases/clase-1-evidencia.md).

| Fase | Estado | Notas |
|---|---|---|
| Instalación de componentes | OK | `class1_app`, `class1_backend`, `class1_helpers`, `class1_runbook` |
| Arranque del backend vía systemd | OK | `active`, escuchando en `0.0.0.0:8888` |
| `bank-start` | OK | Diagnóstico correcto cuando falla |
| `clase1-prep` | OK | App desinstalada y reinstalada desde cero |
| Login real → **M6** | OK | `D Successful Login:: , account=dinesh:Dinesh@123$` |
| Extracción de la BD → **M2** | OK | `mydb`, tabla `names` con `dinesh` |
| `SharedPreferences` | OK | `superSecurePassword` y `EncryptedUsername` |
| Descompilación con JADX | OK | 2291 clases |
| **M1** clave e IV | OK | `CryptoClass.java:22` y `:23` |
| Descifrado M1 → M2 | OK | Devuelve `Dinesh@123$` |
| Extra: Base64, no cifrado | OK | `ZGluZXNo` → `dinesh` |
| `clase1-demo` | OK | Código de salida 0 |
| **Fase 1 (MobSF)** | OK | Contenedor `healthy`, web en `0.0.0.0:8000` alcanzable desde la VM |

### Fase 1 (MobSF): verificada en una segunda ejecución

El demonio de Docker, que había estado inaccesible durante toda la prueba
anterior, arrancó sin incidencias. Con él se completó la fase que quedaba
pendiente:

| Comprobación | Resultado | Detalle |
|---|---|---|
| `systemctl start docker` | OK | Demonio activo |
| `mobsf-server` | OK | Contenedor `mobsf` en estado `healthy` |
| Web en `8000` desde la IP del host | OK | `HTTP 302` en `http://172.25.208.104:8000/` |
| Web en `8000` desde la VM Android | OK | Conexión TCP desde `172.25.208.100` |
| Prueba de control (puerto 9999) | OK | Rechazada, confirma que la prueba anterior no es un falso positivo |

**Segundo fallo encontrado y corregido.** MobSF se quedaba permanentemente en
`unhealthy` sin estar caído. La causa no era MobSF: el healthcheck de la imagen
oficial hace `curl host.docker.internal`, un nombre que sólo resuelve en Docker
Desktop. En Linux el `curl` fallaba con `Could not resolve host` y el contenedor
se marcaba como unhealthy para siempre. Se resuelve con
`--add-host host.docker.internal:host-gateway`. Tras el cambio el healthcheck
pasa y el contenedor queda `healthy`.

Este fallo era invisible antes: mientras el demonio de Docker no arrancaba, el
contenedor tampoco existía, así que nunca se vio el healthcheck roto. Es un
buen argumento para no dar por buena ninguna comprobación que no se haya
ejecutado de verdad.

### Fallo encontrado y corregido en esta ejecución

El servicio del backend entró en un **bucle de 149 reinicios en 5 minutos**.
Causa: el puerto 8888 estaba ocupado por otro proceso, `bind()` fallaba con
`Errno 98`, y `Restart=on-failure` no tenía tope. El instructor se habría
quedado sin diagnóstico y con el journal inundado.

Corregido con tres medidas, todas verificadas:

1. `StartLimitIntervalSec=60` y `StartLimitBurst=5` en la unidad systemd.
2. Aviso en el instalador si el puerto ya está ocupado, indicando el proceso.
3. Diagnóstico explícito en `bank-start` cuando el arranque falla.

Comprobación reproducing el fallo con el puerto ocupado a propósito: el
servicio hace **5 reinicios y se rinde** con estado `failed` limpio, frente a
los 149 anteriores.

---

## 8. Análisis estático del script — VERIFICADO

| Comprobación | Resultado |
|---|---|
| `bash -n` | Correcto |
| `shellcheck -S style -e SC1091` | **Sin avisos** |
| `--help` | Muestra todas las opciones, incluido `--skip-class1` |
| URLs y versiones | Comprobadas una a una |
| Ficheros generados (`mobsf-*`, `vmconnect`, `bank-*`, `clase1-*`) | Generados y validados sintácticamente |
| Idempotencia | Cada instalación comprueba si ya existe |

---

## 9. Clase 2 (M3, M4, M5, M7) — VERIFICADO

El 1 de octubre de 2026 se verificó la Clase 2 completa contra la misma VM
(`172.25.208.100`, API 27, `x86_64`, root por ADB) y el mismo servidor con
`systemd` real. Transcripción en
[`clases/clase-2-evidencia.md`](clases/clase-2-evidencia.md).

### M3 — Autenticación insegura

| Prueba | Resultado |
|---|---|
| `/devlogin` con contraseña vacía, falsa y arbitraria | SIEMPRE `Correct Credentials` |
| `/devlogin` con usuario inexistente | `Correct Credentials` |
| **Bypass end-to-end en la app**: `devadmin` / `inventada999` | Entra en `PostLogin` |
| Credenciales falsas guardadas y descifradas | `inventada999` con la clave de M1 |
| `/changepassword` sin contraseña actual | Toma control de `dinesh`; restaurado después |
| Rate limiting (`sleep`, `limit`, `lockout`, `captcha`) | 0 ocurrencias en `app.py` |
| **Bypass con Frida** sobre `convertStreamToString` | Backend dijo `Wrong Password`, la app entró |

### M4 — Criptografía insuficiente

| Prueba | Resultado |
|---|---|
| Clave hardcodeada | `CryptoClass.java:22` |
| IV de 16 ceros | `CryptoClass.java:23` |
| Modo `AES/CBC/PKCS5Padding` sin MAC | `CryptoClass.java:28` |
| Descifrado de `superSecurePassword` | `Dinesh@123$` |
| **Esquema de firma (hallazgo nuevo)** | Sólo v1 → **Janus / CVE-2017-13156** |

### M5 — Comunicación insegura

| Prueba | Resultado |
|---|---|
| `protocol` hardcodeado | `http://` en 3 clases |
| Tráfico real de la app capturado por el proxy | `password=Dinesh%40123%24` en claro |
| Petición alterada por el proxy | `dinesh` → `jack`, backend lo acepta sin detectar nada |
| Respuesta alterada | `Wrong Password` → `Correct Credentials`; la app entra |

### M7 — Calidad de código del cliente

| Prueba | Resultado |
|---|---|
| `android:debuggable` | `true` |
| `android:allowBackup` | `true` |
| Permisos | 12 declarados, **8 peligrosos** |
| `sdkVersion` / `targetSdkVersion` | `15` / `22` |

### Fallos encontrados y corregidos durante esta verificación

El guion de la Clase 2 que existía dentro del script **tenía seis errores**, cada
uno de los cuales habría roto la clase:

| Error del guion | Corrección |
|---|---|
| Hook de Frida sobre `checkCredentials` | Ese método no existe. El hook va a `convertStreamToString` (`DoLogin$RequestTask`) |
| `hook_login.js` con `<Clase>`/`<método>` sin rellenar | Sustituido por [`clases/hook-m3-bypass.js`](clases/hook-m3-bypass.js), ejecutado y verificado |
| `frida ... --no-pause` | Flag eliminado en Frida 16; provoca `unrecognized arguments` |
| `SSLContext.setDefault()` para el pinning | Ese método no existe, y la app no usa TLS: no hay nada que bypassear |
| «7 permisos peligrosos» | Son **8** |
| Burp Suite para la fase M5 | No arranca en headless; se incluye [`clases/mitm-m5.py`](clases/mitm-m5.py) |

Y cuatro bugs del propio proxy, todos encontrados ejecutándolo y no leyéndolo:

| Bug | Síntoma | Causa |
|---|---|---|
| Log vacío | El proxy «no capturaba» nada | Python bufferiza stdout sin TTY |
| **HTTP 400** | Toda petición devolvía 400 | Al borrar `Proxy-Connection` se dejaba su `\r\n`, que terminaba las cabeceras antes de tiempo |
| **Colgado** | El proxy no respondía | Al alterar el body no se ajustaba `Content-Length` (y la regex `…\d+$` no casaba por el `\r`) |
| App no entraba | Respuesta falsificada inútil | `Wrong`→`Correct` da `Correct Password`, que no contiene `"Correct Credentials"` |

### Una trampa documentada

El backend **sí** registra contraseñas (`print(newpassword)`, `app.py:85`), pero
**no aparecen en `journalctl`**: Python bufferiza stdout cuando no hay terminal.
Pedir a un alumno que busque la contraseña en el log y no verla lleva a la
conclusión equivocada. Documentado en el guion y en `troubleshooting.md`.

---

## 10. Clase 3 (M8, M9, M10) — VERIFICADO

Igual que la Clase 2, ejecutada de extremo a extremo contra la misma VM
(`172.25.208.100:5555`, Android 8.1.0 API 27) y el mismo backend. Transcripción
completa en `docs/clases/clase-3-evidencia.md`.

### Entorno exigido por la clase

| Componente | Estado al empezar | Resolución aplicada |
|---|---|---|
| JADX | Instalado | — |
| **apktool** | **Ausente** | El instalador solo lo pone con `--extras`, pero la clase lo necesita para M8. Está en los repos de Ubuntu 24.04: `sudo apt-get install -y apktool` → `2.7.0-dirty`. El `verify()` del script ahora lo avisa |
| **apksigner** | **Fuera del PATH** | En `/opt/android-sdk/build-tools/33.0.2/`. `verify()` ahora lo comprueba |
| **d8** | Fuera del PATH | Mismo directorio |
| **tshark** | **Ausente** | Se eliminó de la clase: no aporta nada a M8/M9/M10 y `verify()` no lo comprueba |

### Hallazgos verificados (20)

| Bloque | Verificados | Requieren instrumentación |
|---|---|---|
| M9 Reverse Engineering | 6 | 1 (Frida) |
| M8 Code Tampering | 8 | 2 (`apktool`, `apksigner`) |
| M10 Extraneous Functionality | 6 | 0 |

**11 de 20 se demostraron sin más que `adb shell` y `curl`.** Los tres que
necesitan herramienta son: el hook de M9, el parche de smali y el intento Janus.

### Los tres resultados que exigían documentarlos como fallo

1. **Con el backend apagado, la APK parcheada NO entra**, aunque se parchen las
   dos puertas de rejection. El motivo es estructural: el chequeo de login está
   dentro del `try` de `postData`, junto a la llamada de red, así que la
   excepción aborta antes de llegar al código parcheado. No se puede «parchear
   para offline» sin reestructurar el método.

2. **Janus pasa la verificación de firma pero no la instalación.** Con 844 bytes
   de DEX ajeno prependidos y el directorio central del ZIP corregido:
   `apksigner verify` sigue reportando la **firma v1 original como válida**,
   `unzip -t` no reporta errores, y las 555 entradas del ZIP se extraen
   **byte-idénticas** a las del original (mismo SHA-256 para
   `AndroidManifest.xml` y `classes.dex`). Pero `adb install` falla con
   `INSTALL_PARSE_FAILED_UNEXPECTED_EXCEPTION` y
   `PackageParser: java.io.FileNotFoundException: AndroidManifest.xml`.

   La variante sin corregir el directorio central da el mismo error, y la APK
   original instala bien como control.

   Lo que **sí** cambia, y tiene que cambiar, es la *metadata* del ZIP: los
   offsets del directorio central se desplazan +844. Por eso la comprobación
   correcta es entrada a entrada, no `cmp` sobre el fichero entero.

3. **Ese último punto coincide con la documentación.** NVD lista CVE-2017-13156
   como afecta a Android **5.1.1, 6.0, 6.0.1, 7.0, 7.1.1, 7.1.2, 8.0**. La VM
   es **8.1.0**: el fallo ocurre exactamente donde termina el rango documentado.
   Comprobación independiente de un límite publicado.

### Hallazgo principal de la clase

El receptor `MyBroadCastReceiver` está declarado `exported="true"` **sin ningún
permiso**. Desde fuera de la app, un simple `am broadcast` consigue que descifre
la contraseña almacenada con la clave embebida de M4 y la envíe por SMS al número
indicado:

```
System.out: For the changepassword - phonenumber: +34600000000 password is:
             Updated Password from: Dinesh@123$ to: ATACANTE-DICE-ESTO
```

Además, `PostLogin` exportada permite entrar en la zona autenticada con
`am start` desde el launcher, sin usuario ni contraseña, y
`TrackUserContentProvider` (sin `readPermission` ni `writePermission`) permite
**leer e insertar filas** desde cualquier app.

### Errores del guion anterior corregidos

| # | Antes | Ahora |
|---|---|---|
| 1 | `frida … --no-pause` | Eliminado: el flag no existe en Frida 16+ |
| 2 | Hook sobre `CryptoClass.encrypt`/`.decrypt` | Hook sobre `aesEncryptedString` / `aesDeccryptedString`, los nombres reales |
| 3 | El replacement llamaba a `this.encrypt(...)` | Usa `this.aesEncryptedString(theString)`, el overload real |
| 4 | Modificaba `res/drawable-hdpi/ic_launcher.png` | La app no usa `drawable-hdpi`. El rename va por `strings.xml`, y verificado dentro de `resources.arsc` |
| 5 | `tcpdump … host <ip>` y `tshark` | Fase eliminada: sintaxis incorrecta y `tshark` no instalado |
| 6 | El hook no disparaba nunca | Causa: `-f` pierde el descifrado de `onCreate`. Ahora se adjunta por PID |
| 7 | `adb push` de las preferencias | No funciona: el fichero queda de `root` y la app no lo lee. Se configura en la pantalla |

### Comprobado al final

`bash -n` y `shellcheck -S style` sin avisos. `class3_runbook()` copia los
ficheros verificados desde `docs/clases/`, igual que `class2_runbook()`, de modo
que el laboratorio instalado y el repositorio no pueden divergir. `verify()`
comprueba ahora `apksigner` con `[FALLA]` si falta y `apktool` con `[AVISO]`.

---

## 10-bis. Segunda verificación de la Clase 3: ejecución como alumno — VERIFICADO

La primera verificación (§10) comprobó que cada comando **funciona**. Esta
comprobó algo más exigente: que el guion **se puede seguir de arriba abajo**, en
una sola terminal, como se impartirá.

**Método:** se extrajeron los 49 bloques `bash` de
`docs/clases/clase-3-owasp-mobile-top10.md` y se concatenaron en un único
script, conservando el `cwd` entre bloques (que es justo lo que pasa cuando
alguien los va copiando). Se ejecutó desde el laboratorio **reinstalado** y con
el backend reiniciado. La primera pasada dio **5 bloques con error**; la última,
**0**.

### 12 fallos más, todos de estado o de rutas

| # | Síntoma | Causa real | Corrección |
|---|---|---|---|
| 8 | `grep` de §1.2 no devolvía nada | `[a-zA-Z]+` no captura los dígitos de `aes256encrypt`, y `\[\]` dentro de un conjunto de corchetes no es una clase | `public (static )?[A-Za-z]+(\[\])? [A-Za-z0-9]+\(`. Devuelve los **cuatro** métodos |
| 9 | §3.4 y §3.5: `No such file or directory` | Usan rutas relativas (`resources/…`) pero §2.1 había cambiado el `cwd` a `reports/` | `cd` al árbol de JADX en cada bloque |
| 10 | §3.1: `curl` con `rc=7` | §2.6 apagó el backend y el reinicio estaba escondido en una nota de prosa | §2.6 termina con `systemctl start` + comprobación |
| 11 | `BancoSeguro OFICIAL` no aparecía en `resources.arsc` | §2.7 hacía el `sed` pero **no** reconstruía, no firmaba y no reinstalaba. Lo verificado era una APK construida antes del `sed` | §2.7 documenta ahora `apktool b` + `apksigner sign` + `install`, con `InsecureBankv2_mod3_signed.apk` |
| 12 | `Successful Login` y `For the changepassword` vacíos | Tras `uninstall`/`install` desaparecen las preferencias: la app cae en `FilePref` y los `input tap` se quedan en un formulario vacío | Guarda explícita al inicio de §1.3 + snippet de reapuntar la IP en §0.4, §2.5 y §2.9 |
| 13 | El receptor de SMS no logueaba nada | `mySharedPreferences` lo escribe `saveCreds()`; sin login previo, `onReceive` peta NPE y **se traga la excepción** | Prerrequisito documentado + comprobación previa en el Anexo |
| 14 | IP guardada como `10.0.2.2172.25.208.104` | `adb shell input text` **añade**, no sustituye; los campos vienen precargados | Borrado previo con `DEL` tras tocar el borde derecho del campo |
| 15 | `KEYCODE_MOVE_END` dejaba `10172.25.208.104` | En Android 8.1 no lleva el cursor al final en ese campo, y los `DEL` se comen lo de la izquierda | Tocar el borde derecho del campo (`tap 625`) en vez de `MOVE_END` |
| 16 | `javac: file not found` en el paso Janus | El guion compilaba `janus-src/com/android/insecurebankv2/CryptoClass.java`; el fichero real está en `janus-src/CryptoClass.java` (el paquete lo declara el `.java`) | Ruta corregida + `rm -rf classes classes.dex` antes, porque si no se reutiliza el DEX viejo |
| 17 | `prepend.py`: `IndexError` | Necesita **dos** argumentos (original, salida) y el guion no invocaba el script | Comando documentado, validación de uso y comprobación `entrada a entrada identicas: OK (555 entradas)` |
| 18 | `frida: [Errno 2] No such file: hook-m9-clave.js` | El guion lo buscaba en `reports/`, pero el instalador lo deja en `tools/` | Ruta corregida en las dos referencias |
| 19 | El snippet de `FilePref` no guardaba la IP (quedaba `10.0.2.2`) | `sleep 3` fijo: si la pantalla tarda más en pintarse, el `tap` cae en el vacío y `adb` devuelve `0` igual | Esperar a que la UI esté lista (`uiautomator dump` + `grep edittext_serverip`) en vez de un `sleep` fijo |

> El fallo 18 **solo** se detecta ejecutando Frida de verdad. Con un shim que
> devuelve 0 (que es lo que permite validar los otros 48 bloques en lote), el
> bloque pasa sin detectar nada. Es el límite del método: un shim valida la
> construcción del comando, no que el comando haga lo que dice.

### Frida ejecutado de verdad (no simulado)

Los dos sentidos del hook de M9 se ejecutaron contra la app real, adjuntando por
PID como documenta el guion:

```
  [M9] aesEncryptedString  (cifrando)  <-  "Dinesh@123$"
        clave en memoria : "This is the super secret key 123"
        IV en memoria    : 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
```

```
  [M9] aesDeccryptedString (descifrando)  <-  "DTrW2VXjSoFdg0e61fHxJg==
    "
        clave en memoria : "This is the super secret key 123"
```

El segundo caso reveló un detalle que el guion documentaba idealizado: el Base64
guardado lleva un salto de línea y cuatro espacios **dentro** de la cadena, porque
viene del XML indentado de `mySharedPreferences.xml`. `Base64.decode` lo tolera y
la app funciona, pero comparar ese valor con el esperado falla. Ya está
documentado en la clase y en `troubleshooting.md`.

### Dos fallos de documentación, no de ejecución

- El tamaño del DEX de Janus estaba documentado como **856 bytes**; el valor real
  del stub instalado es **844**. Los offsets del directorio central que se
  documentaban (`3408268 -> 3409124`) tampoco cuadraban.
- El listado de SDKs de terceros documentaba **5** entradas; hay **6**
  (faltaba `com.google.android.gms.version`).

Ambos se han vuelto a transcribir desde una ejecución limpia.

### Un hallazgo metodológico, documentado en la clase

`adb shell input tap` devuelve `rc=0` **aunque no haga nada**. Escribir en la
pantalla equivocada es invisible en el código de salida y el síntoma aparece
tres pasos más allá (login que no entra, `grep` vacío, hook que no dispara). Por
eso todos los scripts de la clase terminan verificando un **efecto**
(fichero de preferencias, lista de `shared_prefs`, `uiautomator dump`) en lugar
de confiar en el `rc`.

### Resultado

```
bloques bash en el guion: 49
primera pasada:           5 con error
pasada final:            0 con error  (dos veces seguidas)
```

Los 49 bloques se ejecutan encadenados en una sola terminal desde el laboratorio
reinstalado, y las salidas que el guion declara como reales coinciden con lo
impreso. La penúltima pasada se hizo además **sin reinstalar** (con las
preferencias ya puestas), que es el peor caso para el bloque de `FilePref`:
también da `0`.

### Repetición del 2026-10-06 (previa a impartir la clase)

El día antes de dar la clase se volvió a ejecutar todo desde cero, sobre una VM
que arrancó **desconectada**: hubo que `adb connect`, `adb root` y arrancar
`frida-server` a mano. Con eso preparado:

- **49/49 bloques `bash` con `rc=0`**, dos pasadas seguidas (una reinstalando y
  otra sin reinstalar). Sin regresiones.
- **Frida real** (no el shim), los dos sentidos: `aesEncryptedString <-
  "Dinesh@123$"` y `aesDeccryptedString <- "DTrW2VXjSoFdg0e61fHxJg==\n    "`,
  más el `For the changepassword` en logcat.
- Salidas contrastadas contra el documento: los 4 métodos de §1.2, los 6
  componentes de §1.5, `User Does not Exist` + `Successful Login:: ,
  account=usuario-inexistente:basura`, `BancoSeguro OFICIAL` dentro de
  `resources.arsc`, Janus (844 bytes, 555 entradas idénticas, firma v1 válida,
  Android 8.1 rechaza), `/devlogin` y el provider sin permisos.
- Firma instalada comprobada por `apksigner`: `CN=Dinesh Shetty, …` (original) y
  `CN=Attacker, …` (modificada).
- Copias del laboratorio (`guion`, `hook-m9-clave.js`, `prepend.py`,
  `CryptoClass-janus.java`) **idénticas** a las del repositorio.

**No hubo nada que corregir**: el guion y las herramientas ya estaban bien tras
la ronda del 2026-10-04. El único hallazgo fue operativo —la VM no trae
`frida-server` corriendo tras un reinicio— y quedó recogido en
`troubleshooting.md`.

---

## 10-ter. Comprobaciones de contenido

### Los 15 CVE citados, contrastados contra NVD

Todos los identificadores de `docs/clases/cve-2026-mobile.md` se consultaron en
la API de NVD (`services.nvd.nist.gov/rest/json/cves/2.0`) el **2026-10-04**.
**Los 15 existen.** Resultado:

| CVE | Publicado | CVSS NVD | CWE NVD |
|---|---|---|---|
| CVE-2026-33362 | 2026-05-11 | 8.6 HIGH | CWE-321 |
| CVE-2026-28626 | 2026-09-08 | 7.3 HIGH | CWE-601 |
| CVE-2026-0047 | 2026-03-02 | 8.4 HIGH | CWE-280 |
| CVE-2026-28666 | 2026-09-08 | 8.8 HIGH | CWE-863 |
| CVE-2026-55273 | 2026-09-08 | 7.8 HIGH | CWE-20 |
| CVE-2026-49932 | 2026-09-08 | 7.8 HIGH | CWE-122 |
| CVE-2026-28604 | 2026-09-08 | 7.5 HIGH | CWE-362 |
| CVE-2026-28618 | 2026-09-08 | 8.8 HIGH | — |
| CVE-2026-28639 | 2026-09-08 | 7.8 HIGH | — |
| CVE-2026-28662 | 2026-09-08 | 8.0 HIGH | — |
| CVE-2026-49882 | 2026-09-08 | 8.8 HIGH | — |
| CVE-2026-49884 | 2026-09-08 | 7.8 HIGH | — |
| CVE-2026-49919 | 2026-09-08 | 7.8 HIGH | — |
| CVE-2026-49921 | 2026-09-08 | **9.8 CRITICAL** | CWE-122 |
| CVE-2017-13156 | 2017-12-06 | sin puntuación | CWE-434 |

Dos correcciones salieron de esta comprobación:

1. **CVE-2026-33362 está clasificado como CWE-321** (*Use of Hard-coded
   Cryptographic Key*) en NVD, no como el genérico CWE-798 que decía el
   documento. CWE-321 es además más preciso para el hallazgo.
2. **La columna «Crítica» de la tabla §2.5 del documento de CVE es la escala de
   Google, no la de CVSS.** En NVD, casi todos son `HIGH` y solo CVE-2026-49921
   es `CRITICAL`. Se añadió una nota que obliga a decir de dónde sale cada cifra,
   porque en un informe técnico la diferencia se nota.

También se confirmó el rango de versiones de CVE-2017-13156 tal y como lo usa el
guion para explicar por qué Android 8.1 lo bloquea: `5.1.1, 6.0, 6.0.1, 7.0,
7.1.1, 7.1.2, 8.0` (Android ID `A-64211847`). La VM es 8.1.0.

### Integridad del texto

Recuento automático sobre todo el repositorio (`docs/`,
`setup-mobile-pentest-lab.sh`) en busca de caracteres corruptos: CJK, cirílico,
griego, vietnamita y caracteres de control. **0 hallazgos.** También se buscan
anglicismos y erratas frecuentes (`tried`, `teh`, `recieve`, `occured`,
`teach`…): **0**.

Durante esta pasada se corrigieron dos corrupciones propias introducidas al
reescribir y cinco erratas: dos caracteres CJK, `otro cosa` → `otra cosa`,
`loudo` → `lo`, `distributing` → `colando`, `crypto` → `criptográfica`,
`NSD` → `NVD`. El barrido posterior confirma que no quedan residuos.

### Estado tras las pruebas

```
app instalada:   1  (original, CN=Dinesh Shetty)
backend:         active
proxy VM:        :0
mydb:            0 filas
base del backend: dinesh,jack   (restaurada)
```

---

## 10-quater. Clase 4 (resiliencia) — Material didáctico, verificado lo verificable

La Clase 4 cierra el curso con un **repaso del OWASP Mobile Top 10** y el grupo
**MASVS-RESILIENCE**. No es una clase de ataque: no añade una vulnerabilidad
nueva contra la VM. Por eso lo que se verifica aquí es distinto.

### Qué se ha comprobado

- **Los cuatro controles MASVS-RESILIENCE-1..4** y su descripción, contra la
  documentación oficial en `mas.owasp.org`. Correctos.
- **Los identificadores `MASWE` y `MASTG-KNOW` citados** existen y corresponden a
  lo que dice el guion (p. ej. `MASTG-KNOW-0027` root, `-0035` Play Integrity,
  `-0058` integridad en runtime, `-0065` detección de herramientas de análisis
  dinámico).
- **La presentación `.pptx` se genera y se renderiza.** 18 diapositivas, sin
  texto desbordado (revisadas convirtiendo a PDF y a imagen con LibreOffice).
- **El instalador copia el material** al laboratorio (`CLASE4-RESILIENCIA.pptx`,
  `.md` y el generador), de forma idéntica al repositorio.
- **Las observaciones sobre InsecureBankv2** («no comprueba la firma», «no
  detecta Frida», «root detection decorativa») **reutilizan resultados de las
  Clases 1–3**, que sí están verificados de extremo a extremo.

### Qué NO se ha comprobado (y se dice en el guion)

1. **No se ha construido ni probado una app endurecida.** Los controles se
   describen; no se implementan ni se comprueban en ejecución.
2. **Play Integrity API y Key Attestation no se han probado** (fuera del alcance
   del laboratorio headless).
3. **No se ejecutó el procedimiento de test completo de cada `MASTG-TEST`**; se
   citan sus `MASTG-KNOW` como referencia.

Todo esto está en el
[Anexo B del guion](clases/clase-4-resiliencia.md#anexo-b--lo-que-no-está-verificado).

---

## 11. Lo que **NO** está verificado

Conviene decirlo con claridad:

1. **La instalación completa del script, de principio a fin, sobre un Ubuntu
   24.04 limpio.** Se ha probado por partes, nunca de forma integrada. Un
   fallo de orden entre componentes sólo aparecería en esa ejecución.

2. **El arranque real de MobSF en Docker, y con ello la Fase 1 de la Clase 1.**
   La imagen, el usuario UID 9901, el bind mount y `--shm-size` están
   configurados según la documentación, pero no se ha observado un contenedor
   levantar y aceptar un análisis. En la máquina de pruebas el demonio de
   Docker no era accesible.

3. **El instalador de Burp (`install4j`).** El flag `-q` está puesto porque sin
   él se cuelga, pero la instalación real no se ha ejecutado.

4. **El servicio systemd del backend en un sistema con systemd real.** En el
   entorno de pruebas no había un `systemd` completo.

5. **Clases posteriores a la 4.** Este repositorio documenta y prepara las Clases
   1, 2 y 3 (ataque, verificadas de extremo a extremo) y la Clase 4 (resiliencia,
   material didáctico con lo verificable comprobado en §10-quater). No hay guion
   para una clase 5.

6. **Los CVE citados en `docs/clases/cve-2026-mobile.md` no se han reproducido.**
   Son vulnerabilidades reales de otros productos (Android, SDKs de terceros, apps
   comerciales) usadas para contextualizar los hallazgos del laboratorio. **Este
   repositorio no las ha explotado ni las ha verificado.** Lo que sí se verificó
   en la VM es el comportamiento equivalente en InsecureBankv2. La excepción
   parcial es Janus (CVE-2017-13156), del que se comprobó el comportamiento del
   esquema de firma v1 y se comprobó que Android 8.1 bloquea la instalación.

### Recomendación

Antes de impartir la primera clase, ejecutar el instalador completo una vez
sobre el servidor definitivo y recorrer los guiones de las Clases 1, 2 y 3
enteros. Los tres están escritos con **salidas reales capturadas**, así que
cualquier divergencia se detecta comparando contra lo que hay en el documento.
La Clase 4 es de repaso y defensa: se puede impartir sin depender de la VM,
pero la demo reutiliza resultados de la Clase 3.

El guion de la Clase 3 tiene además una particularidad: documenta **tres ataques
que no funcionan** (§2.6 y §2.8). Si al impartirla uno de ellos te sale bien,
es probable que tu versión de Android sea ≤ 8.0, no que el documento esté mal.

Y una segunda, más sutil: hay varios `grep` que **no** encuentran nada cuando
todo está bien. En concreto, el `For the changepassword` solo aparece si hay un
`mySharedPreferences.xml`, y el `Successful Login` de §2.5 solo si la app sigue
apuntando al host tras el reinstalado. Son fallos **esperados** por diseño, no
averías: por eso el guion los documenta con su prerrequisito al lado. Si un
alumno te dice «no me sale», lo primero que hay que mirar no es su Frida: es si
tiene configurada la IP del servidor.

---

## 12. Estado de la máquina de pruebas

Tras la segunda ejecución, la máquina de pruebas (`172.25.208.104`) queda así:

**Instalado y funcionando:**

- Componentes de la Clase 1 en `~/mobile-owasp-lab/`
- Servicio `insecurebankv2-server` activo y habilitado
- Ayudantes `bank-*`, `clase1-prep`, `clase1-demo`, `vmconnect`, `mobsf-*`

**En la VM `172.25.208.100`:**

- `InsecureBankv2` instalada, configurada apuntando a `172.25.208.104:8888`
- Base de datos `mydb` con un registro (`dinesh`) en la tabla `names`
- Credenciales guardadas en las `SharedPreferences`
- `frida-server` 17.19.0 en `/data/local/tmp/frida-server`, arrancado
- Proxy del sistema **desactivado** (`http_proxy` borrado) tras la fase M5

**Backups y limpieza al terminar la verificación de la Clase 2:**

- Base de datos del backend restaurada: `dinesh` y `jack` con sus contraseñas
  originales (se comprobó el login después de restaurar).
- Tabla `names` de la VM vaciada tras las demos.
- Puerto 8080 liberado.

Para dejar la VM completamente limpia:

```bash
adb -s 172.25.208.100:5555 uninstall com.android.insecurebankv2
```

Para retirar los servicios de esta máquina:

```bash
sudo systemctl disable --now insecurebankv2-server
sudo rm -f /usr/local/bin/{bank-*,clase1-*}
sudo rm -f /etc/systemd/system/insecurebankv2-server.service
sudo systemctl daemon-reload
```
