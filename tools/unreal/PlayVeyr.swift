// Small native launcher: no Terminal window and no direct GPU-gate bypass.
import Foundation

do {
    guard let url = Bundle.main.url(forResource: "LaunchConfig", withExtension: "json"),
          let config = try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: String],
          let python = config["python"], let script = config["script"], let log = config["log"] else {
        exit(2)
    }
    if !FileManager.default.fileExists(atPath: log) {
        FileManager.default.createFile(atPath: log, contents: nil)
    }
    let output = try FileHandle(forWritingTo: URL(fileURLWithPath: log))
    try output.seekToEnd()
    let process = Process()
    process.executableURL = URL(fileURLWithPath: python)
    // Ignore LaunchServices bookkeeping arguments; the GUI always opens the
    // verified current build. --check is reserved for installation validation.
    process.arguments = [script] + (CommandLine.arguments.contains("--check") ? ["--check"] : [])
    var environment = ProcessInfo.processInfo.environment
    environment["PATH"] = "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    process.environment = environment
    process.standardOutput = output
    process.standardError = output
    try process.run()
    process.waitUntilExit()
    try output.close()
    exit(process.terminationStatus)
} catch {
    exit(1)
}
