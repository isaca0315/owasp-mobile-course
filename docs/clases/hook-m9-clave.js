// Hook de instrumentación para OWASP Mobile Top 10 — M9 (Reverse Engineering)
//
// Qué demuestra: la clave AES que CryptoClass usa NO está protegida en ningún
// sentido durante la ejecución. Cuando la app cifra o descifra, la clave está
// en memoria como un String de Java y el texto en claro pasa por los argumentos.
// Este hook las imprime.
//
// Los nombres de método NO son inventados: se han leído del código descompilado
// con JADX (docs/clases/clase-3-evidencia.md, sección 2.1):
//
//   CryptoClass.aesEncryptedString(String) -> String   (CryptoClass.java:48)
//   CryptoClass.aesDeccryptedString(String) -> String  (CryptoClass.java:41)
//
// Ojo al nombre: la app escribe "Deccrypted" con doble ce. Es una errata del
// autor de la app y hay que respetarla; un hook sobre "aesDecryptedString" no se
// dispara nunca y no da ningún error, lo que hace muy fácil concluir que el
// hook "no funciona" cuando en realidad nunca enganchó.
//
// Uso:
//   frida -U -f com.android.insecurebankv2 -l hook-m9-clave.js --no-pause
// (en Frida >= 16 el flag --no-pause ya no existe; basta con omitirlo)
//
// Requiere frida-server corriendo en el dispositivo:
//   adb shell /data/local/tmp/frida-server &

'use strict';

var TARGET = 'com.android.insecurebankv2.CryptoClass';

function marca(metodo, texto) {
  console.log('  [M9] ' + metodo + '  <-  "' + texto + '"');
}

Java.perform(function () {
  console.log('=========================================================');
  console.log(' M9 — Interceptando el cifrado de ' + TARGET);
  console.log('=========================================================');

  // La clave es un atributo de instancia, no un método. Se lee al vuelo.
  var CryptoClass = Java.use(TARGET);

  // --- Cifrado: la app esta guardando una credencial -------------------
  CryptoClass.aesEncryptedString.overload('java.lang.String').implementation =
    function (theString) {
      marca('aesEncryptedString  (cifrando)', theString.toString());

      // Lectura del campo 'key' (String) y del IV (byte[]).
      try {
        console.log('        clave en memoria : ' +
          JSON.stringify(this.key.value));
        console.log('        IV en memoria    : ' +
          this.ivBytes.value.toString());
      } catch (e) {
        console.log('        (no se pudo leer el campo: ' + e + ')');
      }

      // Se llama al metodo original con this.$new: llamar a
      // this.aesEncryptedString(...) desde dentro de su propia
      // implementacion provocaria recursion infinita.
      return this.aesEncryptedString(theString);
    };

  // --- Descifrado: la app esta leyendo una credencial -------------------
  CryptoClass.aesDeccryptedString.overload('java.lang.String').implementation =
    function (theString) {
      marca('aesDeccryptedString (descifrando)', theString.toString());

      try {
        console.log('        clave en memoria : ' +
          JSON.stringify(this.key.value));
      } catch (e) {
        console.log('        (no se pudo leer el campo: ' + e + ')');
      }

      return this.aesDeccryptedString(theString);
    };

  console.log('');
  console.log(' Hooks activos. Haz login (o dispara el receptor de SMS) y mira');
  console.log(' lo que aparece arriba.');
  console.log('=========================================================');
});