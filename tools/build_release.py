"""Build a clean, self-contained Windows onedir ZIP, never the developer tree."""
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from ricca_dglab import __version__


def digest(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream,"sha256").hexdigest()


def build():
    name="Ricca-x-DGlab-"+__version__+"-windows-x64"
    release=ROOT/"release"; release.mkdir(exist_ok=True)
    archive=release/(name+".zip")
    if archive.exists(): raise RuntimeError("Refusing to overwrite frozen archive: "+str(archive))
    work=ROOT/"build"/("release-"+__version__+"-"+str(time.time_ns()))
    work.mkdir(parents=True)
    subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm","--windowed","--onedir",
                    "--name","Ricca-x-DGlab","--icon",str(ROOT/"launcher/ricca-app.ico"),
                    "--version-file",str(ROOT/"launcher/version_info.txt"),
                    "--distpath",str(work/"dist"),"--workpath",str(work/"work"),"--specpath",str(work),
                    "--paths",str(ROOT/"src"),"--paths",str(ROOT),
                    "--add-data",str(ROOT/"src/ricca_dglab/qml")+";ricca_dglab/qml",
                    "--add-data",str(ROOT/"src/ricca_dglab/assets")+";ricca_dglab/assets",
                    str(ROOT/"tools/frozen_entry.py")],check=True,cwd=ROOT)
    app=work/"dist/Ricca-x-DGlab"
    # Match the proven Manaka runtime policy, pruning only named unused files
    # inside this newly-created build. No user/game directories are touched.
    for relative in ("_internal/PySide6/Qt6WebEngineCore.dll","_internal/PySide6/Qt6WebEngineQuick.dll",
                     "_internal/PySide6/Qt6WebEngineQuickDelegatesQml.dll","_internal/PySide6/Qt6WebView.dll",
                     "_internal/PySide6/Qt6WebViewQuick.dll","_internal/PySide6/Qt6Pdf.dll",
                     "_internal/PySide6/Qt6PdfQuick.dll","_internal/PySide6/qml/QtWebEngine",
                     "_internal/PySide6/qml/QtWebView","_internal/PySide6/qml/QtQuick/Pdf",
                     "_internal/icuuc.dll","_internal/icudt78.dll"):
        target=(app/relative).resolve()
        assert target.is_relative_to(app.resolve())
        if target.is_dir(): shutil.rmtree(target)
        elif target.is_file(): target.unlink()
    for filename in ("VCRUNTIME140.dll","VCRUNTIME140_1.dll","MSVCP140.dll","MSVCP140_1.dll","MSVCP140_2.dll"):
        source=app/"_internal/PySide6"/filename
        if source.exists(): shutil.copy2(source,app/"_internal"/filename)
    for filename in ("LICENSE","README.md","SECURITY.md","THIRD_PARTY_NOTICES.md","DIAGNOSTICS.md"):
        shutil.copy2(ROOT/filename,app/filename)
    packages=("PySide6","PySide6_Essentials","PySide6_Addons","shiboken6","numpy","SoundCard",
              "websockets","qrcode","Pillow","cffi","pycparser","colorama","PyInstaller")
    versions={}
    for package in packages:
        try: dist=metadata.distribution(package)
        except metadata.PackageNotFoundError: continue
        versions[package]=dist.version
        for entry in dist.files or ():
            if any(word in Path(str(entry)).name.upper() for word in ("LICENSE","COPYING","NOTICE","AUTHORS")):
                source=Path(dist.locate_file(entry))
                if source.is_file() and source.stat().st_size<2_000_000:
                    destination=app/"third-party-licenses"/package/str(entry).replace("..","_")
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(source,destination)
    python_license=Path(sys.base_prefix)/"LICENSE.txt"
    if python_license.exists():
        target=app/"third-party-licenses/Python/LICENSE.txt"; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(python_license,target)
    (app/"DEPENDENCY_VERSIONS.json").write_text(json.dumps(versions,indent=2),encoding="utf-8")
    source_files=[ROOT/"ricca_hp_smoke_test.py",ROOT/"requirements-native.txt",ROOT/"LICENSE"]
    for folder in ("src","tests","tools"):
        source_files += [p for p in (ROOT/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts
                         and p.suffix in {".py",".qml",".json",".png",".ico",".jpg",".txt"}]
    source_hashes={p.relative_to(ROOT).as_posix():digest(p) for p in source_files}
    with zipfile.ZipFile(app/"SOURCE-1.0.0.zip","w",zipfile.ZIP_DEFLATED) as bundle:
        for path in source_files: bundle.write(path,path.relative_to(ROOT).as_posix())
    (app/"BUILD_INFO.json").write_text(json.dumps({"version":__version__,"platform":"windows-x64",
        "source_sha256":source_hashes,"dependencies":versions,"game_included":False},indent=2),encoding="utf-8")
    (app/"START_HERE.txt").write_text(
        "Ricca x DG-LAB 1.0.0\n\n解压整个文件夹，双击 Ricca-x-DGlab.exe。无需安装 Python 或 BepInEx。\n"
        "首次运行先设置安全硬上限，手机与电脑同一局域网扫码连接。\n"
        "全局急停 Ctrl+Alt+F10，可在个性化范围自定义；仅归零不恢复。\n"
        "支持指定指纹的 Ricca 1.4.1 中/英文构建。不含游戏，不写游戏内存。\n"
        "配置保存在 %LOCALAPPDATA%/Ricca-x-DGlab，更新时不会覆盖。\n\n"
        "Extract the ENTIRE folder and run Ricca-x-DGlab.exe. No Python installation needed.\n"
        "Set the safety cap first. Global emergency stop: Ctrl+Alt+F10 (customizable).\n"
        "The software cap does not guarantee physical safety; follow device instructions.\n\n"
        "フォルダー全体を解凍し Ricca-x-DGlab.exe を起動。Python の別途導入は不要です。\n"
        "最初にハード上限を設定。緊急停止：Ctrl+Alt+F10（変更可能）。\n",encoding="utf-8-sig")
    # Run the packaged app with isolated user data and no socket/microphone.
    qa=work/"qa"; qa.mkdir()
    env={**os.environ,"LOCALAPPDATA":str(qa),"PYTHONPATH":"","PYTHONHOME":""}
    for page in (0,2,5,6):
        shot=qa/("packaged-page-"+str(page)+".png")
        completed=subprocess.run([str(app/"Ricca-x-DGlab.exe"),"--demo","--no-socket","--page",str(page),"--screenshot",str(shot)],env=env,timeout=40)
        if completed.returncode or not shot.exists(): raise RuntimeError("Packaged smoke test failed: "+str(page))
    with zipfile.ZipFile(archive,"x",zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for path in sorted(app.rglob("*")):
            if path.is_file(): bundle.write(path,name+"/"+path.relative_to(app).as_posix())
    info={"version":__version__,"filename":archive.name,"sha256":digest(archive),"bytes":archive.stat().st_size,
          "source_manifest_sha256":digest(app/"BUILD_INFO.json"),"packaged_smoke_pages":[0,2,5,6]}
    (release/(archive.name+".sha256")).write_text(info["sha256"]+"  "+archive.name+"\n",encoding="ascii")
    (release/"release-1.0.0.json").write_text(json.dumps(info,indent=2),encoding="utf-8")
    (work/"package-path.txt").write_text(str(app),encoding="utf-8")
    print(json.dumps({**info,"app_directory":str(app),"qa_directory":str(qa)},ensure_ascii=False),flush=True)

if __name__=="__main__": build()
