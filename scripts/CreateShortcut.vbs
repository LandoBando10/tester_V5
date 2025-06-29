Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

DesktopPath = WshShell.SpecialFolders("Desktop")
Set oShellLink = WshShell.CreateShortcut(DesktopPath & "\Diode Tester V5.lnk")

' Use pythonw to run the .pyw file (no console window)
oShellLink.TargetPath = "pythonw"
oShellLink.Arguments = """C:\Users\landon.epperson\OneDrive\Desktop\Diode_tester_V5\tester_V5\DiodeTester.pyw"""
oShellLink.WindowStyle = 1

' Check if ICO file exists, otherwise use the system python icon
icoPath = "C:\Users\landon.epperson\OneDrive\Desktop\Diode_tester_V5\tester_V5\resources\shortcut_icon.ico"
If fso.FileExists(icoPath) Then
    oShellLink.IconLocation = icoPath
Else
    ' Try to use Python's icon as fallback
    pythonIcon = "C:\Windows\py.exe"
    If fso.FileExists(pythonIcon) Then
        oShellLink.IconLocation = pythonIcon & ", 0"
    End If
End If

oShellLink.Description = "Diode Dynamics Tester V5"
oShellLink.WorkingDirectory = "C:\Users\landon.epperson\OneDrive\Desktop\Diode_tester_V5\tester_V5"
oShellLink.Save

WScript.Echo "Shortcut created on Desktop!" & vbCrLf & vbCrLf & _
             "Note: The program will run without a console window."