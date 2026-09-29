# Catálogo de comandos

Todos los ayudantes se instalan en `/usr/local/bin` y están disponibles para
cualquier usuario del sistema.

---

## MobSF

| Comando | Qué hace |
|---|---|
| `mobsf-start` | Arranca el contenedor (equivalente a `sudo systemctl start mobsf-server`) |
| `mobsf-stop` | Lo para |
| `mobsf-logs` | Sigue el log del contenedor en tiempo real |
| `sudo systemctl status mobsf-server` | Estado del servicio systemd |

**Acceso:** `http://<IP-del-servidor>:8000` — usuario `mobsf`, contraseña `mobsf`.

**Antes de subir una APK**, espera a que el contenedor esté listo:

```bash
mobsf-logs          # esperar a "Gunicorn server started"
```

> El proxy interno de MobSF (puerto 1337) se publica en `MOBSF_BIND_ADDR`, que
> por defecto es `0.0.0.0` para que el dispositivo Android alcance el análisis
> dinámico. Instálalo con `MOBSF_BIND_ADDR=127.0.0.1` para dejarlo sólo local.

---

## VM Android

### `vmconnect`

Conecta con la VM, activa root y muestra un resumen. **Úsalo antes de cualquier
práctica**: hace tres cosas que ADB no hace solo.

```bash
vmconnect
```

1. `adb connect` a la VM
2. `adb root` — **el demonio ADB de la VM se reinicia y la conexión TCP cae**;
   sin reconectar, el dispositivo queda en `offline` y parece que el
   laboratorio está roto
3. Reconexión y resumen: dispositivo, versión de Android, API, ABI y sesión

### `vmconnect frida`

Detecta la ABI real de la VM y la versión del cliente de Frida, e imprime los
comandos exactos para instalar `frida-server`.

```bash
vmconnect frida
```

La versión del cliente y la del servidor **deben coincidir exactamente**; si no,
Frida responde `server version mismatch`.

### Conexión manual

```bash
adb connect 172.25.208.100:5555
adb devices -l
adb root
sleep 3
adb connect 172.25.208.100:5555
```

---

## Clase 1 — InsecureBankv2

| Comando | Qué hace |
|---|---|
| `bank-start [PUERTO]` | Arranca el backend de la app. Sin argumento usa 8888; con argumento cambia el puerto de verdad (lo escribe en `/etc/mobile-lab/bank.env`) |
| `bank-stop` | Lo para |
| `bank-status` | Estado, puerto y si el login responde de verdad |
| `clase1-prep [PUERTO]` | Installa y configura el móvil para la clase (~30 s) |
| `clase1-demo` | Repite la demo de M2 y M6 y guarda los informes |

Si cambias el puerto del backend, reconfigura la app con el **mismo** número o
el login fallará:

```bash
bank-start 8899
clase1-prep 8899
```

### Secuencia recomendada antes de la clase

```bash
bank-start
clase1-prep
```

`clase1-prep` hace, en este orden:

1. Conecta con la VM y activa root
2. **Desactiva la verificación de apps por USB** (si no, `adb install` falla)
3. Instala `InsecureBankv2.apk`
4. Escribe la IP y el puerto del backend en las `SharedPreferences` de la app
5. Abre la app en la pantalla de login

### Credenciales de la app

| Usuario | Contraseña | Nota |
|---|---|---|
| `dinesh` | `Dinesh@123$` | Usuario normal, entra por `/login` |
| `jack` | `Jack@123$` | Segundo usuario, útil para ver el saldo de otro |
| `devadmin` | `devadmin` | Entra por `/devlogin` |

### Comprobar el backend a mano

```bash
curl -s -X POST -d 'username=dinesh&password=Dinesh@123$' \
     http://127.0.0.1:8888/login
# {"message": "Correct Credentials", "user": "dinesh"}
```

Si no devuelve eso, el login de la app fallará y **el log de M6 no se emite**.

### Atajos de la demo

```bash
# M2: extraer y ver la base de datos (se llama mydb, NO insecurebank.db)
adb pull /data/data/com.android.insecurebankv2/databases/mydb .
sqlite3 -header -column mydb "select * from names;"

# M2: las credenciales "cifradas"
adb shell "cat /data/data/com.android.insecurebankv2/shared_prefs/*.xml"

# M6: el log en vivo, en una terminal aparte
adb logcat -c && adb logcat -s Successful Login:

# M6: histórico
adb logcat -d | grep "Successful Login"
```

---

## Análisis de código

```bash
# Descompilar
jadx ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk \
     -d ~/mobile-owasp-lab/reports/jadx/InsecureBankv2

# La evidencia de M1
grep -rn "secret key" InsecureBankv2/sources/com/android/insecurebankv2/

# La base de datos (M2)
grep -rn "DATABASE_NAME" InsecureBankv2/sources/com/android/insecurebankv2/

# El log con la contraseña (M6)
grep -rn "Log\." InsecureBankv2/sources/com/android/insecurebankv2/
```

En un servidor sin escritorio se usa la **CLI**. `jadx-gui` también está
instalado, pero requiere escritorio.

---

## Burp Suite

Burp **no** se autoarranca. Se usa por tunel SSH desde el navegador del alumno:

```bash
ssh -L 8080:127.0.0.1:8080 usuario@servidor
```

Y luego `http://127.0.0.1:8080` en el navegador.

Alternativa con X11:

```bash
ssh -X usuario@servidor
burpsuite
```

El proxy de Burp escucha en `0.0.0.0:8080` **a propósito**: la VM Android
necesita alcanzarlo para el escenario de M5 (comunicación insegura).

---

## Utilidades

| Comando | Uso |
|---|---|
| `vmconnect --help` | Ayuda de los ayudantes |
| `sudo systemctl list-units \| grep -E 'mobsf\|insecurebank'` | Servicios del laboratorio |
| `sudo journalctl -u mobsf-server -f` | Log de MobSF en vivo |
| `sudo journalctl -u insecurebankv2-server -f` | Log del backend |
| `docker ps`, `docker logs -f mobsf` | Estado directo del contenedor |
| `nmap -sV -p 8000,8080,8888,5555 <vm>` | Comprobar qué ve la VM |

---

## Ficheros de configuración

| Ruta | Contenido |
|---|---|
| `/etc/mobile-lab/lab.env` | Variables compartidas (`LAB_DIR`, `LAB_VM`, `LAB_MOBSF_PORT`…) |
| `/etc/profile.d/android-sdk.sh` | Variables del SDK para sesiones de login |
| `/etc/bash.bashrc` | Variables del SDK para sesiones interactivas |

```bash
cat /etc/mobile-lab/lab.env
```
