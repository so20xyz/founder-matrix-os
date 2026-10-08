@echo off
rem FM Figma bridge (PC) - started by Task Scheduler "At log on" (spec 2026-10-09 P2-2)
cd /d "C:\Users\PC\founder-matrix-os\plugins\fm\tools\figma\bridge"
"C:\Program Files\nodejs\node.exe" server.mjs >> "C:\Users\PC\.fmos\logs\figma-bridge.log" 2>&1
