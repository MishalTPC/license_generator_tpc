"""Optional client demo. Author: Mishal Mohanlal; v0.1.0.

This is NOT the admin generator. Replace the repository name and public-key
path when integrating the activation dialog into a new Python application.
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from tpc_licensing.gui import THEME, ensure_licensed_qt

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(THEME)
    public_key = Path(__file__).resolve().parent / "tpc_public_key.pem"
    if not public_key.exists():
        print("First export your public key from the admin generator to tpc_public_key.pem")
        sys.exit(1)
    claims = ensure_licensed_qt("smlz_to_robot", public_key)
    if claims is None:
        sys.exit(1)
    window = QWidget()
    window.setWindowTitle("TPC licence verification demo")
    layout = QVBoxLayout(window)
    layout.addWidget(QLabel(f"Licence valid until {claims['expires_at']}"))
    window.show()
    sys.exit(app.exec())
