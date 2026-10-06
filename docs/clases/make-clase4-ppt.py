#!/usr/bin/env python3
"""Genera la presentación de la Clase 4 (resiliencia) + repaso del OWASP Mobile
Top 10, en formato .pptx de 16:9."""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---------- paleta ----------
NAVY   = RGBColor(0x0F, 0x1B, 0x2D)
NAVY2  = RGBColor(0x18, 0x2A, 0x45)
BLUE   = RGBColor(0x2D, 0x8C, 0xF0)
TEAL   = RGBColor(0x14, 0xB8, 0xA6)
ORANGE = RGBColor(0xF5, 0x9E, 0x0B)
RED    = RGBColor(0xE5, 0x48, 0x4D)
PURPLE = RGBColor(0x8B, 0x5C, 0xF6)
LIGHT  = RGBColor(0xF5, 0xF7, 0xFA)
GREY   = RGBColor(0x5B, 0x6B, 0x7B)
GREY2  = RGBColor(0x94, 0xA3, 0xB8)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
CODEBG = RGBColor(0x11, 0x18, 0x27)
CODEFG = RGBColor(0xD6, 0xE2, 0xF0)

FONT = "DejaVu Sans"
MONO = "DejaVu Sans Mono"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]

_n = 0


def _rect(slide, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE):
    sp = slide.shapes.add_shape(shape, x, y, w, h)
    sp.fill.solid()
    sp.fill.fore_color.rgb = color
    sp.line.fill.background()
    sp.shadow.inherit = False
    return sp


