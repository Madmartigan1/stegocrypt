$iss = ".\installer\StegoCrypt.iss"

# Try PATH first
$cmd = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source

# Fall back to common install locations (both per-machine and per-user)
$try = @(
  $cmd,
  "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if ($try) {
  & $try $iss
} else {
  Write-Warning "Could not find ISCC.exe. Trying to locate the GUI compiler (Compil32.exe)..."
  $gui = @(
    "$env:ProgramFiles(x86)\Inno Setup 6\Compil32.exe",
    "$env:ProgramFiles\Inno Setup 6\Compil32.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\Compil32.exe"
  ) | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($gui) {
    # /cc = command line compile
    & $gui "/cc=$((Resolve-Path $iss).Path)"
  } else {
    Write-Error "Inno Setup not found. Open the .iss in the Inno Setup GUI and click Build → Compile."
  }
}
