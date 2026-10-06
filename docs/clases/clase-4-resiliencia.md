# Clase 4 — Resiliencia: defensa del lado del cliente

| | |
|---|---|
| **Material** | [`clase-4-resiliencia.pptx`](clase-4-resiliencia.pptx) (18 diapositivas) · generador: [`make-clase4-ppt.py`](make-clase4-ppt.py) |
| **Duración** | 60–90 minutos (incluye repaso del Top 10) |
| **Contenido** | Repaso M1–M10 + OWASP **MASVS-RESILIENCE** (R-1 a R-4) |
| **App de referencia** | InsecureBankv2 (`com.android.insecurebankv2`) |
| **Estándar** | OWASP MASVS 2.x · MASWE · MASTG |

> **Estado del documento.** Los controles, los `MASWE` y los `MASTG-KNOW` se
> comprobaron contra la documentación oficial de OWASP MASVS/MASTG. Las
> observaciones sobre InsecureBankv2 («no comprueba la firma», «no detecta
> Frida»…) proceden de las Clases 1–3, que sí se ejecutaron de extremo a
> extremo. **Esta clase es de repaso y de defensa, no de ataque:** no introduce
> un nuevo ataque ejecutado contra la VM, sino el marco con el que se audita la
> defensa. Lo que no está verificado se dice abajo.

---

## Índice

