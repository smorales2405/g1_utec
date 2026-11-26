"""Enlace Modbus TCP con UNA mano, en su propio hilo. No depende de Qt (se usa igual desde las pruebas).

Todo el Modbus de la mano pasa por este hilo: la interfaz solo deja ordenes (angulos, velocidad, borrar error) y
recibe el estado por una funcion. Asi, si la WiFi se atasca, el que espera es este hilo y no la ventana.

  - "Conectada" quiere decir que la mano contesto, no solo que se abrio el socket: por el tunel SSH el puerto local
    acepta siempre, aunque la mano no responda.
  - Al conectar por primera vez se lee SPEED_SET. Si la interfaz la cambia, al soltar la mano se vuelve a escribir
    la de antes: el teleop no manda velocidad y la encontraria cambiada.
  - Los grados de libertad de `fijos` (p. ej. la rotacion del pulgar, 5) se mandan SIEMPRE con el angulo que
    MEDIA la mano (ANGLE_ACT) al conectar la primera vez: como ya esta ahi, no se mueven. ANGLE_SET no sirve para
    esto: en las RH56E2 del G1 no devuelve la consigna (2026-11-26, con las dos manos abiertas a ~1000 leia
    [0, 0, 0, 0, 0, 208] y [0, 0, 0, 0, 0, 160]).
  - Si se cae, reintenta cada segundo. Lo que la mano tenia mandado, lo mantiene. Un gesto que no llego a salir se
    descarta: si no, la mano lo haria al volver la conexion, quiza mucho despues y sin que nadie lo espere.
"""
import logging
import threading
import time

from pymodbus.client import ModbusTcpClient

from . import registros as R

FALLOS_PARA_CAER = 3   # lecturas seguidas fallidas antes de dar la mano por perdida

# pymodbus escribe en la terminal cada reintento de conexion; los fallos ya llegan a la interfaz como eventos
logging.getLogger("pymodbus").setLevel(logging.CRITICAL)


class ErrorModbus(RuntimeError):
    pass


