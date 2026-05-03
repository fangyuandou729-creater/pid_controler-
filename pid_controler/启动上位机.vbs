Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' 尝试 py 启动器
Dim ret
ret = 0
On Error Resume Next
ret = WshShell.Run("py -3 main.py", 0, True)
If ret = 0 And Err.Number = 0 Then WScript.Quit
Err.Clear

' 尝试 python
ret = WshShell.Run("python main.py", 0, True)
If ret = 0 And Err.Number = 0 Then WScript.Quit
Err.Clear

' 尝试完整路径
ret = WshShell.Run(Chr(34) & WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Python\pythoncore-3.14-64\python.exe" & Chr(34) & " main.py", 0, True)
If ret = 0 And Err.Number = 0 Then WScript.Quit

' 全部失败
MsgBox "未找到Python环境！请安装Python 3.8+并确保已添加到PATH。" & vbCrLf & "下载地址: https://www.python.org/downloads/", vbCritical, "模仿者小队 - 错误"