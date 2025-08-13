#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
video2mc_datapack
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
 python video_to_mc.py input.mp4 [datapack_name]
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
MAX_WIDTH = 640  # 想更清晰可以改为 1280或 1920，但粒子越多需要的性能就更多，模组不太推荐超过1000*1000

# 颜色量化（设为 256 或 None 表示不过量化）
MAX_COLORS = 256

# ParticleEx 参数（按需修改）
PARTICLE = 'minecraft:end_rod'
ANCHOR_POS = '~ ~1 ~' #播放坐标
SCALE = 0.3 #缩放比例，
DPB = 10.0
LIFETIME_TICK = 1 #存活时间，以MC的20游戏刻为基础
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
    """
    获取 ffmpeg 可执行路径：
    1. 优先使用当前目录的 ffmpeg
    2. 用户手动指定 FFMPEG_PATH
    3. 系统 PATH
    4. 自动下载并解压
    """
    local_name = 'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg'
    local_path = os.path.join(os.getcwd(), local_name)
    if os.path.isfile(local_path):
        return local_path
    if FFMPEG_PATH and os.path.isfile(FFMPEG_PATH):
        return FFMPEG_PATH
    try:
        subprocess.run([local_name, '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return local_name
    except Exception:
        pass
    # 自动下载
    system = platform.system()
    if system not in FFMPEG_URL:
        raise RuntimeError(f'系统 {system} 不支持自动下载 ffmpeg，请手动提供。')
    url = FFMPEG_URL[system]
    local_archive = 'ffmpeg_download.zip' if url.endswith('.zip') else 'ffmpeg_download.tar.xz'
    if not os.path.isfile(local_archive):
        print('正在下载 ffmpeg...')
        r = requests.get(url, stream=True)
        total = int(r.headers.get('content-length', 0) or 0)
        with tqdm.wrapattr(open(local_archive, 'wb'), 'write', total=total, desc='下载 ffmpeg') as f:
            shutil.copyfileobj(r.raw, f)
    tmpdir = 'ffmpeg'
    os.makedirs(tmpdir, exist_ok=True)
    if local_archive.endswith('.zip'):
        with zipfile.ZipFile(local_archive) as z:
            z.extractall(tmpdir)
    else:
        subprocess.run(['tar', '-xf', local_archive, '-C', tmpdir], check=True)
    for root, _, files in os.walk(tmpdir):
        for fname in files:
            if fname.startswith('ffmpeg') and (fname.endswith('.exe') or fname == 'ffmpeg'):
                return os.path.join(root, fname)
    raise RuntimeError('下载并解压 ffmpeg 失败')

def extract_frames(video: str, out_dir: str, ffmpeg_cmd: str, datapack_name='videopack'):
    """
    使用 ffmpeg 拆帧 + 缩放 + 可选颜色量化
    - scale=MAX_WIDTH:-1 让 ffmpeg 按比例缩放
    - fps=FFMPEG_FPS 保证每秒输出帧数
    - MAX_COLORS < 256 时启用 ffmpeg -colors 限制颜色
    """
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    scale_expr = f'scale={MAX_WIDTH}:-1'
    vf_filters = [f'fps={FFMPEG_FPS}', scale_expr]

    cmd = [ffmpeg_cmd, '-i', video]
    if MAX_COLORS and MAX_COLORS < 256:
        cmd += ['-colors', str(MAX_COLORS)]
    cmd += [
        '-vf', ','.join(vf_filters),
        '-vsync', '0',
        os.path.join(out_dir, f'{datapack_name}_%06d.png')
    ]
    print('执行拆帧：', ' '.join(cmd))
    subprocess.run(cmd, check=True)

def build_datapack(out_dir: str, datapack_name: str):
    """
    生成 Minecraft 数据包：
    1. 复制 PNG 到 ParticleEx 图片目录
    2. 生成每帧对应的 mcfunction
    3. main.mcfunction 调用第一帧
    4. 打包成 zip
    """
    pngs = sorted(glob.glob(os.path.join(out_dir, '*.png')))
    if not pngs:
        print('未找到帧图片，退出。')
        return

    os.makedirs(PARTICLEEX_IMG_DIR, exist_ok=True)
    dp_root = datapack_name
    func_dir = os.path.join(dp_root, 'data', datapack_name, 'functions')
    os.makedirs(func_dir, exist_ok=True)

    # 创建 pack.mcmeta
    pack = {
        "pack": {"pack_format": 6, "description": f"Video particle animation ({datapack_name})"}
    }
    with open(os.path.join(dp_root, 'pack.mcmeta'), 'w', encoding='utf-8') as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)

    # main.mcfunction
    with open(os.path.join(func_dir, 'main.mcfunction'), 'w', encoding='utf-8') as f:
        f.write(f'function {datapack_name}:{datapack_name}_0\n')

    # 每帧 mcfunction + PNG 复制
    for i, src in enumerate(tqdm(pngs, desc='生成 mcfunction 并复制图片')):
        name = os.path.basename(src)
        shutil.copy2(src, os.path.join(PARTICLEEX_IMG_DIR, name))
        mcpath = os.path.join(func_dir, f'{datapack_name}_{i}.mcfunction')
        with open(mcpath, 'w', encoding='utf-8') as mf:
            # particleex image <particle> <pos> <imagename> <scale> ...
            cmd = (f'particleex image {PARTICLE} {ANCHOR_POS} {name} '
                   f'{SCALE} 0 0 0 not {DPB} 0 0 0 {LIFETIME_TICK} "vy=0" 1.0 {GROUP}')
            mf.write(f'execute positioned ~ ~ ~ run {cmd}\n')
            # 调度下一帧
            if i + 1 < len(pngs):
                mf.write(f'schedule function {datapack_name}:{datapack_name}_{i+1} 1t\n')

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

    print(f'数据包已生成：{dp_root}')
    print(f'ZIP 文件：{zipname}')
    print(f'PNG 已复制到：{PARTICLEEX_IMG_DIR}')
    print(f'进游戏 /reload，然后 /function {datapack_name}:main')

def main():
    """程序入口：解析参数 -> 获取 ffmpeg -> 拆帧 -> 生成数据包"""
    if len(sys.argv) < 2:
        print('用法: python video_to_mc.py input.mp4 [datapack_name]')
        sys.exit(1)
    video = sys.argv[1]
    if not os.path.isfile(video):
        print('视频不存在:', video)
        sys.exit(1)
    datapack_name = sys.argv[2] if len(sys.argv) >= 3 else DEFAULT_DATAPACK_NAME
    ffmpeg_cmd = get_ffmpeg()
    print('使用 ffmpeg:', ffmpeg_cmd)
    frames_dir = 'frames'
    extract_frames(video, frames_dir, ffmpeg_cmd, datapack_name)
    build_datapack(frames_dir, datapack_name)
    print('完成。')

if __name__ == '__main__':
    main()









