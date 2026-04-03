import AppKit
import Combine
import Darwin
import ServiceManagement
import SwiftUI

// MARK: - Process runner

@MainActor
final class ProxyRunner: ObservableObject {
    @Published private(set) var isRunning = false
    @Published var lastError: String?

    private var process: Process?
    private var outputPipe: Pipe?
    private var userStopped = false

    /// Repo root (…/tg-ws-proxy-apk)
    @Published var repoPath: String {
        didSet { UserDefaults.standard.set(repoPath, forKey: "repoPath") }
    }

    @Published var secretHex: String {
        didSet { UserDefaults.standard.set(secretHex, forKey: "secretHex") }
    }

    @Published var pythonPath: String {
        didSet { UserDefaults.standard.set(pythonPath, forKey: "pythonPath") }
    }

    @Published var listenPort: String {
        didSet { UserDefaults.standard.set(listenPort, forKey: "listenPort") }
    }

    init() {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let guess = (home as NSString).appendingPathComponent("Documents/proxy/tg-ws-proxy-apk")
        repoPath = UserDefaults.standard.string(forKey: "repoPath") ?? guess
        secretHex = UserDefaults.standard.string(forKey: "secretHex") ?? ""
        pythonPath = UserDefaults.standard.string(forKey: "pythonPath") ?? "/usr/bin/python3"
        listenPort = UserDefaults.standard.string(forKey: "listenPort") ?? "1443"
    }

    var tgLink: String {
        let s = secretHex.trimmingCharacters(in: .whitespaces)
        guard s.count == 32, s.allSatisfy({ $0.isHexDigit }) else {
            return ""
        }
        return "tg://proxy?server=127.0.0.1&port=\(listenPort)&secret=dd\(s)"
    }

    func start() {
        guard !isRunning else { return }
        lastError = nil

        let root = repoPath.trimmingCharacters(in: .whitespaces)
        guard !root.isEmpty else {
            lastError = "Укажите папку репозитория в настройках."
            return
        }

        let script = URL(fileURLWithPath: root).appendingPathComponent("scripts/run_local_proxy.py")
        guard FileManager.default.fileExists(atPath: script.path) else {
            lastError = "Нет файла:\n\(script.path)"
            return
        }

        guard FileManager.default.fileExists(atPath: pythonPath) else {
            lastError = "Нет Python:\n\(pythonPath)"
            return
        }

        let sec = secretHex.trimmingCharacters(in: .whitespaces)
        if !sec.isEmpty && sec.count != 32 {
            lastError = "Секрет должен быть 32 символа hex (без dd)."
            return
        }

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: pythonPath)
        proc.currentDirectoryURL = URL(fileURLWithPath: root)

        var args = [script.path, "--host", "127.0.0.1", "--port", listenPort]
        if !sec.isEmpty {
            args.insert(contentsOf: ["--secret", sec], at: 1)
        }
        proc.arguments = args

        var env = ProcessInfo.processInfo.environment
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        env["HOME"] = home
        env["USER"] = env["USER"] ?? NSUserName()
        env["LANG"] = env["LANG"] ?? "en_US.UTF-8"
        env["PYTHONUNBUFFERED"] = "1"
        let path = env["PATH"] ?? ""
        let extra = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
        env["PATH"] = path.isEmpty ? extra : "\(path):\(extra)"
        proc.environment = env

        let out = Pipe()
        proc.standardOutput = out
        proc.standardError = out
        proc.standardInput = FileHandle.nullDevice

        proc.terminationHandler = { [weak self] p in
            Task { @MainActor in
                guard let self else { return }
                guard self.process?.processIdentifier == p.processIdentifier else { return }
                let tail = Self.readPipeRemainder(self.outputPipe)
                let byUser = self.userStopped
                self.userStopped = false
                if !byUser && p.terminationStatus != 0, self.lastError == nil {
                    if !tail.isEmpty {
                        self.lastError = "Python выход \(p.terminationStatus):\n\(tail)"
                    } else {
                        self.lastError = "Прокси завершился (код \(p.terminationStatus))."
                    }
                }
                self.cleanupProcessAfterTermination()
            }
        }

        do {
            userStopped = false
            try proc.run()
            process = proc
            outputPipe = out
            isRunning = true
            let port = parsedPort(self.listenPort)
            Task { @MainActor in
                for _ in 0..<40 {
                    try? await Task.sleep(nanoseconds: 500_000_000)
                    guard let p = self.process, p.isRunning else { return }
                    if socketPortOpen(host: "127.0.0.1", port: port) { return }
                }
                guard let p = self.process, p.isRunning else { return }
                let tail = Self.readPipeRemainder(self.outputPipe)
                self.lastError = tail.isEmpty
                    ? "За 20 с порт \(port) не открылся — проверь путь к репо и Python в настройках."
                    : "Порт не открылся. Лог:\n\(tail)"
                p.terminate()
            }
        } catch {
            lastError = error.localizedDescription
            cleanupProcess()
        }
    }

    private nonisolated static func readPipeRemainder(_ pipe: Pipe?) -> String {
        guard let h = pipe?.fileHandleForReading else { return "" }
        let data = h.readDataToEndOfFile()
        return String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    /// После ухода процесса — без закрытия pipe до чтения (читает terminationHandler).
    private func cleanupProcessAfterTermination() {
        outputPipe = nil
        process = nil
        isRunning = false
    }

    func stop() {
        guard isRunning else { return }
        if let p = process, p.isRunning {
            userStopped = true
            p.terminate()
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [weak self] in
                guard let self else { return }
                Task { @MainActor in
                    if self.process?.isRunning == true {
                        self.process?.interrupt()
                    }
                    self.cleanupProcess()
                }
            }
        } else {
            cleanupProcess()
        }
    }

    private func cleanupProcess() {
        try? outputPipe?.fileHandleForReading.close()
        outputPipe = nil
        process = nil
        isRunning = false
    }
}

