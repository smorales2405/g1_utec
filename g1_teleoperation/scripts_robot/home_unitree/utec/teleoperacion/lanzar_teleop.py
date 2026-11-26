#!/usr/bin/env python3
"""Lanza teleop_hand_and_arm.py en el G1 de UTEC sin tocar el codigo de Unitree, con estos cambios:

0. Solo en Motion Mode (--motion): los brazos van por rt/arm_sdk y las piernas siguen con la locomocion de
   Unitree (modo Regular: R1+Y en el G1 de UTEC, FSM 501), que se maneja con el mando. Sin --motion, el teleop de Unitree llama a
   ReleaseMode(), que en el G1 quita la locomocion: de pie, el robot se caeria. Por eso:
   - sin --motion (o con otro --arm que G1_29), este programa no arranca;
   - MotionSwitcher.Enter_Debug_Mode() queda anulado: nunca se llama a ReleaseMode();
   - antes de crear el controlador de los brazos se pregunta el modo (CheckMode). Si responde '' (Debug:
     nadie escucha rt/arm_sdk y las piernas no se sostienen), no arranca. Se registra la FSM (GetFsmId).
1. Modelo de la IK: el del G1 de UTEC, modo 15 con las RH56E2 (modelo_ik.py), y no el de Unitree.
2. Entrada suave en arm_sdk. En el original, al crearse el controlador el peso de arm_sdk salta a 1 y los
   brazos van deprisa a 0 grados antes de pulsar r. Aqui:
   a) los brazos se quedan en la postura de la locomocion y el peso sube de 0 a 1 en RAMPA_PESO_S;
   b) al pulsar r, durante RAMPA_INICIO_S la consigna pasa poco a poco de esa postura a la del operador.
   En las dos, y en la salida, el par de los brazos es el de gravedad del modelo de UTEC en la postura mandada.
3. Salida (q, Ctrl-C, un error o un corte del SSH), en este orden:
   a) los brazos van a 0 grados (antebrazos hacia delante);
   b) se abren del todo las dos manos, con los brazos quietos en 0 grados;
   c) los brazos vuelven a la postura de la locomocion, la medida al arrancar;
   d) el peso de arm_sdk baja de 1 a 0 en RAMPA_PESO_S: los brazos vuelven a la locomocion.
   d) se hace SIEMPRE, aunque fallen los anteriores. El original solo baja el peso si los brazos llegan a menos
   de 0.05 rad de 0 grados en ~5 s; si no, el programa termina con el peso en 1.
   Si no se llego a pulsar r, los brazos no se han movido: solo se abren las manos y se hace d).
4. Si se corta el SSH, el teleop sale como con q (y por tanto hace lo mismo). Igual que en el H1-2, el corte
   se detecta por el terminal colgado o porque el PC deja de responder al ping SIN_PING_S segundos.
   SIGHUP se ignora, tambien en los procesos hijos, para que el corte no los mate antes de salir.

Las manos (Inspire_Controller_FTP), la apertura al salir y la vigilancia del SSH son las del H1-2
(h1_2_utec/h1_2_teleoperation/scripts_robot/home_unitree/utec/teleoperacion/lanzar_teleop.py).
"""
import argparse, os, sys, time, runpy, signal, subprocess, threading, multiprocessing
import numpy as np
AQUI = os.path.dirname(os.path.abspath(__file__))
TELEOP = os.path.join(AQUI, "xr_teleoperate", "teleop")
SCRIPT = os.path.join(TELEOP, "teleop_hand_and_arm.py")
sys.path.insert(0, os.path.dirname(TELEOP))
sys.path.insert(0, AQUI)
os.chdir(TELEOP)
import logging_mp
# logging_mp exige basicConfig() antes de cualquier getLogger(), y robot_arm y robot_hand_inspire lo llaman al
# importarse: se configura aqui igual que en la primera linea del teleop y se anula la llamada del teleop.
logging_mp.basicConfig(level=logging_mp.INFO)
logging_mp.basicConfig = lambda *args, **kwargs: None
import pinocchio as pin
from teleop.utils import motion_switcher as ms
from teleop.robot_control import robot_arm, robot_hand_inspire
import modelo_ik

