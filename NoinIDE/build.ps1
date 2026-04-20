param(
    [switch]$Generate,
    [string]$Source = "program.noin",
    [string]$Output = "src/program.generated.c",
    [switch]$Flash,
    [string]$Port = "COM3",
    [int]$Baud = 115200,
    [string]$Programmer = "arduino",
    [string]$BoardProfile = "nano_avr",
    [string]$AvrdudePart = "",
    [switch]$ChipErase,
    [switch]$NoVerify,
    [int]$VerboseLevel = 1,
    [string]$AvrdudeExtraArgs = ""
)

$ErrorActionPreference = "Stop"

$SparkFunPackageIndexUrl = "https://raw.githubusercontent.com/sparkfun/Arduino_Boards/main/IDE_Board_Manager/package_sparkfun_index.json"
$Esp32PackageIndexUrl = "https://espressif.github.io/arduino-esp32/package_esp32_index.json"

function Get-BoardProfileInfo([string]$BoardProfileName) {
    switch ($BoardProfileName) {
        "nano_avr" { return @{ Fqbn = "arduino:avr:nano"; Core = "arduino:avr"; AdditionalUrls = @(); Mcu = "atmega328p"; Fcpu = "16000000UL"; AvrdudePart = "m328p" } }
        "uno_avr" { return @{ Fqbn = "arduino:avr:uno"; Core = "arduino:avr"; AdditionalUrls = @(); Mcu = "atmega328p"; Fcpu = "16000000UL"; AvrdudePart = "m328p" } }
        "promicro_avr" { return @{ Fqbn = "SparkFun:avr:promicro"; Core = "SparkFun:avr"; AdditionalUrls = @($SparkFunPackageIndexUrl) } }
        "esp32_devkit" { return @{ Fqbn = "esp32:esp32:esp32"; Core = "esp32:esp32"; AdditionalUrls = @($Esp32PackageIndexUrl) } }
        default { throw "Unknown BoardProfile: $BoardProfileName" }
    }
}

function Test-ArduinoCliCoreInstalled {
    param([string]$Core)

    $arduinoCli = Get-Command arduino-cli -ErrorAction SilentlyContinue
    if (-not $arduinoCli) {
        return $false
    }

    $output = & $arduinoCli.Source core list 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $output) {
        return $false
    }

    return ($output -match "(?m)^\s*" + [regex]::Escape($Core) + "\s+")
}

function Ensure-ArduinoCliCore {
    param(
        [string]$Core,
        [string[]]$AdditionalUrls = @()
    )

    $arduinoCli = Get-Command arduino-cli -ErrorAction SilentlyContinue
    if (-not $arduinoCli) {
        throw "arduino-cli not found. Install it first: https://arduino.github.io/arduino-cli/"
    }

    if (Test-ArduinoCliCoreInstalled -Core $Core) {
        return
    }

    $coreArgs = @("core", "update-index")
    if ($AdditionalUrls.Count -gt 0) {
        $coreArgs += @("--additional-urls", ($AdditionalUrls -join ","))
    }

    Write-Host "Board platform missing, downloading: $Core"
    & $arduinoCli.Source @coreArgs
    if ($LASTEXITCODE -ne 0) { throw "arduino-cli core update-index failed" }

    $installArgs = @("core", "install", $Core)
    if ($AdditionalUrls.Count -gt 0) {
        $installArgs += @("--additional-urls", ($AdditionalUrls -join ","))
    }

    & $arduinoCli.Source @installArgs
    if ($LASTEXITCODE -ne 0) { throw "arduino-cli core install failed for $Core" }
}

function Invoke-GenerateIfNeeded {
    param([string]$Src, [string]$Out)

    if (-not $Generate) {
        return
    }

    $python = Get-Command py -ErrorAction SilentlyContinue
    if (-not $python) {
        $python = Get-Command python -ErrorAction SilentlyContinue
    }
    if (-not $python) {
        throw "Python not found. Install Python or run without -Generate."
    }

    & $python.Source "tools/noinc.py" $Src $Out
    if ($LASTEXITCODE -ne 0) { throw "DSL generation failed" }
}

