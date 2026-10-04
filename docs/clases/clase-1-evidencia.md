# Evidencia de la Clase 1

Transcripción de una ejecución **real y completa** de la clase, sin recortes.
Sirve para tres cosas:

1. Demostrar que el guion funciona de principio a fin.
2. Proporcionar a quien prepare la clase las salidas de referencia, para
   detectar divergencias en su propio entorno.
3. Registrar los fallos encontrados durante la preparación.

- **Fecha:** 29 de septiembre de 2026
- **Servidor:** `172.25.208.104` (Ubuntu, `systemd` real)
- **VM Android:** `172.25.208.100:5555` — Android 8.1.0, API 27, `x86_64`
- **Script:** `setup-mobile-pentest-lab.sh`, sección de la Clase 1

---

## 0. Preparación

```console
$ systemctl is-system-running
running
$ ps -p 1 -o comm=
systemd
```

### Instalación de los componentes de la Clase 1

Ejecutando las funciones reales del script (`class1_app`, `class1_backend`,
`class1_helpers`, `class1_runbook`):

```
CLASE 1 — BACKEND DE LA APP (AndroLabServer)
[ OK ] Descargado: app.py (5.0K)
[ OK ] Descargado: models.py (1.7K)
[ OK ] Descargado: database.py (727)
[ OK ] Descargado: mydb.db (5.0K)
[ OK ] Fuentes del backend en /home/cwl/mobile-owasp-lab/tools/InsecureBankv2Server
[ .. ] Portando el backend a Python 3...
[ OK ] Backend portado a Python 3.
[ OK ] Backend listo en /home/cwl/mobile-owasp-lab/tools/InsecureBankv2Server
[ OK ] Backend arrancado y escuchando en 0.0.0.0:8888.

[ OK ] Comandos creados: bank-start, bank-stop, bank-status
[ OK ] Comando creado: clase1-prep  (prepara el móvil en un paso)
[ OK ] Comando creado: clase1-demo  (demuestra M2 y M6 de forma repetible)
[ OK ] Guion de la clase (con los comandos ya corregidos)
```

### Comprobación del backend

```console
$ curl -s -X POST -d 'username=dinesh&password=Dinesh@123$' http://127.0.0.1:8888/login
{"message": "Correct Credentials", "user": "dinesh"}

$ systemctl is-active insecurebankv2-server
active
```

---

## 1. FASE 1 — MobSF

**No ejecutada en esta prueba.** La máquina de pruebas no tiene el demonio de
Docker accesible:

```console
$ docker info
$ docker info >/dev/null 2>&1 && echo operativo || echo "daemon no accesible"
daemon no accesible
```

La fase queda pendiente de verificarse sobre el servidor definitivo. Todo lo
demás de la clase sí se ejecutó completo. Ver la sección de limitaciones al
final.

---

## 2. FASE 2 — M2 y M6

### Preparación

```console
$ bank-start
Backend InsecureBankv2 ACTIVO en el puerto 8888
Compruebe que responde:  curl -s -X POST -d 'username=dinesh&password=Dinesh@123$' http://127.0.0.1:8888/login

$ clase1-prep
== 1/5 Conectando con 172.25.208.100:5555 ==
172.25.208.100:5555	device

== 2/5 Desactivando la verificacion de apps por USB ==
   hecho.

== 3/5 Instalando la app ==
Performing Streamed Install
Success

== 4/5 Configurando el servidor en la app ==
   servidor = 172.25.208.104:8888

== 5/5 Arrancando la app ==
   app abierta. Entre con  dinesh / Dinesh@123$
```

### M6 — el log con la contraseña

Introduciendo `dinesh` / `Dinesh@123$` en la app:

```console
$ adb -s 172.25.208.100:5555 logcat -d | grep -i "Successful Login"
09-29 05:02:23.679  5127  5147 D Successful Login:: , account=dinesh:Dinesh@123$
```

**Usuario y contraseña en claro.** Pantalla tras el login:

```console
$ adb shell "cat /sdcard/p.xml" | grep -oE 'text="[^"]*"' | sort -u
text="Change Password"
text="PostLogin"
text="Rooted Device!!"
text="Transfer"
text="View Statement"
```

### M2 — la base de datos

```console
$ adb shell "ls /data/data/com.android.insecurebankv2/databases/"
mydb
mydb-journal

$ adb pull /data/data/com.android.insecurebankv2/databases/mydb .
/data/data/com.android.insecurebankv2/databases/mydb: 1 file pulled, 0 skipped. 4.5 MB/s (20480 bytes in 0.004s)

$ sqlite3 -header -column mydb "select * from names;"
id  name
--  ------
1   dinesh

$ sqlite3 mydb ".schema names"
CREATE TABLE names (id INTEGER PRIMARY KEY AUTOINCREMENT,  name TEXT NOT NULL);
```

