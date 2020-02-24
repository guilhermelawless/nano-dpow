Set oShell = CreateObject ("Wscript.Shell") 

' Launch work server
oShell.Run "cmd /c "".\bin\windows\nano-work-server.exe --gpu 1:0 -l 127.0.0.1:7000""", 0, false

' Launch DPOW client
oShell.Run "cmd /c run_windows.bat -noserver", 0, false