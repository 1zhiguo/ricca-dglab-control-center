"""Freeze updated QML/support files after checking compiled Python is unchanged."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def sha(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream,"sha256").hexdigest()
def main():
    app=Path(sys.argv[1]).resolve()
    if not app.is_relative_to((ROOT/"build").resolve()): raise ValueError("Not a managed build")
    build=json.loads((app/"BUILD_INFO.json").read_text(encoding="utf-8"))
    for name,digest in build["source_sha256"].items():
        if (name.startswith("src/") and name.endswith(".py")) or name=="ricca_hp_smoke_test.py":
            if sha(ROOT/name)!=digest: raise ValueError("Compiled Python changed; rebuild required: "+name)
    for filename in (ROOT/"src/ricca_dglab/qml").glob("*.qml"):
        shutil.copy2(filename,app/"_internal/ricca_dglab/qml"/filename.name)
    for name in ("README.md","SECURITY.md","DIAGNOSTICS.md","THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT/name,app/name)
    files=[ROOT/"ricca_hp_smoke_test.py",ROOT/"requirements-native.txt",ROOT/"LICENSE"]
    for folder in ("src","tests","tools"):
        files += [p for p in (ROOT/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts
                  and p.suffix in {".py",".qml",".json",".png",".ico",".jpg",".txt"}]
    build["source_sha256"]={p.relative_to(ROOT).as_posix():sha(p) for p in files}
    with zipfile.ZipFile(app/"SOURCE-1.0.0.zip","w",zipfile.ZIP_DEFLATED) as source:
        for path in files: source.write(path,path.relative_to(ROOT).as_posix())
    (app/"BUILD_INFO.json").write_text(json.dumps(build,indent=2),encoding="utf-8")
    qa=app.parent.parent/"final-qa"; qa.mkdir(exist_ok=True)
    env={**os.environ,"LOCALAPPDATA":str(qa),"PYTHONPATH":"","PYTHONHOME":""}
    for page in (0,2,5,6):
        shot=qa/("packaged-page-"+str(page)+".png")
        result=subprocess.run([str(app/"Ricca-x-DGlab.exe"),"--demo","--no-socket","--page",str(page),"--screenshot",str(shot)],env=env,timeout=40)
        if result.returncode or not shot.exists(): raise RuntimeError("Final packaged smoke failed")
    release=ROOT/"release"; name="Ricca-x-DGlab-1.0.0-windows-x64"
    archive=release/(name+".zip")
    preserved=app.parent.parent/("candidate-before-final-qml-"+str(time.time_ns())+".zip")
    archive.rename(preserved)
    with zipfile.ZipFile(archive,"x",zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for path in sorted(app.rglob("*")):
            if path.is_file(): bundle.write(path,name+"/"+path.relative_to(app).as_posix())
    info={"version":"1.0.0","filename":archive.name,"sha256":sha(archive),"bytes":archive.stat().st_size,
          "source_manifest_sha256":sha(app/"BUILD_INFO.json"),"packaged_smoke_pages":[0,2,5,6],"signed":False}
    (release/(archive.name+".sha256")).write_text(info["sha256"]+"  "+archive.name+"\n",encoding="ascii")
    (release/"release-1.0.0.json").write_text(json.dumps(info,indent=2),encoding="utf-8")
    print(json.dumps(info),flush=True)
if __name__=="__main__": main()
