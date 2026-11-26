"""Panel de UNA mano: sus gestos y la lectura de sus 6 dedos."""
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from manos import registros as R
from manos.gestos import GESTOS, PAUSA_PASOS_MS, POR_NOMBRE

from . import estilo

# Un gesto de varios pasos espera PAUSA_PASOS_MS entre paso y paso, como la Interfaz. Ademas, el paso siguiente no
# sale hasta que los dedos llegan al anterior o se paran (QUIETO_S sin moverse): a velocidad baja, 0.8 s no bastan
# y el pulgar cerraria sobre los dedos a medio camino, y un dedo que agarra algo se para sin llegar a la consigna.
CERCA = 30          # registros
QUIETO_S = 0.4
MOVIMIENTO = 3      # registros entre dos lecturas para contar como movimiento
ESPERA_MAX_PASO_S = 10.0


class PanelMano(QGroupBox):
    def __init__(self, lado, direccion_real, parent=None):
        super().__init__(f"Mano {R.NOMBRE_LADO[lado]} del robot", parent)
        self.lado = lado
        self.enlace = None
        self._ultimo = None           # ultimo estado leido
        self._pasos = []              # pasos del gesto que faltan por mandar
        self._objetivo = None         # el paso mandado por ultima vez
        self._t_paso = 0.0
        self._t_movimiento = 0.0      # ultima vez que se movio algun dedo
        self._reloj_pasos = QTimer(self)
        self._reloj_pasos.setInterval(50)
        self._reloj_pasos.timeout.connect(self._siguiente_paso)
        self._construir(direccion_real)
        self.habilitar(False)

    # ── Construccion ─────────────────────────────────────────────────────────

    def _construir(self, direccion_real):
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 12, 10, 8)
        v.setSpacing(8)

        cab = QHBoxLayout()
        self._punto = QLabel("●")
        self._punto.setFixedWidth(16)
        cab.addWidget(self._punto)
        self._conexion = QLabel()
        self._conexion.setFont(QFont("Arial", 10, QFont.Bold))
        cab.addWidget(self._conexion)
        cab.addStretch()
        ip = QLabel(direccion_real)
        ip.setStyleSheet("color:#607D8B;")
        cab.addWidget(ip)
        v.addLayout(cab)
        self.poner_conexion("Desconectada", estilo.GRIS)

        fila = QHBoxLayout()
        fila.setSpacing(6)
        self._botones = []
        for nombre, _ in GESTOS:
            b = QPushButton(nombre)
            b.setMinimumHeight(34)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(estilo.BOTON_GESTO)
            b.clicked.connect(lambda _c, n=nombre: self.ejecutar(n))
            fila.addWidget(b)
            self._botones.append(b)
        v.addLayout(fila)

        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(5)
        for col, (texto, tip) in enumerate([
                ("Dedo", ""), ("Ángulo medido", "ANGLE_ACT: 0 = cerrado, 1000 = abierto"),
                ("Consigna", "último ANGLE_SET mandado desde esta interfaz"), ("Fuerza", "FORCE_ACT, gramos-fuerza"),
                ("Estado", "STATUS de cada dedo"), ("Err", "ERROR de cada dedo (0 = sin fallo)"), ("°C", "")]):
            t = QLabel(texto)
            t.setFont(QFont("Arial", 9, QFont.Bold))
            t.setStyleSheet("color:#546E7A;")
            t.setToolTip(tip)
            g.addWidget(t, 0, col)
        self._filas = []
        for i, nombre in enumerate(R.DEDOS):
            barra = QProgressBar()
            barra.setRange(0, 1000)
            barra.setFormat("—")
            barra.setMinimumWidth(110)
            celdas = {"barra": barra}
            g.addWidget(QLabel(nombre), i + 1, 0)
            g.addWidget(barra, i + 1, 1)
            for col, clave, ancho in [(2, "consigna", 52), (3, "fuerza", 52), (5, "error", 34), (6, "temp", 30)]:
                lbl = QLabel("—")
                lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                lbl.setMinimumWidth(ancho)
                g.addWidget(lbl, i + 1, col)
                celdas[clave] = lbl
            est = QLabel("—")
            est.setMinimumWidth(140)
            g.addWidget(est, i + 1, 4)
            celdas["status"] = est
            self._filas.append(celdas)
        g.setColumnStretch(1, 1)
        v.addLayout(g)

        pie = QHBoxLayout()
        self._aviso = QLabel("")
        self._aviso.setStyleSheet("color:#607D8B;")
        self._aviso.setWordWrap(True)
        pie.addWidget(self._aviso, 1)
        self._borrar = QPushButton("Borrar error")
        self._borrar.setToolTip("Escribe 1 en CLEAR_ERROR (1004), como ./manos.sh borrar-error")
        self._borrar.setStyleSheet(estilo.BOTON_SECUNDARIO)
        self._borrar.setCursor(Qt.PointingHandCursor)
        self._borrar.clicked.connect(self._borrar_error)
        pie.addWidget(self._borrar)
        v.addLayout(pie)
        v.addStretch(1)

    # ── Lo que llama la ventana ──────────────────────────────────────────────

    def habilitar(self, si):
        for b in self._botones:
            b.setEnabled(si)
        self._borrar.setEnabled(si)
        if not si:
            self.cancelar_gesto()

    def poner_conexion(self, texto, color):
        self._conexion.setText(texto)
        self._punto.setStyleSheet(f"color:{color};")

    def avisar(self, texto):
        self._aviso.setText(texto)

    def ejecutar(self, nombre):
        """Manda el gesto a esta mano. Uno nuevo cancela los pasos que falten del anterior."""
        if not (self.enlace and self.enlace.conectada):
            return
        self.cancelar_gesto()
        pasos = [list(p) for p in POR_NOMBRE[nombre]]
        if not self._mandar(pasos.pop(0)):
            return
        self._pasos = pasos
        if pasos:
            self._reloj_pasos.start()
        self.avisar(f"gesto: {nombre}")

    def cancelar_gesto(self):
        self._pasos = []
        self._reloj_pasos.stop()

    def mostrar_estado(self, s):
        if self._ultimo is None or any(abs(a - b) > MOVIMIENTO for a, b in zip(s["angulo"], self._ultimo["angulo"])):
            self._t_movimiento = time.monotonic()
        self._ultimo = s
        for i, c in enumerate(self._filas):
            a = s["angulo"][i]
            c["barra"].setValue(max(0, min(1000, a)))
            c["barra"].setFormat(str(a))
            cons = s["consigna"]
            c["consigna"].setText("—" if cons is None else str(cons[i]))
            c["fuerza"].setText(str(s["fuerza"][i]))
            color, texto = R.ESTADOS.get(s["status"][i], (estilo.GRIS, f"código {s['status'][i]}"))
            c["status"].setText(f"<span style='color:{color}'>●</span> {texto}")
            e = s["error"][i]
            c["error"].setText(str(e))
            c["error"].setStyleSheet(f"color:{estilo.ROJO if e else '#37474F'}; font-weight:{'bold' if e else 'normal'};")
            c["error"].setToolTip(R.describir_error(e))
            c["temp"].setText(str(s["temp"][i]))
        self.poner_conexion(f"Conectada · {s['ms']:.0f} ms", estilo.VERDE)

    def limpiar(self):
        self._ultimo = None
        for c in self._filas:
            c["barra"].setValue(0)
            c["barra"].setFormat("—")
            for k in ("consigna", "fuerza", "status", "error", "temp"):
                c[k].setText("—")
                c[k].setStyleSheet("")

    # ── Interno ──────────────────────────────────────────────────────────────

    def _mandar(self, valores):
        """False si la mano no lo acepta (sin conexion, o un dedo fijo sin consigna valida)."""
        enviados = self.enlace.mandar_angulos(valores)
        self._objetivo = enviados        # con los dedos fijos ya puestos: es lo que la mano devolvera en ANGLE_SET
        self._t_paso = time.monotonic()
        return enviados is not None

    def _siguiente_paso(self):
        if not self._pasos or not (self.enlace and self.enlace.conectada):
            self.cancelar_gesto()
            return
        ahora = time.monotonic()
        transcurrido = ahora - self._t_paso
        if transcurrido < PAUSA_PASOS_MS / 1000.0:
            return
        u = self._ultimo
        leido = u is not None and u["consigna"] == self._objetivo     # la lectura es de despues de mandar el paso
        llego = leido and all(abs(a - o) <= CERCA for a, o in zip(u["angulo"], self._objetivo))
        quieto = leido and ahora - self._t_movimiento >= QUIETO_S
        if llego or quieto or transcurrido >= ESPERA_MAX_PASO_S:
            if not self._mandar(self._pasos.pop(0)) or not self._pasos:
                self.cancelar_gesto()

    def _borrar_error(self):
        if self.enlace and self.enlace.conectada:
            self.enlace.borrar_error()
