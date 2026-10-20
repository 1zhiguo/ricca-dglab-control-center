using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows.Forms;

internal static class RiccaLauncher
{
    private static readonly string ReferencePython = Environment.GetEnvironmentVariable("RICCA_DEV_PYTHON") ?? "";

    [STAThread]
    private static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
        string localPython = Path.Combine(root, @".venv\Scripts\pythonw.exe");
        string python = File.Exists(localPython) ? localPython : ReferencePython;
        string source = Path.Combine(root, "src");

        if (!File.Exists(python))
        {
            ShowError("没有找到 Ricca × DG-LAB 的 Python 运行环境。\n\n请先运行 setup_native.ps1。");
            return 2;
        }
        if (!Directory.Exists(source))
        {
            ShowError("程序文件不完整：缺少 src 目录。\n\n请不要单独移动这个 EXE。");
            return 3;
        }

        var forwarded = new List<string> { "-m", "ricca_dglab.app" };
        forwarded.AddRange(args);
        var info = new ProcessStartInfo
        {
            FileName = python,
            Arguments = string.Join(" ", forwarded.Select(Quote)),
            WorkingDirectory = root,
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Normal,
        };
        string existingPath = Environment.GetEnvironmentVariable("PYTHONPATH") ?? "";
        info.EnvironmentVariables["PYTHONPATH"] = string.IsNullOrWhiteSpace(existingPath)
            ? source
            : source + Path.PathSeparator + existingPath;

        try
        {
            Process process = Process.Start(info);
            if (process == null)
            {
                ShowError("启动进程失败。");
                return 4;
            }
            if (process.WaitForExit(1800) && process.ExitCode != 0)
            {
                ShowError("客户端启动失败，退出代码：" + process.ExitCode +
                          "\n\n请运行 run_native_debug.cmd 查看详细错误。");
                return process.ExitCode;
            }
            return 0;
        }
        catch (Exception error)
        {
            ShowError("客户端启动失败：\n\n" + error.Message);
            return 5;
        }
    }

    private static string Quote(string value)
    {
        return "\"" + value.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
    }

    private static void ShowError(string message)
    {
        MessageBox.Show(message, "Ricca × DG-LAB", MessageBoxButtons.OK, MessageBoxIcon.Error);
    }
}