RAMPA_PESO_S = 2.0    # s para subir (al arrancar) y bajar (al salir) el peso de arm_sdk entre 0 y 1
RAMPA_INICIO_S = 2.0  # s, tras pulsar r, para pasar de la postura de la locomocion a la del operador
MANO_ABIERTA = 0.95   # angle_act/1000 de una mano abierta (medido en las RH56DFTP del H1-2)
ESPERA_MANOS_S = 3.0  # si no terminan de abrir en este tiempo, los brazos vuelven igual
VEL_BRAZOS = 1.0      # rad/s de media, en la junta que mas se mueve, en los dos movimientos de la salida
TOL_BRAZOS = 0.05     # rad; la misma que ctrl_dual_arm_go_home de Unitree
ESPERA_BRAZOS_S = 1.0 # tras la rampa, si no han llegado en este tiempo se sigue igual
SIN_PING_S = 3.0      # sin respuesta del PC durante esto -> q (la WiFi del H1-2 tenia picos de 0.5 s)

Brazos = robot_arm.G1_29_ArmController
JUNTAS_BRAZOS = [int(j) for j in robot_arm.G1_29_JointArmIndex]
PESO = int(robot_arm.G1_29_JointIndex.kNotUsedJoint0)   # motor_cmd[29].q: el peso de arm_sdk
_, MODELO = modelo_ik.construir()                          # el mismo que usa la IK, para el par de gravedad
_DATOS = MODELO.createData()
_CEROS = np.zeros(MODELO.nv)
_CERROJO_MODELO = threading.Lock()


def aviso(texto):
    # Tras un corte del SSH puede no quedar donde escribir: que eso no tumbe el cierre ordenado
    try:
        print(f"[lanzar_teleop] {texto}", flush=True)
    except OSError:
        pass


def suave(s):
    s = min(max(s, 0.0), 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * s)


def gravedad(q):
    # Igual que sol_tauff de la IK (rnea con v = a = 0). Lo llaman el hilo que publica y el principal
    with _CERROJO_MODELO:
        return pin.rnea(MODELO, _DATOS, np.asarray(q, dtype=float), _CEROS, _CEROS).copy()


class Rampa:
    """Un valor que va de donde este a otro en un tiempo, con perfil coseno. Se lee desde otro hilo."""

    def __init__(self, valor):
        self._cerrojo = threading.Lock()
        self._de = self._a = float(valor)
        self._t0, self._dur = 0.0, 1e-3

    def _ahora(self):
        return self._de + (self._a - self._de) * suave((time.monotonic() - self._t0) / self._dur)

    def valor(self):
        with self._cerrojo:
            return self._ahora()

    def ir(self, destino, duracion):
        with self._cerrojo:
            self._de, self._a = self._ahora(), float(destino)
            self._t0, self._dur = time.monotonic(), max(float(duracion), 1e-3)

    def terminada(self):
        with self._cerrojo:
            return time.monotonic() - self._t0 >= self._dur


# --- 0. solo Motion Mode, y comprobando el modo ---
def rehusar_debug(self, *args, **kwargs):
    raise RuntimeError("lanzar_teleop: en el G1 no se llama a ReleaseMode() (quitaria la locomocion)")


def comprobar_modo():
    # Solo lectura: CheckMode y GetFsmId. El canal DDS ya lo ha abierto el teleop (ChannelFactoryInitialize).
    from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
    msc = MotionSwitcherClient()
    msc.SetTimeout(2.0)
    msc.Init()
    codigo, modo = msc.CheckMode()
    aviso(f"CheckMode: {codigo} {modo}")
    if codigo == 0 and isinstance(modo, dict) and not modo.get("name"):
        raise RuntimeError("el robot esta en Debug (CheckMode con name ''): nadie escucha rt/arm_sdk y las piernas "
                           "no se sostienen. Ponlo de pie en modo Regular (R1+Y) con el mando y vuelve a lanzar.")
    if codigo != 0:
        aviso(f"AVISO: no se pudo comprobar el modo (CheckMode {codigo}); se sigue")
    try:
        from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient
        loco = LocoClient()
        loco.SetTimeout(2.0)
        loco.Init()
        codigo, fsm = loco.GetFsmId()
        aviso(f"FSM de la locomocion: {fsm} (GetFsmId {codigo})")
    except Exception as e:
        aviso(f"AVISO: no se pudo leer la FSM: {e}")


