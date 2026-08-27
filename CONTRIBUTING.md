# 开发与发布

## 开发约定

- `main` 为主分支；功能与修复在独立分支开发，通过审查后合并，发布 tag 从主分支的已验证提交创建。
- 仅维护 iOS arm64 和 iOS Simulator arm64。
- 保留独立动态库边界，不引入解码器或其他媒体处理依赖。
- `Vendor` 中的官方源码归档及许可证必须完整保留，不直接修改解压后的生成文件。
- `.build`、`Artifacts`、`Release` 为生成目录，不提交到 Git。
- 修改构建配置、公开接口或支持范围时，同时更新 README、变更记录和相关验证。

## 构建与验证

```sh
python3 Scripts/build.py
python3 Scripts/verify.py --device SIMULATOR_UDID
swiftformat . --lint --config .swiftformat --cache ignore
```

SwiftFormat 是开发检查工具，不是构建依赖。修改 Swift 文件后先格式化，再执行相关编译验证。

构建日志保留在 `.build/lame`；验证结果保留在 `.build/verification`。脚本仅关闭本次自行启动的模拟器，不关闭原先已运行的开发会话。

`Artifacts/build-info.json` 记录上游配置、编译器、SDK 和二进制校验值。相同输入可按脚本重新构建，但目前不保证跨机器的二进制与 ZIP 逐字节一致。验证记录只对实际测试的产物和环境负责。

## 版本管理

- `upstream.json.version` 表示上游 LAME 版本；`packageVersion` 表示本库版本。
- 采用 `MAJOR.MINOR.PATCH`。tag 与 `packageVersion` 完全一致，例如 `0.1.0`，不添加 `v` 前缀。
- `0.x` 阶段的兼容性变化提升次版本；修复提升补丁版本。稳定的 `1.x` 及后续版本中，不兼容变更提升主版本。
- 每个版本对应独立提交、带说明的 tag 和 CHANGELOG 条目。
- 不移动已发布 tag，不覆盖已有二进制资产。修复使用新版本，并保留旧版对应源码及许可证。
- 源码 tag 与二进制 Release 分开描述；未验证的下载地址不能作为已可用的安装入口。

## 升级上游

1. 人工核查官方发布说明、API 与许可证变化。
2. 下载完整官方归档，检查归档完整性并计算 SHA-256；固定哈希不等于额外验证了上游数字签名。
3. 更新 `Vendor`、`upstream.json` 与许可证副本。尽量保持零补丁；确需补丁时保存独立补丁并让构建脚本明确应用，不只记录名称。
4. 重新构建两个切片，检查架构、最低系统版本、动态依赖与 Swift 导入/链接，运行编码回读回归。
5. 更新库版本、CHANGELOG 与验证记录，记录新增限制和未覆盖范围。

## 发布源码版本

1. 确认版本字段一致，工作区只包含预期变更。
2. 完成对应代码变更的构建与验证；纯文档修改无需重编译未变更的二进制。
3. 提交源码、文档和完整许可证，创建与 `packageVersion` 同名的 annotated tag。
4. 推送提交和 tag，核对远端 tag 指向的提交。
5. README 保留准确的源码构建说明，不将源码版本写成可直接下载的二进制包。

## 准备二进制 Release

```sh
python3 Scripts/package_release.py --repository dogegg-cc/lame-apple
```

脚本只生成本地材料，不上传、不创建 tag，也不修改根目录 `Package.swift`。输出位于 `Release/<packageVersion>`：

- `LAME.xcframework.zip` 与 SHA-256。
- 完整官方源码归档及包含构建/验证脚本的工程源码 ZIP。
- 许可证、构建信息、版本配置、README、CHANGELOG 与维护/验证文档。
- 指向相应 GitHub Release 资产的远端 `Package.swift`。

发布前必须核查源码和二进制对应关系、应用嵌入签名、真机运行及许可证分发要求。远端二进制清单应随发布提交进入根目录，同时为本地开发保留明确的本地产物验证入口；不能让维护脚本转而测试旧版远端二进制。

为新的二进制版本安排 draft Release、提交、tag 与资产上传，确认 `releases/download/<version>/LAME.xcframework.zip` 可访问且 SHA-256 与清单一致，再完成干净环境下的远端 SPM 下载和两个平台消费验证。不要把重建产生的新 checksum 覆盖进已发布版本；必须提升版本。

## 报告问题

提交问题时注明库版本、Xcode/SDK、目标系统和架构，并提供最小复现步骤、PCM 格式与相关错误。不要上传私密音频、鉴权信息或包含敏感路径的完整日志。
