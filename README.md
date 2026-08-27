# lame-apple

面向 iOS / iPadOS 的独立 LAME MP3 编码库。将官方 LAME 源码构建为动态 XCFramework，通过 Swift Package Manager 接入，直接提供 `import LAME` 和官方 C API。

## 支持范围

| 项目 | 支持 |
| --- | --- |
| 库版本 | 0.1.1 |
| 上游版本 | LAME 4.0 |
| 系统 | iOS / iPadOS 17.0+ |
| 真机架构 | arm64 |
| 模拟器架构 | arm64（Apple Silicon） |
| 分发形式 | 动态 XCFramework，Swift Package Manager 二进制包 |
| 编码 | PCM → MP3 |

不包含音频解码、媒体文件读取或剪辑功能，不依赖 FFmpeg。不支持 Intel 模拟器、macOS、watchOS、tvOS 或 visionOS。

## 安装

### Swift Package Manager

在 Xcode 的 Package Dependencies 中添加 `https://github.com/dogegg-cc/lame-apple.git`，选择 **0.1.1 或更高版本**，为应用 Target 添加 `LAME` 产品。

也可以在 `Package.swift` 中声明：

```swift
dependencies: [
    .package(url: "https://github.com/dogegg-cc/lame-apple.git", from: "0.1.1")
]
// 在消费 Target 的 dependencies 中添加：
// .product(name: "LAME", package: "lame-apple")
```

SPM 根据版本清单下载 [Release](https://github.com/dogegg-cc/lame-apple/releases) 中的 XCFramework，并校验 SHA-256。使用预编译版本不需要 Python、`make` 或 `pkg-config`。

`0.1.0` 仅支持本地源码构建，不能直接作为远端 SPM 依赖。遇到 `does not contain a binary artifact` 时，请将版本要求调整为 `0.1.1` 或更高版本，并在 Xcode 中更新包版本。

## 从源码构建

### 构建要求

- Apple Silicon Mac。
- 完整 Xcode 与 iOS SDK，使用 `xcode-select` 选择工具链。
- Python 3.12+、`make`、`pkg-config`。

### 构建命令

```sh
git clone --branch 0.1.1 https://github.com/dogegg-cc/lame-apple.git
cd lame-apple
python3 Scripts/build.py
```

构建产物位于 `Artifacts/LAME.xcframework`，并生成 `Artifacts/Package.swift`。在 Xcode 中将 **`Artifacts` 目录**添加为 Local Package，为应用 Target 选择 `LAME` 产品。最低 Swift 工具版本为 5.9。

根目录 `Package.swift` 始终用于远端分发；本地开发使用 `Artifacts` 包，避免把已发布二进制误当成本次源码构建结果。

脚本读取仓库内锁定的官方源码归档并校验 SHA-256；真机和模拟器分别编译，不在线下载依赖。构建使用 ad-hoc 签名，应用分发时仍需正常的嵌入与签名流程。

## 使用

```swift
import LAME

if let encoder = lame_init() {
    defer { lame_close(encoder) }
    // 配置采样率、声道和码率，检查返回值，再调用 lame_init_params。
    // 分块送入 PCM，结束时 flush 并回写 LAME/Xing 信息。
}
```

以上仅展示实例生命周期。完整的编码与回读示例见 [Tests/Smoke/main.swift](Tests/Smoke/main.swift)，API 定义见构建产物中的 `Headers/lame.h`。

- 每个输出文件独占一个编码实例，不要并发访问同一指针。
- 归一化 Float32 PCM 使用 `lame_encode_buffer_ieee_float`；普通 `lame_encode_buffer_float` 接收的是 ±32768 数值范围。
- 帧数参数表示每声道采样数；MP3 支持单声道和双声道，其他声道布局需要调用方下混。
- 校验采样率、码率与 CBR/VBR 组合，处理所有负返回码，预留足够输出空间。
- 连续输入所有 PCM 后仅 flush 一次，并正确更新 LAME/Xing 信息。
- 文件读取、重采样、取消、进度与失败清理由调用方负责。

## 验证

安装 iOS 模拟器后运行：

```sh
xcrun simctl list devices available
python3 Scripts/verify.py --device SIMULATOR_UDID
```

验证覆盖两个平台的 Swift 6 编译/链接、本地 SPM Release 构建，以及 44.1/48 kHz、单/双声道、短片段/非整帧输入的 8 组 MP3 编码回读。

维护者发布后还需执行远端验证，它使用隔离的源码检出、包缓存和 DerivedData：

```sh
python3 Scripts/verify_remote.py --version 0.1.1
```

已执行的环境、结果和覆盖边界见 [VALIDATION.md](VALIDATION.md)。模拟器验证不代替真机或应用分发验证。

## 维护

- [变更记录](CHANGELOG.md)
- [开发、升级与发布规范](CONTRIBUTING.md)
- [问题反馈](https://github.com/dogegg-cc/lame-apple/issues)

`main` 为主分支。本库版本与上游 LAME 版本分别管理。发布 tag 与 `upstream.json` 的 `packageVersion` 保持一致，已发布版本不覆盖或移动。

## 许可证

采用 **LGPL-2.0-or-later**。官方许可证及说明保留在 [LICENSE](LICENSE)、[Licenses/LAME-COPYING](Licenses/LAME-COPYING) 和 [Licenses/LAME-LICENSE](Licenses/LAME-LICENSE)；新增构建脚本和验证代码采用相同许可证。

动态链接不代表自动满足分发要求。使用者仍需核对对应源码提供、许可证声明、重新链接/替换权利及目标分发渠道的条款。

上游：[LAME 官方网站](https://lame.sourceforge.io/)、[LAME 4.0 源码发布](https://sourceforge.net/projects/lame/files/lame/4.0/)。
