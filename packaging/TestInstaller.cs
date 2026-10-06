using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows.Forms;

class TestInstaller {
    [STAThread]
    static int Main(string[] args) {
        bool check = args.Length == 2 && args[0] == "--extract";
        string target = check ? Path.GetFullPath(args[1]) : Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "HuianMahjongTest", "__PROJECT_VERSION__-" + DateTime.Now.ToString("yyyyMMddHHmmssfff"));
        try {
            if (Directory.Exists(target)) throw new IOException("安装目标已存在，请使用新目录。");
            Directory.CreateDirectory(target);
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
            using (ZipArchive zip = new ZipArchive(stream, ZipArchiveMode.Read)) {
                foreach (ZipArchiveEntry entry in zip.Entries) {
                    string dest = Path.GetFullPath(Path.Combine(target, entry.FullName));
                    if (!dest.StartsWith(target + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                        throw new IOException("Invalid payload path");
                    Directory.CreateDirectory(Path.GetDirectoryName(dest));
                    entry.ExtractToFile(dest, false);
                }
            }
            if (check) return 0;
            ProcessStartInfo doctor = new ProcessStartInfo(Path.Combine(target, "runtime", "python.exe"),
                "-B \"" + Path.Combine(target, "launch.py") + "\" --check");
            doctor.WorkingDirectory = target;
            doctor.UseShellExecute = false;
            doctor.CreateNoWindow = true;
            doctor.RedirectStandardOutput = true;
            doctor.RedirectStandardError = true;
            doctor.EnvironmentVariables["PYTHONUTF8"] = "1";
            using (Process process = Process.Start(doctor)) {
                string output = process.StandardOutput.ReadToEnd();
                string error = process.StandardError.ReadToEnd();
                process.WaitForExit();
                File.WriteAllText(Path.Combine(target, "installation-check.txt"), output + error);
                if (process.ExitCode != 0) throw new IOException("自检失败，请查看 " + target + "\\installation-check.txt");
            }
            Type shellType = Type.GetTypeFromProgID("WScript.Shell");
            dynamic shell = Activator.CreateInstance(shellType);
            string shortcutPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
                "惠安麻将测试版-向听辅助.lnk");
            if (File.Exists(shortcutPath)) shortcutPath = Path.Combine(
                Path.GetDirectoryName(shortcutPath), "惠安麻将测试版-" + DateTime.Now.ToString("yyyyMMddHHmmss") + ".lnk");
            dynamic shortcut = shell.CreateShortcut(shortcutPath);
            shortcut.TargetPath = Path.Combine(target, "runtime", "pythonw.exe");
            shortcut.Arguments = "-B \"" + Path.Combine(target, "launch.py") + "\"";
            shortcut.WorkingDirectory = target;
            shortcut.Description = "惠安麻将 Hint Alpha 内部只读测试版";
            shortcut.Save();
            MessageBox.Show("安装完成，已创建桌面快捷方式。\n新增向听与候选弃牌，可点击人工录牌；实时识别为实验功能。\n完整V0.10建议尚未接入，Executor关闭。\n安装目录：" + target,
                "惠安麻将测试版");
            return 0;
        } catch (Exception error) {
            if (check) File.WriteAllText(target + ".error.txt", error.ToString());
            else MessageBox.Show(error.Message, "安装失败");
            return 1;
        }
    }
}
