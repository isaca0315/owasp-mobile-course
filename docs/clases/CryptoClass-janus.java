package com.android.insecurebankv2;

/** DEX prependido por Janus. Si esta copia se carga, su clave sustituye a la
 *  original que estaba en CryptoClass.java:22 (OWASP M4). */
public class CryptoClass {
    public CryptoClass() {}

    public String aesEncryptedString(String theString) {
        return "JANUS-CLAVE-DEL-ATACANTE";
    }

    public String aesDeccryptedString(String theString) {
        return "JANUS-DESCIFRADO";
    }
}
