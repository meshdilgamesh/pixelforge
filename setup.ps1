# PixelForge Setup - modern installation wizard for Windows
# Classic wizard flow: Welcome -> Setup Type -> Installing -> Finish
# with Back / Next / Cancel navigation and a branded side banner.
# Launched by setup.bat. No admin rights needed.
# NOTE: keep this file plain ASCII - Windows PowerShell 5.1 reads .ps1
# files without a BOM as ANSI, and non-ASCII corrupts the parse.

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::EnableVisualStyles()

# ---- colors ----------------------------------------------------------------
$script:COL_BG    = [System.Drawing.Color]::FromArgb(14, 17, 28)
$script:COL_PANEL = [System.Drawing.Color]::FromArgb(27, 33, 52)
$script:COL_PANEL2= [System.Drawing.Color]::FromArgb(38, 45, 72)
$script:COL_TEXT  = [System.Drawing.Color]::FromArgb(238, 242, 255)
$script:COL_DIM   = [System.Drawing.Color]::FromArgb(154, 166, 195)
$script:COL_VIOLET= [System.Drawing.Color]::FromArgb(139, 92, 246)
$script:COL_CYAN  = [System.Drawing.Color]::FromArgb(34, 211, 238)
$script:COL_OK    = [System.Drawing.Color]::FromArgb(52, 211, 153)
$script:COL_ERR   = [System.Drawing.Color]::FromArgb(251, 113, 133)

# ---- form --------------------------------------------------------------------
$form                 = New-Object System.Windows.Forms.Form
$form.Text            = "PixelForge Setup"
$form.ClientSize      = New-Object System.Drawing.Size(820, 570)
$form.StartPosition   = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox     = $false
$form.BackColor       = $script:COL_BG

# ---- left art rail -------------------------------------------------------------
$art = New-Object System.Windows.Forms.PictureBox
$art.Location = New-Object System.Drawing.Point(0, 0)
$art.Size     = New-Object System.Drawing.Size(240, 570)
$art.SizeMode = "StretchImage"
$artPath = Join-Path $PSScriptRoot "setup-art.png"
if (Test-Path $artPath) { try { $art.Image = [System.Drawing.Image]::FromFile($artPath) } catch {} }
$form.Controls.Add($art)

# helper constructors ------------------------------------------------------------
function New-Label($text, $x, $y, $w, $h, $size, $bold, $color) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $text
    $l.Location = New-Object System.Drawing.Point($x, $y)
    $l.Size = New-Object System.Drawing.Size($w, $h)
    $l.ForeColor = $color
    $l.BackColor = [System.Drawing.Color]::Transparent
    $style = "Regular"
    if ($bold) { $style = "Bold" }
    $l.Font = New-Object System.Drawing.Font("Segoe UI", $size, [System.Drawing.FontStyle]::$style)
    return $l
}

# ---- shared header on content side ----------------------------------------------
$pageTag = New-Label "Step 1 of 3" 610  20  130  22  10  $false  $script:COL_DIM
$form.Controls.Add($pageTag)

# wizard pages: welcome(0), type(1), install(2), done(3)
$script:page = 0
$script:installing = $false

# ================================== PAGE 0: welcome ==============================
$pWelcome = New-Object System.Windows.Forms.Panel
$pWelcome.Location = New-Object System.Drawing.Point(264, 24)
$pWelcome.Size = New-Object System.Drawing.Size(530, 420)
$pWelcome.BackColor = $script:COL_BG
$form.Controls.Add($pWelcome)

$pWelcome.Controls.Add((New-Label "Welcome to" 0  30  520  40  20  $false  $script:COL_DIM))
$pWelcome.Controls.Add((New-Label "PixelForge Setup" 0  62  520  52  30  $true  $script:COL_TEXT))

$pWelcome.Controls.Add((New-Label "Forge blurry, low-resolution images into sharp, detailed 4K and 8K masterpieces - right on your own computer." 0  130  520  60  12  $false  $script:COL_TEXT))

