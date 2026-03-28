Set shell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = scriptDir
shell.Run """" & scriptDir & "\start_infofeeder.bat""", 0, False
WScript.Sleep 4000
shell.Run "http://localhost:8502", 1, False
