# Minecraft 视频粒子动画数据包生成工具

将视频拆解为 PNG 帧，再转换成 Minecraft datapack 中的 particleex 动画，实现视频在 Minecraft 中的播放效果。

---

## 项目介绍

本项目基于 Python，通过 FFmpeg 拆解视频帧，并利用 Pillow 进行图片缩放和色彩量化，最终生成符合 Minecraft datapack 规范的 `.mcfunction` 指令文件，结合 particleex 插件可实现视频粒子动画播放。

---

## 功能特点

- 自动检测并下载 FFmpeg（Windows / Linux / Mac）
- 支持自适应分辨率，保持视频比例缩放，避免画面变形
- 支持透明通道，保留 PNG 透明效果
- 粒子动画静止播放，避免粒子飞散或上升
- 自动生成完整 Minecraft datapack 结构文件，便于直接导入游戏
- 带进度条显示视频拆帧和生成过程，方便监控进度

---

## 环境依赖

- Python 3.6+
- [FFmpeg](https://ffmpeg.org/)（自动下载或手动配置路径）
- Python 库：
  - `Pillow`
  - `tqdm`
  - `requests`

可通过以下命令安装依赖：

```bash
pip install Pillow tqdm requests
```
```bash
python video2mc_particle.py 你的视频文件.mp4
```
程序会自动：

拆分视频帧（默认 20 FPS）。

自适应缩放到 Minecraft 合理分辨率，保持比例。

量化颜色到最多 32 色。

生成 mc_commands.mcfunction 指令文件。

数据包结构示例
你需要把生成的 .mcfunction 文件放到数据包的合适路径，例如：

```bash

videopack/
├── data/
│   ├── minecraft/
│   │   └── tags/
│   │       └── functions/
│   │           └── tick.json        # 让函数每 tick 运行
│   └── videopack/
│       └── functions/
│           └── mc_commands.mcfunction
│           └── frame_000001.mcfunction
│           └── frame_000002.mcfunction
│           └── ...                  # 每帧对应的 mcfunction
```
并在 tick.json 中添加：

```json

{
  "values": ["videopack:mc_commands"]
}
```
参数配置
在脚本开头部分可以调整：

| 参数名            | 说明                       | 默认值                 |
| -------------- | ------------------------ | ------------------- |
| FFMPEG\_FPS    | 拆帧帧率，推荐 20 以配合 Minecraft | 20                  |
| RESIZE\_W      | 目标最大宽度（自适应时作为最大值）        | 64                  |
| RESIZE\_H      | 目标最大高度（自适应时作为最大值）        | 64                  |
| MAX\_COLORS    | 最大颜色数，减小粒子颜色复杂度          | 32                  |
| PARTICLE       | Minecraft 粒子类型           | minecraft\:end\_rod |
| ANCHOR\_POS    | 粒子生成坐标相对位置               | `~ ~1 ~`            |
| SCALE          | 粒子缩放比例                   | 0.5                 |
| DPB            | 粒子点间距                    | 10.0                |
| LIFETIME\_TICK | 粒子生命周期，推荐 1（播放完即消失）      | 1                   |
| GROUP          | 粒子分组，用于分组管理              | null                |


# 其他说明
确保 Minecraft 版本支持 particleex 插件。

生成的 mcfunction 文件可根据需求拆分为每帧独立函数，以支持精准控制动画播放。

如需调整粒子效果、颜色或大小，请修改脚本中的相关参数。

脚本会自动下载并解压 ffmpeg（如果系统中未安装），无需额外配置。
