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

2. **Janus pasa la verificación de firma pero no la instalación.** Con 856 bytes
   de DEX ajeno prependidos y el directorio central del ZIP corregido:
   `apksigner verify` sigue reportando la **firma v1 original como válida**,
   `unzip -t` no reporta errores, y `AndroidManifest.xml` y `classes.dex` son
   **byte-idénticos** a los originales (mismo SHA-256). Pero `adb install` falla
   con `INSTALL_PARSE_FAILED_UNEXPECTED_EXCEPTION` y
   `PackageParser: java.io.FileNotFoundException: AndroidManifest.xml`.

   La variante sin corregir el directorio central da el mismo error, y la APK
   original instala bien como control.

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

`bash -n` y `shellcheck -S style` sin avisos. `class3_runbook()` (7714 → 4239
caracteres) copia los ficheros verificados desde `docs/clases/`, igual que
`class2_runbook()`, de modo que el laboratorio instalado y el repositorio no
pueden divergir. `verify()` comprueba ahora `apksigner` con `[FALLA]` si falta y
`apktool` con `[AVISO]`.

### Estado tras las pruebas

```
app instalada:   1  (original, CN=Dinesh Shetty)
backend:         active
proxy VM:        :0
mydb:            0 filas
base del backend: dinesh,jack   (restaurada)
```

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

5. **Clases 4 en adelante.** Este repositorio documenta y prepara las Clases 1,
   2 y 3. **Las tres están escritas y verificadas** (ver secciones 9 y 10). No hay
   guion de clase posterior a la 3.

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

El guion de la Clase 3 tiene además una particularidad: documenta **tres ataques
que no funcionan** (§2.6 y §2.8). Si al impartirla uno de ellos te sale bien,
es probable que tu versión de Android sea ≤ 8.0, no que el documento esté mal.

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
