' CONFIG: GPU hardware identifier
Dim gpu_id
gpu_id = "0:0"



Set oShell = CreateObject ("Wscript.Shell") 
oShell.Run "cmd /c "".\bin\windows\nano-work-server.exe --gpu " & gpu_id & " -l 127.0.0.1:7000""", 0, false
oShell.Run "cmd /c run_windows.bat -noserver", 0, false