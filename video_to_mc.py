#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
video2mc_datapack.py
视频 -> PNG 帧 -> particleex mcfunctions -> Minecraft 数据包（zip）
特性：
 - 自适应高画质（按视频宽度缩放到 MAX_WIDTH，保持宽高比）
 - 优先使用当前目录的 ffmpeg（./ffmpeg 或 ./ffmpeg.exe）
 - 若无则使用系统 ffmpeg 或自动下载（支持 Win/Linux/Mac）
 - 生成每帧单独的 function：frame_0...frame_N
 - 生成 main.mcfunction 入口
 - 将 PNG 复制到 ParticleEx 图片目录（可配置）
 - 自动打包成 zip
依赖: pip install tqdm pillow requests
用法:
 python video2mc_datapack.py input.mp4 [datapack_name]
"""

from __future__ import annotations
import os, sys, subprocess, glob, shutil, zipfile, platform, json
from tqdm import tqdm
from PIL import Image
import requests

# ---------------- 用户可配置项 ----------------
# 输出帧率（建议 20 与 Minecraft 20 tick/s 对齐）
FFMPEG_FPS = 20

# 最大宽度（按视频宽度等比例缩放到这个宽度）
MAX_WIDTH = 640  # 想更清晰可以改为 1280或 1920，但性能/粒子/内存需求就更多

# 颜色量化（设为 256 或 None 表示不过量化）
MAX_COLORS = 256

# ParticleEx 参数（按需修改）
PARTICLE = 'minecraft:end_rod'
ANCHOR_POS = '~ ~1 ~'
SCALE = 0.1
DPB = 10.0
LIFETIME_TICK = 2
GROUP = 'null'

# 数据包默认命名空间（可由命令行覆盖）
DEFAULT_DATAPACK_NAME = 'videopack'

# ffmpeg 手动路径（None = 自动检测）
FFMPEG_PATH = None

# ParticleEx 图片目录 —— 请改成你本地 particleImages 实际目录
PARTICLEEX_IMG_DIR = os.path.expanduser(
    r'D:\我的世界\minecraft\.minecraft\versions\1.16.5-Fabric\particleImages'
)
# -----------------------------------------------

# ffmpeg 下载 URL（按系统）
FFMPEG_URL = {
    'Windows': 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
    'Linux':   'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz',
    'Darwin':  'https://evermeet.cx/ffmpeg/ffmpeg.zip'
}

def get_ffmpeg() -> str:
    """优先使用当前目录的 ffmpeg，其次用户指定，其次系统 PATH，否则下载解压并返回可执行路径。"""
    # 1. 当前目录的 ffmpeg
    local_name = 'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg'
    local_path = os.path.join(os.getcwd(), local_name)
    if os.path.isfile(local_path):
        return local_path

    # 2. 用户指定
    if FFMPEG_PATH and os.path.isfile(FFMPEG_PATH):
        return FFMPEG_PATH

    # 3. 系统 PATH
    try:
        subprocess.run([local_name, '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return local_name
    except Exception:
        pass

    # 4. 自动下载（若支持）
    system = platform.system()
    if system not in FFMPEG_URL:
        raise RuntimeError(f'系统 {system} 不支持自动下载 ffmpeg，请手动把 ffmpeg 放在脚本目录或设置 FFMPEG_PATH。')
    url = FFMPEG_URL[system]
    local_archive = 'ffmpeg_download.zip' if url.endswith('.zip') else 'ffmpeg_download.tar.xz'
    if not os.path.isfile(local_archive):
        print('正在下载 ffmpeg（可能较大）...')
        r = requests.get(url, stream=True)
        total = int(r.headers.get('content-length', 0) or 0)
        with tqdm.wrapattr(open(local_archive, 'wb'), 'write', total=total, desc='下载 ffmpeg') as f:
            shutil.copyfileobj(r.raw, f)
    # 解压
    tmpdir = 'ffmpeg_temp'
    os.makedirs(tmpdir, exist_ok=True)
    if local_archive.endswith('.zip'):
        import zipfile
        with zipfile.ZipFile(local_archive) as z:
            z.extractall(tmpdir)
    else:
        subprocess.run(['tar', '-xf', local_archive, '-C', tmpdir], check=True)
    # 查找可执行
    for root, _, files in os.walk(tmpdir):
        for fname in files:
            if fname.startswith('ffmpeg') and (fname.endswith('.exe') or 'ffmpeg' == fname):
                path = os.path.join(root, fname)
                return path
    raise RuntimeError('下载并解压 ffmpeg 失败：未找到可执行文件')

def probe_video_resolution(video: str, ffmpeg_cmd: str) -> tuple[int,int]:
    """用 ffmpeg -i 解析分辨率，返回 (width,height)；出错用 1920x1080 作为后备。"""
    # 调用 ffmpeg -i 输出并解析 stderr
    try:
        proc = subprocess.Popen([ffmpeg_cmd, '-i', video], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        _, err = proc.communicate(timeout=10)
    except Exception:
        return 1920, 1080
    width = height = None
    for line in err.splitlines():
        if 'Video:' in line and 'x' in line:
            # 找到类似 "1280x720" 的字段
            parts = line.replace(',', ' ').split()
            for p in parts:
                if 'x' in p and p.count('x') == 1:
                    sub = p.split('x')
                    if len(sub) == 2 and sub[0].isdigit() and sub[1].isdigit():
                        width, height = int(sub[0]), int(sub[1])
                        return width, height
    return 1920, 1080

def extract_frames_and_scale(video: str, out_dir: str, ffmpeg_cmd: str):
    """使用 ffmpeg 拆帧并在输出时做 scale 保证画质与宽高比"""
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    vw, vh = probe_video_resolution(video, ffmpeg_cmd)
    # 防止除以零
    if vw <= 0 or vh <= 0:
        vw, vh = 1920, 1080
    # 计算目标高度，保持宽高比
    target_w = MAX_WIDTH
    target_h = max(1, int(vh * (target_w / vw)))

    # FFmpeg filter：fps + scale（保持整数）
    # 使用 -vsync 0 可以避免帧重复/丢失
    cmd = [
        ffmpeg_cmd, '-i', video,
        '-vf', f'fps={FFMPEG_FPS},scale={target_w}:{target_h}',
        '-vsync', '0',
        os.path.join(out_dir, f'{DEFAULT_DATAPACK_NAME}_%06d.png')
    ]
    print('执行拆帧：', ' '.join(cmd))
    subprocess.run(cmd, check=True)

def post_process_images(out_dir: str):
    """可选的颜色量化 / 透明保留等处理"""
    files = sorted(glob.glob(os.path.join(out_dir, '*.png')))
    for p in tqdm(files, desc='图像处理'):
        img = Image.open(p).convert('RGBA')
        if MAX_COLORS and MAX_COLORS < 256:
            img = img.quantize(colors=MAX_COLORS).convert('RGBA')
        img.save(p)

def build_datapack(out_dir: str, datapack_name: str):
    """生成数据包文件夹与 zip，复制 png 到 ParticleEx 文件夹，并生成每帧 mcfunction"""
    pngs = sorted(glob.glob(os.path.join(out_dir, '*.png')))
    if not pngs:
        print('未找到任何帧图片，退出。')
        return

    # 创建 ParticleEx 图像目录（确保存在）
    os.makedirs(PARTICLEEX_IMG_DIR, exist_ok=True)

    dp_root = datapack_name
    func_dir = os.path.join(dp_root, 'data', datapack_name, 'functions')
    os.makedirs(func_dir, exist_ok=True)

    # pack.mcmeta (1.16.x -> pack_format 6)
    pack = {
        "pack": {
            "pack_format": 6,
            "description": f"Video particle animation ({datapack_name})"
        }
    }
    with open(os.path.join(dp_root, 'pack.mcmeta'), 'w', encoding='utf-8') as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)

    # main.mcfunction
    with open(os.path.join(func_dir, 'main.mcfunction'), 'w', encoding='utf-8') as f:
        f.write(f'function {datapack_name}:frame_0\n')

    # per-frame functions
    for i, src in enumerate(tqdm(pngs, desc='生成 mcfunction 并复制图片')):
        name = os.path.basename(src)
        target = os.path.join(PARTICLEEX_IMG_DIR, name)
        shutil.copy2(src, target)  # 复制到 ParticleEx 指定目录

        mcpath = os.path.join(func_dir, f'{DEFAULT_DATAPACK_NAME}_{i}.mcfunction')
        with open(mcpath, 'w', encoding='utf-8') as mf:
            # 注意：particleex image <particle> <pos> <imagename> <scale> ...
            # 这里使用 imagename（模组会在它自己的图片目录下寻找）
            cmd = (f'particleex image {PARTICLE} {ANCHOR_POS} {name} '
                   f'{SCALE} 0 0 0 not {DPB} 0 0 0 {LIFETIME_TICK} "vy=0" 1.0 {GROUP}')
            mf.write(f'execute positioned ~ ~ ~ run {cmd}\n')
            # 调度下一帧（如果存在）
            if i + 1 < len(pngs):
                mf.write(f'schedule function {datapack_name}:frame_{i+1} 1t\n')

    # 打包 zip
    zipname = f'{datapack_name}.zip'
    if os.path.exists(zipname):
        os.remove(zipname)
    with zipfile.ZipFile(zipname, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(dp_root):
            for fn in files:
                absf = os.path.join(root, fn)
                arcname = os.path.relpath(absf, dp_root)
                z.write(absf, arcname)

    print('数据包已生成：', dp_root)
    print('ZIP 文件：', zipname)
    print('PNG 已复制到 图片目录：', PARTICLEEX_IMG_DIR)
    print('将 ZIP 或文件夹放入 <存档>/datapacks/，进游戏 /reload，然后 /function {0}:main'.format(datapack_name))

def main():
    if len(sys.argv) < 2:
        print('用法: python video2mc_datapack.py input.mp4 [datapack_name]')
        sys.exit(1)

    video = sys.argv[1]
    if not os.path.isfile(video):
        print('视频不存在:', video); sys.exit(1)

    datapack_name = sys.argv[2] if len(sys.argv) >= 3 else DEFAULT_DATAPACK_NAME

    ffmpeg_cmd = get_ffmpeg()
    print('使用 ffmpeg:', ffmpeg_cmd)
    frames_dir = 'frames'
    extract_frames_and_scale(video, frames_dir, ffmpeg_cmd)
    post_process_images(frames_dir)
    build_datapack(frames_dir, datapack_name)
    print('完成。')

if __name__ == '__main__':
    main()


