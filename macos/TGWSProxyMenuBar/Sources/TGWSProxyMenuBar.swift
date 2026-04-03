import AppKit
import Combine
import ServiceManagement
import SwiftUI

// MARK: - Process runner

@MainActor
final class ProxyRunner: ObservableObject {
    @Published private(set) var isRunning = false
    @Published var lastError: String?

    private var process: Process?
    private var outputPipe: Pipe?
    private var listenTimer: Timer?

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

        let out = Pipe()
        proc.standardOutput = out
        proc.standardError = out
        proc.standardInput = FileHandle.nullDevice

        proc.terminationHandler = { [weak self] p in
            Task { @MainActor in
                guard let self else { return }
                if self.process?.processIdentifier == p.processIdentifier {
                    self.cleanupProcess()
                }
            }
        }

        do {
            try proc.run()
            process = proc
            outputPipe = out
            isRunning = true
            listenTimer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
                guard let self else { return }
                Task { @MainActor in self.drainPipeChunk() }
            }
        } catch {
            lastError = error.localizedDescription
            cleanupProcess()
        }
    }

    func stop() {
        guard isRunning else { return }
        if let p = process, p.isRunning {
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

    private func drainPipeChunk() {
        let h = outputPipe?.fileHandleForReading
        let data = h?.availableData ?? Data()
        if !data.isEmpty, let s = String(data: data, encoding: .utf8) {
           // При необходимости лог в консоль
            NSLog("%@", s.trimmingCharacters(in: .whitespacesAndNewlines))
        }
    }

    private func cleanupProcess() {
        listenTimer?.invalidate()
        listenTimer = nil
        try? outputPipe?.fileHandleForReading.close()
        outputPipe = nil
        process = nil
        isRunning = false
    }
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
            guard !runner.tgLink.isEmpty else { return }
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(runner.tgLink, forType: .string)
        }
        .disabled(runner.tgLink.isEmpty)

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
                TextField("Секрет: 32 hex без dd (пусто — прокси сам сгенерирует; в Telegram обнови ключ)", text: $runner.secretHex)
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