_init_brazos = Brazos.__init__
_ctrl_brazos_unitree = Brazos.ctrl_dual_arm


def init_brazos(self, motion_mode=False, simulation_mode=False):
    if not motion_mode:
        raise RuntimeError("lanzar_teleop: el G1 solo se teleopera en Motion Mode (--motion)")
    comprobar_modo()
    self._peso = Rampa(0.0)
    self._t_inicio = None   # cuando se pulso r (primera llamada a ctrl_dual_arm)
    _init_brazos(self, motion_mode=motion_mode, simulation_mode=simulation_mode)


# --- 2. entrada suave ---
def publicar(self):
    # El bucle de G1_29_ArmController._ctrl_motor_state (robot_arm.py, 817fb00) con dos cambios: la consigna
    # inicial es la postura medida (no 0 grados), con su par de gravedad, y el peso sube con una rampa en vez de
    # saltar a 1. Lo arranca el __init__ de Unitree, despues de medir la postura y de preparar self.msg.
    with self.ctrl_lock:
        self.q_target = self.get_current_dual_arm_q()
        self.tauff_target = gravedad(self.q_target)
    self._peso.ir(1.0, RAMPA_PESO_S)
    aviso(f"arm_sdk: el peso sube a 1 en {RAMPA_PESO_S:.0f} s; los brazos se quedan en la postura de la locomocion")
    while True:
        t0 = time.time()
        with self.ctrl_lock:
            q, tau = self.q_target, self.tauff_target
        if not self.simulation_mode:
            q = self.clip_arm_q_target(q, velocity_limit=self.arm_velocity_limit)
        for i, j in enumerate(JUNTAS_BRAZOS):
            self.msg.motor_cmd[j].q = q[i]
            self.msg.motor_cmd[j].dq = 0
            self.msg.motor_cmd[j].tau = tau[i]
        self.msg.motor_cmd[PESO].q = self._peso.valor()
        self.msg.crc = self.crc.Crc(self.msg)
        self.lowcmd_publisher.Write(self.msg)
        time.sleep(max(0.0, self.control_dt - (time.time() - t0)))


def ctrl_brazos(self, q_target, tauff_target):
    # La llama el teleop en cada vuelta, solo despues de pulsar r. Durante RAMPA_INICIO_S mezcla la postura que
    # habia con la de la IK; despues pasa la de la IK tal cual (lo de Unitree).
    if self._t_inicio is None:
        with self.ctrl_lock:
            self._q_entrada = np.array(self.q_target)
        self._t_inicio = time.monotonic()
        aviso(f"r: los brazos pasan a seguir al operador en {RAMPA_INICIO_S:.0f} s")
    k = suave((time.monotonic() - self._t_inicio) / RAMPA_INICIO_S)
    if k < 1.0:
        q_target = self._q_entrada + k * (np.asarray(q_target) - self._q_entrada)
        tauff_target = gravedad(q_target)
    _ctrl_brazos_unitree(self, q_target, tauff_target)


# --- 3. salida: brazos a 0 grados, abrir las manos, brazos a la postura de la locomocion, peso a 0 ---
# Se crea antes de que el teleop arranque el proceso de las manos (fork), asi que lo comparten
ABRIR_MANOS = multiprocessing.Value("b", False)
MANOS = []   # el Inspire_Controller_FTP del teleop

_init_mano = robot_hand_inspire.Inspire_Controller_FTP.__init__
_enviar_mano = robot_hand_inspire.Inspire_Controller_FTP._send_hand_command


def init_mano(self, *args, **kwargs):
    _init_mano(self, *args, **kwargs)
    MANOS.append(self)


