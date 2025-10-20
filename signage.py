#!/usr/bin/env python3
import os, time, subprocess, socket, json, hashlib, pathlib

MOUNT = "/mnt/box"
IPCSOCK = "/tmp/mpv-signage.sock"
PLAYLIST = "/home/pi/playlist.m3u"
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}

def wait_for_mount(path, timeout=None):
    start = time.time()
    while not (os.path.ismount(path) or os.path.isdir(path) and os.listdir(path) is not None):
        if timeout and time.time()-start > timeout:
            break
        time.sleep(1)

def scan_files(root):
    files = []
    for p in pathlib.Path(root).rglob("*"):
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            files.append(str(p))
    files.sort()
    return files

def write_playlist(paths, pl):
    with open(pl, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(p + "\n")

def sha(paths):
    h = hashlib.sha1()
    for p in paths:
        h.update(p.encode())
        try:
            h.update(str(os.path.getmtime(p)).encode())
        except Exception:
            pass
    return h.hexdigest()

def start_mpv(ipc, playlist):
    # Ensure old socket is gone
    try: os.unlink(ipc)
    except FileNotFoundError: pass
    cmd = [
        "/usr/bin/mpv",
        "--fs",
        "--no-osc", "--no-osd-bar",
        "--really-quiet",
        "--loop-playlist=inf",
        "--idle=yes",
        f"--input-ipc-server={ipc}",
        f"--playlist={playlist}",
    ]
    return subprocess.Popen(cmd)

def mpv_loadlist(ipc, playlist):
    msg = {"command": ["loadlist", playlist, "replace"]}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        s.connect(ipc)
        s.send((json.dumps(msg) + "\n").encode())

def main():
    wait_for_mount(MOUNT)
    files = scan_files(MOUNT)
    write_playlist(files, PLAYLIST)
    last = sha(files)
    proc = start_mpv(IPCSOCK, PLAYLIST)

    try:
        while True:
            time.sleep(15)  # poll for changes
            new = scan_files(MOUNT)
            sig = sha(new)
            if sig != last:
                write_playlist(new, PLAYLIST)
                # Reload playlist without restarting mpv
                try:
                    mpv_loadlist(IPCSOCK, PLAYLIST)
                except Exception:
                    # If IPC not ready, restart mpv
                    proc.kill()
                    proc = start_mpv(IPCSOCK, PLAYLIST)
                last = sig
    finally:
        proc.kill()

if __name__ == "__main__":
    main()
