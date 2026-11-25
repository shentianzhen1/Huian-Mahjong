using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[ComImport, Guid("00021401-0000-0000-C000-000000000046")]
class ShellLink { }

// Native Unicode shortcut interface. WScript.Shell.Save converts Chinese link
// names through the system ANSI code page on English Windows installations.
[ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IShellLinkW {
    [PreserveSig] int GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int size, IntPtr data, uint flags);
    void GetIDList(out IntPtr id); void SetIDList(IntPtr id);
    void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder text, int size);
    void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string text);
    void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int size);
    void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string path);
    void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder text, int size);
    void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string text);
    void GetHotkey(out short key); void SetHotkey(short key);
    void GetShowCmd(out int command); void SetShowCmd(int command);
    void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int size, out int index);
    void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path, int index);
    void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, uint reserved);
    void Resolve(IntPtr window, uint flags);
    void SetPath([MarshalAs(UnmanagedType.LPWStr)] string path);
}

class TestInstaller {
    const string Layout = "shared-data-current-v1";
    const string ShortcutName = "惠安麻将测试版-向听辅助.lnk";

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, EntryPoint = "GetLongPathNameW")]
    static extern uint GetLongPathName(string path, StringBuilder output, uint size);
    static string CanonicalPath(string path) {
        string full = Path.GetFullPath(path);
        StringBuilder output = new StringBuilder(32768);
        uint length = GetLongPathName(full, output, (uint)output.Capacity);
        if (length > 0 && length < output.Capacity) return output.ToString();
        // Old shortcut targets may no longer exist, while their parent does.
        string parent = Path.GetDirectoryName(full);
        length = GetLongPathName(parent, output, (uint)output.Capacity);
        return length > 0 && length < output.Capacity ? Path.Combine(output.ToString(), Path.GetFileName(full)) : full;
    }

    static string ShortcutTarget(string path) {
        IShellLinkW link = (IShellLinkW)new ShellLink();
        try {
            ((IPersistFile)link).Load(path, 0);
            StringBuilder target = new StringBuilder(32768);
            Marshal.ThrowExceptionForHR(link.GetPath(target, target.Capacity, IntPtr.Zero, 4));
            return target.ToString();
        } finally { Marshal.FinalReleaseComObject(link); }
    }
    static void SaveShortcut(string path, string target) {
        IShellLinkW link = (IShellLinkW)new ShellLink();
        try {
            link.SetPath(Path.Combine(target, "runtime", "pythonw.exe"));
            link.SetArguments("-B \"" + Path.Combine(target, "launch.py") + "\"");
            link.SetWorkingDirectory(target);
            link.SetDescription("惠安麻将 Hint Alpha 内部只读测试版");
            ((IPersistFile)link).Save(path, true);
        } finally { Marshal.FinalReleaseComObject(link); }
    }

    static string Inside(string root, string relative) {
        string path = Path.GetFullPath(Path.Combine(root, relative));
        if (!path.StartsWith(Path.GetFullPath(root) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            throw new IOException("Invalid payload path");
        return path;
    }
    static string Hash(string path) {
        using (SHA256 hash = SHA256.Create())
        using (Stream stream = File.OpenRead(path))
            return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }
    static Dictionary<string, object> Manifest(string path) {
        JavaScriptSerializer json = new JavaScriptSerializer();
        json.MaxJsonLength = Int32.MaxValue;
        return json.Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(path, "BUILD_INFO.json")));
    }
    static bool OwnedInstall(string path, bool current) {
        try {
            Dictionary<string, object> info = Manifest(path);
            if (!(info["executor_enabled"] is bool) || (bool)info["executor_enabled"] ||
                !info.ContainsKey("source_sha256") || !info.ContainsKey("build") ||
                !File.Exists(Path.Combine(path, "launch.py")) || !File.Exists(Path.Combine(path, "runtime", "python.exe"))) return false;
            if (current) return info.ContainsKey("installation_layout") && (string)info["installation_layout"] == Layout;
            Match match = Regex.Match(Path.GetFileName(path), @"^(\d+\.\d+\.\d+)-\d{17}$");
            return match.Success && match.Groups[1].Value == (string)info["project_version"];
        } catch { return false; }
    }
    static void PlainTree(string path) {
        if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
            throw new IOException("安装目录含链接，请先人工检查：" + path);
        if (Directory.Exists(path)) foreach (string child in Directory.GetFileSystemEntries(path)) PlainTree(child);
    }
    static void CopyData(string source, string target) {
        Directory.CreateDirectory(target);
        foreach (string file in Directory.GetFiles(source)) {
            string destination = Path.Combine(target, Path.GetFileName(file));
            if (File.Exists(destination)) {
                if (Hash(file) != Hash(destination)) throw new IOException("旧数据存档冲突，已保留旧版本：" + destination);
            } else File.Copy(file, destination);
        }
        foreach (string directory in Directory.GetDirectories(source)) CopyData(directory, Path.Combine(target, Path.GetFileName(directory)));
    }
    static void Extract(string target) {
        if (Directory.Exists(target) || File.Exists(target)) throw new IOException("安装目标已存在。");
        Directory.CreateDirectory(target);
        using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
        using (ZipArchive zip = new ZipArchive(stream, ZipArchiveMode.Read)) {
            foreach (ZipArchiveEntry entry in zip.Entries) {
                string destination = Inside(target, entry.FullName);
                Directory.CreateDirectory(Path.GetDirectoryName(destination));
                entry.ExtractToFile(destination, false);
            }
        }
    }
    static void Check(string target) {
        Dictionary<string, object> info = Manifest(target);
        foreach (KeyValuePair<string, object> item in (Dictionary<string, object>)info["payload_sha256"]) {
            string path = Inside(target, item.Key);
            if (!File.Exists(path) || Hash(path) != (string)item.Value) throw new IOException("安装文件校验失败：" + item.Key);
        }
        ProcessStartInfo doctor = new ProcessStartInfo(Path.Combine(target, "runtime", "python.exe"),
            "-B \"" + Path.Combine(target, "launch.py") + "\" --check");
        doctor.WorkingDirectory = target; doctor.UseShellExecute = false; doctor.CreateNoWindow = true;
        doctor.RedirectStandardOutput = true; doctor.RedirectStandardError = true;
        doctor.EnvironmentVariables["PYTHONUTF8"] = "1";
        using (Process process = Process.Start(doctor)) {
            string output = process.StandardOutput.ReadToEnd(); string error = process.StandardError.ReadToEnd();
            process.WaitForExit();
            File.WriteAllText(Path.Combine(target, "installation-check.txt"), output + error);
            if (process.ExitCode != 0) throw new IOException("新版本自检失败，旧版本保持不变。\n" + output + error);
        }
    }
    static bool Targets(string executable, List<string> installs) {
        if (String.IsNullOrEmpty(executable)) return false;
        string path = CanonicalPath(executable);
        foreach (string install in installs)
            if (path.StartsWith(CanonicalPath(install) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) return true;
        return false;
    }
    static List<string> Upgrade(string root, string desktop) {
        Directory.CreateDirectory(root);
        root = CanonicalPath(root);
        if ((File.GetAttributes(root) & FileAttributes.ReparsePoint) != 0) throw new IOException("安装根目录不能是链接。");
        using (FileStream installLock = new FileStream(Path.Combine(root, ".install.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None)) {
            string current = Path.Combine(root, "current");
            List<string> old = new List<string>();
            if (File.Exists(current) || (Directory.Exists(current) && !OwnedInstall(current, true)))
                throw new IOException("current 目录不是可确认的本程序安装，已保留原文件。");
            if (Directory.Exists(current)) old.Add(current);
            foreach (string directory in Directory.GetDirectories(root)) if (OwnedInstall(directory, false)) old.Add(directory);
            foreach (string directory in old) PlainTree(directory);
            foreach (Process process in Process.GetProcesses()) {
                try { if (Targets(process.MainModule.FileName, old)) throw new IOException("请先关闭旧版惠安麻将及其采集进程，再运行安装。"); }
                catch (System.ComponentModel.Win32Exception) { } catch (InvalidOperationException) { }
                finally { process.Dispose(); }
            }
            string data = Path.Combine(root, "data");
            if (Directory.Exists(data)) PlainTree(data);
            Directory.CreateDirectory(desktop);
            string shortcutPath = Path.Combine(desktop, ShortcutName);
            if (File.Exists(shortcutPath) && !Targets(ShortcutTarget(shortcutPath), old))
                throw new IOException("桌面同名快捷方式不属于本程序，请先重命名。");
            string stage = Path.Combine(root, ".staging-" + Guid.NewGuid().ToString("N"));
            string backup = Path.Combine(root, ".previous-" + Guid.NewGuid().ToString("N"));
            string shortcutTemp = Path.Combine(desktop, ".huian-install-" + Guid.NewGuid().ToString("N") + ".lnk");
            bool swapped = false; bool committed = false; List<string> retained = new List<string>();
            try {
                Extract(stage); Check(stage);
                foreach (string directory in old) {
                    string source = Path.Combine(directory, "data");
                    if (Directory.Exists(source)) CopyData(source, Path.Combine(data, "legacy", Path.GetFileName(directory)));
                }
                if (Directory.Exists(current)) Directory.Move(current, backup);
                try { Directory.Move(stage, current); swapped = true; }
                catch { if (Directory.Exists(backup)) Directory.Move(backup, current); throw; }
                SaveShortcut(shortcutTemp, current);
                if (File.Exists(shortcutPath)) File.Replace(shortcutTemp, shortcutPath, null);
                else File.Move(shortcutTemp, shortcutPath);
                committed = true;
                if (Directory.Exists(backup)) old.Add(backup);
                // Resolve old shortcut aliases while their parent folders still exist.
                foreach (string link in Directory.GetFiles(desktop, "惠安麻将测试版-*.lnk")) {
                    if (link == shortcutPath) continue;
                    try { if (Targets(ShortcutTarget(link), old)) File.Delete(link); }
                    catch { retained.Add(link); }
                }
                foreach (string directory in old) {
                    if (directory == current) continue;
                    try { Directory.Delete(directory, true); } catch { retained.Add(directory); }
                }
                return retained;
            } finally {
                if (!committed && swapped) {
                    Directory.Delete(current, true);
                    if (Directory.Exists(backup)) Directory.Move(backup, current);
                }
                if (Directory.Exists(stage)) Directory.Delete(stage, true);
                if (File.Exists(shortcutTemp)) File.Delete(shortcutTemp);
            }
        }
    }
    [STAThread]
    static int Main(string[] args) {
        bool extract = args.Length == 2 && args[0] == "--extract";
        bool test = args.Length == 2 && args[0] == "--install-test";
        string root = test ? Path.GetFullPath(args[1]) : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "HuianMahjongTest");
        try {
            if (extract) { Extract(Path.GetFullPath(args[1])); return 0; }
            string desktop = test ? Path.Combine(root, "desktop") : Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            List<string> retained = Upgrade(root, desktop);
            if (!test) MessageBox.Show("安装/升级完成，桌面保留一个固定入口。\n旧版记录已存档，新记录继续保存在 data 目录。\n安装目录：" + Path.Combine(root, "current")
                + (retained.Count == 0 ? "" : "\n部分旧文件未能清理，已保留：\n" + String.Join("\n", retained)), "惠安麻将测试版");
            return 0;
        } catch (Exception error) {
            if (extract) File.WriteAllText(Path.GetFullPath(args[1]) + ".error.txt", error.ToString());
            else if (test) File.WriteAllText(root + ".error.txt", error.ToString());
            else MessageBox.Show(error.Message, "安装失败");
            return 1;
        }
    }
}
