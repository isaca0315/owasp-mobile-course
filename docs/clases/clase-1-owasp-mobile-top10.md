CLASE 1 — OWASP MOBILE TOP 10 · M1, M2 y M6
=============================================================================
App objetivo : InsecureBankv2  (paquete com.android.insecurebankv2)
Proyecto     : Dinesh Shetty — referenciado por OWASP MASTG como MASTG-APP-0010
Dispositivo  : VM Android-x86 (API 27) por ADB
Duración     : 90 min

------------------------------------------------------------------------------
AVISO IMPORTANTE ANTES DE IMPARTIR LA CLASE
------------------------------------------------------------------------------
El guion original de esta clase contenía cuatro fallos que rompían la
demostración en directo. Todos están corregidos y verificados contra la VM:

  1. BASE DE DATOS ERRÓNEA
     El guion dice  adb pull .../databases/insecurebank.db
     La base de datos real se llama  mydb  y su tabla es  names
     (TrackUserContentProvider.java:19). El comando del guion falla.

  2. CLAVE HARDCODEADA ERRÓNEA
     El guion dice  public static final String SECRET_KEY = "..."
     La clave real es un campo de instancia, no una constante estática:
         String key = "This is the super secret key 123";   (CryptoClass.java:22)
     y además el vector de inicialización es un array de 16 ceros (:23).

  3. EL LOG DE M6 ES MUCHO PEOR DE LO QUE DICE EL GUION
     El guion dice que la app imprime "un token de sesión".
     Lo que hace es imprimir el usuario Y LA CONTRASEÑA en claro:
         Log.d("Successful Login:", ", account=" + usuario + ":" + contraseña)
                                                              (DoLogin.java:115)
     Salida real verificada:
         D Successful Login:: , account=dinesh:Dinesh@123$

  4. FALTA EL BACKEND DE LA APLICACIÓN
     InsecureBankv2 NO tiene servidor embebido. La IP y el puerto se leen de
     SharedPreferences y el login falla si nada escucha. El log de M6 sólo se
     emite cuando el servidor responde "Correct Credentials".
     El backend original (AndroLabServer) es Python 2 y no arranca en
     Ubuntu 22.04; el script de instalación lo porta a Python 3.

  Además, en imágenes de Android 8.x la verificación de apps por USB está
  activa y  adb install  falla con INSTALL_FAILED_VERIFICATION_FAILURE.
  El script lo desactiva automáticamente (clase1-prep, paso 2).

------------------------------------------------------------------------------
PREPARACIÓN (20 min antes de empezar)
------------------------------------------------------------------------------
  bank-start          # arranca el backend en el puerto 8888
  clase1-prep         # instala la app, la configura y abre el login
                      # (tarda ~30 s; deja el móvil listo)

  Opcional, para ver el resultado sin tocar la app a mano:
  clase1-demo         # repite la demo de M2 y M6 y guarda los informes

  Comprueba que todo responde antes de empezar:
      curl -s -X POST -d 'username=dinesh&password=Dinesh@123$' \
           http://127.0.0.1:8888/login
      # debe devolver: {"message": "Correct Credentials", "user": "dinesh"}

  Si bank-start dice que el puerto 8888 está ocupado:
      sudo ss -ltnp | grep 8888          # ver quién lo tiene
      sudo systemctl stop insecurebankv2-server
      bank-start                        # y reintentar
  Sin backend no hay login, y sin login no hay log de M6: la mitad de la
  clase depende de este paso.

  Credenciales:  dinesh / Dinesh@123$        jack / Jack@123$
                 devadmin / devadmin           (entra por /devlogin)


=============================================================================
1. INTRODUCCIÓN (10 min)
=============================================================================

"Bienvenidos. Hoy no vamos solo a hackear una app: vamos a aprender a pensar
como un auditor. Usaremos el OWASP Mobile Top 10 como brújula, porque un
hallazgo sin categoría es una anecdote y un hallazgo con categoría es un
riesgo que se puede gestionar. Vamos a demostrar tres riesgos: M1, M2 y M6."