class EnlaceMano:
    def __init__(self, lado, host, puerto, al_estado=None, al_evento=None, hz=10.0, timeout=1.0):
        """lado: 'izq' o 'der'. al_estado(lado, dict) y al_evento(lado, tipo, texto) se llaman desde ESTE hilo.

        Tipos de evento: 'conectando', 'conectada', 'caida', 'aviso', 'soltada'.
        """
        self.lado, self.host, self.puerto = lado, host, puerto
        self._al_estado = al_estado or (lambda *a: None)
        self._al_evento = al_evento or (lambda *a: None)
        self._periodo = 1.0 / hz
        self._timeout = timeout
        self._cli = None
        self._hilo = None
        self._parar = threading.Event()
        self._restaurar = True
        self._cerrojo = threading.Lock()
        self._pendiente = {}              # 'angulos' -> [6], 'velocidad' -> [6], 'borrar' -> True
        self.conectada = False
        self.velocidad_original = None    # SPEED_SET leida al conectar la primera vez
        self._velocidad_cambiada = False
        self.consigna = None              # ultimo ANGLE_SET escrito (leerlo de la mano no sirve: ver arriba)
        self.fijos = set()                # DOF que no se mueven
        self.sujecion = None              # ANGLE_ACT al conectar la primera vez: lo que se manda a los DOF fijos
        self._fallos = 0
        self._vuelta = 0
        self._lento = None                # temperatura y velocidad, que se leen una vuelta de cada 5

    # ── Lo que llama la interfaz (cualquier hilo) ────────────────────────────

    def iniciar(self):
        if self._hilo and self._hilo.is_alive():
            return
        self._parar.clear()
        self._hilo = threading.Thread(target=self._bucle, name=f"mano-{self.lado}", daemon=True)
        self._hilo.start()

    def mandar_angulos(self, valores):
        """Deja el ANGLE_SET para la vuelta siguiente del hilo; los DOF de `fijos` llevan el angulo que median al
        conectar. Devuelve los 6 valores que se van a escribir, o None si no se manda nada (mano sin conexion)."""
        valores = [int(max(0, min(1000, v))) for v in valores]
        if len(valores) != 6:
            raise ValueError("ANGLE_SET son 6 valores")
        with self._cerrojo:
            if not self.conectada or self._parar.is_set() or self.sujecion is None:
                return None
            for i in self.fijos:
                valores[i] = self.sujecion[i]
            self._pendiente["angulos"] = valores
        return valores

    def mandar_velocidad(self, velocidad):
        valores = [velocidad] * 6 if isinstance(velocidad, int) else list(velocidad)
        with self._cerrojo:
            self._pendiente["velocidad"] = [int(max(0, min(1000, v))) for v in valores]

    def borrar_error(self):
        with self._cerrojo:
            if not self.conectada or self._parar.is_set():
                return False
            self._pendiente["borrar"] = True
        return True

    def soltar(self, restaurar_velocidad=True, espera=4.0):
        """Para el hilo: deja la velocidad como estaba (si se cambio) y cierra la conexion."""
        self._restaurar = restaurar_velocidad
        self._parar.set()
        if self._hilo:
            self._hilo.join(espera)

    @property
    def activo(self):
        return bool(self._hilo and self._hilo.is_alive())

    # ── El hilo ───────────────────────────────────────────────────────────────

    def _bucle(self):
        try:
            while not self._parar.is_set():
                if not self.conectada:
                    if not self._conectar():
                        self._parar.wait(1.0)
                        continue
                t0 = time.monotonic()
                try:
                    self._escribir_pendientes()
                    estado = self._leer_estado()
                except Exception as e:     # pymodbus da errores de varios tipos al caerse el enlace
                    self._fallos += 1
                    if self._fallos >= FALLOS_PARA_CAER:
                        self._caer(f"sin respuesta: {e}")
                    continue
                self._fallos = 0
                estado["ms"] = (time.monotonic() - t0) * 1000.0
                self._al_estado(self.lado, estado)
                self._parar.wait(max(0.0, self._periodo - (time.monotonic() - t0)))
        finally:
            self._final()

    def _conectar(self):
        self._al_evento(self.lado, "conectando", f"{self.host}:{self.puerto}")
        self._cerrar_cliente()
        try:
            cli = ModbusTcpClient(self.host, port=self.puerto, timeout=self._timeout, retries=1)
            if not cli.connect():
                raise ErrorModbus("no se abre la conexión")
            self._cli = cli
            velocidad = self._leer(R.SPEED_SET, 6)   # la primera lectura dice si la mano contesta de verdad
            angulo = [max(0, min(1000, a)) for a in R.con_signo(self._leer(R.ANGLE_ACT, 6))]
        except Exception as e:
            self._cerrar_cliente()
            self._al_evento(self.lado, "caida", str(e))
            return False
        if self.velocidad_original is None:
            self.velocidad_original = velocidad
        with self._cerrojo:
            if self.sujecion is None:            # tras una caida se sigue con la de la primera vez
                self.sujecion = angulo
        self.conectada, self._fallos = True, 0
        self._al_evento(self.lado, "conectada", f"velocidad {R.texto_bloque(velocidad)}")
        return True

    def _caer(self, motivo):
        self.conectada = False
        self._cerrar_cliente()
        with self._cerrojo:                      # la velocidad si se queda: no mueve nada
            descartado = [self._pendiente.pop(k) for k in ("angulos", "borrar") if k in self._pendiente]
        if descartado:
            motivo += " (orden sin enviar descartada)"
        self._al_evento(self.lado, "caida", motivo)

    def _final(self):
        if self._restaurar and self._velocidad_cambiada and self.velocidad_original is not None:
            try:
                if not self.conectada:
                    self._conectar_para_restaurar()
                self._escribir(R.SPEED_SET, self.velocidad_original)
                self._velocidad_cambiada = False
                self._al_evento(self.lado, "aviso", f"velocidad restaurada a {R.texto_bloque(self.velocidad_original)}")
            except Exception as e:
                self._al_evento(self.lado, "aviso",
                                f"NO se pudo restaurar la velocidad {self.velocidad_original}: {e}")
        self.conectada = False
        self._cerrar_cliente()
        self._al_evento(self.lado, "soltada", "")

    def _conectar_para_restaurar(self):
        cli = ModbusTcpClient(self.host, port=self.puerto, timeout=self._timeout, retries=1)
        if not cli.connect():
            raise ErrorModbus("no se abre la conexión")
        self._cli = cli

    def _cerrar_cliente(self):
        if self._cli is not None:
            try:
                self._cli.close()
            except Exception:
                pass
        self._cli = None

    # ── Modbus ────────────────────────────────────────────────────────────────

    def _leer(self, direccion, n):
        r = self._cli.read_holding_registers(direccion, n, slave=R.ID_MANO)
        if r.isError():
            raise ErrorModbus(f"lectura de {direccion}: {r}")
        if len(r.registers) != n:
            raise ErrorModbus(f"lectura de {direccion}: {len(r.registers)} registros de {n}")
        return list(r.registers)

    def _escribir(self, direccion, valores):
        r = self._cli.write_registers(direccion, [int(v) & 0xFFFF for v in valores], slave=R.ID_MANO)
        if r.isError():
            raise ErrorModbus(f"escritura en {direccion}: {r}")

    def _escribir_pendientes(self):
        with self._cerrojo:
            pendiente, self._pendiente = self._pendiente, {}
        try:
            if "borrar" in pendiente:
                self._escribir(R.CLEAR_ERROR, [1])
                del pendiente["borrar"]
                self._al_evento(self.lado, "aviso", "error borrado (registro 1004)")
            if "velocidad" in pendiente:
                self._escribir(R.SPEED_SET, pendiente["velocidad"])
                self._velocidad_cambiada = pendiente["velocidad"] != self.velocidad_original
                del pendiente["velocidad"]
            if "angulos" in pendiente:
                self._escribir(R.ANGLE_SET, pendiente["angulos"])   # SIEMPRE el bloque de 6
                self.consigna = pendiente.pop("angulos")
        except Exception:
            # lo que no se pudo escribir se reintenta en la vuelta siguiente, salvo que haya llegado algo mas nuevo
            with self._cerrojo:
                for k, v in pendiente.items():
                    self._pendiente.setdefault(k, v)
            raise

    def _leer_estado(self):
        # De uno en uno, por bloques de 6 como manos.py: en el H1-2, leer 1546..1620 de una vez daba basura.
        # La temperatura y la velocidad cambian poco: una vuelta de cada 5.
        if self._lento is None or self._vuelta % 5 == 0:
            self._lento = {"temp": R.a_bytes(self._leer(R.TEMP, 3)), "velocidad": self._leer(R.SPEED_SET, 6)}
        estado = {
            "angulo": R.con_signo(self._leer(R.ANGLE_ACT, 6)),
            "fuerza": R.con_signo(self._leer(R.FORCE_ACT, 6)),
            "error": R.a_bytes(self._leer(R.ERROR, 3)),
            "status": R.a_bytes(self._leer(R.STATUS, 3)),
            **self._lento,
            "consigna": self.consigna,
        }
        self._vuelta += 1
        return estado
