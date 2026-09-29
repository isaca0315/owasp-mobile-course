# Clase 3 — OWASP Mobile Top 10: M8, M9 y M10

> **Estado del documento:** guion preparado para la sesión de aula. Todas las
> salidas y referencias de código marcadas como «salida real» deben
> verificarse contra la VM antes de impartir la clase, igual que se hizo con
> la Clase 1 (`docs/clases/clase-1-evidencia.md`).

| | |
|---|---|
| **App objetivo** | InsecureBankv2 (`com.android.insecurebankv2`) |
| **Proyecto** | Dinesh Shetty — referenciado por OWASP MASTG como `MASTG-APP-0010` |
| **Dispositivo** | VM Android-x86, API 27, por ADB |
| **Duración prevista** | 120 minutos |
| **Riesgos** | M8 Code Tampering · M9 Reverse Engineering · M10 Extraneous Functionality |
| **Requisitos** | JADX (análisis estático) · apktool (reempaquetado) · frida-server (instrumentación) |

## Índice

- [Antes de impartir la clase](#antes-de-impartir-la-clase)
- [Fase 0 — Preparación](#fase-0--preparación)
- [Fase 1 — M9: Reverse Engineering](#fase-1--m9-reverse-engineering)
  - [1.1 Descompilar la APK](#11-descompilar-la-apk)
  - [1.2 Analizar el código](#12-analizar-el-código)
  - [1.3 Buscar secretos hardcodeados](#13-buscar-secretos-hardcodeados)
  - [1.4 Análisis dinámico con Frida](#14-análisis-dinámico-con-frida)
- [Fase 2 — M8: Code Tampering](#fase-2--m8-code-tampering)
  - [2.1 Modificar la APK](#21-modificar-la-apk)
  - [2.2 Reempaquetar y firmar](#22-reempaquetar-y-firmar)
  - [2.3 Instalar la APK modificada](#23-instalar-la-apk-modificada)
  - [2.4 Modificar recursos de la APK](#24-modificar-recursos-de-la-apk)
- [Fase 3 — M10: Funcionalidad extraña](#fase-3--m10-funcionalidad-extraña)
  - [3.1 Buscar funcionalidades ocultas](#31-buscar-funcionalidades-ocultas)
  - [3.2 Analizar permisos excesivos](#32-analizar-permisos-excesivos)
  - [3.3 Buscar backdoors](#33-buscar-backdoors)
  - [3.4 Análisis de red de la app](#34-análisis-de-red-de-la-app)
- [Cierre](#cierre)
- [Anexo A — Referencias de código](#anexo-a--referencias-de-código)
- [Anexo B — Comandos del laboratorio](#anexo-b--comandos-del-laboratorio)

---

## Antes de impartir la clase

> ⚠️ **Esta clase requiere JADX, apktool y frida-server.** Asegúrate de que
> todos funcionan antes de empezar.

### Requisitos previos

| Componente | Estado | Verificación |
|---|---|---|
| JADX | Instalado | `jadx --version` |
| apktool | Instalado | `apktool --version` |
| frida-server | Corriendo en la VM | `frida-ps -Uai` lista las apps |
| Backend InsecureBankv2 | Activo en puerto 8888 | `bank-status` |
| App InsecureBankv2 | Instalada y configurada | `clase1-prep` (de la Clase 1) |
| Descompilación JADX | Generada en `reports/jadx/` | `ls ~/mobile-pentesting-lab/reports/jadx/` |
| APK original | Descargada | `ls ~/mobile-pentesting-lab/apps/apk/InsecureBankv2.apk` |

### Credenciales de la app

| Usuario | Contraseña | Nota |
|---|---|---|
| `dinesh` | `Dinesh@123$` | Usuario normal |
| `jack` | `Jack@123$` | Segundo usuario |
| `devadmin` | `devadmin` | Entra por `/devlogin` |

---

## Fase 0 — Preparación

```bash
# 1. Verificar que el backend está activo
bank-status

# 2. Conectar con la VM y activar root
vmconnect

# 3. Verificar que frida-server está corriendo
frida-ps -Uai

# 4. Verificar que las herramientas están instaladas
jadx --version
apktool --version

# 5. Verificar que la descompilación existe
ls ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/

# 6. Verificar que la APK original existe
ls ~/mobile-pentesting-lab/apps/apk/InsecureBankv2.apk
```

Si `frida-ps -Uai` no lista las apps, reinicia frida-server:

```bash
adb -s 172.25.208.100:5555 shell '/data/local/tmp/frida-server-android-x86_64 &'
```

---

## Fase 1 — M9: Reverse Engineering

> M9 es el riesgo que hace que tu app sea fácil de entender, modificar y atacar.
> Un atacante con acceso a tu APK puede descompilarla, analizarla y descubrir
> secretos, lógica de negocio y vulnerabilidades.

### 1.1 Descompilar la APK

Lo primero es descompilar la APK para ver el código fuente.

```bash
cd ~/mobile-pentesting-lab/reports/jadx
jadx ~/mobile-pentesting-lab/apps/apk/InsecureBankv2.apk -d InsecureBankv2
```

**Salida esperado:**

```
INFO  - loading ...
INFO  - done in 12.345s
```

**Estructura generada:**

```
InsecureBankv2/
├── sources/
│   └── com/
│       └── android/
│           └── insecurebankv2/
│               ├── CryptoClass.java
│               ├── DoLogin.java
│               ├── TrackUserContentProvider.java
│               └── ...
├── resources/
│   ├── AndroidManifest.xml
│   ├── res/
│   └── ...
└── ...
```

> **¿Por qué es M9?** Cualquiera puede descompilar una APK en minutos. El
> código fuente de tu app no es secreto: es público para cualquiera que tenga
> la APK.

### 1.2 Analizar el código

Ahora vamos a analizar el código para entender cómo funciona la app.

**Buscar la clase de cifrado:**

```bash
grep -rn "AES\|Crypto\|encrypt\|decrypt" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -20
```

**Hallazgo:**

```
InsecureBankv2/sources/com/android/insecurebankv2/CryptoClass.java:22:    String key = "This is the super secret key 123";
InsecureBankv2/sources/com/android/insecurebankv2/CryptoClass.java:23:    byte[] ivBytes = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
```

**Buscar la clase de login:**

```bash
grep -rn "Login\|Auth\|Password" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -20
```

**Hallazgo:**

```
InsecureBankv2/sources/com/android/insecurebankv2/DoLogin.java:115:    Log.d("Successful Login:", ", account=" + DoLogin.this.username + ":" + DoLogin.this.password);
```

> **¿Por qué es M9?** Un atacante puede entender la lógica de la app en minutos.
> No hay ofuscación, los nombres de las variables son descriptivos, y el código
> es fácil de seguir.

### 1.3 Buscar secretos hardcodeados

Vamos a buscar secretos en el código: claves, tokens, URLs, etc.

```bash
# Buscar claves y secretos
grep -rniE "secret|key|token|password|api" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -30
```

**Hallazgo:**

```
InsecureBankv2/sources/com/android/insecurebankv2/CryptoClass.java:22:    String key = "This is the super secret key 123";
```

> **¿Por qué es M9?** Los secretos hardcodeados en el código son visibles para
> cualquiera que descompile la APK. Android ofrece el **Keystore** para
> almacenar secretos de forma segura, pero la app no lo usa.

### 1.4 Análisis dinámico con Frida

El análisis estático es útil, pero el análisis dinámico nos permite ver qué
hace la app en tiempo de ejecución.

**Script Frida para hookar el método de cifrado:**

```javascript
// hook_crypto.js - Análisis dinámico de la criptografía
Java.perform(() => {
    const CryptoClass = Java.use("com.android.insecurebankv2.CryptoClass");

    // Hookar el método de cifrado
    CryptoClass.encrypt.implementation = function (plaintext) {
        console.log("[*] encrypt() llamado con:");
        console.log("    plaintext: " + plaintext);
        const result = this.encrypt(plaintext);
        console.log("[+] encrypt() devolvió: " + result);
        return result;
    };

    // Hookar el método de descifrado
    CryptoClass.decrypt.implementation = function (ciphertext) {
        console.log("[*] decrypt() llamado con:");
        console.log("    ciphertext: " + ciphertext);
        const result = this.decrypt(ciphertext);
        console.log("[+] decrypt() devolvió: " + result);
        return result;
    };

    console.log("[*] Hooks de criptografía instalados.");
});
```

**Ejecutar el hook:**

```bash
frida -U -f com.android.insecurebankv2 -l hook_crypto.js --no-pause
```

**En la app:**
1. Abrir InsecureBankv2
2. Hacer login con cualquier credencial
3. Observar la salida de Frida

> **¿Por qué es M9?** El análisis dinámico nos permite ver qué hace la app en
> tiempo de ejecución. Podemos ver las claves, los datos en claro, y el
> comportamiento de la app.

---

## Fase 2 — M8: Code Tampering

> M8 es el riesgo que hace que tu app sea fácil de modificar. Un atacante puede
> descompilar tu APK, modificar el código, reempaquetarla y distribuirla como
> si fuera la tuya.

### 2.1 Modificar la APK

Vamos a modificar la APK para saltarnos la autenticación.

**Descompilar la APK con apktool:**

```bash
cd ~/mobile-pentesting-lab/reports/
apktool d ~/mobile-pentesting-lab/apps/apk/InsecureBankv2.apk -o InsecureBankv2_mod
```

**Estructura generada:**

```
InsecureBankv2_mod/
├── AndroidManifest.xml
├── apktool.yml
├── res/
├── smali/
│   └── com/
│       └── android/
│           └── insecurebankv2/
│               ├── CryptoClass.smali
│               ├── DoLogin.smali
│               └── ...
└── ...
```

**Modificar el código smali:**

```bash
# Buscar la clase de login
find ~/mobile-pentesting-lab/reports/InsecureBankv2_mod/smali/ -name "DoLogin.smali"
```

**Editar el archivo smali:**

```bash
# Abrir el archivo con un editor
nano ~/mobile-pentesting-lab/reports/InsecureBankv2_mod/smali/com/android/insecurebankv2/DoLogin.smali
```

**Buscar la validación de credenciales y modificarla:**

```smali
# Buscar la línea que valida las credenciales
# Cambiar la validación para que siempre devuelva true
```

> **Nota:** La modificación exacta del código smali depende de la estructura
> de la clase. El objetivo es encontrar la validación de credenciales y
> modificarla para que siempre devuelva `true`.

### 2.2 Reempaquetar y firmar

Una vez modificada la APK, hay que reempaquetarla y firmarla.

```bash
# Reempaquetar la APK
apktool b ~/mobile-pentesting-lab/reports/InsecureBankv2_mod \
  -o ~/mobile-pentesting-lab/reports/InsecureBankv2_mod.apk

# Generar una clave de firma (solo una vez)
keytool -genkey -v -keystore ~/mobile-pentesting-lab/reports/debug.keystore \
  -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass android -keypass android

# Firmar la APK
apksigner sign --ks ~/mobile-pentesting-lab/reports/debug.keystore \
  --ks-pass pass:android --key-pass pass:android \
  --out ~/mobile-pentesting-lab/reports/InsecureBankv2_mod_signed.apk \
  ~/mobile-pentesting-lab/reports/InsecureBankv2_mod.apk
```

**Salida esperado:**

```
Verifying
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
```

### 2.3 Instalar la APK modificada

Ahora vamos a instalar la APK modificada en la VM.

```bash
# Desinstalar la app original
adb -s 172.25.208.100:5555 uninstall com.android.insecurebankv2

# Instalar la APK modificada
adb -s 172.25.208.100:5555 install \
  ~/mobile-pentesting-lab/reports/InsecureBankv2_mod_signed.apk

# Configurar la app con el servidor
clase1-prep
```

**En la app:**
1. Abrir InsecureBankv2
2. Introducir cualquier credencial
3. Observar si la modificación funciona

> **¿Por qué es M8?** La app no verifica la integridad del código. Un atacante
> puede modificar la APK, reempaquetarla y distribuirla como si fuera la
> original. La solución es:
> - Verificación de firma de código
> - Integridad del código en tiempo de ejecución
> - Ofuscación del código

### 2.4 Modificar recursos de la APK

Además de modificar el código, también podemos modificar los recursos de la APK.

**Modificar el icono de la app:**

```bash
# Reemplazar el icono
cp ~/mobile-pentesting-lab/reports/icono_falso.png \
  ~/mobile-pentesting-lab/reports/InsecureBankv2_mod/res/drawable-hdpi/ic_launcher.png

# Reempaquetar
apktool b ~/mobile-pentesting-lab/reports/InsecureBankv2_mod \
  -o ~/mobile-pentesting-lab/reports/InsecureBankv2_mod.apk
```

**Modificar el nombre de la app:**

```bash
# Editar el archivo strings.xml
nano ~/mobile-pentesting-lab/reports/InsecureBankv2_mod/res/values/strings.xml
```

```xml
<!-- Cambiar el nombre de la app -->
<string name="app_name">Banco Seguro</string>
```

> **¿Por qué es M8?** Un atacante puede modificar los recursos de la APK para
> hacer que parezca una app legítima. Esto es útil para ataques de phishing.

---

## Fase 3 — M10: Funcionalidad extraña

> M10 es el riesgo de que tu app tenga funcionalidades ocultas que no deberían
> estar ahí. Pueden ser backdoors, funcionalidades de depuración, o código
> que se quedó de desarrollo.

### 3.1 Buscar funcionalidades ocultas

Vamos a buscar funcionalidades ocultas en el código.

**Buscar endpoints ocultos:**

```bash
grep -rniE "http://|https://|/api/|/dev/|/debug/|/test/" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -20
```

**Hallazgo:**

```
InsecureBankv2/sources/com/android/insecurebankv2/DoLogin.java:    private static final String SERVER_URL = "http://172.25.208.104:8888";
```

**Buscar clases de depuración:**

```bash
find ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ \
  -name "*Debug*" -o -name "*Test*" -o -name "*Dev*"
```

> **¿Por qué es M10?** Las funcionalidades ocultas pueden ser backdoors o
> funcionalidades de depuración que permiten a un atacante acceder a la app de
> forma no autorizada.

### 3.2 Analizar permisos excesivos

Vamos a analizar los permisos de la app.

```bash
# Ver los permisos de la APK
aapt dump permissions ~/mobile-pentesting-lab/apps/apk/InsecureBankv2.apk
```

**Salida esperado:**

```
package: com.android.insecurebankv2
uses-permission: android.permission.INTERNET
uses-permission: android.permission.ACCESS_NETWORK_STATE
```

> **¿Por qué es M10?** Los permisos excesivos permiten a la app acceder a
> recursos que no necesita. Un atacante puede explotar estos permisos para
> acceder a datos sensibles.

### 3.3 Buscar backdoors

Vamos a buscar backdoors en el código.

**Buscar credenciales hardcodeadas:**

```bash
grep -rniE "admin|root|backdoor|master|superuser" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -20
```

**Buscar endpoints de administración:**

```bash
grep -rniE "/admin|/manage|/config|/setup" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -20
```

> **¿Por qué es M10?** Los backdoors permiten a un atacante acceder a la app de
> forma no autorizada. Pueden ser credenciales hardcodeadas, endpoints de
> administración, o funcionalidades de depuración.

### 3.4 Análisis de red de la app

Vamos a analizar el tráfico de red de la app para buscar funcionalidades ocultas.

**Capturar el tráfico de red:**

```bash
# En el servidor: capturar el tráfico
sudo tcpdump -i any -w ~/mobile-pentesting-lab/reports/captura.pcap host 172.25.208.100
```

**En la app:**
1. Abrir InsecureBankv2
2. Hacer login
3. Navegar por la app

**Analizar la captura:**

```bash
# Ver las conexiones de la app
tshark -r ~/mobile-pentesting-lab/reports/captura.pcap -Y "http"
```

> **¿Por qué es M10?** El análisis de red nos permite ver qué servidores contacta
> la app. Podemos descubrir funcionalidades ocultas, endpoints de administración,
> o conexiones a servidores maliciosos.

---

## Cierre

> Hemos recorrido tres de los riesgos más críticos del OWASP Mobile Top 10:
>
> - **M9 (Reverse Engineering):** la app es fácil de descompilar y analizar.
>   Los secretos hardcodeados son visibles para cualquiera.
> - **M8 (Code Tampering):** la app es fácil de modificar. Un atacante puede
>   descompilarla, modificarla y distribuirla como si fuera la original.
> - **M10 (Extraneous Functionality):** la app puede tener funcionalidades
>   ocultas que permiten a un atacante acceder de forma no autorizada.
>
> **La lección:** los riesgos del OWASP Mobile Top 10 no son etiquetas sueltas:
> son encadenamientos. M9 hace que M8 sea posible. M8 hace que M10 sea
> peligrosa. Y todo empieza con un código que no está protegido.

**Próxima clase:** Repaso general y examen final.

---

## Anexo A — Referencias de código

Las referencias exactas deben confirmarse con `jadx` y la app instalada. Estas
son las hipótesis de partida:

| Riesgo | Componente | Comprobación |
|---|---|---|
| M9 | `CryptoClass.java:22` | Clave hardcodeada: `String key = "This is the super secret key 123";` |
| M9 | `DoLogin.java:115` | Log con credenciales: `Log.d("Successful Login:", "account=" + user + ":" + pass)` |
| M8 | Toda la APK | Verificar que no hay verificación de firma de código |
| M8 | Toda la APK | Verificar que no hay integridad del código en tiempo de ejecución |
| M10 | `AndroidManifest.xml` | Buscar permisos excesivos |
| M10 | Todo el código | Buscar funcionalidades ocultas, backdoors, endpoints de depuración |

---

## Anexo B — Comandos del laboratorio

| Comando | Función |
|---|---|
| `jadx --version` | Verifica que JADX está instalado |
| `apktool --version` | Verifica que apktool está instalado |
| `bank-status` | Estado del backend |
| `vmconnect` | Conecta con la VM y activa root |
| `vmconnect frida` | URL y comandos de frida-server |
| `frida-ps -Uai` | Lista apps instaladas en la VM |
| `clase1-prep` | Instala y configura el móvil |

### Atajos de la demo

```bash
# M9: descompilar la APK
cd ~/mobile-pentesting-lab/reports/jadx
jadx ~/mobile-pentesting-lab/apps/apk/InsecureBankv2.apk -d InsecureBankv2

# M9: buscar secretos
grep -rniE "secret|key|token|password|api" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -30

# M9: análisis dinámico con Frida
frida -U -f com.android.insecurebankv2 -l hook_crypto.js --no-pause

# M8: descompilar con apktool
cd ~/mobile-pentesting-lab/reports/
apktool d ~/mobile-pentesting-lab/apps/apk/InsecureBankv2.apk -o InsecureBankv2_mod

# M8: reempaquetar
apktool b ~/mobile-pentesting-lab/reports/InsecureBankv2_mod \
  -o ~/mobile-pentesting-lab/reports/InsecureBankv2_mod.apk

# M8: firmar
apksigner sign --ks ~/mobile-pentesting-lab/reports/debug.keystore \
  --ks-pass pass:android --key-pass pass:android \
  --out ~/mobile-pentesting-lab/reports/InsecureBankv2_mod_signed.apk \
  ~/mobile-pentesting-lab/reports/InsecureBankv2_mod.apk

# M8: instalar APK modificada
adb -s 172.25.208.100:5555 install \
  ~/mobile-pentesting-lab/reports/InsecureBankv2_mod_signed.apk

# M10: ver permisos
aapt dump permissions ~/mobile-pentesting-lab/apps/apk/InsecureBankv2.apk

# M10: buscar funcionalidades ocultas
grep -rniE "admin|root|backdoor|master|superuser" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -20

# M10: análisis de red
sudo tcpdump -i any -w ~/mobile-pentesting-lab/reports/captura.pcap host 172.25.208.100
tshark -r ~/mobile-pentesting-lab/reports/captura.pcap -Y "http"
```