function BuildWithMake {
    param(
        [string]$port,
        [int]$baud,
        [string]$programmer,
        [string]$mcu,
        [string]$fcpu,
        [string]$avrdudePart,
        [switch]$chipErase,
        [switch]$noVerify,
        [int]$verboseLevel,
        [string]$avrdudeExtraArgs
    )

    $base = Join-Path $env:LOCALAPPDATA "Arduino15\packages\arduino\tools"
    if (-not (Test-Path $base)) {
        throw "Arduino tools folder not found: $base"
    }

    $gccExe = Get-ChildItem -Path $base -Recurse -Filter avr-gcc.exe | Sort-Object FullName -Descending | Select-Object -First 1
    $objcopyExe = Get-ChildItem -Path $base -Recurse -Filter avr-objcopy.exe | Sort-Object FullName -Descending | Select-Object -First 1
    $sizeExe = Get-ChildItem -Path $base -Recurse -Filter avr-size.exe | Sort-Object FullName -Descending | Select-Object -First 1
    $avrdudeExe = Get-ChildItem -Path $base -Recurse -Filter avrdude.exe | Sort-Object FullName -Descending | Select-Object -First 1
    $avrdudeConf = Get-ChildItem -Path $base -Recurse -Filter avrdude.conf | Sort-Object FullName -Descending | Select-Object -First 1

    if (-not $gccExe -or -not $objcopyExe -or -not $sizeExe -or -not $avrdudeExe -or -not $avrdudeConf) {
        throw "Could not find one or more AVR tools under: $base"
    }

    $makeTool = Get-Command mingw32-make -ErrorAction SilentlyContinue
    if (-not $makeTool) {
        throw "mingw32-make is not installed or not in PATH"
    }

    Write-Host "Using avr-gcc: $($gccExe.FullName)"
    Write-Host "Using avrdude: $($avrdudeExe.FullName)"

    $makeArgs = @(
        "CC=$($gccExe.FullName)",
        "OBJCOPY=$($objcopyExe.FullName)",
        "SIZE=$($sizeExe.FullName)",
        "AVRDUDE=$($avrdudeExe.FullName)",
        "AVRDUDE_CONF=$($avrdudeConf.FullName)",
        "MCU=$mcu",
        "F_CPU=$fcpu",
        "AVRDUDE_PART=$avrdudePart"
    )

    & mingw32-make @makeArgs
    if ($LASTEXITCODE -ne 0) { throw "Build failed" }

    if ($Flash) {
        $effectiveVerboseLevel = [Math]::Max(0, $verboseLevel)
        $avrdudeFlags = @()
        for ($i = 0; $i -lt $effectiveVerboseLevel; $i++) {
            $avrdudeFlags += "-v"
        }
        if (-not $chipErase) {
            $avrdudeFlags += "-D"
        }
        if ($noVerify) {
            $avrdudeFlags += "-V"
        }
        if ($avrdudeExtraArgs) {
            $avrdudeFlags += $avrdudeExtraArgs.Trim()
        }

        $avrdudeFlagsText = ($avrdudeFlags -join " ").Trim()
        Write-Host "AVRDUDE flags: $avrdudeFlagsText"

        & mingw32-make @makeArgs "PORT=$port" "BAUD=$baud" "PROGRAMMER=$programmer" "AVRDUDE_FLAGS=$avrdudeFlagsText" flash
        if ($LASTEXITCODE -ne 0) { throw "Flash failed" }
    }
}

function BuildWithArduinoCli {
    param(
        [string]$fqbn,
        [string]$core,
        [string[]]$AdditionalUrls,
        [string]$port
    )

    Ensure-ArduinoCliCore -Core $core -AdditionalUrls $AdditionalUrls

    $arduinoCli = Get-Command arduino-cli -ErrorAction SilentlyContinue

    $sketchDir = Join-Path $env:TEMP "noin_sketch"
    $null = New-Item -ItemType Directory -Path $sketchDir -Force

    Copy-Item -Path "include/noin_program.h" -Destination (Join-Path $sketchDir "noin_program.h") -Force
    Copy-Item -Path "include/noin_runtime.h" -Destination (Join-Path $sketchDir "noin_runtime.h") -Force
    Copy-Item -Path "src/noin_runtime_arduino.cpp" -Destination (Join-Path $sketchDir "noin_runtime.cpp") -Force
    Copy-Item -Path $Output -Destination (Join-Path $sketchDir "program.generated.cpp") -Force

    @"
#include <Arduino.h>
#include "noin_program.h"

void setup() {
    noin_run();
}

void loop() {
}
"@ | Set-Content -Path (Join-Path $sketchDir "noin_sketch.ino") -Encoding UTF8

    & $arduinoCli.Source compile --fqbn $fqbn $sketchDir
    if ($LASTEXITCODE -ne 0) { throw "arduino-cli compile failed" }

    if ($Flash) {
        & $arduinoCli.Source upload -p $port --fqbn $fqbn $sketchDir
        if ($LASTEXITCODE -ne 0) { throw "arduino-cli upload failed" }
    }
}

Push-Location $PSScriptRoot
try {
    Invoke-GenerateIfNeeded -Src $Source -Out $Output

    $boardInfo = Get-BoardProfileInfo $BoardProfile

    if ($boardInfo.Core -eq "arduino:avr") {
        $effectiveAvrdudePart = if ($AvrdudePart) { $AvrdudePart } else { $boardInfo.AvrdudePart }
        BuildWithMake -port $Port -baud $Baud -programmer $Programmer -mcu $boardInfo.Mcu -fcpu $boardInfo.Fcpu -avrdudePart $effectiveAvrdudePart -chipErase:$ChipErase -noVerify:$NoVerify -verboseLevel $VerboseLevel -avrdudeExtraArgs $AvrdudeExtraArgs
    }
    else {
        Write-Host "Using board: $BoardProfile ($($boardInfo.Fqbn))"
        BuildWithArduinoCli -fqbn $boardInfo.Fqbn -core $boardInfo.Core -AdditionalUrls $boardInfo.AdditionalUrls -port $Port
    }
}
finally {
    Pop-Location
}
