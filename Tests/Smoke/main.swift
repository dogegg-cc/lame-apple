import AVFoundation
import Foundation
import LAME

enum SmokeError: Error { case failed(String) }

func require(_ condition: Bool, _ message: String) throws {
    if !condition { throw SmokeError.failed(message) }
}

func encode(sampleRate: Int, channels: Int, frames: Int) throws -> Data {
    guard let encoder = lame_init() else { throw SmokeError.failed("lame_init") }
    defer { lame_close(encoder) }
    for (name, result) in [
        ("sampleRate", lame_set_in_samplerate(encoder, Int32(sampleRate))),
        ("outputRate", lame_set_out_samplerate(encoder, Int32(sampleRate))),
        ("channels", lame_set_num_channels(encoder, Int32(channels))),
        ("CBR", lame_set_VBR(encoder, vbr_off)),
        ("bitrate", lame_set_brate(encoder, 192)),
        ("quality", lame_set_quality(encoder, 2)),
        ("tag", lame_set_bWriteVbrTag(encoder, 1)),
        ("samples", lame_set_num_samples(encoder, UInt(frames))),
    ] {
        try require(result == 0, "Invalid setting: \(name), \(result)")
    }
    lame_set_write_id3tag_automatic(encoder, 0)
    try require(lame_init_params(encoder) == 0, "lame_init_params")
    var encoded = Data()
    var bytes = [UInt8](repeating: 0, count: 16384)
    var cursor = 0
    // 刻意使用非 MP3 帧长度的块，覆盖内部缓冲与最后不足一块的输入。
    while cursor < frames {
        let count = min(997, frames - cursor)
        let left = (0 ..< count).map { Float(0.4 * sin(2 * .pi * 440 * Double(cursor + $0) / Double(sampleRate))) }
        let right = (0 ..< count).map { Float(0.4 * sin(2 * .pi * 880 * Double(cursor + $0) / Double(sampleRate))) }
        let written: Int32 = try left.withUnsafeBufferPointer { l in
            try right.withUnsafeBufferPointer { r in
                try bytes.withUnsafeMutableBufferPointer { output in
                    guard let lp = l.baseAddress, let rp = r.baseAddress, let dst = output.baseAddress else {
                        throw SmokeError.failed("Missing PCM buffer")
                    }
                    // ieee_float 接收 [-1, 1] 浮点 PCM；普通 float 入口要求 16-bit 数值范围。
                    return lame_encode_buffer_ieee_float(encoder, lp, channels == 1 ? lp : rp,
                                                         Int32(count), dst, Int32(output.count))
                }
            }
        }
        try require(written >= 0, "encode failed: \(written)")
        encoded.append(contentsOf: bytes.prefix(Int(written)))
        cursor += count
    }
    let flushed = lame_encode_flush(encoder, &bytes, Int32(bytes.count))
    try require(flushed >= 0, "flush failed: \(flushed)")
    encoded.append(contentsOf: bytes.prefix(Int(flushed)))
    // 未写 ID3v2，预留的 Xing/Info 帧位于文件开头；回写延迟和填充信息。
    let tagLength = lame_get_lametag_frame(encoder, &bytes, bytes.count)
    try require(tagLength > 0 && tagLength <= bytes.count && tagLength <= encoded.count, "Invalid LAME tag")
    encoded.replaceSubrange(0 ..< tagLength, with: bytes.prefix(tagLength))
    return encoded
}

func validate(sampleRate: Int, channels: Int, frames: Int, directory: URL) throws -> [String: Any] {
    let data = try encode(sampleRate: sampleRate, channels: channels, frames: frames)
    let name = "\(sampleRate)-\(channels)ch-\(frames).mp3"
    let url = directory.appendingPathComponent(name)
    try data.write(to: url)
    let header = [UInt8](data.prefix(4))
    try require(header.count == 4 && header[0] == 0xFF && header[1] & 0xE0 == 0xE0, "Missing MPEG header")
    try require((header[1] >> 3) & 3 == 3 && (header[1] >> 1) & 3 == 1, "Not MPEG-1 Layer III")
    let bitrates = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
    try require(bitrates[Int(header[2] >> 4)] == 192, "Not 192 kbps")
    let file: AVAudioFile
    do {
        file = try AVAudioFile(forReading: url)
    } catch {
        throw SmokeError.failed("Opening \(name): \(error)")
    }
    let format = file.processingFormat
    try require(format.sampleRate == Double(sampleRate), "Sample rate changed")
    try require(format.channelCount == channels, "Channel count changed")
    guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 4096) else {
        throw SmokeError.failed("Cannot allocate decode buffer")
    }
    var decodedFrames = 0
    var energy = [Double](repeating: 0, count: channels)
    var real = [Double](repeating: 0, count: channels)
    var imaginary = [Double](repeating: 0, count: channels)
    while file.framePosition < file.length {
        do {
            try file.read(into: buffer, frameCount: AVAudioFrameCount(min(Int64(buffer.frameCapacity), file.length - file.framePosition)))
        } catch {
            throw SmokeError.failed("Reading \(name) at frame \(file.framePosition)/\(file.length): \(error)")
        }
        let count = Int(buffer.frameLength)
        if count == 0 { break }
        guard let samples = buffer.floatChannelData else { throw SmokeError.failed("No float PCM") }
        for channel in 0 ..< channels {
            let frequency = channel == 0 ? 440.0 : 880.0
            for index in 0 ..< count {
                let value = Double(samples[channel][index])
                try require(value.isFinite, "Non-finite decoded sample")
                energy[channel] += value * value
                let phase = 2 * Double.pi * frequency * Double(decodedFrames + index) / Double(sampleRate)
                real[channel] += value * cos(phase)
                imaginary[channel] += value * sin(phase)
            }
        }
        decodedFrames += count
    }
    // 系统解码器可能保留部分编解码延迟，记录实测值且拒绝明显丢尾或错误时长。
    try require(abs(decodedFrames - frames) <= 2304, "Unexpected decoded duration: \(decodedFrames) vs \(frames)")
    for channel in 0 ..< channels {
        let rms = sqrt(energy[channel] / Double(max(decodedFrames, 1)))
        let amplitude = 2 * hypot(real[channel], imaginary[channel]) / Double(max(decodedFrames, 1))
        try require(rms > 0.1 && rms < 0.5 && amplitude > 0.15, "Wrong signal or channel order")
    }
    return ["file": name, "sampleRate": sampleRate, "channels": channels,
            "inputFrames": frames, "decodedFrames": decodedFrames, "bytes": data.count, "bitrateKbps": 192]
}

do {
    guard CommandLine.arguments.count == 2, let versionPointer = get_lame_version() else {
        throw SmokeError.failed("Usage: smoke <output-directory>")
    }
    let directory = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    let version = String(cString: versionPointer)
    try require(version == "4.0", "Unexpected upstream version: \(version)")
    var results: [[String: Any]] = []
    for rate in [44100, 48000] {
        for channels in [1, 2] {
            for frames in [rate * 2 + 137, rate / 20] {
                try results.append(validate(sampleRate: rate, channels: channels, frames: frames, directory: directory))
            }
        }
    }
    let report: [String: Any] = ["lameVersion": version, "cases": results, "passed": results.count]
    try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
        .write(to: directory.appendingPathComponent("results.json"))
    print("PASS: LAME \(version), \(results.count) encode/decode cases")
} catch {
    print("FAIL: \(error)")
    exit(1)
}
