@echo off
setlocal
set PLINK="C:\Program Files\PuTTY\plink.exe"
set HOST=212.227.110.234
set USER=root
set KEY=%USERPROFILE%\.ssh\id_ed25519_watchmatch_212.ppk
set HOSTKEY=ssh-ed25519 255 SHA256:oDgY9+Bmslici+cX5DUYWuQ2j4cVG9OgwoKIUYliuII
%PLINK% -batch -ssh -hostkey "%HOSTKEY%" -i "%KEY%" -l %USER% %HOST% %*