$wBullets = @(
    "Free and open source - no subscription, no account",
    "Your images never leave this computer",
    "Runs great on modest GPUs - 6 GB is plenty",
    "Includes 9 AI models + your exclusive Signature model"
)
$wy = 205
foreach ($b in $wBullets) {
    $pWelcome.Controls.Add((New-Label "[+]" 4  $wy  34  24  11  $true  $script:COL_CYAN))
    $pWelcome.Controls.Add((New-Label $b 40  $wy  480  24  11  $false  $script:COL_TEXT))
    $wy += 30
}
$pWelcome.Controls.Add((New-Label "Install size: about 6 GB of disk. Internet needed once for PyTorch." 0  350  520  24  10  $false  $script:COL_DIM))

# ================================== PAGE 1: setup type ===========================
$pType = New-Object System.Windows.Forms.Panel
$pType.Location = New-Object System.Drawing.Point(264, 24)
$pType.Size = New-Object System.Drawing.Size(530, 420)
$pType.BackColor = $script:COL_BG
$form.Controls.Add($pType)

$pType.Controls.Add((New-Label "Setup Type" 0  26  520  44  26  $true  $script:COL_TEXT))

# card 1: Complete
$cardComplete = New-Object System.Windows.Forms.Panel
$cardComplete.Location = New-Object System.Drawing.Point(0, 86)
$cardComplete.Size = New-Object System.Drawing.Size(520, 92)
$cardComplete.BackColor = $script:COL_PANEL
$pType.Controls.Add($cardComplete)
$rbComplete = New-Object System.Windows.Forms.RadioButton
$rbComplete.Text = "Complete  (recommended)"
$rbComplete.Checked = $true
$rbComplete.ForeColor = $script:COL_CYAN
$rbComplete.BackColor = [System.Drawing.Color]::Transparent
$rbComplete.Location = New-Object System.Drawing.Point(14, 10)
$rbComplete.Size = New-Object System.Drawing.Size(480, 24)
$rbComplete.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$cardComplete.Controls.Add($rbComplete)
$cardComplete.Controls.Add((New-Label "Installs everything: app, AI models, Start Menu icon and auto-updates." 18  40  480  20  10  $false  $script:COL_DIM))
$cardComplete.Controls.Add((New-Label "Recommended for most users." 18  60  480  20  10  $false  $script:COL_DIM))

# card 2: Custom
$cardCustom = New-Object System.Windows.Forms.Panel
$cardCustom.Location = New-Object System.Drawing.Point(0, 190)
$cardCustom.Size = New-Object System.Drawing.Size(520, 92)
$cardCustom.BackColor = $script:COL_PANEL
$pType.Controls.Add($cardCustom)
$rbCustom = New-Object System.Windows.Forms.RadioButton
$rbCustom.Text = "Custom"
$rbCustom.ForeColor = $script:COL_TEXT
$rbCustom.BackColor = [System.Drawing.Color]::Transparent
$rbCustom.Location = New-Object System.Drawing.Point(14, 10)
$rbCustom.Size = New-Object System.Drawing.Size(480, 24)
$rbCustom.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$cardCustom.Controls.Add($rbCustom)
$cardCustom.Controls.Add((New-Label "Choose your own install folder and skip the Start Menu icon." 18  40  480  20  10  $false  $script:COL_DIM))
$cardCustom.Controls.Add((New-Label "Recommended for advanced users." 18  60  480  20  10  $false  $script:COL_DIM))

# location row (enabled for Custom)
$locLabel = New-Label "Install location:" 0  300  200  22  11  $true  $script:COL_TEXT
$pType.Controls.Add($locLabel)
$locBox = New-Object System.Windows.Forms.TextBox
$locBox.Text = "$env:LOCALAPPDATA\PixelForge"
$locBox.Location = New-Object System.Drawing.Point(0, 326)
$locBox.Size = New-Object System.Drawing.Size(420, 24)
$pType.Controls.Add($locBox)
$browse = New-Object System.Windows.Forms.Button
$browse.Text = "Browse..."
$browse.Location = New-Object System.Drawing.Point(430, 325)
$browse.Size = New-Object System.Drawing.Size(88, 26)
$pType.Controls.Add($browse)

