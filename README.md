视频转 Minecraft 粒子动画数据包工具
项目简介
本项目提供一个 Python 脚本，将视频文件转换为 Minecraft 中可播放的粒子动画数据包（datapack）格式。
流程是将视频拆帧成 PNG 图像，调整大小和颜色数量后，生成对应的 mcfunction 指令文件，通过 Minecraft 自定义数据包的方式播放粒子动画效果。

使用了 particleex 这个高级粒子扩展插件，实现了在 Minecraft 内展示逐帧视频的效果。

功能特点
自动检测并下载 ffmpeg，支持 Windows、Linux、macOS。

按照 Minecraft 每秒 20 tick 速度拆帧，帧率与游戏同步。

支持自适应视频分辨率缩放，保持原始视频比例。

限制颜色数量，减小粒子颜色复杂度。

生成完整的 mcfunction 指令文件，用于 Minecraft 数据包直接调用。

粒子动画播放时粒子静止，播放完毕粒子立刻消失，避免飞向天空。

带有命令行进度条，方便跟踪处理进度。

使用说明
环境准备
Python 3.6 及以上

安装依赖：

bash
复制
编辑
pip install tqdm requests pillow
脚本执行
bash
复制
编辑
python video2mc_particle.py 你的视频文件.mp4
程序会自动：

拆分视频帧（默认 20 FPS）。

自适应缩放到 Minecraft 合理分辨率，保持比例。

量化颜色到最多 32 色。

生成 mc_commands.mcfunction 指令文件。

数据包结构示例
你需要把生成的 .mcfunction 文件放到数据包的合适路径，例如：

bash
复制
编辑
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
并在 tick.json 中添加：

json
复制
编辑
{
  "values": ["videopack:mc_commands"]
}
参数配置
在脚本开头部分可以调整：

参数名	说明	默认值
FFMPEG_FPS	拆帧帧率，推荐 20 以配合 Minecraft	20
RESIZE_W	目标最大宽度（自适应时作为最大值）	64
RESIZE_H	目标最大高度（自适应时作为最大值）	64
MAX_COLORS	最大颜色数，减小粒子颜色复杂度	32
PARTICLE	Minecraft 粒子类型	minecraft:end_rod
ANCHOR_POS	粒子生成坐标相对位置	~ ~1 ~
SCALE	粒子缩放比例	0.5
DPB	粒子点间距	10.0
LIFETIME_TICK	粒子生命周期，推荐 1（播放完即消失）	1
GROUP	粒子分组，用于分组管理	null

其他说明
确保 Minecraft 版本支持 particleex 插件。

生成的 mcfunction 文件可根据需求拆分为每帧独立函数，以支持精准控制动画播放。

如需调整粒子效果、颜色或大小，请修改脚本中的相关参数。

脚本会自动下载并解压 ffmpeg（如果系统中未安装），无需额外配置。
