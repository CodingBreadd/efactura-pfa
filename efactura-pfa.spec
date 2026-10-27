# PyInstaller build for the Windows .exe:  pyinstaller efactura-pfa.spec
# Output: dist/efactura-pfa.exe (single file, console window shows the app is running)
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ["efactura/__main__.py"],
    pathex=[SPECPATH],
    datas=[("efactura/templates", "efactura/templates")],
    hiddenimports=["efactura.app"] + collect_submodules("uvicorn"),
    excludes=["tkinter", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="efactura-pfa",
    console=True,
    upx=False,
)
