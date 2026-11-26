# Gestos de las manos del G1 desde la laptop

Interfaz gráfica (PyQt5) para hacer **gestos con las dos manos Inspire RH56E2 del G1 EDU-U6** desde la laptop, por la
WiFi del robot. Los gestos son los de la interfaz de la RH56DFTP (`inspire_hand_interface/Interfaz`): **Abrir,
Cerrar, Señalar, Pinza y Pulgar arriba**, en cada mano por separado o en las dos a la vez. Muestra en vivo el ángulo,
la fuerza, el estado, el error y la temperatura de cada dedo, y deja cambiar la velocidad.

Habla con las manos igual que el teleop (`../g1_teleoperation`): **Modbus TCP**, puerto 6000, los mismos registros y
`ANGLE_SET` siempre como bloque de 6. **En el robot no se instala ni se lanza nada.**

---

## 1. Cómo funciona

```
  Laptop (WiFi UTEC_H1_2)                         G1: PC2 (Jetson)                  manos (red interna, eth1)
  interfaz_manos.sh
   └─ ssh -L ─────── túnel SSH ──────────────▶  sshd 192.168.0.151 ──────────▶  192.168.123.210:6000  IZQUIERDA
        127.0.0.1:16210 ─────────────────────────────────────────────────────▶  192.168.123.211:6000  DERECHA
        127.0.0.1:16211
   └─ interfaz/main.py  (Modbus TCP a 127.0.0.1:16210 y :16211)
        · cada 2 s, por la misma conexión SSH: ¿corre el teleop o el driver de las manos?
```

- Las manos están en la **red interna** del robot, a la que la laptop no llega. El túnel SSH las trae a
  `127.0.0.1` y se cierra al cerrar la interfaz. Si la laptop no tiene su clave SSH en el robot
  (`ssh-copy-id unitree@192.168.0.151`), pide la contraseña de `unitree` **una vez**, al lanzar.
- **Izquierda y derecha son las del robot** (su propia perspectiva): `.210` es la izquierda y `.211` la derecha,
  comprobado el 2026-11-26 (`g1_teleoperation`, README §9).
- Cada mano tiene su propio hilo para el Modbus: si la WiFi se atasca, la ventana no se congela. Lee el estado a
  ~10 Hz.

## 2. Requisitos (laptop)

- Linux con `ssh` y Python 3 con **PyQt5** y **pymodbus 3.6.9** (`pip install PyQt5 pymodbus==3.6.9`). Con otras
  versiones de pymodbus la API cambia.
- Estar en la WiFi del robot (`UTEC_H1_2`). El robot es `unitree@192.168.0.151`, como en `g1_teleoperation`.

## 3. Uso

```bash
cd ~/Documents/g1_utec/g1_hands
./interfaz_manos.sh                          # abre el túnel (contraseña de unitree si no hay clave) y la interfaz
ROBOT_SSH=unitree@<IP> ./interfaz_manos.sh   # si el robot tiene otra IP
```

1. **Conectar**: primero mira en el robot si corre el teleop o el driver de las manos. Si corre, **no se conecta** y
   lo dice (`./teleop_xr.sh parar` en `g1_teleoperation/scripts`). Conectar **no mueve nada**.
2. Los botones de **«Las dos manos»** mandan el gesto a las dos; los de cada panel, solo a esa mano. Un gesto nuevo
   cancela lo que quedara del anterior.
3. **Velocidad** (`SPEED_SET` de las dos manos, 100–1000): arranca en la que tienen las manos. **Al desconectar o
   cerrar, cada mano vuelve a la velocidad que tenía**: el teleop no manda velocidad y la encontraría cambiada.
4. **Borrar error** (por mano): escribe `CLEAR_ERROR` (1004), como `./manos.sh borrar-error`. Hace falta si un dedo
   se queda con `err` distinto de 0 (pasa el cursor por encima para ver qué fallo es).
5. Cerrar la ventana, o Ctrl-C en la terminal, suelta las manos (con su velocidad) y cierra el túnel.

Las manos **se quedan donde estén** al desconectar: la interfaz no las abre al salir.

## 4. Los gestos

Valores de `ANGLE_SET` (`0` = cerrado, `1000` = abierto), en el orden meñique, anular, medio, índice, flexión del
pulgar y rotación del pulgar. Son los de `inspire_hand_interface/Interfaz` (`gesture_panel.py`), en
[`interfaz/manos/gestos.py`](interfaz/manos/gestos.py).

| Gesto | Pasos |
|---|---|
| Abrir | `1000 1000 1000 1000 1000 1000` |
| Cerrar | `0 0 0 0 1000 1000` → `0 0 0 0 0 1000` (primero los dedos y después el pulgar, que queda por fuera) |
| Señalar | `0 0 0 1000 0 500` |
| Pinza | `1000 1000 1000 486 580 133` (calculada con los grados de la RH56DFTP) |
| Pulgar arriba | `0 0 0 0 1000 1000` |

En los gestos de varios pasos, el paso siguiente sale como pronto a los 0,8 s, igual que en la Interfaz, y además
**espera a que los dedos lleguen o se paren**. A velocidad baja, con solo 0,8 s el pulgar cerraría sobre unos dedos
que aún no han llegado.

