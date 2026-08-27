# Changelog

本文件记录 lame-apple 的版本变化；上游 LAME 版本单独标注。

## 0.1.1 — 2026-08-27

### Fixed

- 根 SPM 清单改为固定 Release 下载地址与 SHA-256，修复远端检出缺少本地 XCFramework 的错误。
- 源码构建生成独立的 `Artifacts/Package.swift`，本地验证不再依赖远端发布包。
- 打包时可显式更新根清单，并将同一清单纳入源码归档。
- 验证失败不再沿用先前成功的本地验证报告。

### Added

- 隔离缓存的远端 SPM 消费者验证，覆盖 arm64 真机与模拟器的 Release 构建。

上游仍为 LAME 4.0，编码 API 和支持平台未变。`0.1.0` tag 保留不动；远端 SPM 用户请升级至 `0.1.1`。

## 0.1.0 — 2026-08-27

首个源码构建版本，基于未经修改的官方 LAME 4.0。

### Added

- iOS / iPadOS 17.0+ 的 arm64 真机和 arm64 模拟器动态 XCFramework 构建。
- 本地 Swift Package Manager 包与 `LAME` C API 模块。
- 固定官方源码归档、SHA-256 校验、许可证与构建信息。
- Swift 6 编译/链接检查、两个平台的 SPM Release 构建及模拟器 MP3 编码回读验证。
- 本地发布材料打包与远端二进制 SPM 清单生成脚本。

### Distribution

- `0.1.0` tag 提供源码，使用前需本地构建 XCFramework。
- 不提供已发布的远端二进制 SPM 依赖；生成发布清单不代表对应下载地址已经可用。

### Validation

- iOS 17.0、26.5 模拟器各通过 8 组编码回读。
- 真机运行、应用分发、长时音频及完整音质回归尚未覆盖，详见 [VALIDATION.md](VALIDATION.md)。
