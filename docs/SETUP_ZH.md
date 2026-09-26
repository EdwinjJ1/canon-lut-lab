# 在自己的 EOS R7 上复现

这是一条 **Mac + 固定版本 Canon 软件 + R7** 的研究路线。它使用用户定义照片风格槽位，拍照预览和 JPEG 可以使用该风格；相机不会新增 `.cube` 菜单。先读完整页再动相机。所列命令在仓库根目录执行，`local/` 会保存本机数据且不会被 Git 提交。

## 1. 准备

- EOS R7：本次验证固件 1.0.1，电池电量充足、USB 数据线可用。其他固件版本单独核对。
- Mac：本次验证 macOS 26.6.2、Apple Silicon；安装 Xcode Command Line Tools、Python 3、Node.js。
- 官方 Canon [EOS Utility](https://cam.start.canon/en/S003/manual/html/index.html) 3.20.21.3 和 Picture Style Editor 1.32.20。软件需要由使用者自行安装；仓库不分发它们。
- 一份自己可使用的**纯 3D** `.cube`，支持 2–65 阶，不支持混合 1D shaper。先确认源 LUT 的输入类型。Rec.709 的创意 LUT 可做第一轮；Log LUT 先转换输入域，见[色彩空间说明](INPUT_COLOR.md)。
- 一张自己拍的 R7 RAW，用 PSE 创建并保存一份有效的中性基础 PF3。不要用空白字节构造 PF3。

确认解析器文件：

```sh
CANON_APP='/Applications/Canon Utilities/EOS Utility/EU3/EOS Utility 3.app'
CANON_SDK="$CANON_APP/Contents/Frameworks/EDSDK.framework/Versions/A/EDSDK"
CANON_PARSER="$CANON_APP/Contents/PlugIns/EdsCFParse.bundle/Contents/MacOS/EdsCFParse"
shasum -a 256 "$CANON_PARSER"
shasum -a 256 "$CANON_SDK"
```

本项目编译器只接受 SHA-256 `f4f2f931c174bfb200fde98d26c0e35c6bcaa3cf2374dbf89583bbeb7fe866b5`。哈希不同意味着 ABI 未经这套代码验证；编译器会停止，**不要删掉检查继续写机身**。本次 EDSDK SHA-256 为 `35a425fc84460bac539eb051b921362c142dfcde966514b18249be8c393529ea`，快照和安装工具也会校验它。安装路径也不同则需先调查自己的版本，而不能照搬二进制偏移。

## 2. 先让目标槽位有正常的佳能基础风格

在 Picture Style Editor 用自己的 R7 RAW 建立普通中性照片风格，保存到 `local/PSE-Neutral-Base.pf3`。再在 EOS Utility 的 **相机设置 → 注册照片风格文件** 中选择需要的用户定义槽位，把这份正常 PF3 注册一次。Canon [官方手册](https://cam.start.canon/ky/S003/manual/html/UG-02_CameraSetting_0020.html)列出用户定义 1–3 及注册步骤。该动作会覆盖所选槽位原先内容；先记录原有名称和设置。

这一步是初始化槽位控制状态。注册后相机的控制值应分别为 65、66、67。只编译文件、不进行这次官方初始化，可能出现名称或载荷已在槽位中但风格没有启用的情况。

先在相机选择该基础风格拍一张正常 JPEG，确认没有 Err 10 或黑屏。退出 EOS Utility，再运行以下程序；相机同一时刻只能由一个程序占用。

## 3. 读取自己相机的快照

```sh
mkdir -p local
./build_macos.sh
build/R7LutTool.app/Contents/MacOS/eds_snapshot "$CANON_SDK" local/camera-before
```

`local/camera-before/` 必须是新目录。应有机型 `property-01000001-param-0.bin`（4 字节）、描述符 `property-01000210-param-0.bin`（本次 R7 为 15076 字节），以及目标槽位 `property-01000203-param-33.bin`、`34.bin` 或 `35.bin`（本次为 83076 字节）。照片风格控制及滑块记录在 `property-00000114-*` 和 `property-00000115-*`。这些都是**本机私有备份**，不要上传。

若只读程序列出 0 台相机，退出 EOS Utility、检查 USB、半按快门唤醒，再从新的输出目录重试。不要把没有读到文件的运行视为快照成功。

## 4. 离线转换自己的 CUBE

示例：目标为用户定义 3，源文件自己放在 `local/MyLook.cube`：

```sh
python3 src/cfp_bridge.py \
  --base local/PSE-Neutral-Base.pf3 \
  --cube local/MyLook.cube \
  --title 'My Look Test' \
  --output local/My-Look-Test.pf3

python3 src/compile_r7_dense.py \
  --camera-data local/camera-before \
  --out local/compiled-my-look \
  local/My-Look-Test.pf3
```

`--title` 必须为 1–31 个 ASCII 字节。PF3 输出文件和编译输出目录必须尚不存在。编译成功后应得到 `local/compiled-my-look/My-Look-Test.bin`，大小 83076 字节，日志中两张网格均为 `finite: true`。此时尚未写入相机。

桥接器会基于真实 PSE 模板分别合成两张 33³ 色表，保留其他已知属性。编译器在自己的进程中调用本机解析器的原生 17³ 色表生成路径，并生成实时预览所需的 4096 字节辅助表。直接让 PSE 再保存中间 PF3 可能抹掉合成结果。

## 5. 只写目标槽位并核对

再次退出 EOS Utility，确认相机开机。**快照拍摄后若又改过该槽位，请重新读快照并重新离线编译。** 单槽安装器会比较当前机型、完整描述符、槽位载荷、控制值和参数与快照完全一致；任一不符即停止。示例：

```sh
build/R7LutTool.app/Contents/MacOS/eds_install_one \
  "$CANON_SDK" \
  local/camera-before \
  3 \
  local/compiled-my-look/My-Look-Test.bin \
  local/install-my-look
```

输出目录也必须是新目录。成功日志包含 `"event":"verified"`、`"readbackExact":true`、`"settingsUnchanged":true`。工具只会写选定槽位；写前把旧载荷、控制值、参数保存到输出目录，写入或验证失败时尝试恢复并记录结果。**写入返回 0 或看到名称还不够，必须检查读回与真实照片。**

编译和安装中的型号、描述符与载荷长度限制是为本次实测 R7 建的。不要把它用于 R5、R8 或其他机身，除非针对对应机型完成独立研究。

## 6. 机身验证与日常使用

在相机照片模式选择目标「用户定义」风格。让镜头对准同时有红、蓝、绿色的场景，固定相机、光照、白平衡和曝光。先在内置「中性」拍 JPEG，再用新风格拍 JPEG；确认实时取景和拍后回放均出现预期变化。断开 USB，重启相机，再拍一次。比较**相机直出的原始 JPEG**；不要用电脑后套 LUT 的图片充当直出。

若要严谨测试 `.cube` 是否对应，先在 Python 虚拟环境安装 `requirements-analysis.txt` 中的 NumPy 和 Pillow，再运行 `compare_lut_pair.py` 对同场景基准 JPEG、目标 JPEG 和重复基准做数值分析。只有几种颜色或不同构图时，不能把结果推广到全部场景。`docs/VALIDATION.md` 记录了本次实际证据与限制。

JPEG 烘焙风格颜色。RAW 在外部软件显影时不一定自动应用自定义风格。设备上可切回内置「标准」或「中性」。相机仍然只提供三个用户定义槽位；更多 LUT 可保存在电脑、日后替换。

异常时看[恢复步骤](RECOVERY.md)。
