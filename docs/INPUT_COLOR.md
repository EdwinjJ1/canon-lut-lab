# 先确认 LUT 的输入色彩空间

3D CUBE 是 RGB 数值表；同一组数字在不同输入空间里可能完全不同。文件标题、说明和创作者文档比文件名更有用。`LUT_3D_SIZE 33` 只说明网格大小，不说明输入是 Rec.709、V-Log 还是 F-Log2。

本次用户提供的 Kinetic 02 文件头写明 **Designed for Rec.709 Color Space**，因此采用 Canon 中性基础上已渲染的 RGB 做第一轮适配。它改变的是 LUT 数值本身；佳能基础曲线与原作者制作 LUT 时的基础风格未被测量为完全相同。

另四份用户文件有 `#LUMIXPHOTOSTYLE` 标记：1992 为 `VIVD`，Filmlike-V2 为 `CNEV2`，Summer 和 Teal Flat-S 为 `STD`。按[松下官方说明](https://eww.pavc.panasonic.co.jp/dscoi/DC-L10/html/DC-L10_DVQP3497_eng/0077.html)，它们分别指定 Vivid、Cinelike V2、Standard 基础风格；带有效标记的这些文件不应因为出自松下就统一当 V-Log 处理。Canon 中性风格只提供可用测试基底，没有复刻松下基础风格。

富士 NC 样例来自[富士官方 LUT 下载页](https://www.fujifilm-x.com/en-ie/support/download/lut/)的 GFX ETERNA 55 `FLog2_to_CLASSIC-Neg._65grid_V.1.00.cube`。原 LUT 明确要求 F-Log2/F-Gamut 输入。我们做了一个显式**候选适配**：sRGB 解码 → 线性 BT.709 到 F-Gamut → [F-Log2 编码](https://dl.fujifilm-x.com/technical-data/F-Log2_DataSheet_E_Ver.1.1.pdf) → 官方 65³ LUT → 对 gamma 2.2 输出解码 → sRGB 编码 → 33³。代码见 `src/prepare_fuji_nc.py`。这个步骤把显示端 sRGB 解码值作为场景线性值，不能反解佳能完整显影，也不能恢复剪切高光。因此只能说“用真正的富士原始 LUT 作为来源并适配后在这组 R7 场景里验证”，不能说“R7 等同富士相机”。

`src/prepare_fuji_nc.py` 不包含或下载富士 LUT。源文件由使用者自行从官方页面取得；其他来源的 LUT 请核对其许可和技术输入要求。

取得官方 65³ CUBE 后，可在本机运行适配脚本。它会验证源 SHA-256，输出新的候选 33³ CUBE 和一份参数报告：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-analysis.txt
.venv/bin/python src/prepare_fuji_nc.py \
  local/FLog2_to_CLASSIC-Neg._65grid_V.1.00.cube \
  local/Fuji-NC-sRGB-candidate.cube \
  --report local/Fuji-NC-preparation.json
```

本次重建输出的 SHA-256 为 `c903e1cb356fa2485a31a2f1525c5a376099eea5b88430f8c275745ef7be6b22`。这一步只生成待检验的转换 CUBE；仍须按[安装指南](SETUP_ZH.md)完成 PF3、原生编译、写入和实拍。