### M2 — las credenciales «cifradas»

```console
$ adb shell "cat /data/data/com.android.insecurebankv2/shared_prefs/*.xml"
  "serverip = 172.25.208.104
  "serverport = 8888
  "superSecurePassword = DTrW2VXjSoFdg0e61fHxJg==
  "EncryptedUsername = ZGluZXNo
```

---

## 3. FASE 3 — M1 y el descifrado

### Descompilación

```console
$ jadx -d InsecureBankv2 ~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk
INFO  - done        (2291 clases)
```

### M1 — la clave

```console
$ grep -rn "secret key" InsecureBankv2/sources/com/android/insecurebankv2/
InsecureBankv2/sources/com/android/insecurebankv2/CryptoClass.java:22:    String key = "This is the super secret key 123";

$ grep -rn "ivBytes = {" InsecureBankv2/sources/com/android/insecurebankv2/CryptoClass.java
23:    byte[] ivBytes = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
```

### M2 — el nombre de la base de datos

```console
$ grep -rn "DATABASE_NAME =" InsecureBankv2/sources/com/android/insecurebankv2/
InsecureBankv2/sources/com/android/insecurebankv2/TrackUserContentProvider.java:19:    static final String DATABASE_NAME = "mydb";
```

### M6 — la referencia en el código

```console
$ grep -rn "Successful Login" InsecureBankv2/sources/com/android/insecurebankv2/
InsecureBankv2/sources/com/android/insecurebankv2/DoLogin.java:115:                    Log.d("Successful Login:", ", account=" + DoLogin.this.username + ":" + DoLogin.this.password);
```

### El remate: M1 descifra M2

```console
$ ~/mobile-owasp-lab/tools/InsecureBankv2Server/venv/bin/python - <<'PY'
import base64
from Crypto.Cipher import AES
key = b"This is the super secret key 123"   # M1: CryptoClass.java:22
iv  = b"\x00" * 16                          # M1: CryptoClass.java:23
blob = "DTrW2VXjSoFdg0e61fHxJg=="           # M2: superSecurePassword
print(AES.new(key, AES.MODE_CBC, iv).decrypt(base64.b64decode(blob)).rstrip(b"\n\r").decode())
PY
Dinesh@123$
```

Y el extra: el campo que dice «cifrado» que no lo está.

```console
$ python -c "import base64; print(base64.b64decode('ZGluZXNo').decode())"
dinesh
```

---

## 4. Repetición con `clase1-demo`

```console
$ clase1-demo
############################################################
# M2 - INSECURE DATA STORAGE
############################################################

--> La base de datos se llama 'mydb' (NO 'insecurebank.db')
    Created in: TrackUserContentProvider.java:19

total 20
-rw-rw---- 1 u0_a72 u0_a72 20480 2026-09-29 05:02 mydb
-rw-rw---- 1 u0_a72 u0_a72     0 2026-09-29 05:02 mydb-journal

--> Extrayendo la base de datos...
--> Contenido (sqlite3):
id  name
--  ------
1   dinesh

--> SharedPreferences: la app guarda las credenciales 'cifradas'
  "superSecurePassword = DTrW2VXjSoFdg0e61fHxJg==
  "EncryptedUsername = ZGluZXNo

############################################################
# M6 - INSECURE LOGGING
############################################################

    Verificacion historica de lo ya registrado:
09-29 05:02:23.679  5127  5147 D Successful Login:: , account=dinesh:Dinesh@123$

Informes guardados en: /home/cwl/mobile-owasp-lab/reports/clase1
```

Código de salida: `0`.

---

## 5. Fallo encontrado durante la preparación

### Bucle de reinicios del backend

**Síntoma.** Durante la primera instalación, el servicio
`insecurebankv2-server` entró en bucle de reinicios:

```console
$ sudo journalctl -u insecurebankv2-server | grep -c "Scheduled restart job"
149
```

**Causa.** Otro proceso ocupaba el puerto 8888, el backend no podía hacer
`bind()` y fallaba con `OSError: [Errno 98] Address already in use`. La unidad
tenía `Restart=on-failure` **sin ningún tope**, así que systemd reintentaba
indefinidamente: 149 reinicios en 5 minutos, llenando el journal y sin
explicarle nada al usuario.

**Corrección aplicada.**

1. Tope de reinicios en la unidad systemd:

   ```ini
   StartLimitIntervalSec=60
   StartLimitBurst=5
   ```

2. Aviso previo en el instalador si el puerto ya está ocupado, con el proceso
   que lo ocupa.