"Nuestra víctima es InsecureBankv2. No es una app real: es un proyecto público
de Divesh Shetty, referenciado por OWASP MASTG. Existe precisamente para
aprender, y su código es deliberadamente malo."

"Para validar los riesgos usaremos tres herramientas, y quiero que
entiendan desde el principio que no son tres cajas sueltas: cada una responde
a una pregunta distinta del mismo hallazgo."

  MobSF  -> automatiza el descubrimiento y ya nos categoriza los riesgos
  ADB    -> valida en el dispositivo, donde el riesgo de verdad ocurre
  JADX   -> va a la raíz: el código, donde el error se escribió


=============================================================================
2. FASE 1 — MAPEO DE RIESGOS CON MobSF (20 min)
=============================================================================

  -- Arrancar MobSF -------------------------------------------------------
  El guion original decía "./run.sh". Eso NO existe en este laboratorio:
  MobSF corre en Docker, systemd y en el puerto 8000. En un servidor headless
  no hay escritorio al que abrir un navegador, así que:

      mobsf-start                       # o: sudo systemctl start mobsf-server
      mobsf-logs                        # ver el log de arranque
      echo "http://$(hostname -I | awk '{print $1}'):8000"

  Desde el navegador de cualquier alumno:
      http://<IP-del-servidor>:8000
      usuario: mobsf   contraseña: mobsf

  MobSF tarda 1-2 minutos en levantar. Mientras tanto, descarga la app:

      ls -lh ~/mobile-pentesting-lab/apps/apk/InsecureBankv2.apk
      echo "Sube este fichero en 'Upload APK'"

  -- Análisis del reporte ------------------------------------------------
  "MobSF no sólo encuentra bugs: nos da una puntuación y una categorización.
  Eso es exactamente lo que un cliente pide: no 'hay un problema', sino
  'este riesgo, con esta severidad, en este componente'."

  En el reporte, sección Security Analysis, mapa al OWASP:

  M1 — Improper Platform Usage
       MobSF lo reporta como "Hardcoded Secrets" / uso de AES con clave
       estática. La plataforma Android ofrece el Android Keystore para
       guardar material criptográfico. Hardcodear una clave en el .dex es
       usar mal la plataforma: cualquiera que descargue la APK la tiene.

  M2 — Insecure Data Storage
       Lo reporta como "Insecure Data Storage": SharedPreferences y bases de
       datos SQLite sin cifrar en el sandbox de la app.

  M6 — Insecure Logging
       En el análisis de código aparecen llamadas a Log.d() con datos
       sensibles.

  "Conclusión de la fase 1: MobSF nos ha dado el mapa. Ahora vamos a
  validar y explotar cada punto a mano, porque un reporte sin prueba no es
  un hallazgo: es una sospecha."


