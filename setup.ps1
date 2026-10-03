# PixelForge Setup - GUI installer for Windows
# Shows a real setup window: welcome, install-location picker, progress.
# Launched by setup.bat. No admin rights needed.
# NOTE: keep this file plain ASCII - Windows PowerShell 5.1 reads .ps1 files
# without a BOM as ANSI, and non-ASCII characters corrupt the parse.

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::EnableVisualStyles()

$form                    = New-Object System.Windows.Forms.Form
$form.Text               = "PixelForge Setup"
$form.Size               = New-Object System.Drawing.Size(600, 400)
$form.StartPosition      = "CenterScreen"
$form.FormBorderStyle    = "FixedDialog"
$form.MaximizeBox        = $false
$form.BackColor          = [System.Drawing.Color]::FromArgb(18, 21, 36)

# ---- banner ---------------------------------------------------------------
$banner                  = New-Object System.Windows.Forms.Label
$banner.Text             = "PixelForge"
$banner.Font             = New-Object System.Drawing.Font("Segoe UI", 22, [System.Drawing.FontStyle]::Bold)
$banner.ForeColor        = [System.Drawing.Color]::FromArgb(139, 92, 246)
$banner.AutoSize         = $true
$banner.Location         = New-Object System.Drawing.Point(24, 14)
$form.Controls.Add($banner)

$tagline                 = New-Object System.Windows.Forms.Label
$tagline.Text            = "Free, open-source AI image upscaler - runs 100 percent on your PC"
$tagline.ForeColor       = [System.Drawing.Color]::Gainsboro
$tagline.AutoSize        = $true
$tagline.Location        = New-Object System.Drawing.Point(26, 58)
$form.Controls.Add($tagline)

$welcome                 = New-Object System.Windows.Forms.Label
$welcome.Text            = "Installs the app, PyTorch with NVIDIA CUDA support and your AI models. Nothing is uploaded anywhere; no admin rights needed."
$welcome.ForeColor       = [System.Drawing.Color]::Silver
$welcome.Size            = New-Object System.Drawing.Size(530, 40)
$welcome.Location        = New-Object System.Drawing.Point(26, 88)
$form.Controls.Add($welcome)

# ---- location row ----------------------------------------------------------
$locLabel                = New-Object System.Windows.Forms.Label
$locLabel.Text           = "Install location:"
$locLabel.ForeColor      = [System.Drawing.Color]::White
$locLabel.AutoSize       = $true
$locLabel.Location       = New-Object System.Drawing.Point(26, 140)
$form.Controls.Add($locLabel)

$locBox                  = New-Object System.Windows.Forms.TextBox
$locBox.Text             = "$env:LOCALAPPDATA\PixelForge"
$locBox.Size             = New-Object System.Drawing.Size(420, 26)
$locBox.Location         = New-Object System.Drawing.Point(26, 162)
$form.Controls.Add($locBox)

$browse                  = New-Object System.Windows.Forms.Button
$browse.Text             = "Browse..."
$browse.Size             = New-Object System.Drawing.Size(90, 26)
$browse.Location         = New-Object System.Drawing.Point(456, 161)
$browse.Add_Click({
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = "Where should PixelForge be installed?"
    if ($dlg.ShowDialog() -eq "OK") { $locBox.Text = $dlg.SelectedPath }
})
$form.Controls.Add($browse)

# ---- checkbox + progress ----------------------------------------------------
$launchAfter             = New-Object System.Windows.Forms.CheckBox
$launchAfter.Text        = "Launch PixelForge when setup finishes"
$launchAfter.Checked     = $true
$launchAfter.ForeColor   = [System.Drawing.Color]::White
$launchAfter.AutoSize    = $true
$launchAfter.Location    = New-Object System.Drawing.Point(26, 202)
$form.Controls.Add($launchAfter)

$status                  = New-Object System.Windows.Forms.Label
$status.Text             = "Ready to install."
$status.ForeColor        = [System.Drawing.Color]::FromArgb(34, 211, 238)
$status.AutoSize         = $true
$status.Location         = New-Object System.Drawing.Point(26, 240)
$form.Controls.Add($status)

$bar                     = New-Object System.Windows.Forms.ProgressBar
$bar.Size                = New-Object System.Drawing.Size(520, 22)
$bar.Location            = New-Object System.Drawing.Point(26, 266)
$form.Controls.Add($bar)