3. Diagnóstico en `bank-start` cuando el arranque falla.

**Verificación de la corrección.** Ocupando el puerto a propósito con un
proceso ajeno y arrancando el servicio:

```console
$ bank-start
El backend NO arranca. Diagnostico:
  CAUSA: el puerto 8888 ya esta ocupado por otro proceso.
  Solucion:  sudo ss -ltnp | grep 8888
             y detenga el proceso, o use otro puerto:
             bank-start 8889   (y configure la app con ese puerto)

Ultimas lineas del log:
... OSError: No socket could be created -- (('0.0.0.0', 8888): [Errno 98] Address already in use)
(codigo de salida: 1)
```

Y contando reinicios con el tope puesto:

```console
$ sudo journalctl -u insecurebankv2-server --since "3 minutes ago" | grep -c "Scheduled restart job"
5
$ systemctl is-failed insecurebankv2-server
failed
$ sudo journalctl -u insecurebankv2-server -n 1
... Start request repeated too quickly.
```

**5 reinicios y se rinde**, con un estado limpio, en lugar de 149 infinitos.

### Segunda corrección: el puerto que cambiaba de mentira

El diagnóstico anterior ofrecía `bank-start 8889` como solución, pero el
argumento **no hacía nada**: el puerto estaba fijo en `ExecStart` y el servicio
seguía arrancando en 8888. El mensaje era correcto, la solución no.

Ahora el puerto vive en `/etc/mobile-lab/bank.env` y systemd lo lee desde ahí,
así que el argumento sí lo mueve. Verificado moviéndolo y comprobando que el
puerto antiguo queda libre:

```console
$ bank-start 8899
Backend InsecureBankv2 ACTIVO y respondiendo en el puerto 8899
Recuerde reconfigurar la app con el mismo puerto:  clase1-prep 8899

$ curl -s -X POST -d 'username=dinesh&password=Dinesh@123$' http://127.0.0.1:8899/login
{"message": "Correct Credentials", "user": "dinesh"}
```

Al escribir el fichero de entorno apareció un error propio que conviene no
repetir: **systemd no entiende la sintaxis de shell `${VAR:-defecto}`**, solo
`$VAR` y `${VAR}`. La primera versión pasó el texto literal a Python y murió con
`ValueError: invalid literal for int() with base 10: '${BANK_PORT:-8888}'`.
Por eso el `EnvironmentFile` es obligatorio: si falta, systemd lo dice claro en
vez de dejar un error de Python que no apunta a la causa.

El diagnóstico de puerto ocupado también se corrigió: proponía un puerto fijo
(8899) que podía ser justo el ocupado. Ahora busca uno libre:

```console
$ bank-start 8899        # con 8899 ocupado por un proceso ajeno
El backend NO arranca. Diagnostico:
  CAUSA: el puerto 8899 ya esta ocupado por otro proceso.
  Solucion A:  sudo ss -ltnp | grep 8899
              y detenga el proceso que lo ocupe.
  Solucion B:  arrancar en el puerto 8890, que esta libre:
              bank-start 8890   y luego  clase1-prep 8890
```

### Tercera corrección: «vivo» no es «respondiendo»

`bank-start` y `bank-status` confirmaban el arranque con `systemctl is-active`,
que solo dice que el proceso existe. Un backend vivo que devuelve 500 pasaba ese
filtro y el instructor se encontraba con un `[ OK ]` y un login que no funciona.

Ahora ambos preguntan al endpoint de verdad:

```console
$ bank-status
Estado: ACTIVO (puerto 8888)
Login:  OK (responde 'Correct Credentials')
```

---

## 6. Limitaciones de esta prueba

Lo que **no** se ha podido verificar aquí:

| Elemento | Motivo |
|---|---|
| Instalación completa del script | Se ejecutó la sección de la Clase 1, no el flujo entero |
| Burp Suite e `install4j` | Fuera del alcance de la Clase 1 |
| Clases 2 en adelante | No escritas todavía |

La **Fase 1 (MobSF)** se verificó después, cuando el demonio de Docker
arrancó. Quedó `healthy` y accesible desde la VM en `0.0.0.0:8000`. Esa
verificación destapó un segundo fallo: el healthcheck de la imagen oficial
hace `curl host.docker.internal`, que sólo resuelve en Docker Desktop, así
que en Linux el contenedor se marcaba `unhealthy` para siempre aunque
funcionara. Se corrige con `--add-host host.docker.internal:host-gateway`.
Los detalles están en [`verificacion.md`](../verificacion.md).

Todo lo de la Fase 2 y la Fase 3 **sí** está verificado de extremo a extremo,
con salidas reales, no de documentación de terceros.