=============================================================================
3. FASE 2 — VALIDACIÓN EN EL DISPOSITIVO (30 min)
=============================================================================

  -- Conexión -------------------------------------------------------------
      vmconnect                        # conecta + root + resumen del dispositivo
      adb devices                      # debe.listar la VM como 'device'

  "Usamos ADB porque M2 sólo se demuestra en su entorno natural: el
  dispositivo. Y tenemos root, que es lo que representa a un atacante con
  acceso físico o con un exploit previo."

  -- M2: almacenamiento inseguro -----------------------------------------
      adb shell
      ls /data/data/com.android.insecurebankv2/databases/
      exit

  Salida real:
      mydb
      mydb-journal

  "Antes de continuar, un aviso: el nombre del fichero no es el que esperáis.
  No es 'insecurebank.db'. Es 'mydb', y se crea en
  TrackUserContentProvider.java:19. El OWASP no os da el nombre del fichero;
  os da la categoría. Vosotros tenéis que encontrarlo."

  Extracción y examination:

      mkdir -p ~/mobile-pentesting-lab/reports/clase1 && cd $_
      adb pull /data/data/com.android.insecurebankv2/databases/mydb .
      sqlite3 -header -column mydb "select * from names;"

  Salida real (tras haber iniciado sesión):
      id  name
      --  ------
      1   dinesh

  "Aquí está la prueba. La app guarda en una base de datos SQLite, en el
  sandbox, sin cifrar, los usuarios que han iniciado sesión. Sin root esto
  está protegido por el aislamiento de Linux entre apps; con root, o en un
  dispositivo comprometido, no. Eso es M2: el dato existe en claro en disco."

  Y el segundo hallazgo, más grave:

      adb shell "cat /data/data/com.android.insecurebankv2/shared_prefs/*.xml"

  Salida real:
      "serverip = 172.25.208.104
      "serverport = 8888
      "superSecurePassword = DTrW2VXjSoFdg0e61fHxJg==
      "EncryptedUsername = ZGluZXNo

  "Mirad el nombre: superSecurePassword. Suena a que está protegido. No lo
  está. Está cifrado con una clave que está dentro del propio APK, y ya la
  vamos a ver en la fase 3. Esta es la cadena entre M1 y M2: el criptograma
  sólo vale lo que vale la clave."

  -- M6: registro inseguro de eventos ------------------------------------
      adb logcat -c
      adb logcat -s Successful Login: &        # en una terminal aparte

  ... el alumno inicia sesión en la app ...

  Salida real:
      D Successful Login:: , account=dinesh:Dinesh@123$

  "Aquí está. El usuario y la contraseña, en claro, en un log del sistema.
  El guion original de esta clase decía que la app imprimía 'un token
  de sesión'. Es peor: es la contraseña completa. El impacto de M6 aquí no es
  teórico, es un robo de credenciales trivial."

  "Además, un log es un dato persistente: sobrevive al cierre de la app, se
  acumula en el búfer del sistema, y cualquier persona con un shell lo ve. En
  un móvil corporativo, con un empleado que pierde el dispositivo o lo
  comparte, eso es un robo de credenciales trivial."


=============================================================================
4. FASE 3 — ANÁLISIS DE CÓDIGO PARA CONFIRMAR M1 (25 min)
=============================================================================

  -- Descompilar ----------------------------------------------------------
  El guion original decía "abrir con JADX-GUI". Este servidor es headless:
  no hay interfaz gráfica. El equivalente real es la CLI, y además es
  mejor para enseñar, porque vemos el fichero exacto y la línea exacta.

      cd ~/mobile-pentesting-lab/reports/jadx
      jadx ~/mobile-pentesting-lab/apps/apk/InsecureBankv2.apk -d InsecureBankv2

  Luego se explora con cualquier editor. Si hay escritorio, también existe
  jadx-gui, pero no es necesario.

  -- La clave hardcodeada -------------------------------------------------
      grep -rn "secret key" InsecureBankv2/sources/com/android/insecurebankv2/

  Salida real:
      CryptoClass.java:22:    String key = "This is the super secret key 123";

  "El guion decía que aquí encontrabais 'public static final String
  SECRET_KEY'. No es así: es un campo de instancia, sin static ni final. Pero
  lo que importa no es la forma que tenga: es que la clave está en el código
  que viaja dentro de la APK. Cualquiera puede descomprimirla y leerla."

  Y tres líneas más abajo, en la misma clase:

      CryptoClass.java:23:    byte[] ivBytes = {0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};

  "Y el vector de inicialización son dieciséis ceros. Cero es lo opuesto a
  aleatorio. En criptografía, un IV constante no es un detalle: anula la
  confidencialidad del modo CBC."

  -- Cerrar el círculo: descifrar lo "cifrado" ----------------------------
  Con la clave de M1 desciframos el M2. Es el remate de la clase.

      # Usa el Python del venv del backend: es el único que tiene pycryptodome.
      # (Si prefiere el del sistema:  pip3 install pycryptodome)
      PY_BIN=~/mobile-pentesting-lab/tools/InsecureBankv2Server/venv/bin/python
      "$PY_BIN" - <<'PY'
      import base64
      from Crypto.Cipher import AES
      key = b"This is the super secret key 123"   # M1: CryptoClass.java:22
      iv  = b"\x00" * 16                          # M1: CryptoClass.java:23
      blob = "DTrW2VXjSoFdg0e61fHxJg=="           # M2: superSecurePassword
      print(AES.new(key, AES.MODE_CBC, iv).decrypt(base64.b64decode(blob)).rstrip(b"\n\r").decode())
      PY

  Salida real:
      Dinesh@123$

  "La contraseña que la app guardaba 'protegida', descifrada con una línea
  copiada del código fuente. Eso es M1 y M2 trabajando juntos: M1 permite
  romper M2. Por eso el OWASP los trata como riesgos distintos pero
  relacionados."

  Y un detalle extra, si queréisbonus:

      python3 -c "import base64; print(base64.b64decode('ZGluZXNo').decode())"
      dinesh

  "El campo que se llama 'EncryptedUsername' no estaba cifrado. Estaba en
  Base64. Base64 es una codificación, no un cifrado. Es un clásico: ponerle
  un nombre que diga 'cifrado' a algo que no lo está."


