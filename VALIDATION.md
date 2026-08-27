# 本地验证记录

日期：2026-08-27。本记录针对 0.1.1 构建产物的本地验证；不作为真机或应用分发验证的证明。

## 环境与输入

- Apple Silicon，Xcode 26.6（17F113），iOS / iOS Simulator SDK 26.5。
- 官方 LAME 4.0，未修改上游源码。
- 源码归档 SHA-256：`3df5124d5ad3a98312ffd7ba6a9b36230e4f8a3e66d3ce0f425e336c32d216eb`。
- `build-info.json` SHA-256：`c4d1ca8f57a8a1a4bc3c67c9f37c3441f28d16ca7673d67a66c86f2dc48fe1ff`。

## 已执行结果

| 检查 | 结果 |
| --- | --- |
| `python3 Scripts/build.py` | 两个动态 Framework 构建成功，XCFramework 组装成功 |
| Mach-O 架构 / 平台 | 仅 arm64；分别为 IOS 和 IOSSIMULATOR；最低系统版本均为 17.0 |
| 动态依赖 | 除自身 install name 外，仅 `/usr/lib/libSystem.B.dylib` |
| Swift 6 严格并发编译和链接 | iOS 与模拟器均通过 |
| 本地 SPM 消费者 Release 构建 | 通过独立的 `Artifacts/Package.swift` 消费本次产物，两个平台均通过 |
| iPhone 15 Pro / iOS 17.0 模拟器 | 8/8 编码与 AVAudioFile 回读通过 |
| iPhone 17 Pro / iOS 26.5 模拟器 | 8/8 编码与 AVAudioFile 回读通过 |

每个系统运行 44.1/48 kHz × 单/双声道 × 短片段/非整帧长输入，CBR 192 kbps。实际回读帧数在全部 16 个案例中都与输入一致，并通过信号幅度和声道顺序检查；验证程序的时长判定仍允许最多 2304 帧差异，不据此承诺所有播放器的无缝播放。

可用 `python3 Scripts/verify.py --device SIMULATOR_UDID` 复验。运行输出位于 `.build/verification`，按模拟器分目录保存样本；`verification.json` 保存最近一次成功结果。构建日志位于 `.build/lame`。

## 尚未验证

- 物理 iPhone/iPad 运行、应用嵌入签名与 App Store 归档/上传。
- 与其他媒体库共同链接、实际应用集成。
- 远端 SPM 下载与消费验证需要在资产公开后执行 `Scripts/verify_remote.py`；本地验证不能代替该检查。
- VBR、其他码率/采样率、长时音频、并发压力、取消/失败清理和完整音质回归。
- 上游 C 编译告警的逐项复核。当前保留告警，没有修改源码或全局禁用告警。

模拟器执行和通用 iOS 目标编译不能替代真机测试。