$rbComplete.Add_CheckedChanged({
    if ($rbComplete.Checked) {
        $cardComplete.BackColor = $script:COL_PANEL2
        $cardCustom.BackColor = $script:COL_PANEL
        $locBox.Enabled = $false
        $browse.Enabled = $false
    }
})
$rbCustom.Add_CheckedChanged({
    if ($rbCustom.Checked) {
        $cardCustom.BackColor = $script:COL_PANEL2
        $cardComplete.BackColor = $script:COL_PANEL
        $locBox.Enabled = $true
        $browse.Enabled = $true
    }
})
$cardComplete.Add_Click({ $rbComplete.Checked = $true })
$cardCustom.Add_Click({ $rbCustom.Checked = $true })
$browse.Add_Click({
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = "Where should PixelForge be installed?"
    if ($dlg.ShowDialog() -eq "OK") { $locBox.Text = $dlg.SelectedPath }
})

# ================================== PAGE 2: installing ===========================
$pInstall = New-Object System.Windows.Forms.Panel
$pInstall.Location = New-Object System.Drawing.Point(264, 24)
$pInstall.Size = New-Object System.Drawing.Size(530, 420)
$pInstall.BackColor = $script:COL_BG
$form.Controls.Add($pInstall)

$pInstall.Controls.Add((New-Label "Installing PixelForge" 0  40  520  44  26  $true  $script:COL_TEXT))
$pInstall.Controls.Add((New-Label "This takes a few minutes on the first run - the big download happens only once." 0  96  520  24  11  $false  $script:COL_DIM))
$script:statusLbl = New-Label "Preparing..." 0  150  520  24  12  $true  $script:COL_CYAN
$pInstall.Controls.Add($statusLbl)
$script:bar = New-Object System.Windows.Forms.ProgressBar
$bar.Location = New-Object System.Drawing.Point(0, 184)
$bar.Size = New-Object System.Drawing.Size(520, 26)
$pInstall.Controls.Add($bar)
$script:detailLbl = New-Label "" 0  224  520  60  10  $false  $script:COL_DIM
$pInstall.Controls.Add($detailLbl)

# ================================== PAGE 3: done =================================
$pDone = New-Object System.Windows.Forms.Panel
$pDone.Location = New-Object System.Drawing.Point(264, 24)
$pDone.Size = New-Object System.Drawing.Size(530, 420)
$pDone.BackColor = $script:COL_BG
$form.Controls.Add($pDone)

$pDone.Controls.Add((New-Label "Installation complete!" 0  60  520  48  28  $true  $script:COL_OK))
$pDone.Controls.Add((New-Label "PixelForge has been installed successfully." 0  120  520  24  12  $false  $script:COL_TEXT))
$doneMsg = New-Label "" 0  152  520  60  11  $false  $script:COL_DIM
$pDone.Controls.Add($doneMsg)
$launchNow = New-Object System.Windows.Forms.CheckBox
$launchNow.Text = "Launch PixelForge now"
$launchNow.Checked = $true
$launchNow.ForeColor = $script:COL_TEXT
$launchNow.Location = New-Object System.Drawing.Point(0, 230)
$launchNow.AutoSize = $true
$pDone.Controls.Add($launchNow)

# ================================== navigation ==================================
$btnBack   = New-Object System.Windows.Forms.Button
$btnBack.Text = "< Back"
$btnBack.Size = New-Object System.Drawing.Size(88, 32)
$btnBack.Location = New-Object System.Drawing.Point(470, 524)
$btnBack.FlatStyle = "Flat"
$btnBack.FlatAppearance.BorderColor = $script:COL_VIOLET
$btnBack.BackColor = $script:COL_PANEL
$btnBack.ForeColor = $script:COL_TEXT
$form.Controls.Add($btnBack)

$btnNext   = New-Object System.Windows.Forms.Button
$btnNext.Text = "Next >"
$btnNext.Size = New-Object System.Drawing.Size(96, 32)
$btnNext.Location = New-Object System.Drawing.Point(564, 524)
$btnNext.FlatStyle = "Flat"
$btnNext.FlatAppearance.BorderSize = 0
$btnNext.BackColor = $script:COL_VIOLET
$btnNext.ForeColor = [System.Drawing.Color]::White
$form.Controls.Add($btnNext)

$btnCancel = New-Object System.Windows.Forms.Button
$btnCancel.Text = "Cancel"
$btnCancel.Size = New-Object System.Drawing.Size(80, 32)
$btnCancel.Location = New-Object System.Drawing.Point(666, 524)
$btnCancel.FlatStyle = "Flat"
$btnCancel.FlatAppearance.BorderSize = 0
$btnCancel.BackColor = $script:COL_PANEL
$btnCancel.ForeColor = $script:COL_TEXT
$form.Controls.Add($btnCancel)