def enviar_mano(self, izq, der):
    # Corre en el proceso de las manos, a 100 Hz: con ABRIR_MANOS manda abrir en vez del retargeting
    if ABRIR_MANOS.value:
        izq = der = [1000] * robot_hand_inspire.Inspire_Num_Motors
    _enviar_mano(self, izq, der)


def abrir_manos():
    if not MANOS:
        return
    mano = MANOS[0]
    aviso("abriendo las manos")
    ABRIR_MANOS.value = True
    t0 = time.monotonic()
    while True:
        angulos = list(mano.left_hand_state_array[:]) + list(mano.right_hand_state_array[:])
        if min(angulos) >= MANO_ABIERTA:
            aviso(f"manos abiertas en {time.monotonic() - t0:.1f} s")
            return
        if time.monotonic() - t0 > ESPERA_MANOS_S:
            aviso(f"AVISO: las manos no terminaron de abrir en {ESPERA_MANOS_S:.0f} s "
                  f"(izq {[round(a, 2) for a in angulos[:6]]}, der {[round(a, 2) for a in angulos[6:]]}); "
                  "se sigue igual")
            return
        time.sleep(0.05)


def mover_brazos(self, q_final, destino):
    # Rampa suave desde la consigna actual, con el par de gravedad de cada postura intermedia
    q_ini = self.get_current_dual_arm_q()
    duracion = max(np.max(np.abs(q_final - q_ini)) / VEL_BRAZOS, 0.2)
    aviso(f"brazos a {destino}: {duracion:.1f} s")
    t0 = time.monotonic()
    while (s := (time.monotonic() - t0) / duracion) < 1.0:
        q = q_ini + (q_final - q_ini) * suave(s)
        _ctrl_brazos_unitree(self, q, gravedad(q))
        time.sleep(0.004)
    _ctrl_brazos_unitree(self, q_final, gravedad(q_final))
    t0 = time.monotonic()
    while (error := np.max(np.abs(self.get_current_dual_arm_q() - q_final))) > TOL_BRAZOS:
        if time.monotonic() - t0 > ESPERA_BRAZOS_S:
            aviso(f"AVISO: brazos a {error:.3f} rad de {destino}; se sigue igual")
            return
        time.sleep(0.02)


def soltar_arm_sdk(self):
    aviso(f"arm_sdk: el peso baja a 0 en {RAMPA_PESO_S:.0f} s; los brazos vuelven a la locomocion")
    self._peso.ir(0.0, RAMPA_PESO_S)
    while not self._peso.terminada():
        time.sleep(0.02)
    time.sleep(0.2)   # que salgan unos cuantos mensajes con el peso ya en 0
    aviso(f"arm_sdk suelto (peso {self._peso.valor():.2f})")


def intentar(paso, *args):
    # Que el fallo de un paso no impida los siguientes
    try:
        paso(*args)
    except Exception as e:
        aviso(f"{paso.__name__} fallo: {e}")


def salida(self):
    # all_motor_q se mide en __init__, antes de que el controlador publique nada: la postura de la locomocion
    q_inicio = self.all_motor_q[JUNTAS_BRAZOS]
    if self._t_inicio is not None:
        intentar(mover_brazos, self, np.zeros(q_inicio.shape), "0 grados")
        intentar(abrir_manos)
        intentar(mover_brazos, self, q_inicio, "la postura de la locomocion")
    else:
        aviso("no se llego a pulsar r: los brazos no se han movido")
        intentar(abrir_manos)
    intentar(soltar_arm_sdk, self)


# --- 4. corte del SSH = q ---
def modulo_teleop():
    # Mientras corre, runpy.run_path deja el modulo del teleop en sys.modules["__main__"]
    g = sys.modules["__main__"].__dict__
    return g if g.get("__file__") == SCRIPT else None


def hay_terminal():
    # Al colgarse el terminal, el kernel se lo quita a toda la sesion y abrir /dev/tty da ENXIO
    try:
        os.close(os.open("/dev/tty", os.O_RDONLY | os.O_NOCTTY))
        return True
    except OSError:
        return False


