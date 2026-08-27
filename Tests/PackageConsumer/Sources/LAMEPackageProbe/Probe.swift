import LAME

public func linkedLAMEVersion() -> String? {
    guard let version = get_lame_version() else { return nil }
    return String(cString: version)
}