## 5. Con el teleop

La interfaz y el teleop **no pueden mandar las manos a la vez**: el driver del teleop escribe `ANGLE_SET` a 100 Hz y
la mano obedecería a los dos.

- Con el teleop o el driver de las manos corriendo (`inspire_ftp_dual_driver.py`, `lanzar_teleop.py`), la interfaz
  **no se conecta**.
- Si se arranca el teleop con la interfaz conectada, la interfaz lo ve en ≤ 2 s y **suelta las manos** (con su
  velocidad). Las manos aceptan dos clientes Modbus a la vez (comprobado leyendo), así que el driver del teleop se
  conecta igual.
- Aun así, lo correcto es **cerrar la interfaz antes de lanzar el teleop**.

Si se corta la WiFi, cada mano se queda donde estaba y la interfaz reintenta cada segundo. Un gesto que no llegó a
salir se descarta para que la mano no lo haga sola al volver la conexión.

## 6. Pruebas sin robot

```bash
./interfaz_manos.sh --local                 # la interfaz contra dos manos falsas (pruebas/mano_falsa.py)
python3 pruebas/prueba_ventana.py           # la ventana sin pantalla, con un robot falso (21 comprobaciones)
python3 pruebas/mano_falsa.py 16210 16211 & python3 pruebas/prueba_enlace.py gestos   # sin ventana
```

`prueba_enlace.py` sirve también contra las manos reales con el túnel abierto (mismos puertos):
`leer` y `dos-clientes` (solo lectura), `gestos [NOMBRE…]`, `indice` (mueve solo el índice: orden de los bytes de
`STATUS`) y `velocidad V` (la pone y comprueba que se restaura). Con `--fijar 5`, la rotación del pulgar se manda
siempre con el ángulo que medía al conectar, para no moverla (p. ej. si el pulgar puede chocar con la pierna).

## 7. Estado

| Fecha | Qué | Resultado |
|---|---|---|
| 2026-11-26 | Manos falsas (`prueba_enlace.py`, `prueba_ventana.py`) | los 5 gestos en las dos manos; uno distinto en cada mano; un gesto nuevo cancela el anterior; Cerrar a velocidad 200 espera a los dedos; velocidad puesta y restaurada al desconectar, al cerrar y al aparecer el teleop; no conecta con el teleop corriendo; reconexión tras caerse una mano sin repetir órdenes viejas |
| 2026-11-26 | **G1 real**, por WiFi (túnel a `unitree@192.168.0.151`), teleop parado | **los 5 gestos en las dos manos**, rotación del pulgar incluida: todos los dedos a ≤ 16 de la consigna. Velocidad 300 puesta y restaurada a 1000. La ventana conecta, comprueba el teleop por SSH cada 2 s y lee las manos con ciclos de 27–55 ms. El lanzador abre y cierra su túnel |

Medido en el G1:

- **Pinza:** el índice y el pulgar se tocan. La derecha aprieta con **766 gf** en el índice y la izquierda con 82 gf.
- **La rotación del pulgar** queda ~15 por debajo de la consigna (1000 → 985, 500 → 485, 133 → 118).
- **Orden de los bytes** de `STATUS`, `ERROR` y `TEMP`: el byte **bajo** es el del dedo par, como en `manos.py`.
  Al mover solo el índice, el que seguía en movimiento era el índice. El SDK de Inspire los toma al revés, así que
  lo que publica el driver del teleop en `err`, `status` y `temperature` sale cambiado por parejas de dedos.
- **`ANGLE_SET` no se puede leer**: con las manos abiertas devuelve `[0, 0, 0, 0, 0, 208]` (derecha) y
  `[0, 0, 0, 0, 0, 160]` (izquierda). La interfaz solo lo escribe. La columna «Consigna» es lo último que mandó la
  interfaz.
- **Dos clientes Modbus a la vez** en cada mano: 10 de 10 lecturas buenas en los dos.
- Al recibir un `ANGLE_SET`, la mano pone los 6 dedos en «Cerrando»/«Abriendo» un instante, y a veces se quedan así
  un rato después de llegar.

## 8. Qué hay en esta carpeta

```
g1_hands/
├── README.md
├── interfaz_manos.sh          túnel SSH + interfaz (o --local con manos falsas)
├── interfaz/
│   ├── main.py                la ventana (argumentos: --izq/--der HOST:PUERTO, --ssh-control, --robot)
│   ├── manos/                 sin Qt
│   │   ├── registros.py       direcciones Modbus, IP, nombres de los dedos, estados y errores
│   │   ├── gestos.py          los 5 gestos
│   │   ├── enlace.py          una mano: hilo con el Modbus, velocidad restaurada al soltar
│   │   └── robot.py           ¿corre el teleop? (pgrep por el ControlMaster del túnel)
│   └── ui/                    ventana.py, panel_mano.py, estilo.py (el de la Interfaz)
└── pruebas/
    ├── mano_falsa.py          manos RH56E2 falsas por Modbus TCP
    ├── prueba_enlace.py       el enlace sin ventana (manos falsas o reales)
    └── prueba_ventana.py      la ventana sin pantalla, pulsando sus botones
```