def responde(ip):
    return subprocess.run(["ping", "-c", "1", "-W", "1", "-q", ip],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def vigilar_conexion():
    con_terminal = hay_terminal()
    ip = os.environ.get("SSH_CLIENT", "").split(" ")[0]
    # Se espera a que el teleop haya arrancado (y creado sus procesos) antes de lanzar pings
    while (g := modulo_teleop()) is None or not g.get("READY"):
        if g is not None and g.get("STOP"):
            return
        time.sleep(0.1)
    ultimo_ping = [None]   # no se vigila el ping hasta la primera respuesta, por si el PC no contesta pings

    def hacer_ping():
        while True:
            if responde(ip):
                ultimo_ping[0] = time.monotonic()
            time.sleep(0.5)

    if ip:
        threading.Thread(target=hacer_ping, name="ping_pc", daemon=True).start()
    aviso(f"vigilando el SSH: terminal {'si' if con_terminal else 'no'}, ping a {ip or '-'} "
          f"(q si no responde {SIN_PING_S:.0f} s)")
    t0, avisado = time.monotonic(), False
    while not g.get("STOP"):
        motivo = None
        if con_terminal and not hay_terminal():
            motivo = "se colgo el terminal del SSH"
        elif ultimo_ping[0] is not None and time.monotonic() - ultimo_ping[0] > SIN_PING_S:
            motivo = f"el PC {ip} no responde al ping desde hace {SIN_PING_S:.0f} s"
        elif ip and ultimo_ping[0] is None and not avisado and time.monotonic() - t0 > 5:
            aviso(f"AVISO: el PC {ip} no responde al ping: solo se vigila el terminal")
            avisado = True
        if motivo:
            aviso(f"CORTE: {motivo} -> salgo como con q")
            g["on_press"]("q")
            return
        time.sleep(0.2)


def aplicar_parches():
    ms.MotionSwitcher.Enter_Debug_Mode = rehusar_debug
    Brazos.__init__ = init_brazos
    Brazos._ctrl_motor_state = publicar
    Brazos.ctrl_dual_arm = ctrl_brazos
    Brazos.ctrl_dual_arm_go_home = salida
    robot_hand_inspire.Inspire_Controller_FTP.__init__ = init_mano
    robot_hand_inspire.Inspire_Controller_FTP._send_hand_command = enviar_mano


def comprobar_argumentos(argv):
    # Sin --motion el teleop de Unitree llamaria a ReleaseMode() antes de crear nada: hay que pararlo aqui
    if "-h" in argv or "--help" in argv:
        return
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--arm", default="G1_29")
    p.add_argument("--motion", action="store_true")
    a, _ = p.parse_known_args(argv)
    if a.arm != "G1_29":
        sys.exit(f"lanzar_teleop: este lanzador es solo para el G1 (--arm=G1_29), no para --arm={a.arm}")
    if not a.motion:
        sys.exit("lanzar_teleop: falta --motion. Sin el, el teleop de Unitree quita la locomocion (ReleaseMode) "
                 "y el G1 de pie se caeria. arrancar.sh ya lo pasa.")


if __name__ == "__main__":
    comprobar_argumentos(sys.argv[1:])
    # Antes de que se cree ningun proceso: el SIG_IGN lo heredan todos los hijos, por fork o por exec
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    # Precarga PIL y TODOS sus plugins antes de que televuer haga fork() del proceso de Vuer: si no, el hijo
    # hereda el cerrojo de importacion tomado por otro hilo y se bloquea al importar PngImagePlugin en el
    # primer JPEG que manda a las gafas (visto con py-spy el 2026-09-25 en el H1-2).
    from PIL import Image as _PIL_Image; _PIL_Image.init()
    aviso("modelo de la IK: " + modelo_ik.escribir_cache(TELEOP))
    aplicar_parches()
    threading.Thread(target=vigilar_conexion, name="vigilar_conexion", daemon=True).start()
    sys.argv = ["teleop_hand_and_arm.py"] + sys.argv[1:]
    runpy.run_path(SCRIPT, run_name="__main__")
