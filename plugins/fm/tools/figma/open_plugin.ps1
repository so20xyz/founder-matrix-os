Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;using System.Runtime.InteropServices;
public class W{[DllImport("user32.dll")]public static extern bool SetForegroundWindow(IntPtr h);[DllImport("user32.dll")]public static extern bool ShowWindow(IntPtr h,int c);}
"@
$p = Get-Process figma | Where-Object {$_.MainWindowTitle} | Select -First 1
[W]::ShowWindow($p.MainWindowHandle,9) | Out-Null
[W]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
Start-Sleep 2
[System.Windows.Forms.SendKeys]::SendWait("^/")
Start-Sleep 1
[System.Windows.Forms.SendKeys]::SendWait("Claude Bridge")
Start-Sleep 2
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Start-Sleep 2
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $b.Width,$b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen(0,0,0,0,$bmp.Size)
$bmp.Save("C:\Users\USER\AppData\Local\Temp\fig-shot.png")
