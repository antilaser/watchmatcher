@echo off
setlocal
set SSH=C:\Windows\System32\OpenSSH\ssh.exe
set CFG=C:\ssh\watchmatch\ssh_config
"%SSH%" -F "%CFG%" watchmatch %*