=============================================================================
5. RESUMEN Y CIERRE (5 min)
=============================================================================

"Hemos recorrido el ciclo completo del auditor:

  MobSF descubre -> JADX localiza -> ADB extrae -> la clave descifra.

  Y sobre todo, hemos visto que los riesgos del OWASP Mobile Top 10 no son
  etiquetas: son encadenamientos. M1 no es 'una clave mal puesta', es lo que
  hace indefendible el M2. M6 no es 'un log feo', es el robo de credenciales
  que hace posible el M3 en la próxima clase.

  La lección que os lleváis no es 'esta app está mal'. Es que hay que mirar
  cada capa y preguntarse qué pasa si el atacante ya tiene acceso a la de
  abajo."

"Próxima clase: M3 (autenticación insegura) y M5 (comunicación insegura).
Con esta misma base de datos, esta misma sesión y esta misma clave, vamos a
atacar el canal."


=============================================================================
ANEXO — Referencia rápida de hallazgos verificados
=============================================================================

  Riesgo  Fichero:línea            Evidencia
  ------  ----------------------   --------------------------------------------
  M1      CryptoClass.java:22      String key = "This is the super secret key 123";
  M1      CryptoClass.java:23      IV de 16 ceros
  M2      TrackUserContentProvider.java:19   DATABASE_NAME = "mydb"
  M2      (sin fichero)            tabla 'names': usuarios que hicieron login
  M2      SharedPreferences         superSecurePassword = DTrW2VXjSoFdg0e61fHxJg==
  M2      SharedPreferences         EncryptedUsername = ZGluZXNo  (sólo Base64)
  M6      DoLogin.java:115         Log.d(..., "account=" + user + ":" + pass)

  Descifrado: superSecurePassword -> Dinesh@123$   (usando la clave de M1)

=============================================================================
ANEXO — Comandos del laboratorio
=============================================================================

  bank-start      arranca el backend de InsecureBankv2 (puerto 8888)
  bank-stop       lo para
  bank-status     estado + últimas líneas del log
  clase1-prep     instala y configura el móvil para la clase
  clase1-demo     repite la demo de M2 y M6 y guarda informes
  vmconnect       conecta con la VM, activa root y muestra el resumen
  vmconnect frida URL y comandos exactos de frida-server para esta VM
  mobsf-start     arranca MobSF (Docker, puerto 8000)
  mobsf-logs      log de MobSF
  mobsf-stop      para MobSF

  Desinstalar todo:
      sudo systemctl disable --now insecurebankv2-server mobsf-server
      sudo rm -f /usr/local/bin/{bank-*,clase1-*,vmconnect,mobsf-*}
      adb -s 172.25.208.100:5555 uninstall com.android.insecurebankv2
