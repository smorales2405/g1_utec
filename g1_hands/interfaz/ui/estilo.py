"""Hoja de estilo: la de la Interfaz de la RH56DFTP (inspire_hand_interface/Interfaz/main.py), con los botones de
gesto de su gesture_panel.py."""

HOJA = """
QMainWindow, QWidget { background-color: #ECEFF1; }
QGroupBox {
    font-weight: bold;
    border: 1px solid #BDBDBD;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
    background-color: #FFFFFF;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #37474F; }
QGroupBox QWidget { background-color: #FFFFFF; }
QLabel { background-color: transparent; }
QSlider::groove:horizontal { height: 6px; background: #CFD8DC; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -5px 0; background: #1565C0; border-radius: 8px; }
QSlider::handle:horizontal:disabled { background: #B0BEC5; }
QSlider::sub-page:horizontal { background: #90CAF9; border-radius: 3px; }
QProgressBar {
    border: 1px solid #CFD8DC; border-radius: 3px; background: #F5F5F5; text-align: center; height: 16px;
}
QProgressBar::chunk { background-color: #90CAF9; border-radius: 2px; }
"""

BOTON_GESTO = (
    "QPushButton {"
    "  background-color: #E3F2FD; border: 1px solid #90CAF9; border-radius: 4px; padding: 4px 8px;"
    "}"
    "QPushButton:hover   { background-color: #BBDEFB; }"
    "QPushButton:pressed { background-color: #64B5F6; }"
    "QPushButton:disabled { background-color: #F5F5F5; color: #9E9E9E; border-color: #E0E0E0; }"
)

BOTON_SECUNDARIO = (
    "QPushButton {"
    "  background-color: #FFF3E0; border: 1px solid #FFCC80; border-radius: 4px; padding: 4px 8px;"
    "}"
    "QPushButton:hover   { background-color: #FFE0B2; }"
    "QPushButton:disabled { background-color: #F5F5F5; color: #9E9E9E; border-color: #E0E0E0; }"
)

VERDE, ROJO, GRIS, NARANJA, AZUL = "#4CAF50", "#F44336", "#9E9E9E", "#FF9800", "#1565C0"


def boton_conectar(conectado):
    color = ROJO if conectado else VERDE
    return f"QPushButton {{ background-color:{color}; color:white; border-radius:4px; padding:5px 10px; }}" \
           "QPushButton:disabled { background-color:#B0BEC5; }"
