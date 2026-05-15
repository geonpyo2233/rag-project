[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$ModuleDllPath,

    [string]$ModuleName = "FilePathCheckerModule",

    [ValidateSet("CurrentUser", "LocalMachine")]
    [string]$Scope = "CurrentUser",

    [switch]$VerifyCom
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[STEP] $Message" -ForegroundColor Cyan
}

function Get-DllBitness {
    param([string]$Path)

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 64) {
        throw "Invalid PE file (too small): $Path"
    }

    $peOffset = [BitConverter]::ToInt32($bytes, 0x3C)
    if ($peOffset -le 0 -or $peOffset + 6 -ge $bytes.Length) {
        throw "Invalid PE header offset: $Path"
    }

    $machine = [BitConverter]::ToUInt16($bytes, $peOffset + 4)
    switch ($machine) {
        0x8664 { return "x64" } # IMAGE_FILE_MACHINE_AMD64
        0x014c { return "x86" } # IMAGE_FILE_MACHINE_I386
        default { return ("unknown(0x{0:X4})" -f $machine) }
    }
}

function Get-HwpAutomationRegistryPath {
    param([string]$TargetScope)

    switch ($TargetScope) {
        "CurrentUser" { return "HKCU:\Software\HNC\HwpAutomation\Modules" }
        "LocalMachine" { return "HKLM:\Software\HNC\HwpAutomation\Modules" }
        default { throw "Unsupported scope: $TargetScope" }
    }
}

function Register-ModulePath {
    param(
        [string]$RegistryPath,
        [string]$Name,
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $RegistryPath)) {
        if ($PSCmdlet.ShouldProcess($RegistryPath, "Create registry key")) {
            New-Item -Path $RegistryPath -Force | Out-Null
        }
    }

    if ($PSCmdlet.ShouldProcess("$RegistryPath\$Name", "Set module DLL path")) {
        New-ItemProperty -Path $RegistryPath -Name $Name -PropertyType String -Value $Path -Force | Out-Null
    }
}

function Test-ComRegisterModule {
    param([string]$Name)

    $hwp = $null
    try {
        $hwp = New-Object -ComObject "HWPFrame.HwpObject"
        $ok = $hwp.RegisterModule("FilePathCheckDLL", $Name)
        return [bool]$ok
    } catch {
        Write-Warning ("COM verification failed: " + $_.Exception.Message)
        return $false
    } finally {
        if ($null -ne $hwp) {
            try { $hwp.Quit() } catch {}
            [System.Runtime.InteropServices.Marshal]::ReleaseComObject($hwp) | Out-Null
        }
    }
}

$resolvedDll = (Resolve-Path -LiteralPath $ModuleDllPath).Path
if (-not (Test-Path -LiteralPath $resolvedDll -PathType Leaf)) {
    throw "DLL not found: $resolvedDll"
}

$dllBitness = Get-DllBitness -Path $resolvedDll
$osBitness = if ([Environment]::Is64BitOperatingSystem) { "x64" } else { "x86" }

Write-Step "Security module setup started"
Write-Host ("DLL Path     : {0}" -f $resolvedDll)
Write-Host ("Module Name  : {0}" -f $ModuleName)
Write-Host ("Scope        : {0}" -f $Scope)
Write-Host ("DLL Bitness  : {0}" -f $dllBitness)
Write-Host ("OS Bitness   : {0}" -f $osBitness)

if ($dllBitness -eq "unknown(0x0000)") {
    Write-Warning "DLL machine type could not be determined. Continue carefully."
}

$registryPath = Get-HwpAutomationRegistryPath -TargetScope $Scope
Write-Step "Writing registry entry"
Register-ModulePath -RegistryPath $registryPath -Name $ModuleName -Path $resolvedDll

$currentValue = (Get-ItemProperty -Path $registryPath -Name $ModuleName -ErrorAction Stop).$ModuleName
Write-Host ("Registered   : {0}\{1}" -f $registryPath, $ModuleName) -ForegroundColor Green
Write-Host ("Value        : {0}" -f $currentValue)

if ($VerifyCom) {
    Write-Step "Running COM RegisterModule verification"
    $verified = Test-ComRegisterModule -Name $ModuleName
    if ($verified) {
        Write-Host "COM verification: SUCCESS" -ForegroundColor Green
    } else {
        Write-Warning "COM verification: FAILED (check Hancom install, bitness, and module path)."
    }
}

Write-Step "Done"
Write-Host "Next: run document conversion once and confirm that security popups are reduced."
