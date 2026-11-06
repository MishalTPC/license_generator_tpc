"""PySide6 desktop admin generator and reusable activation dialog.

Author: Mishal Mohanlal | Version: 0.1.0
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from .core import (AUTHOR, VERSION, LicenceError, export_public_key,
                   generate_signing_key, install_licence, issue_licence,
                   licence_location, machine_id, require_licence, save_licence)

THEME = """
QWidget { background: #11161d; color: #f8fafc; font-family: 'Segoe UI'; font-size: 12px; }
QFrame#Panel { background: #1b232e; border: 1px solid #334155; border-radius: 12px; }
QLabel#Heading { font-size: 21px; font-weight: 700; color: #ffffff; }
QLabel#Caption { color: #aebbc8; }
QLabel#Status { color: #e4bd4d; font-weight: 600; }
QLineEdit, QComboBox { padding: 9px 11px; border: 1px solid #475569;
    border-radius: 6px; background: #0b1220; color: #f8fafc; min-height: 18px; }
QLineEdit:focus, QComboBox:focus { border-color: #d1ac40; }
QPushButton { border-radius: 7px; padding: 10px 14px; background: #bd9c3b;
    color: #111827; font-weight: 700; }
QPushButton:hover { background: #e0bd56; }
QPushButton#Secondary { background: #334155; color: white; }
QPushButton#Secondary:hover { background: #475569; }
QPushButton:disabled { background: #475569; color: #94a3b8; }
"""


def _assets_path() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets"


def _header() -> QVBoxLayout:
    layout = QVBoxLayout()
    layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    file = _assets_path() / "logo.b64"
    if file.exists():
        logo = QPixmap()
        logo.loadFromData(base64.b64decode(file.read_text(encoding="ascii")))
        picture = QLabel()
        picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        picture.setPixmap(logo.scaled(460, 220, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(picture)
    else:
        title = QLabel("THE PROJECT COMPANY")
        title.setObjectName("Heading")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
    return layout


def _footer() -> QLabel:
    widget = QLabel(f"Author: {AUTHOR}   |   Version {VERSION}   |   The Project Company")
    widget.setObjectName("Caption")
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return widget


def _field(placeholder: str = "", *, secret: bool = False) -> QLineEdit:
    line = QLineEdit()
    line.setPlaceholderText(placeholder)
    if secret:
        line.setEchoMode(QLineEdit.EchoMode.Password)
    return line


def _panel(content: QVBoxLayout) -> QFrame:
    frame = QFrame()
    frame.setObjectName("Panel")
    frame.setLayout(content)
    content.setContentsMargins(20, 20, 20, 20)
    content.setSpacing(12)
    return frame


def _error(parent: QWidget, exc: Exception) -> None:
    QMessageBox.warning(parent, "TPC licensing", str(exc))


def default_key_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".tpc")
    return Path(base) / "TPC" / "Licensing" / "admin_private_key.pem"


class AdminWindow(QMainWindow):
    """Admin-only UI: generate an encrypted identity, export public key, sign."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"TPC Universal Licence Generator - v{VERSION}")
        self.resize(700, 790)
        content = QWidget()
        self.setCentralWidget(content)
        column = QVBoxLayout(content)
        column.setContentsMargins(28, 12, 28, 16)
        column.setSpacing(12)
        column.addLayout(_header())
        title = QLabel("Universal Licence Generator")
        title.setObjectName("Heading")
        column.addWidget(title)
        subtitle = QLabel("Offline, machine-locked licences for any repository name")
        subtitle.setObjectName("Caption")
        column.addWidget(subtitle)

        key_group = QVBoxLayout()
        key_label = QLabel("ADMIN SIGNING IDENTITY")
        key_label.setObjectName("Status")
        key_group.addWidget(key_label)
        self.key_path = _field("Path to encrypted signing key")
        self.key_path.setText(str(default_key_path()))
        key_group.addWidget(self.key_path)
        self.password = _field("Private-key password (minimum 12 characters)", secret=True)
        key_group.addWidget(self.password)
        self.confirm = _field("Repeat password when creating a new key", secret=True)
        key_group.addWidget(self.confirm)
        controls = QHBoxLayout()
        new_key = QPushButton("Create Signing Key")
        new_key.setObjectName("Secondary")
        new_key.clicked.connect(self.create_key)
        controls.addWidget(new_key)
        pub = QPushButton("Export Public Key")
        pub.setObjectName("Secondary")
        pub.clicked.connect(self.export_key)
        controls.addWidget(pub)
        browse = QPushButton("Open Existing Key")
        browse.setObjectName("Secondary")
        browse.clicked.connect(self.browse_key)
        controls.addWidget(browse)
        key_group.addLayout(controls)
        column.addWidget(_panel(key_group))

        licence_group = QVBoxLayout()
        lic_label = QLabel("ISSUE NEW LICENCE")
        lic_label.setObjectName("Status")
        licence_group.addWidget(lic_label)
        form = QFormLayout()
        form.setSpacing(11)
        self.repository = _field("e.g. smlz_to_robot — no GitHub account")
        self.repository.setText("smlz_to_robot")
        self.machine = _field("XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX")
        self.customer = _field("Optional name or organisation")
        self.term = QComboBox()
        for label, months in (("1 year (12 months)", 12), ("6 months", 6),
                               ("2 years (24 months)", 24), ("3 years (36 months)", 36)):
            self.term.addItem(label, months)
        form.addRow("Repository name", self.repository)
        form.addRow("Machine ID", self.machine)
        form.addRow("Customer", self.customer)
        form.addRow("Duration", self.term)
        licence_group.addLayout(form)
        issue = QPushButton("Generate and Save Signed Licence (.lic)")
        issue.clicked.connect(self.create_licence)
        licence_group.addWidget(issue)
        column.addWidget(_panel(licence_group))
        self.status = QLabel("Create your signing key once, then keep it backed up and private.")
        self.status.setObjectName("Caption")
        self.status.setWordWrap(True)
        column.addWidget(self.status)
        column.addStretch(1)
        column.addWidget(_footer())

    def browse_key(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, "Open encrypted signing key", "", "PEM (*.pem);;All files (*)")
        if name:
            self.key_path.setText(name)

    def create_key(self) -> None:
        if self.password.text() != self.confirm.text():
            _error(self, LicenceError("The two passwords do not match."))
            return
        try:
            target = generate_signing_key(self.key_path.text(), self.password.text())
            self.status.setText(f"Encrypted signing identity created: {target}. Back up this key securely.")
            QMessageBox.information(self, "Key created", "Keep your encrypted private key and password safe. Losing it prevents renewing existing customers with the same public key.")
        except (LicenceError, OSError) as exc:
            _error(self, exc)

    def export_key(self) -> None:
        name, _ = QFileDialog.getSaveFileName(self, "Save public verification key", "tpc_public_key.pem", "PEM (*.pem)")
        if not name:
            return
        try:
            path = export_public_key(self.key_path.text(), self.password.text(), name)
            self.status.setText(f"Public key saved: {path}. Distribute this key with client applications.")
        except (LicenceError, OSError) as exc:
            _error(self, exc)

    def create_licence(self) -> None:
        try:
            licence = issue_licence(self.key_path.text(), self.password.text(),
                                    self.repository.text(), self.machine.text(),
                                    customer=self.customer.text(), months=self.term.currentData())
        except (LicenceError, OSError) as exc:
            _error(self, exc)
            return
        suggested = f"{licence['payload']['application']}-{licence['payload']['licence_id'][:8]}.lic"
        name, _ = QFileDialog.getSaveFileName(self, "Save signed licence", suggested, "TPC licences (*.lic)")
        if not name:
            return
        try:
            save_licence(licence, name)
            self.status.setText(f"Issued licence until {licence['payload']['expires_at']} UTC. Saved to {name}")
            QMessageBox.information(self, "Licence issued", "Signed licence saved successfully. Send only the .lic file to the user, never your private key.")
        except OSError as exc:
            _error(self, exc)


class ActivationDialog(QDialog):
    """Reusable activation UI for a licensed Python/Qt client application."""

    def __init__(self, application: str, public_key: str | Path | bytes, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.application = application
        self.public_key = public_key
        self.setWindowTitle(f"Activate {application}")
        self.resize(630, 440)
        root = QVBoxLayout(self)
        root.addLayout(_header())
        root.addWidget(QLabel(f"Application: {application}"))
        self.hardware = _field()
        self.hardware.setText(machine_id())
        self.hardware.setReadOnly(True)
        root.addWidget(QLabel("Your machine ID — send this to the administrator"))
        root.addWidget(self.hardware)
        copy = QPushButton("Copy Machine ID")
        copy.setObjectName("Secondary")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.hardware.text()))
        root.addWidget(copy)
        browse = QPushButton("Install a Signed Licence (.lic)")
        browse.clicked.connect(self.activate)
        root.addWidget(browse)
        self.status = QLabel("Offline activation. No account or internet required.")
        self.status.setObjectName("Caption")
        root.addWidget(self.status)
        root.addStretch(1)
        root.addWidget(_footer())

    def activate(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, "Select signed licence", "", "TPC licences (*.lic)")
        if not name:
            return
        try:
            dest = install_licence(name, self.public_key, self.application)
            self.status.setText(f"Licence installed to {dest}")
            QMessageBox.information(self, "Activated", "The signed licence was verified and installed.")
            self.accept()
        except (LicenceError, OSError) as exc:
            _error(self, exc)


def ensure_licensed_qt(application: str, public_key: str | Path | bytes, parent: QWidget | None = None) -> dict | None:
    """Call at Qt-app startup. Returns claims, or None when activation is cancelled."""
    try:
        return require_licence(application, public_key)
    except LicenceError:
        dialog = ActivationDialog(application, public_key, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return require_licence(application, public_key)
        return None


def run_admin() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(THEME)
    win = AdminWindow()
    win.show()
    sys.exit(app.exec())
