param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)
$ssh = "C:\Windows\System32\OpenSSH\ssh.exe"
$cfg = "C:\ssh\watchmatch\ssh_config"
& $ssh -F $cfg watchmatch @Args
