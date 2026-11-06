# TPC Universal Licence Generator

**Author:** Mishal Mohanlal  
**Version:** 0.1.0  
**Company:** The Project Company (Mining and Infrastructure)

Fully offline annual licensing for Python engineering applications. The licence is **locked to one machine and one GitHub repository NAME**, not `owner/repository`. The first target application is `smlz_to_robot`; any new project can integrate the same library.

## What is included

- Dark-themed, company-branded **PySide6** admin GUI.
- Signed `.lic` files using **Ed25519** digital signatures.
- Admin private key **encrypted with a password** and kept OUT of the client applications.
- Exportable `.pem` **public** verification key for client applications.
- A reusable, GUI-independent `tpc_licensing` Python package.
- Reusable Qt activation dialog that displays/copies the local machine ID, imports a licence and reports activation.
- Windows build script and GitHub Actions workflow for a standalone EXE.
- Automated signing, expiry, product-isolation, tampering and machine-binding tests.

## Installation and launch (Windows)

Install Python 3.10+ and run:

```powershell
py -3 -m pip install -e ".[gui]"
py -3 run_admin.py
```

Or double-click **`build_windows.bat`**. It creates `dist\TPC_Licence_Generator.exe` on a Windows machine with Python and internet access for the initial dependency installation. The **built EXE works offline**, including on computers without Python.

The GitHub Actions **Build Windows licence generator** workflow also builds a Windows EXE. In the repository, open **Actions**, select that workflow, run it (or use the latest completed build), then download the `TPC_Licence_Generator_Windows_v0.1.0` **artifact**. Unzip and run the EXE. Builds are artifacts, not automatically created Releases.

## First-time admin setup

1. Open the admin GUI. Enter a strong signing-key password (at least 12 characters), confirm it, and click **Create Signing Key**. By default it saves under `%APPDATA%\TPC\Licensing\admin_private_key.pem`.
2. Back up the encrypted signing-key PEM AND remember its password. **Never add the private key to GitHub or distribute it to clients.**
3. Click **Export Public Key** and save `tpc_public_key.pem`. This is the ONLY key that client applications need.
4. When a customer supplies a machine ID, enter the **repository name only** (e.g. `smlz_to_robot`), the machine ID, and select 12 months.
5. Click **Generate and Save Signed Licence** and send the `.lic` file to the customer.
6. The customer's application checks the signature, repository name, machine ID and expiry locally; no server is contacted.

The private key must remain the same across renewals, otherwise existing applications would need to ship a new public key. The signing key is NOT embedded in the admin EXE.

## Integrate licensing into a new Python project

Install the reusable package from a checkout (or build and install a wheel):

```powershell
py -3 -m pip install "C:\path\to\license_generator_tpc"
```

**Headless application (no GUI required):**

```python
from pathlib import Path
from tpc_licensing import require_licence

# Store the exported PUBLIC key as a resource beside your application.
PUBLIC_KEY = Path(__file__).resolve().parent / "tpc_public_key.pem"
require_licence("smlz_to_robot", PUBLIC_KEY)  # call BEFORE starting protected work

# Original engineering application starts here.
```

**PySide6 desktop application:**

```python
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from tpc_licensing.gui import THEME, ensure_licensed_qt

app = QApplication(sys.argv)
app.setStyleSheet(THEME)
public_key = Path(__file__).resolve().parent / "tpc_public_key.pem"
claims = ensure_licensed_qt("smlz_to_robot", public_key)
if claims is None:
    sys.exit(1)  # user cancelled activation
# Launch the original application's main window here.
```

For each **new** application, only change the repository name and include the same public key. It must match the value issued by the administrator. The owner/organisation part of a GitHub URL is NEVER included. The package supports command-line programs without installing PySide6; only the GUI needs PySide6. Bundled applications must contain the public key and validation library.

## Activation flow

The client application's activation dialog displays a hashed machine ID (for example `1234ABCD-5678EF90-1234ABCD-5678EF90`). Send it to the admin, receive a signed `.lic` file, and install it using the dialog. Valid licences are stored in the current user's application-data directory (`%LOCALAPPDATA%\TPC\Licences\<repository>.lic` on Windows).

## Security / limitations

- Licence signing uses Ed25519. Editing expiry, application name, or machine ID invalidates the signature.
- The computer ID prefers the Windows SMBIOS UUID. On unsuitable devices it falls back to Windows MachineGuid, which changes on OS reinstall. Linux fallback is supported for developer testing.
- Different hardware, some virtual machine clones or Windows reinstallations can change the ID, requiring a reissued licence.
- **Offline expiry cannot be made tamper-proof**: a user who changes the system clock or patches a distributed Python executable can potentially bypass enforcement. This is a practical commercial deterrent, not DRM with guaranteed resistance to reverse engineering.
- There is no online revocation or centrally managed activation limit. A stolen admin private key must be replaced and client public keys updated. Protect your signing-key backup.
- Two different GitHub accounts with the SAME repository name have the same application identity, as requested.

## Development checks

```powershell
py -3 -m pip install ".[test]"
py -3 -m pytest -q
```

Source files carry the author/version metadata; the admin and activation GUI footer displays them.