private func parsedPort(_ s: String) -> UInt16 {
    let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
    let v = Int(t) ?? 1443
    return UInt16(clamping: v)
}

private func socketPortOpen(host: String, port: UInt16) -> Bool {
    let fd = socket(AF_INET, SOCK_STREAM, 0)
    guard fd >= 0 else { return false }
    defer { close(fd) }
    var addr = sockaddr_in()
    addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
    addr.sin_family = sa_family_t(AF_INET)
    addr.sin_port = in_port_t(UInt16(port).byteSwapped)
    inet_pton(AF_INET, host, &addr.sin_addr)
    let rc = withUnsafePointer(to: &addr) {
        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
            connect(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
        }
    }
    return rc == 0
}

// MARK: - Launch at login

enum LaunchAtLoginHelper {
    static var isEnabled: Bool {
        SMAppService.mainApp.status == .enabled
    }

    static func setEnabled(_ on: Bool) throws {
        if on {
            try SMAppService.mainApp.register()
        } else {
            try SMAppService.mainApp.unregister()
        }
    }
}

// MARK: - UI

struct MenuCommandsView: View {
    @ObservedObject var runner: ProxyRunner

    var body: some View {
        if let err = runner.lastError {
            Text(err)
                .font(.caption)
                .foregroundStyle(.red)
                .lineLimit(8)
                .fixedSize(horizontal: false, vertical: true)
                .textSelection(.enabled)
            Divider()
        }
        Button(runner.isRunning ? "Выключить прокси" : "Включить прокси") {
            if runner.isRunning {
                runner.stop()
            } else {
                runner.start()
            }
        }
        .keyboardShortcut("p", modifiers: [.command])

        Divider()

        Button("Скопировать tg:// ссылку") {
            if runner.tgLink.isEmpty {
                let a = NSAlert()
                a.messageText = "Нельзя собрать ссылку"
                a.informativeText = """
                В «Настройках» нужно ввести секрет: ровно 32 символа hex без префикса dd \
                (как в логе после строки Secret:). Тогда в ссылку подставится tg://proxy?…&secret=dd…

                Если секрет пустой, прокси при каждом запуске сам выдаёт новый — стабильной ссылки нет, \
                смотри вывод в Консоли или запускай из Терминала.
                """
                a.alertStyle = .informational
                a.addButton(withTitle: "OK")
                a.runModal()
                return
            }
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(runner.tgLink, forType: .string)
        }

        if runner.tgLink.isEmpty {
            Text("Ссылка: введи 32 hex в Настройках")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }

        SettingsLink {
            Text("Настройки…")
        }

        Divider()

        Button("Выйти") {
            if runner.isRunning {
                runner.stop()
            }
            NSApplication.shared.terminate(nil)
        }
    }
}

struct SettingsForm: View {
    @ObservedObject var runner: ProxyRunner
    @State private var launchOn = LaunchAtLoginHelper.isEnabled
    @State private var launchErr: String?

    var body: some View {
        Form {
            Section("Репозиторий tg-ws-proxy-apk") {
                TextField("Полный путь к папке", text: $runner.repoPath)
                    .textFieldStyle(.roundedBorder)
                HStack {
                    Button("Выбрать папку…") {
                        let p = NSOpenPanel()
                        p.canChooseFiles = false
                        p.canChooseDirectories = true
                        p.allowsMultipleSelection = false
                        if p.runModal() == .OK, let url = p.url {
                            runner.repoPath = url.path
                        }
                    }
                    Text("Должны лежать scripts/run_local_proxy.py и proxy/")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            Section("Прокси") {
                TextField("Порт", text: $runner.listenPort)
                TextField("Секрет: 32 hex без dd (пусто — новый ключ каждый раз; для кнопки «Скопировать» заполни)", text: $runner.secretHex)
                    .font(.system(.body, design: .monospaced))
                TextField("Python", text: $runner.pythonPath)
                Text("Если /usr/bin/python3 не тот: /opt/homebrew/bin/python3")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Section("Автозапуск") {
                Toggle("Открывать при входе в систему", isOn: $launchOn)
                    .onChange(of: launchOn) { _, v in
                        launchErr = nil
                        do {
                            try LaunchAtLoginHelper.setEnabled(v)
                        } catch {
                            launchErr = error.localizedDescription
                            launchOn = LaunchAtLoginHelper.isEnabled
                        }
                    }
                if let e = launchErr {
                    Text(e).foregroundStyle(.red).font(.caption)
                }
                Text("Нужна подпись Apple для SMAppService; иначе добавьте приложение вручную: Системные настройки → Основные → Объекты входа.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            if let err = runner.lastError {
                Section {
                    Text(err).foregroundStyle(.red)
                }
            }
        }
        .formStyle(.grouped)
        .frame(minWidth: 520, minHeight: 380)
    }
}

@main
struct TGWSProxyMenuBarApp: App {
    @StateObject private var runner = ProxyRunner()

    var body: some Scene {
        MenuBarExtra(
            "TG WS",
            systemImage: runner.isRunning ? "bolt.horizontal.circle.fill" : "bolt.horizontal.circle"
        ) {
            MenuCommandsView(runner: runner)
        }

        Settings {
            SettingsForm(runner: runner)
        }
    }
}