# ---- install button ----------------------------------------------------------
$installBtn              = New-Object System.Windows.Forms.Button
$installBtn.Text         = "Install"
$installBtn.Size         = New-Object System.Drawing.Size(520, 38)
$installBtn.Location     = New-Object System.Drawing.Point(26, 300)
$installBtn.BackColor    = [System.Drawing.Color]::FromArgb(99, 102, 241)
$installBtn.ForeColor    = [System.Drawing.Color]::White
$installBtn.FlatStyle    = "Flat"
$form.Controls.Add($installBtn)

function Set-Status($text, $pct) {
    $status.Text = $text
    $bar.Value = [Math]::Max(0, [Math]::Min(100, $pct))
    $form.Refresh()
    [System.Windows.Forms.Application]::DoEvents()
}

$installBtn.Add_Click({
    $installBtn.Enabled = $false
    $browse.Enabled = $false
    $locBox.Enabled = $false
    $src  = $PSScriptRoot
    $dest = $locBox.Text.Trim().TrimEnd("\")

    try {
        if (-not (Test-Path (Join-Path $src "pixelforge.py"))) {
            throw "pixelforge.py not found next to this installer. Please extract the zip first, then run setup.bat from the extracted folder."
        }
        Set-Status "Creating install folder..." 5
        New-Item -ItemType Directory -Force -Path $dest | Out-Null

        Set-Status "Copying app files (includes any downloaded Python environment)..." 15
        robocopy $src $dest /E /NFL /NDL /NJH /NJS /XD outputs uploads datasets __pycache__ .git dist | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "Copying files failed (robocopy code $LASTEXITCODE). Check antivirus notifications and try another install location." }

        Set-Status "Setting up Python tooling (one time)..." 30
        $uv = "$env:USERPROFILE\.local\bin\uv.exe"
        if (-not (Test-Path $uv)) {
            $cmd = Get-Command uv -ErrorAction SilentlyContinue
            if ($cmd) { $uv = $cmd.Source } else {
                irm https://astral.sh/uv/install.ps1 | iex
                $uv = "$env:USERPROFILE\.local\bin\uv.exe"
            }
        }
        if (-not (Test-Path $uv)) { $cmd = Get-Command uv -ErrorAction SilentlyContinue; if ($cmd) { $uv = $cmd.Source } }
        if (-not (Test-Path $uv)) { throw "Could not find or install uv (the Python manager). Check your internet connection." }

        $venvPy = Join-Path $dest ".venv\Scripts\python.exe"
        if (-not (Test-Path $venvPy)) {
            Set-Status "Creating Python environment..." 40
            & $uv venv --python 3.13 (Join-Path $dest ".venv")
            if ($LASTEXITCODE -ne 0) { throw "Creating the Python environment failed. Check your internet connection." }
        }

        Set-Status "Checking PyTorch with NVIDIA CUDA support..." 50
        & $venvPy -c "import torch" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Set-Status "Installing PyTorch with NVIDIA CUDA (about 3 GB, one time)..." 55
            & $uv pip install -p $venvPy torch --index-url https://download.pytorch.org/whl/cu126
            if ($LASTEXITCODE -ne 0) { throw "Downloading PyTorch failed. Check your internet connection and retry." }
        }

        if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
            Set-Status "Verifying CUDA support..." 70
            & $venvPy -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>$null
            if ($LASTEXITCODE -ne 0) {
                Set-Status "Upgrading PyTorch to the CUDA build (one time)..." 75
                & $uv pip install -p $venvPy --reinstall-package torch --index-url https://download.pytorch.org/whl/cu126
            }
        }

        Set-Status "Installing app dependencies..." 85
        & $uv pip install -p $venvPy spandrel pillow numpy fastapi "uvicorn[standard]" python-multipart
        if ($LASTEXITCODE -ne 0) { throw "Installing app dependencies failed. Check your internet connection and retry." }

        Set-Status "Creating Start Menu shortcut..." 95
        $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\PixelForge.lnk")
        $lnk.TargetPath = Join-Path $dest "start.bat"
        $lnk.WorkingDirectory = $dest
        $lnk.Save()

        Set-Status "Done! PixelForge is installed." 100

        if ($launchAfter.Checked) {
            Start-Process cmd -ArgumentList "/c", "`"$dest\start.bat`""
            $form.Close()
        } else {
            [System.Windows.Forms.MessageBox]::Show("PixelForge is installed!`n`nFind it in your Start Menu, or run start.bat in:`n$dest", "PixelForge Setup", "OK", "Information") | Out-Null
            $form.Close()
        }
    }
    catch {
        $status.Text = "Setup problem"
        $bar.Value = 0
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, "PixelForge Setup", "OK", "Warning") | Out-Null
        $installBtn.Enabled = $true
        $browse.Enabled = $true
        $locBox.Enabled = $true
    }
})

[void]$form.ShowDialog()