function Show-Page($n) {
    $script:page = $n
    $pWelcome.Visible = ($n -eq 0)
    $pType.Visible    = ($n -eq 1)
    $pInstall.Visible = ($n -eq 2)
    $pDone.Visible    = ($n -eq 3)
    $btnBack.Enabled  = ($n -eq 1)
    $btnCancel.Enabled = (-not $script:installing)
    if ($n -eq 0) { $pageTag.Text = "Step 1 of 3"; $btnNext.Text = "Next >";  $btnNext.Enabled = $true }
    if ($n -eq 1) { $pageTag.Text = "Step 2 of 3"; $btnNext.Text = "Install"; $btnNext.Enabled = $true }
    if ($n -eq 2) { $pageTag.Text = "Step 3 of 3"; $btnNext.Enabled = $false }
    if ($n -eq 3) { $pageTag.Text = "Done";        $btnNext.Text = "Finish";  $btnNext.Enabled = $true; $btnNext.BackColor = $script:COL_OK }
    if ($n -lt 3 -and $n -ne 2) { $btnNext.BackColor = $script:COL_VIOLET }
    $form.Refresh()
}

function Set-Status($text, $pct) {
    $statusLbl.Text = $text
    $bar.Value = [Math]::Max(0, [Math]::Min(100, $pct))
    $form.Refresh()
    [System.Windows.Forms.Application]::DoEvents()
}

$btnBack.Add_Click({ Show-Page 0 })
$btnCancel.Add_Click({
    if ($script:installing) { return }
    $r = [System.Windows.Forms.MessageBox]::Show("Cancel the PixelForge setup?", "PixelForge Setup", "YesNo", "Question")
    if ($r -eq "Yes") { $form.Close() }
})
$btnNext.Add_Click({
    if ($script:page -eq 0) { Show-Page 1; return }
    if ($script:page -eq 3) {
        if ($launchNow.Checked) { Start-Process cmd -ArgumentList "/c", "`"$(Join-Path $script:destPath 'start.bat')`"" }
        $form.Close()
        return
    }
    if ($script:page -eq 1) {
        # resolve destination
        if ($rbComplete.Checked) { $script:destPath = "$env:LOCALAPPDATA\PixelForge" }
        else {
            $script:destPath = $locBox.Text.Trim().TrimEnd("\")
            if (-not $script:destPath) {
                [System.Windows.Forms.MessageBox]::Show("Please choose an install location first.", "PixelForge Setup", "OK", "Warning") | Out-Null
                return
            }
        }
        Show-Page 2
        $script:installing = $true
        $btnNext.Enabled = $false
        $btnBack.Enabled = $false
        $btnCancel.Enabled = $false
        Run-Install
    }
})

function Run-Install {
    try {
        $src  = $PSScriptRoot
        $dest = $script:destPath

        if (-not (Test-Path (Join-Path $src "pixelforge.py"))) {
            throw "pixelforge.py not found next to this installer. Please extract the zip first, then run setup.bat from the extracted folder."
        }
        Set-Status "Creating install folder..." 5
        New-Item -ItemType Directory -Force -Path $dest | Out-Null

        Set-Status "Copying app files (reuses any downloaded Python environment)..." 15
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

        if ($rbComplete.Checked) {
            Set-Status "Creating Start Menu shortcut..." 95
            $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\PixelForge.lnk")
            $lnk.TargetPath = Join-Path $dest "start.bat"
            $lnk.WorkingDirectory = $dest
            $lnk.Save()
            $doneMsg.Text = "Find PixelForge in your Start Menu, or run start.bat in:`n$dest"
        } else {
            $doneMsg.Text = "Portable install. Run start.bat in:`n$dest"
        }

        Set-Status "Done! PixelForge is installed." 100
        $script:installing = $false
        Show-Page 3
    }
    catch {
        $script:installing = $false
        $statusLbl.Text = "Setup problem"
        $statusLbl.ForeColor = $script:COL_ERR
        $bar.Value = 0
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, "PixelForge Setup", "OK", "Warning") | Out-Null
        $btnBack.Enabled = $true
        $btnCancel.Enabled = $true
        Show-Page 1
    }
}

Show-Page 0
[void]$form.ShowDialog()
