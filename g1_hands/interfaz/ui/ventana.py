"""Ventana principal: conexion (con la comprobacion del teleop), gestos para las dos manos, velocidad y un panel por
mano."""
from PyQt5.QtCore import QObject, QProcess, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QApplication, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QPushButton, QSlider,
                             QVBoxLayout, QWidget)

from manos import registros as R
from manos import robot
from manos.enlace import EnlaceMano
from manos.gestos import GESTOS

from . import estilo
from .panel_mano import PanelMano

COMPROBAR_CADA_MS = 2000   # el driver del teleop se rinde a los 10 s sin la mano: soltarla mucho antes


class Puente(QObject):
    """Lleva al hilo de la ventana lo que los hilos de las manos cuentan."""
    estado = pyqtSignal(str, dict)
    evento = pyqtSignal(str, str, str)


class Ventana(QMainWindow):
    def __init__(self, direcciones, direcciones_reales, control=None, robot_ssh=None, titulo=""):
        """direcciones: {'izq': (host, puerto), 'der': ...} a las que se conecta (el tunel, o las falsas).
        direcciones_reales: el texto que se muestra en cada panel. control/robot_ssh: el ControlMaster del tunel;
        sin el, no se comprueba el teleop (manos falsas)."""
        super().__init__()
        self.direcciones = direcciones
        self.control, self.robot_ssh = control, robot_ssh
        self.enlaces = {}
        self._soltando = set()
        self._cerrando = False
        self._velocidad_puesta = False    # el slider ya tomo la velocidad de una mano
        self._vel_movida = False          # el usuario movio el slider
        self._puente = Puente()
        self._puente.estado.connect(self._al_estado)
        self._puente.evento.connect(self._al_evento)
        self._proceso = None
        self._tras_comprobar = None
        self._reloj = QTimer(self)
        self._reloj.setInterval(COMPROBAR_CADA_MS)
        self._reloj.timeout.connect(lambda: self._comprobar(None))
        self._reloj_vel = QTimer(self)
        self._reloj_vel.setSingleShot(True)
        self._reloj_vel.setInterval(250)
        self._reloj_vel.timeout.connect(self._mandar_velocidad)

        self.setWindowTitle("Manos RH56E2 del G1 — Gestos" + (f"  ({titulo})" if titulo else ""))
        self.setMinimumSize(1180, 560)
        central = QWidget()
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(10, 8, 10, 8)
        raiz.setSpacing(8)
        raiz.addWidget(self._construir_conexion(titulo))
        raiz.addWidget(self._construir_ambas())
        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(10)
        self.paneles = {}
        for lado in ("izq", "der"):
            self.paneles[lado] = PanelMano(lado, direcciones_reales[lado])
            cuerpo.addWidget(self.paneles[lado], 1)
        raiz.addLayout(cuerpo, 1)
        self.setCentralWidget(central)
        self._habilitar(False)
        self.statusBar().showMessage("Desconectado. Las manos no se mueven hasta pulsar un gesto.")

    # ── Construccion ─────────────────────────────────────────────────────────

    def _construir_conexion(self, titulo):
        grp = QGroupBox("Conexión")
        fila = QHBoxLayout(grp)
        fila.setContentsMargins(10, 4, 10, 6)
        if self.control:
            destino = f"Robot <b>{self.robot_ssh}</b> por túnel SSH (WiFi)"
        else:
            destino = f"<b>{titulo or 'sin robot'}</b> · sin comprobación del teleop"
        fila.addWidget(QLabel(destino))
        fila.addSpacing(16)
        self._teleop = QLabel("")
        self._teleop.setWordWrap(True)
        fila.addWidget(self._teleop, 1)
        self._boton = QPushButton("Conectar")
        self._boton.setFont(QFont("Arial", 10, QFont.Bold))
        self._boton.setFixedWidth(130)
        self._boton.setCursor(Qt.PointingHandCursor)
        self._boton.setStyleSheet(estilo.boton_conectar(False))
        self._boton.clicked.connect(self._conectar_o_soltar)
        fila.addWidget(self._boton)
        return grp

    def _construir_ambas(self):
        grp = QGroupBox("Las dos manos")
        fila = QHBoxLayout(grp)
        fila.setContentsMargins(10, 4, 10, 6)
        fila.setSpacing(6)
        self._botones_ambas = []
        for nombre, _ in GESTOS:
            b = QPushButton(nombre)
            b.setMinimumHeight(34)
            b.setMinimumWidth(96)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(estilo.BOTON_GESTO)
            b.clicked.connect(lambda _c, n=nombre: self._gesto_ambas(n))
            fila.addWidget(b)
            self._botones_ambas.append(b)
        fila.addSpacing(20)
        caja = QVBoxLayout()
        caja.setSpacing(2)
        fila_vel = QHBoxLayout()
        titulo_vel = QLabel("Velocidad")
        titulo_vel.setFont(QFont("Arial", 10, QFont.Bold))
        fila_vel.addWidget(titulo_vel)
        fila_vel.addSpacing(12)
        fila_vel.addWidget(QLabel("Lento"))
        self._vel = QSlider(Qt.Horizontal)
        self._vel.setRange(100, 1000)
        self._vel.setSingleStep(50)
        self._vel.setPageStep(100)
        self._vel.setValue(1000)
        self._vel.setMinimumWidth(180)
        self._vel.valueChanged.connect(self._al_mover_velocidad)
        fila_vel.addWidget(self._vel, 1)
        fila_vel.addWidget(QLabel("Rápido"))
        self._vel_valor = QLabel("—")
        self._vel_valor.setMinimumWidth(36)
        self._vel_valor.setFont(QFont("Arial", 10, QFont.Bold))
        fila_vel.addWidget(self._vel_valor)
        caja.addLayout(fila_vel)
        self._vel_nota = QLabel("SPEED_SET de las dos manos")
        self._vel_nota.setStyleSheet("color:#607D8B; font-size:9pt;")
        caja.addWidget(self._vel_nota)
        fila.addLayout(caja, 1)
        return grp

    # ── Conectar y soltar ────────────────────────────────────────────────────

    def _conectar_o_soltar(self):
        if self.enlaces:
            self._soltar("pedido")
            return
        self._boton.setEnabled(False)
        self._comprobar(self._conectar)

    def _conectar(self, libre, texto):
        if libre is False:
            self._boton.setEnabled(True)
            self._avisar_teleop(f"No se conecta: {texto}. Para el teleop antes: ./teleop_xr.sh parar", estilo.ROJO)
            return
        if libre is None:
            self._boton.setEnabled(True)
            self._avisar_teleop(f"No se conecta: {texto}", estilo.ROJO)
            return
        self._velocidad_puesta = self._vel_movida = False
        self._vel_nota.setText("SPEED_SET de las dos manos")
        for lado, (host, puerto) in self.direcciones.items():
            e = EnlaceMano(lado, host, puerto, self._puente.estado.emit, self._puente.evento.emit)
            self.enlaces[lado] = e
            self.paneles[lado].enlace = e
            e.iniciar()
        self._boton.setText("Desconectar")
        self._boton.setStyleSheet(estilo.boton_conectar(True))
        self._boton.setEnabled(True)
        if self.control:
            self._reloj.start()
        self.statusBar().showMessage("Conectando con las manos…")

    def _soltar(self, motivo):
        """Suelta las dos manos (restaurando la velocidad) sin bloquear la ventana: el evento 'soltada' termina."""
        self._reloj.stop()
        self._reloj_vel.stop()
        self._habilitar(False)
        self._boton.setEnabled(False)
        self._soltando = set(self.enlaces)
        for e in self.enlaces.values():
            e.soltar(espera=0)
        self.statusBar().showMessage(f"Soltando las manos ({motivo})…")

    def _terminar_soltar(self):
        self.enlaces = {}
        for p in self.paneles.values():
            p.enlace = None
            p.poner_conexion("Desconectada", estilo.GRIS)
            p.limpiar()
        self._boton.setText("Conectar")
        self._boton.setStyleSheet(estilo.boton_conectar(False))
        self._boton.setEnabled(True)
        self._vel_valor.setText("—")
        self.statusBar().showMessage("Desconectado.")
        if self._cerrando:
            self.close()

    # ── Comprobacion del teleop ──────────────────────────────────────────────

    def _comprobar(self, despues):
        """Pregunta al robot (asincrono) si corre el teleop o su driver; luego llama a despues(libre, texto)."""
        if not self.control:
            if despues:
                despues(True, "")
            return
        if self._proceso is not None:          # sigue la anterior
            if despues:
                self._tras_comprobar = despues
            return
        self._tras_comprobar = despues
        if despues:
            self._avisar_teleop("Comprobando el robot…", estilo.GRIS)
        argv = robot.comando(self.control, self.robot_ssh)
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.finished.connect(lambda codigo, _estado, p=p: self._comprobado(p, codigo))
        p.errorOccurred.connect(lambda _e, p=p: self._comprobado(p, -1) if p.state() == QProcess.NotRunning else None)
        self._proceso = p
        p.start(argv[0], argv[1:])
        limite = QTimer(p)               # hijo del proceso: muere con el
        limite.setSingleShot(True)
        limite.timeout.connect(p.kill)
        limite.start(8000)

    def _comprobado(self, p, codigo):
        if p is not self._proceso:
            return
        self._proceso = None
        salida = bytes(p.readAll()).decode(errors="replace")
        p.deleteLater()
        libre, texto = robot.interpretar(codigo, salida)
        despues, self._tras_comprobar = self._tras_comprobar, None
        if libre is True:
            self._avisar_teleop(f"✓ {texto}", estilo.VERDE)
        elif libre is False:
            self._avisar_teleop(f"⚠ {texto}", estilo.ROJO)
        else:
            self._avisar_teleop(f"⚠ {texto}", estilo.NARANJA)
        if despues:
            despues(libre, texto)
        elif libre is False and self.enlaces and not self._soltando:
            # el teleop ha arrancado con la interfaz conectada: soltarle las manos
            self._soltar("el teleop está usando las manos")
            self._avisar_teleop(f"⚠ {texto}: manos soltadas para el teleop", estilo.ROJO)

    def _avisar_teleop(self, texto, color):
        self._teleop.setText(texto)
        self._teleop.setStyleSheet(f"color:{color}; font-weight:bold;")

    # ── Lo que llega de las manos ────────────────────────────────────────────

    def _al_estado(self, lado, s):
        if lado not in self.enlaces or lado in self._soltando:
            return
        self.paneles[lado].mostrar_estado(s)

    def _al_evento(self, lado, tipo, texto):
        panel = self.paneles[lado]
        if tipo == "conectando":
            if lado not in self._soltando:
                panel.poner_conexion("Conectando…", estilo.NARANJA)
        elif tipo == "conectada":
            if lado in self._soltando or lado not in self.enlaces:
                return
            panel.habilitar(True)
            self._actualizar_ambas()
            panel.avisar(texto)
            self._poner_slider_velocidad(lado)
            self.statusBar().showMessage(f"Mano {R.NOMBRE_LADO[lado]} conectada.")
        elif tipo == "caida":
            panel.habilitar(False)
            self._actualizar_ambas()
            if lado not in self._soltando:
                panel.poner_conexion("Sin respuesta (reintentando)", estilo.ROJO)
            panel.avisar(texto)
        elif tipo == "aviso":
            panel.avisar(texto)
            self.statusBar().showMessage(f"Mano {R.NOMBRE_LADO[lado]}: {texto}")
        elif tipo == "soltada":
            self._soltando.discard(lado)
            if not self._soltando:
                self._terminar_soltar()

    # ── Gestos y velocidad ───────────────────────────────────────────────────

    def _gesto_ambas(self, nombre):
        for p in self.paneles.values():
            p.ejecutar(nombre)

    def _habilitar(self, si):
        for p in self.paneles.values():
            p.habilitar(si)
        for b in self._botones_ambas:
            b.setEnabled(si)
        self._vel.setEnabled(si)

    def _actualizar_ambas(self):
        alguna = any(e.conectada for e in self.enlaces.values()) and not self._soltando
        for b in self._botones_ambas:
            b.setEnabled(alguna)
        self._vel.setEnabled(alguna)

    def _poner_slider_velocidad(self, lado):
        """Al conectar una mano. El slider arranca en la velocidad de la primera; si ya se habia movido, la mano
        que llega tarde (o vuelve tras caerse) recibe la del slider."""
        e = self.enlaces[lado]
        if not self._velocidad_puesta:
            self._velocidad_puesta = True
            self._vel.blockSignals(True)
            self._vel.setValue(max(100, min(1000, e.velocidad_original[0])))
            self._vel.blockSignals(False)
            self._vel_valor.setText(str(self._vel.value()))
        elif self._vel_movida:
            e.mandar_velocidad(self._vel.value())
        orig = {l: x.velocidad_original for l, x in self.enlaces.items() if x.velocidad_original}
        texto = " · ".join(f"{l} {R.texto_bloque(v)}" for l, v in orig.items())
        self._vel_nota.setText(f"Al desconectar vuelve a la de antes: {texto}")

    def _al_mover_velocidad(self, v):
        self._vel_valor.setText(str(v))
        self._vel_movida = True
        self._reloj_vel.start()          # se manda 250 ms despues del ultimo movimiento

    def _mandar_velocidad(self):
        for e in self.enlaces.values():
            if e.conectada:
                e.mandar_velocidad(self._vel.value())

    # ── Cierre ───────────────────────────────────────────────────────────────

    def closeEvent(self, ev):
        if self.enlaces:
            # primero soltar las manos (restaurar la velocidad); la ventana se cierra cuando lo hayan hecho
            self._cerrando = True
            if not self._soltando:
                self._soltar("cerrando")
            QTimer.singleShot(6000, self._forzar_cierre)
            ev.ignore()
            return
        if self._proceso is not None:
            self._proceso.kill()
        ev.accept()

    def _forzar_cierre(self):
        self.enlaces = {}
        QApplication.instance().quit()