def _text(slide, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
          space_after=6, line_spacing=1.0):
    """runs: lista de (texto, size, color, bold, italic) o lista de bloques
    [(parrafo_runs, level)]."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    first = True
    for item in runs:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        p.space_after = Pt(space_after)
        p.line_spacing = line_spacing
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], int):
            # (bloque_de_runs, level)
            bloque, lvl = item
            p.level = lvl
            partes = bloque
        else:
            partes = [item]
        for r in partes:
            txt, size, color, bold, italic = (list(r) + [False, False])[:5]
            run = p.add_run()
            run.text = txt
            run.font.size = Pt(size)
            run.font.color.rgb = color
            run.font.bold = bold
            run.font.italic = italic
            run.font.name = FONT
    return tb


def header(slide, kicker, title, accent=BLUE):
    global _n
    _n += 1
    _rect(slide, 0, 0, SW, Inches(1.15), NAVY)
    _rect(slide, 0, Inches(1.15), SW, Emu(38000), accent)
    _text(slide, Inches(0.55), Inches(0.12), Inches(11.5), Inches(0.35),
          [(kicker.upper(), 12, accent, True, False)])
    _text(slide, Inches(0.55), Inches(0.42), Inches(12.2), Inches(0.65),
          [(title, 29, WHITE, True, False)])
    _text(slide, Inches(12.35), Inches(0.5), Inches(0.6), Inches(0.4),
          [(f"{_n:02d}", 14, GREY2, True, False)], align=PP_ALIGN.RIGHT)


def content_slide(kicker, title, accent=BLUE):
    s = prs.slides.add_slide(BLANK)
    _rect(s, 0, 0, SW, SH, LIGHT)
    header(s, kicker, title, accent)
    return s


def bullets(slide, x, y, w, h, items, size=17, gap=8, ls=1.02):
    """items: lista de (texto, level) o (texto, level, color)."""
    runs = []
    for it in items:
        txt, lvl = it[0], it[1]
        col = it[2] if len(it) > 2 else NAVY
        pref = "• " if lvl == 0 else "–  "
        mark = "" if lvl == 0 else ""
        runs.append(([(("•   " if lvl == 0 else "–   ") + txt, size, col, False, False)], lvl))
    _text(slide, x, y, w, h, runs, space_after=gap, line_spacing=ls)


def code_box(slide, x, y, w, h, lines, size=13, title=None):
    _rect(slide, x, y, w, h, CODEBG, MSO_SHAPE.ROUNDED_RECTANGLE)
    yy = y + Inches(0.14)
    if title:
        _text(slide, x + Inches(0.22), yy, w - Inches(0.4), Inches(0.3),
              [(title, 11.5, TEAL, True, False)])
        yy += Inches(0.34)
    tb = slide.shapes.add_textbox(x + Inches(0.22), yy, w - Inches(0.44),
                                  h - (yy - y) - Inches(0.1))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(1)
        p.line_spacing = 0.98
        r = p.add_run()
        r.text = ln
        r.font.size = Pt(size)
        r.font.name = MONO
        r.font.color.rgb = CODEFG
    return tb


def table(slide, x, y, w, h, data, col_w=None, size=12.5, header_color=NAVY,
          first_bold=True):
    rows, cols = len(data), len(data[0])
    gt = slide.shapes.add_table(rows, cols, x, y, w, h).table
    if col_w:
        total = sum(col_w)
        for i, cw in enumerate(col_w):
            gt.columns[i].width = Emu(int(w * cw / total))
    for ri, row in enumerate(data):
        for ci, val in enumerate(row):
            cell = gt.cell(ri, ci)
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.space_after = Pt(0)
            r = p.add_run()
            r.text = str(val)
            r.font.name = FONT
            if ri == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = header_color
                r.font.color.rgb = WHITE
                r.font.bold = True
                r.font.size = Pt(size)
            else:
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE if ri % 2 else RGBColor(0xEC, 0xF1, 0xF7)
                r.font.color.rgb = NAVY
                r.font.size = Pt(size)
                r.font.bold = (ci == 0 and first_bold)
    return gt


def badge(slide, x, y, w, h, text, color, tcolor=WHITE, size=15):
    _rect(slide, x, y, w, h, color, MSO_SHAPE.ROUNDED_RECTANGLE)
    _text(slide, x, y, w, h, [(text, size, tcolor, True, False)],
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


# ============================================================ 1. PORTADA
s = prs.slides.add_slide(BLANK)
_n += 1
_rect(s, 0, 0, SW, SH, NAVY)
_rect(s, 0, 0, Inches(0.28), SH, BLUE)
_rect(s, Inches(0.28), 0, Inches(0.10), SH, TEAL)
_text(s, Inches(1.0), Inches(1.15), Inches(11), Inches(0.5),
      [("OWASP MOBILE TOP 10 — CURSO DE ANÁLISIS DE SEGURIDAD MÓVIL", 15, TEAL, True, False)])
_text(s, Inches(1.0), Inches(1.75), Inches(11.5), Inches(1.9),
      [("Clase 4", 66, WHITE, True, False),
       ("Resiliencia y Anti-Tampering", 36, BLUE, True, False)])
_text(s, Inches(1.0), Inches(4.05), Inches(11), Inches(1.0),
      [("Repaso de M1–M10  ·  Defensa del lado del cliente  ·  MASVS-RESILIENCE",
        19, GREY2, False, False)])
_rect(s, Inches(1.0), Inches(4.95), Inches(3.2), Emu(30000), GREY)
_text(s, Inches(1.0), Inches(5.2), Inches(11), Inches(1.2),
      [("Laboratorio: InsecureBankv2 (MASTG-APP-0010)  ·  VM Android 8.1 API 27 con root",
        15, WHITE, False, False),
       ("JADX · apktool · apksigner · Frida · MobSF · Burp Suite", 14, GREY2, False, False)])

# ============================================================ 2. AGENDA
s = content_slide("Agenda", "Qué vamos a ver hoy")
_data = [
    [("01", 26, BLUE, True, False), ],  # placeholder
]
_text(s, Inches(0.9), Inches(1.7), Inches(11.6), Inches(5.2), [
    ([("1.  ", 20, BLUE, True, False), ("Repaso del OWASP Mobile Top 10", 20, NAVY, True, False),
      ("  — los 10 riesgos y su evidencia real en el laboratorio", 15, GREY, False, False)], 0),
    ([("2.  ", 20, TEAL, True, False), ("No son etiquetas: son cadenas", 20, NAVY, True, False),
      ("  — cómo M9 hace posible M8, y M1 hace indefendible M2", 15, GREY, False, False)], 0),
    ([("3.  ", 20, ORANGE, True, False), ("El puente", 20, NAVY, True, False),
      ("  — sabemos romperlo. ¿Cómo se defiende?", 15, GREY, False, False)], 0),
    ([("4.  ", 20, PURPLE, True, False), ("MASVS-RESILIENCE-1 a 4", 20, NAVY, True, False),
      ("  — integridad, anti-tampering, anti-RE, anti-análisis dinámico", 15, GREY, False, False)], 0),
    ([("5.  ", 20, RED, True, False), ("Técnicas en Android", 20, NAVY, True, False),
      ("  — root, emulador, Frida, firma, obfuscación, attestation", 15, GREY, False, False)], 0),
    ([("6.  ", 20, BLUE, True, False), ("Demo en vivo", 20, NAVY, True, False),
      ("  — InsecureBankv2 no tiene NADA de esto (y se ve)", 15, GREY, False, False)], 0),
    ([("7.  ", 20, TEAL, True, False), ("La parte honesta", 20, NAVY, True, False),
      ("  — por qué la resiliencia no es seguridad", 15, GREY, False, False)], 0),
], space_after=14, line_spacing=1.0)

# ============================================================ 3. CÓMO LO HEMOS TRABAJADO
s = content_slide("Repaso · contexto", "Cómo hemos trabajado el Top 10")
table(s, Inches(0.9), Inches(1.75), Inches(11.5), Inches(2.0), [
    ["", "Clase", "Riesgos", "Herramientas nuevas"],
    ["1", "M1 · M2 · M6", "MobSF descubre · JADX localiza · ADB extrae · la clave descifra", "MobSF, JADX, sqlite3"],
    ["2", "M3 · M4 · M5 · M7", "Endpoints, cripto, canal HTTP y calidad de código", "Burp, mitm-m5.py, Frida"],
    ["3", "M8 · M9 · M10", "Ingeniería inversa, manipulación de código y superficie extra", "apktool, apksigner, d8, Frida"],
], col_w=[0.45, 1.9, 6.2, 2.95], size=13.5)
_text(s, Inches(0.9), Inches(4.15), Inches(11.5), Inches(2.6), [
    ([("La app es la misma en las tres: ", 16, GREY, False, False),
      ("InsecureBankv2", 16, NAVY, True, False),
      (" (Dinesh Shetty), referenciada por OWASP MASTG como ", 16, GREY, False, False),
      ("MASTG-APP-0010", 16, NAVY, True, False), (".", 16, GREY, False, False)], 0),
    ([("La VM es la misma: ", 16, GREY, False, False),
      ("Android 8.1 (API 27) x86_64, con root", 16, NAVY, True, False),
      (". Todo lo que veremos está ", 16, GREY, False, False),
      ("verificado ejecutándolo de verdad", 16, TEAL, True, False),
      (", no copiado de un guion.", 16, GREY, False, False)], 0),
    ([("Herramientas: ", 16, GREY, False, False),
      ("MobSF, JADX, apktool, apksigner, d8, Frida, Burp", 16, NAVY, True, False),
      (". Todas headless, por SSH.", 16, GREY, False, False)], 0),
], space_after=12)

# ============================================================ 4. M1 M2 M6
s = content_slide("Repaso · Clase 1", "M1 · M2 · M6 — Plataforma, datos y logs", accent=TEAL)
table(s, Inches(0.9), Inches(1.7), Inches(11.5), Inches(4.0), [
    ["", "Riesgo", "Qué encontramos", "Evidencia"],
    ["M1", "Improper Platform Usage", "Clave AES e IV de ceros embebidos en el código", 'key = "This is the super secret key 123"'],
    ["M2", "Insecure Data Storage", "Contraseña «cifrada» con esa clave en SharedPreferences; usuarios en claro en SQLite", "superSecurePassword = DTrW2VXjSoFdg0e61fHxJg=="],
    ["M6", "Insecure Logging", "Usuario y contraseña completos en logcat", 'Log.d("Successful Login:", "account=" + user + ":" + pass)'],
], col_w=[0.5, 2.4, 5.0, 3.6], size=13.5)
badge(s, Inches(0.9), Inches(5.9), Inches(11.5), Inches(0.85),
      "M1 define la clave  →  con ella se descifra M2  →  y M6 la deja escrita en el log.  Tres riesgos, una sola cadena.",
      NAVY, WHITE, size=15)

# ============================================================ 5. M3 M4 M5 M7
s = content_slide("Repaso · Clase 2", "M3 · M4 · M5 · M7 — Autenticación, cripto y canal", accent=ORANGE)
table(s, Inches(0.9), Inches(1.65), Inches(11.5), Inches(4.5), [
    ["", "Riesgo", "Qué encontramos"],
    ["M3", "Insecure Authentication", "/devlogin no valida nada · /changepassword no pide la actual · sin rate limit · enumeración de usuarios"],
    ["M4", "Insufficient Cryptography", "Clave hardcodeada · IV de 16 ceros · AES-CBC sin MAC · APK firmada solo con v1 (Janus)"],
    ["M5", "Insecure Communication", 'HTTP plano (protocol = "http://") · credenciales en claro · respuesta alterable en vuelo'],
    ["M7", "Client Code Quality", "debuggable + allowBackup · 8 permisos peligrosos · minSdk 15 / targetSdk 22 · sin validar entradas"],
], col_w=[0.5, 2.9, 8.1], size=14)
badge(s, Inches(0.9), Inches(6.35), Inches(11.5), Inches(0.8),
      "M3 y M5 son el mismo ataque desde dos lados: el cliente decide el acceso a partir de una cadena que llega por un canal que nadie verifica.",
      ORANGE, WHITE, size=14)

# ============================================================ 6. M8 M9 M10
s = content_slide("Repaso · Clase 3", "M8 · M9 · M10 — Inversa, manipulación y superficie", accent=RED)
table(s, Inches(0.9), Inches(1.65), Inches(11.5), Inches(4.5), [
    ["", "Riesgo", "Qué encontramos"],
    ["M9", "Reverse Engineering", "JADX devuelve clave, IV y modo · Frida captura la contraseña en claro en memoria · debuggable lo facilita"],
    ["M8", "Code Tampering", "Parchear smali (nop), reconstruir y re-firmar con CN=Attacker · renombrar la app · v1 no protege la metadata (Janus)"],
    ["M10", "Extraneous Functionality", "/devlogin · 4 actividades exportadas · receptor que exfiltra la contraseña por SMS · provider sin permisos · Google Wallet en un banco"],
], col_w=[0.8, 2.6, 8.1], size=13.5)
badge(s, Inches(0.9), Inches(6.35), Inches(11.5), Inches(0.8),
      "M9 hace posible M8. M8 hace inútil evitar M10. Ninguno de los tres necesita una vulnerabilidad de la plataforma: basta con que la app no se defienda.",
      RED, WHITE, size=14)

# ============================================================ 7. LA CADENA
s = content_slide("Repaso · síntesis", "La lección: no son etiquetas, son cadenas")
# columnas
colw = Inches(3.5)
for i, (tit, color, items) in enumerate([
    ("Cadena de datos", TEAL, ["M1  clave embebida", "M2  datos «cifrados» con esa clave", "M6  credenciales en el log", "M3  el atacante ya tiene credenciales"]),
    ("Cadena de ataque", RED, ["M9  ingeniería inversa", "M8  modificar y re-firmar", "M10  usar la superficie extra", "cuentas ajenas, sin avisar"]),
    ("Cadena cripto", PURPLE, ["M4  clave + IV + CBC sin MAC", "rompe lo guardado (M2)", "rompe lo transmitido (M5)", "firma v1 → Janus → M8"]),
]):
    x = Inches(0.75) + i * (colw + Inches(0.25))
    _rect(s, x, Inches(1.75), colw, Inches(4.4), WHITE, MSO_SHAPE.ROUNDED_RECTANGLE)
    _rect(s, x, Inches(1.75), colw, Inches(0.6), color, MSO_SHAPE.ROUNDED_RECTANGLE)
    _text(s, x, Inches(1.75), colw, Inches(0.6), [(tit, 16, WHITE, True, False)],
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    _text(s, x + Inches(0.2), Inches(2.6), colw - Inches(0.4), Inches(3.4),
          [("• " + it, 14, NAVY, False, False) for it in items], space_after=10)
_text(s, Inches(0.75), Inches(6.35), Inches(11.8), Inches(0.7),
      [([("Ningún control aislado arregla esto. ", 16, NAVY, True, False),
         ("La seguridad móvil es el conjunto: datos, cripto, canal y código — del lado del servidor y del lado del cliente.",
          16, GREY, False, False)], 0)])

# ============================================================ 8. PUENTE
s = content_slide("Puente a la Clase 4", "Sabemos romperlo. ¿Y defenderlo?")
_text(s, Inches(0.9), Inches(1.8), Inches(11.5), Inches(3.6), [
    ([("Todo lo anterior vive en el ", 20, NAVY, False, False),
      ("lado del cliente", 20, RED, True, False),
      (": la APK que el usuario tiene en la mano.", 20, NAVY, False, False)], 0),
    ([("Si el atacante controla el dispositivo —y en móvil, siempre lo hace— puede "
       "leer, modificar y volver a empaquetar tu app.", 18, GREY, False, False)], 0),
    ([("La pregunta de la Clase 4 no es «cómo evitar que la rompan», porque no se puede. "
       "Es ", 18, GREY, False, False),
      ("cómo subir el coste, detectar la manipulación y no depender del cliente para la seguridad real.",
       18, NAVY, True, False)], 0),
], space_after=16)
_rect(s, Inches(0.9), Inches(5.35), Inches(11.5), Inches(1.5), NAVY, MSO_SHAPE.ROUNDED_RECTANGLE)
_rect(s, Inches(0.9), Inches(5.35), Inches(0.12), Inches(1.5), ORANGE)
_text(s, Inches(1.25), Inches(5.55), Inches(10.9), Inches(1.1),
      [("«Resilience controls are never absolute... Any client-side protection can be bypassed, "
        "so these must be treated as additional protection against threat-specific attacks.»",
        15, WHITE, False, True),
       ("— OWASP MASVS-RESILIENCE", 13, ORANGE, True, False)], space_after=6)

# ============================================================ 9. MASVS-RESILIENCE
s = content_slide("Clase 4 · fundamento", "MASVS-RESILIENCE: los cuatro controles", accent=PURPLE)
table(s, Inches(0.9), Inches(1.7), Inches(11.5), Inches(4.3), [
    ["", "Control", "Qué exige", "En una palabra"],
    ["R-1", "Integridad de la plataforma", "Detectar root/jailbreak, emuladores, entornos virtuales y atestiguar el dispositivo", "¿dónde corre?"],
    ["R-2", "Anti-tampering", "Comprobar la integridad de la firma, el código (DEX/nativo) y los recursos; detectar repackaging", "¿es mi app?"],
    ["R-3", "Anti-ingeniería inversa", "Ofuscar código y recursos; dificultar la lectura estática", "¿se entiende?"],
    ["R-4", "Anti-análisis dinámico", "Anti-debug y detección de herramientas de instrumentación (Frida, hooking)", "¿la están observando?"],
], col_w=[0.7, 2.9, 6.4, 2.0], size=13.5)
_text(s, Inches(0.9), Inches(6.25), Inches(11.5), Inches(0.7),
      [("Son los cuatro grupos del estándar OWASP MASVS. InsecureBankv2 no cumple ", 15, GREY, False, False),
       ("ninguno de los cuatro", 15, RED, True, False)])

# ============================================================ 10. R-1
s = content_slide("Clase 4 · R-1", "Integridad de la plataforma", accent=TEAL)
bullets(s, Inches(0.9), Inches(1.7), Inches(6.4), Inches(5.0), [
    ("Detección de root / jailbreak: binarios su, Magisk, build tags test-keys, /system escribible.", 0),
    ("Detección de emulador: huella del build, ausencia/rareza de sensores, propiedades QEMU.", 0),
    ("Detección de virtualización: entornos como VirtualApp / contenedores.", 0),
    ("Device attestation: Play Integrity API o Key Attestation, verificada en el servidor.", 0),
    ("Referencias MASTG reales:", 0),
    ("MASTG-KNOW-0027 (root), -0031 (emulador), -0052 (virtual), -0054 (attestation), -0035 (Play Integrity).", 1),
], size=15.5, gap=10)
code_box(s, Inches(7.6), Inches(1.7), Inches(4.8), Inches(4.3), [
    "// raíz del asunto: comprobar en",
    "// RUNTIME si el entorno es de fiar",
    "",
    "val tags = Build.TAGS",
    "if (tags != null &&",
    "    tags.contains(\"test-keys\")) {",
    "    // build de desarrollo / ROM",
    "}",
    "",
    "// y lo importante: NO decidir",
    "// en el cliente. Lo detectado se",
    "// firma y se manda AL SERVIDOR.",
], title="el patrón (conceptual)")

# ============================================================ 11. R-2
s = content_slide("Clase 4 · R-2", "Anti-tampering: ¿es mi app la que corre?", accent=BLUE)
bullets(s, Inches(0.9), Inches(1.7), Inches(6.4), Inches(5.0), [
    ("Integridad de la firma: leer el certificado en runtime y compararlo con el hash esperado.", 0),
    ("Integridad del código: verificar el DEX y las librerías nativas (hashes) antes de confiar.", 0),
    ("Integridad de recursos: que nadie sustituya strings, imágenes o configuración.", 0),
    ("Detección de repackaging: la app re-firmada por un atacante deja de validar.", 0),
    ("Error clásico:", 0),
    ("comprobar la firma en Java es un control que Frida parchea en 30 segundos. El contraste real va en nativo y, sobre todo, en el servidor.", 1),
], size=15.5, gap=9)
code_box(s, Inches(7.6), Inches(1.7), Inches(4.8), Inches(4.3), [
    "// firma esperada (server-side ideal)",
    "val pkg = packageManager",
    "   .getPackageInfo(packageName,",
    "       PackageManager.GET_SIGNATURES)",
    "val sig = pkg.signatures[0]",
    "val hash = sha256(sig.toByteArray())",
    "",
    "if (hash != EXPECTED) {",
    "    // app manipulada O re-firmada",
    "    // (InsecureBankv2 no tiene esto:",
    "    //  en Clase 3 la re-firmamos y",
    "    //  arranca sin quejarse)",
    "}",
], title="comprobación de firma")

# ============================================================ 12. R-3
s = content_slide("Clase 4 · R-3", "Anti-ingeniería inversa: que cueste leerlo", accent=ORANGE)
bullets(s, Inches(0.9), Inches(1.75), Inches(11.5), Inches(4.4), [
    ("Ofuscación de código (R8 / ProGuard): renombra clases y métodos y elimina lo no usado.", 0),
    ("Ofuscación de cadenas: la clave de InsecureBankv2 viaja en texto claro; ofuscarla esconde el literal pero no la lógica.", 0),
    ("Flujo de control y aritmética: encarece el análisis estático (DexGuard, Virbox, Promon…).", 0),
    ("Parte lógica en nativo (NDK + JNI): añade una capa de dificultad sobre Java/smali.", 0),
    ("Límite honesto: la ofuscación retrasa, no impide. Un analista con tiempo (o un LLM) la deshace.", 0),
], size=15.5, gap=11)

# ============================================================ 13. R-4
s = content_slide("Clase 4 · R-4", "Anti-análisis dinámico: Frida y el depurador", accent=RED)
bullets(s, Inches(0.9), Inches(1.7), Inches(6.5), Inches(5.0), [
    ("Anti-debug: Debug.isDebuggerConnected(), ptrace(PTRACE_TRACEME), TracerPid en /proc/self/status.", 0),
    ("Detección de Frida: puerto por defecto 27042, hilos gum-js-loop / gmain, regiones frida-agent en /proc/self/maps.", 0),
    ("Detección de hooking: comprobar la integridad de métodos, ART, o el retorno de llamadas nativas.", 0),
    ("En InsecureBankv2:", 0),
    ("nada de esto. En la Clase 3 hookeamos aesEncryptedString con Frida y la app ni se enteró.", 1),
], size=15.5, gap=10)
code_box(s, Inches(7.7), Inches(1.7), Inches(4.7), Inches(4.3), [
    "# huecos que InsecureBankv2 deja",
    "# abiertos (lo que un control",
    "# real vigilaría)",
    "",
    "cat /proc/self/maps | grep -i frida",
    "cat /proc/net/tcp  # 27042?",
    "ls /proc/self/task    # gum-js-loop?",
    "",
    "# la app no mira nada de esto:",
    "# por eso el hook de M9 funcionó",
    "# a la primera.",
], title="qué miraría un anti-Frida")

# ============================================================ 14. ATTESTATION
s = content_slide("Clase 4 · técnica clave", "Attestation: no depender del cliente", accent=PURPLE)
bullets(s, Inches(0.9), Inches(1.75), Inches(11.5), Inches(4.3), [
    ("El cliente puede mentir sobre su propio estado. Un tercero con claves en hardware, no.", 0),
    ("Play Integrity API: el dispositivo firma un veredicto (integridad de app, del dispositivo y de la licencia) que el servidor verifica.", 0),
    ("Key Attestation (Android KeyStore): claves respaldadas por hardware con certificados verificables.", 0),
    ("La clave está en dónde se decide:", 0),
    ("la verificación se hace en el SERVIDOR. Si el cliente es el que decide si el cliente es de fiar, ya has perdido.", 1),
    ("Referencias: MASVS-RESILIENCE-1 · MASTG-KNOW-0035 (Play Integrity) · -0119/-0120 (Key / Device Attestation).", 0),
], size=15.5, gap=11)

# ============================================================ 15. DEMO
s = content_slide("Demo en vivo", "InsecureBankv2 no tiene NINGUNA defensa (y se ve)", accent=TEAL)
table(s, Inches(0.9), Inches(1.7), Inches(11.5), Inches(3.9), [
    ["Qué probamos", "Qué esperamos ver", "Por qué"],
    ["Re-firmar la app (Clase 3)", "Arranca igual, firmada por CN=Attacker", "No hay comprobación de firma (R-2)"],
    ["Detección de root", "«Rooted Device!!» es solo un texto: no bloquea nada", "No hay control real de plataforma (R-1)"],
    ["Hook con Frida (Clase 3)", "Captura la contraseña; la app no reacciona", "No hay anti-análisis dinámico (R-4)"],
    ["mapas / puertos de Frida", "Nadie los mira", "No hay detección de instrumentación (R-4)"],
], col_w=[3.3, 4.6, 3.6], size=13.5)
_text(s, Inches(0.9), Inches(5.85), Inches(11.5), Inches(1.0),
      [([("El contraste es el mensaje: ", 15, NAVY, True, False),
         ("estos mismos cuatro puntos, en una app bancaria real, son exactamente donde R-1/R-2/R-4 tendrían que saltar.",
          15, GREY, False, False)], 0)])

# ============================================================ 16. LA PARTE HONESTA
s = content_slide("Clase 4 · honestidad", "La resiliencia NO es seguridad", accent=RED)
bullets(s, Inches(0.9), Inches(1.75), Inches(11.5), Inches(4.6), [
    ("Todo control del lado del cliente se puede saltar: en el momento en que el atacante controla el dispositivo, también controla tus comprobaciones.", 0),
    ("MASVS lo deja escrito: la AUSENCIA de controles de resiliencia no es, por sí sola, una vulnerabilidad. Son defensa en profundidad.", 0),
    ("No sustituyen la seguridad del diseño: validación en el servidor, criptografía bien hecha y mínima superficie. Esos sí son requisitos.", 0),
    ("Coste real: rendimiento, falsos positivos (usuarios con root legítimo), y fricción para quien audita la app en tu nombre.", 0),
    ("Úsalos para:", 0),
    ("deter client-side abuse (fraude, trampas, clonado), no como la puerta que protege el dinero.", 1),
], size=15.5, gap=10)

# ============================================================ 17. CÓMO SE EVALÚA
s = content_slide("Clase 4 · método", "Cómo se evalúa (MASTG)", accent=BLUE)
table(s, Inches(0.9), Inches(1.7), Inches(11.5), Inches(4.2), [
    ["Área", "Knowledge (MASTG-KNOW)", "Qué se prueba"],
    ["Root", "0027 Root Detection", "¿Se detecta el root y se actúa?"],
    ["Anti-debug", "0028 Anti-Debugging", "¿Se detecta el depurador?"],
    ["Integridad", "0029 File Integrity · 0032 Runtime Integrity", "¿Se verifica código y recursos?"],
    ["Herramientas", "0030 RE Tool Detection", "¿Se detecta Frida / instrumentación?"],
    ["Emulador", "0031 Emulator Detection", "¿Se detecta la máquina virtual?"],
    ["Ofuscación", "0033 Obfuscation", "¿Cuánto cuesta leer el binario?"],
    ["Attestation", "0035 Play Integrity API", "¿Se verifica en el servidor?"],
], col_w=[1.6, 4.7, 5.2], size=13)
_text(s, Inches(0.9), Inches(6.1), Inches(11.5), Inches(0.7),
      [("El mismo marco con el que evaluamos las Clases 1–3, ahora del lado de la defensa.", 14, GREY, False, False)])

# ============================================================ 18. CIERRE
s = prs.slides.add_slide(BLANK)
_n += 1
_rect(s, 0, 0, SW, SH, NAVY)
_rect(s, 0, 0, Inches(0.28), SH, TEAL)
_text(s, Inches(1.0), Inches(1.0), Inches(11.5), Inches(1.0),
      [("CIERRE", 15, TEAL, True, False)])
_text(s, Inches(1.0), Inches(1.5), Inches(11.5), Inches(3.6), [
    ([("Clase 1–3: ", 20, GREY2, True, False), ("sabemos romper una app móvil.", 20, WHITE, False, False)], 0),
    ([("Clase 4: ", 20, TEAL, True, False), ("sabemos leer cómo una app intenta defenderse.", 20, WHITE, False, False)], 0),
    ([("La regla que no cambia: ", 20, ORANGE, True, False),
      ("nada que decida el cliente es de fiar.", 20, WHITE, False, False)], 0),
], space_after=16)
_rect(s, Inches(1.0), Inches(4.9), Inches(3.2), Emu(30000), GREY2)
_text(s, Inches(1.0), Inches(5.15), Inches(11.5), Inches(1.6),
      [("Siguiente paso:", 15, WHITE, True, False),
       ("repaso final y examen · mapa de CVE de 2026 en docs/clases/cve-2026-mobile.md", 15, GREY2, False, False),
       ("«No digas: evité que la modificaran. Di: encarecí la modificación y me enteré cuando lo hicieron.»",
        15, TEAL, False, True)], space_after=8)

BASE = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(BASE, "clase-4-resiliencia.pptx")
prs.save(out)
print(f"{len(prs.slides.__iter__.__self__._sldIdLst)} diapositivas -> {out}")