- [Dónde encaja esta clase](#dónde-encaja-esta-clase)
- [Parte 1 — Repaso del OWASP Mobile Top 10](#parte-1--repaso-del-owasp-mobile-top-10)
- [Parte 2 — El puente: sabemos romperlo, ¿y defenderlo?](#parte-2--el-puente)
- [Parte 3 — MASVS-RESILIENCE](#parte-3--masvs-resilience)
- [Parte 4 — Técnicas en Android](#parte-4--técnicas-en-android)
- [Parte 5 — Demo: InsecureBankv2 no se defiende](#parte-5--demo)
- [Parte 6 — La parte honesta](#parte-6--la-parte-honesta)
- [Parte 7 — Cómo se evalúa (MASTG)](#parte-7--cómo-se-evalúa-mastg)
- [Cierre](#cierre)
- [Anexo A — Generar la presentación](#anexo-a--generar-la-presentación)
- [Anexo B — Lo que NO está verificado](#anexo-b--lo-que-no-está-verificado)

---

## Dónde encaja esta clase

Las Clases 1, 2 y 3 recorren los **diez riesgos del OWASP Mobile Top 10**
atacando una app real. La Clase 4 hace dos cosas:

1. **Repasa** el Top 10 completo, porque es la síntesis del curso.
2. **Cruza al lado de la defensa** con el grupo **MASVS-RESILIENCE** del estándar
   OWASP MASVS: qué protecciones pone una app *de verdad* cuando asume que su
   binario está en manos del enemigo.

No hay una app nueva. El objetivo no es «un ataque más», sino **saber leer una
app defendida** y saber decir, con criterio, qué control existe, qué control
falta y por qué ninguno de ellos es, por sí solo, seguridad.

---

## Parte 1 — Repaso del OWASP Mobile Top 10

### Los diez riesgos, con su evidencia real en el laboratorio

| | Riesgo | Dónde se vio | Evidencia capturada |
|---|---|---|---|
| **M1** | Improper Platform Usage | Clase 1 §3 | `CryptoClass.java:22` — `"This is the super secret key 123"` |
| **M2** | Insecure Data Storage | Clase 1 §2 | `superSecurePassword = DTrW2VXjSoFdg0e61fHxJg==` en SharedPreferences; usuarios en claro en SQLite |
| **M3** | Insecure Authentication | Clase 2 §1 | `/devlogin` no valida; `/changepassword` no pide la actual; sin rate limit |
| **M4** | Insufficient Cryptography | Clase 2 §2 | Clave hardcodeada, IV de ceros, AES-CBC sin MAC, firma solo-v1 |
| **M5** | Insecure Communication | Clase 2 §3 | `protocol = "http://"`; credenciales en claro; respuesta alterable |
| **M6** | Insecure Logging | Clase 1 §2 | `Log.d("Successful Login:", "account=" + user + ":" + pass)` |
| **M7** | Client Code Quality | Clase 2 §4 | `debuggable="true"`, `allowBackup="true"`, 8 permisos de más, `targetSdk 22` |
| **M8** | Code Tampering | Clase 3 §2 | Parche de smali + re-firma con `CN=Attacker`; renombrado de la app |
| **M9** | Reverse Engineering | Clase 3 §1 | JADX devuelve clave/IV/modo; Frida captura la contraseña en claro |
| **M10** | Extraneous Functionality | Clase 3 §3 | `/devlogin`, 4 actividades exportadas, receptor que exfiltra por SMS, provider sin permisos |

### La lección: no son etiquetas, son cadenas

El mensaje que hay que llevarse no es que la app esté mal en diez sitios, sino
que **unos riesgos hacen indefendibles a otros**:

- **Cadena de datos:** M1 embebe la clave → M2 guarda datos «cifrados» con ella →
  M6 deja las credenciales en el log → M3 permite que el atacante ya las tenga.
- **Cadena de ataque:** M9 (ingeniería inversa) → M8 (modificar y re-firmar) →
  M10 (usar la superficie extra) → cuentas ajenas, sin avisar.
- **Cadena cripto:** M4 (clave + IV + CBC sin MAC) rompe lo guardado (M2) y lo
  transmitido (M5); la firma solo-v1 abre la puerta a M8 (Janus).

---

## Parte 2 — El puente

Todo lo anterior vive en el **lado del cliente**: la APK que el usuario tiene en
la mano. Si el atacante controla el dispositivo —y en móvil, siempre lo hace—
puede leerla, modificarla y volver a empaquetarla.

La pregunta de esta clase **no** es «cómo evitar que la rompan», porque no se
puede. Es **cómo subir el coste, detectar la manipulación y no depender del
cliente para la seguridad real.**

> «Resilience controls are never absolute. Any client-side protection can be
> bypassed, so these must be treated as additional protection against
> threat-specific attacks.»
> — OWASP MASVS-RESILIENCE

---

## Parte 3 — MASVS-RESILIENCE

El estándar OWASP MASVS agrupa la defensa del cliente en **cuatro controles**:

| Control | Qué exige | En una palabra |
|---|---|---|
| **MASVS-RESILIENCE-1** | Integridad de la plataforma: detectar root/jailbreak, emuladores y entornos virtuales; atestiguar el dispositivo | ¿dónde corre? |
| **MASVS-RESILIENCE-2** | Anti-tampering: integridad de la firma, del código (DEX/nativo) y de los recursos; detección de repackaging | ¿es mi app? |
| **MASVS-RESILIENCE-3** | Anti-ingeniería inversa: ofuscar código y recursos para encarecer el análisis estático | ¿se entiende? |
| **MASVS-RESILIENCE-4** | Anti-análisis dinámico: anti-debug y detección de herramientas de instrumentación | ¿la observan? |

Cada control tiene sus debilidades asociadas en **MASWE** (Mobile Application
Security Weaknesses Enumeration), que es lo que un auditor busca:

| Control | MASWE asociados |
|---|---|
| R-1 | MASWE-0051 (root no detectado), -0052 (virtualización), -0053 (emulador), -0054 (attestation) |
| R-2 | MASWE-0055 (malware), -0056 (app attestation), -0057 (integridad de recursos), -0058 (integridad de código en runtime) |
| R-3 | MASWE-0059 (sin ofuscación de código), -0060 (sin ofuscación de recursos), -0061 (artefactos de debug), -0062 (sin cifrado de payload), -0063 (mecanismos de debug activos) |
| R-4 | MASWE-0064 (sin detección de depurador), -0065 (sin detección de herramientas de análisis dinámico) |

> ⚠️ **La ausencia de estos controles no es, por sí sola, una vulnerabilidad.**
> Lo dice el propio MASVS: son defensa en profundidad. Una app sin root
> detection no es insegura por ese hecho; una app que confía el acceso a datos a
> que el cliente no esté rooteado, sí.

---

## Parte 4 — Técnicas en Android

### R-1 · Integridad de la plataforma

- **Detección de root/jailbreak:** binarios `su`, Magisk, `Build.TAGS` con
  `test-keys`, `/system` montado como escribible, apps conocidas de root.
- **Detección de emulador:** huella del build (`ro.product.model`,
  `ro.hardware`), rareza o ausencia de sensores, propiedades de QEMU.
- **Detección de virtualización:** entornos tipo VirtualApp/contenedor que
  ejecutan la app fuera de su sandbox.
- **Device attestation:** **Play Integrity API** o **Key Attestation**
  (Android KeyStore), que produce un veredicto firmado con claves de hardware.
  **La verificación se hace en el servidor**, nunca en el cliente.

Referencias MASTG: `MASTG-KNOW-0027` (root), `-0031` (emulador), `-0052`
(virtual), `-0054` (attestation), `-0035` (Play Integrity).

### R-2 · Anti-tampering

- **Integridad de la firma:** leer el certificado en runtime y comparar su hash
  con el esperado.
- **Integridad del código:** verificar `classes.dex` y las librerías nativas
  antes de confiar en ellos.
- **Integridad de recursos:** que nadie sustituya `strings.xml`, imágenes o
  configuración.
- **Detección de repackaging:** la app re-firmada por un atacante (Clase 3) deja
  de validar.

> **Error clásico:** comprobar la firma *en Java* es un control que Frida
> parchea en 30 segundos. El contraste que vale es en **nativo** y, sobre todo,
> contra **el servidor**.

### R-3 · Anti-ingeniería inversa

- **Ofuscación de código** (R8 / ProGuard): renombra clases y métodos y elimina
  lo no usado.
- **Ofuscación de cadenas:** la clave de InsecureBankv2 viaja en texto claro;
  ofuscarla esconde el literal, no la lógica.
- **Flujo de control y aritmética:** encarece el análisis (DexGuard, Virbox,
  Promon…).
- **Parte de la lógica en nativo** (NDK + JNI): una capa más sobre Java/smali.
- **Límite honesto:** la ofuscación **retrasa**, no impide.

### R-4 · Anti-análisis dinámico

- **Anti-debug:** `Debug.isDebuggerConnected()`, `ptrace(PTRACE_TRACEME)`,
  `TracerPid` en `/proc/self/status`.
- **Detección de Frida:** puerto por defecto `27042`, hilos `gum-js-loop` /
  `gmain`, regiones `frida-agent` en `/proc/self/maps`.
- **Detección de hooking:** integridad de métodos, del runtime ART, o del
  retorno de llamadas nativas.

### Attestation, la técnica clave

El cliente puede mentir sobre su propio estado; un tercero con claves en
hardware, no. **Play Integrity API** y **Key Attestation** producen un veredicto
firmado que **el servidor** verifica. La regla:

> Si es el cliente el que decide si el cliente es de fiar, ya has perdido.

Referencias: MASVS-RESILIENCE-1 · `MASTG-KNOW-0035` (Play Integrity) ·
`-0119`/`-0120` (Key/Device Attestation).

---

## Parte 5 — Demo

InsecureBankv2 **no implementa ninguno de los cuatro controles**, y eso se ve
reutilizando lo que ya está demostrado en las Clases 1–3:

| Qué probamos | Qué se observa | Control ausente |
|---|---|---|
| Re-firmar la app (Clase 3 §2.4) | Arranca igual, firmada por `CN=Attacker` | R-2 |
| Detección de root (Clase 3 §3.6) | `Rooted Device!!` es **solo un texto**; no bloquea nada | R-1 |
| Hook con Frida (Clase 3 §1.3) | Captura la contraseña; la app ni reacciona | R-4 |
| `mapas`/puertos de Frida | Nadie los mira | R-4 |

**El contraste es el mensaje:** estos cuatro puntos, en una app bancaria real,
son exactamente donde R-1/R-2/R-4 tendrían que saltar.

---

## Parte 6 — La parte honesta

- Todo control del lado del cliente **se puede saltar**: quien controla el
  dispositivo controla también tus comprobaciones.
- MASVS lo deja escrito: la **ausencia** de controles de resiliencia **no es una
  vulnerabilidad** por sí sola. Son defensa en profundidad.
- **No sustituyen** al diseño: validación en el servidor, criptografía correcta
  y superficie mínima. Esos sí son requisitos.
- **Coste real:** rendimiento, falsos positivos (usuarios con root legítimo) y
  fricción para quien audita la app en tu nombre.
- **Úsalos para** deter *client-side abuse* (fraude, trampas, clonado), no como
  la puerta que protege el dinero.

---

## Parte 7 — Cómo se evalúa (MASTG)

| Área | Knowledge (MASTG-KNOW) | Qué se prueba |
|---|---|---|
| Root | 0027 Root Detection | ¿Se detecta el root y se actúa? |
| Anti-debug | 0028 Anti-Debugging | ¿Se detecta el depurador? |
| Integridad | 0029 File Integrity · 0032 Runtime Integrity | ¿Se verifica código y recursos? |
| Herramientas | 0030 RE Tool Detection | ¿Se detecta Frida / instrumentación? |
| Emulador | 0031 Emulator Detection | ¿Se detecta la máquina virtual? |
| Ofuscación | 0033 Obfuscation | ¿Cuánto cuesta leer el binario? |
| Attestation | 0035 Play Integrity API | ¿Se verifica en el servidor? |

> **Nota de método:** en MASVS 2.x los controles de resiliencia **no se marcan
> como fallo (`FAIL`)**, sino que se **documentan o se eximen (waive)** según el
> modelo de amenaza. Es coherente con el punto de la Parte 6: son defensa en
> profundidad, no un requisito binario. El mismo marco (MASTG) con el que se
> evaluaron las Clases 1–3, ahora del lado de la defensa.

---

## Cierre

- **Clases 1–3:** sabemos romper una app móvil.
- **Clase 4:** sabemos **leer cómo una app intenta defenderse** y decirlo con
  criterio.
- **La regla que no cambia:** nada que decida el cliente es de fiar.

Para conectar con el panorama actual, ver
[`cve-2026-mobile.md`](cve-2026-mobile.md), que mapea cada hallazgo a
vulnerabilidades reales publicadas en 2026.

---

## Anexo A — Generar la presentación

La `.pptx` se genera con `python-pptx` desde un script versionado:

```bash
python3 -m venv /tmp/pptx-venv
/tmp/pptx-venv/bin/pip install python-pptx
/tmp/pptx-venv/bin/python docs/clases/make-clase4-ppt.py
# 18 diapositivas -> docs/clases/clase-4-resiliencia.pptx
```

El script es la fuente de verdad: si hay que editar una diapositiva, se edita el
script y se regenera. Así la presentación y el guion no se separan.

---

## Anexo B — Lo que NO está verificado

Honestidad, como en el resto del curso:

1. **No se ha construido ni probado una app *endurecida*.** Esta clase describe
   los controles y los señala como ausentes en InsecureBankv2; no implementa
   root detection, anti-Frida ni attestation en ninguna app. Las técnicas de la
   Parte 4 son el marco estándar (MASVS/MASTG), no código ejecutado aquí.
2. **Play Integrity API y Key Attestation no se han probado.** Requieren una app
   firmada subida a Play (o respaldada por hardware con atestación real); fuera
   del alcance del laboratorio headless.
3. **Los `MASWE`/`MASTG-KNOW` se citan por su identificador oficial** verificado
   contra `mas.owasp.org`; no se ha ejecutado su procedimiento de test completo.
4. **La demo reutiliza observaciones de las Clases 1–3**, que sí están
   verificadas. No añade una ejecución nueva contra la VM.
