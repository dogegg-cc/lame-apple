# lame-apple

将官方 LAME 编码库构建为 iOS 可使用的独立动态 XCFramework，通过 Swift Package Manager 接入。

远端仓库：[dogegg-cc/lame-apple](https://github.com/dogegg-cc/lame-apple)。目前仅配置本地 origin，尚未推送或发布。

## 首版范围

- 上游：LAME **4.0**，完整原始源码归档位于 `Vendor/lame-4.0.tar.gz`。
- 本工程版本：**0.1.0**（本地开发，尚未发布）。这个版本与上游 LAME 版本分别管理。
- iOS 17.0+ / iPadOS 17.0+。
- 仅两个切片：`ios-arm64` 和 `ios-arm64-simulator`。
- 不支持 Intel / x86_64 模拟器，不构建 macOS、watchOS、tvOS 或 visionOS。
- 只启用 MP3 编码，关闭解码器、命令行前端和分析器钩子；不链接 FFmpeg、libmpg123 或其他第三方音频库。
- 直接暴露官方 C API，Swift 中使用 `import LAME`。本工程不包含 FileBox 的文件管理或剪辑业务。

官方源码：[下载页面](https://lame.sourceforge.io/download.php)、[4.0 发布目录](https://sourceforge.net/projects/lame/files/lame/4.0/)。

## 环境

- Apple Silicon Mac。
- Xcode 及 iOS SDK；通过 `xcode-select` 选择完整 Xcode。
- Python **3.12+**（使用 `tarfile` 的安全解包过滤）。
- `make`、`pkg-config`。官方发布包已带 `configure`，普通构建不需要重新运行 Autoconf/Automake。
- 运行回读验证时需要已安装的 iOS 模拟器。

构建只读取工程内锁定的源码，不在线下载，也不修改上游源码。`upstream.json` 中记录的 SHA-256 是从下载的完整官方发布归档计算的固定值，不代表额外验证过上游数字签名。

## 本地构建

```sh
python3 Scripts/build.py
```

生成：

```text
Artifacts/
  LAME.xcframework/
    ios-arm64/
    ios-arm64-simulator/
  build-info.json
```

真机和模拟器必须分别编译，即使两者都是 arm64。脚本使用 SDK 专用 target，生成动态库并设置 `@rpath/LAME.framework/LAME`，同时检查架构和运行时依赖。

`.build/lame` 内保留 configure/make 日志。每次构建只清理本工程生成的源文件解包与平台工作目录。产物包含 Clang module map、头文件、许可证和隐私清单。构建时仅做本地 ad-hoc 签名，接入 App 后仍需正常的应用签名流程。

`build-info.json` 记录编译器、SDK、上游校验和与配置。相同输入可按脚本重新构建；当前不承诺不同机器生成的二进制和 ZIP 逐字节一致。

## Swift Package Manager

先构建 XCFramework，再在 Xcode 中添加本工程作为 **Local Package**，为应用 Target 选择 `LAME` 产品：

```swift
import LAME

if let encoder = lame_init() {
    defer { lame_close(encoder) }
    // 设置采样率、声道和码率，检查返回码，再调用 lame_init_params。
}
```

根目录 `Package.swift` 引用本地产物，**直接把当前仓库 URL 加到 Xcode 并不能替代这一步**。远端二进制包清单需要在指定真实仓库和发布产物后生成，见发布章节。

编码注意事项：

- 每个输出文件独占一个 LAME 实例；不要跨任务并发使用同一指针。
- 多个剪辑片段连续送入同一实例，所有数据结束后只 flush 一次。
- 归一化 Float32 PCM 应使用 `lame_encode_buffer_ieee_float`，普通 `lame_encode_buffer_float` 预期的是 ±32768 数值范围。
- 帧数参数是每声道采样数；MP3 仅支持单/双声道，额外声道需调用方下混。
- 采样率、CBR/VBR 与码率组合需要校验，不能无条件保持任意输入格式。
- 处理所有负返回码，预留足够输出空间，最后 flush 并正确写入 LAME/Xing 信息。
- 音频输入解析、分块 PCM 读取、取消和文件清理由调用方负责。

## 验证

列出模拟器，然后传入真实的 UDID：

```sh
xcrun simctl list devices available
python3 Scripts/verify.py --device SIMULATOR_UDID
```

脚本为两个 SDK 编译并链接 Swift 6 验证程序，并以 `ARCHS=arm64` 为两个平台构建 Release SPM 消费者，然后在选定模拟器执行 8 组 PCM → MP3 → PCM 验证：44.1/48 kHz × 单/双声道 × 短片段/非整帧长输入。检查版本、MPEG Layer III、192 kbps、声道、采样率、解码时长、信号幅度和声道顺序。

如果脚本启动了原本关闭的模拟器，结束时会恢复关闭状态；不会安装或启动 FileBox。结果和样本保留在 `.build/verification`。这只是基础编码验证，不是完整音质评测或内存压力测试；时长允许最多 2304 个采样的编解码延迟差异，不等同于验证所有播放器的精确无缝播放。

`Tests/PackageConsumer` 是最小本地 SPM 消费者，用于确认包依赖解析与 `import LAME`，不需要更改 FileBox。

本次已执行的环境、结果和未覆盖范围见 [VALIDATION.md](VALIDATION.md)。

## 本地准备发布材料

```sh
python3 Scripts/package_release.py
```

在 `Release/0.1.0` 生成 XCFramework ZIP、SHA-256、完整官方源码归档、包含构建/验证脚本的工程源码 ZIP、许可证、文档和构建信息。脚本要求当前构建已经通过 `verify.py`，并核对实际二进制和源码归档校验值，不能拿旧验证记录给新构建打包。**该命令不会创建远端仓库、tag、上传文件或发布 Release。**

当前仓库可运行 `python3 Scripts/package_release.py --repository dogegg-cc/lame-apple`，额外生成远端 `Package.swift`。发布时应：

1. 先完成真机运行、应用集成、许可证和分发方式核查。
2. 将完整源码、构建脚本及所有补丁保存在可访问的仓库/发布材料中。
3. 上传 `LAME.xcframework.zip` 和配套源码、许可证到与 `packageVersion` 同名的 Release。
4. 用生成的远端清单安排发布提交和 tag，核对 URL 可访问及 checksum 匹配，防止发布一个仍引用本地 Artifacts 的包。
5. 从干净环境通过远端 SPM 消费者验证后，再让 FileBox 固定该版本。

## 升级策略

上游更新时，人工检查变更与编码 API，下载完整发布归档，更新 `Vendor`、`upstream.json` 和许可证副本，再执行构建及验证。尽量保持零补丁。若不得不修补上游，保存独立补丁并记录原因，不直接修改生成目录。

## 许可证与分发

官方代码沿用 **GNU Library General Public License v2 或更高版本**，详见 `Licenses/LAME-COPYING` 和 `Licenses/LAME-LICENSE`。本工程新增构建脚本和验证代码也按 LGPL-2.0-or-later 提供；不将 LAME 重新标为 MIT。

选择动态库是为了保留独立库边界，但**不构成 App Store 可分发或许可证合规保证**。发布者仍需核对实际许可证版本、对应源码提供、修改记录、用户替换/重新链接权利及商店条款。隐私清单基于当前仅编码构建；加入新功能后必须重新审核。

## 当前未完成事项

- 真机执行与 App Store 归档/上传验证。
- 推送、CI 工作流、公开 Release 和远端 SPM 下载验证。
- FileBox 集成及 FFmpegKit 移除。
- 长时音频、取消/失败清理和完整音质回归。
- 上游 C 代码在当前 Clang 下的告警复核（包含旧式声明、常量移位和未使用变量）；当前没有为了消除告警而修改源码或全局禁用告警。

以上内容不因本地构建成功而视为已完成。
