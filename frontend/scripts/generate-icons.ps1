Add-Type -AssemblyName System.Drawing
$root = Join-Path $PSScriptRoot '..\public'
foreach ($size in @(32, 180)) {
    $canvas = [System.Drawing.Bitmap]::new($size, $size)
    $graphics = [System.Drawing.Graphics]::FromImage($canvas)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.ScaleTransform($size / 64, $size / 64)
    $dark = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#202b2a'))
    $lime = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#c6fb4a'))
    $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
    $path.AddArc(0, 0, 28, 28, 180, 90)
    $path.AddArc(36, 0, 28, 28, 270, 90)
    $path.AddArc(36, 36, 28, 28, 0, 90)
    $path.AddArc(0, 36, 28, 28, 90, 90)
    $path.CloseFigure()
    $graphics.FillPath($dark, $path)
    $pen = [System.Drawing.Pen]::new($lime.Color, 7)
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    $graphics.DrawLine($pen, 13, 50, 30, 14)
    $graphics.DrawLine($pen, 30, 14, 47, 50)
    $bar = [System.Drawing.Pen]::new($lime.Color, 5)
    $bar.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $bar.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $graphics.DrawLine($bar, 22, 37, 38, 37)
    $graphics.FillEllipse($lime, 46, 13, 8, 8)
    $name = if ($size -eq 32) { 'favicon-32.png' } else { 'apple-touch-icon.png' }
    $canvas.Save((Join-Path $root $name), [System.Drawing.Imaging.ImageFormat]::Png)
    $bar.Dispose(); $pen.Dispose(); $path.Dispose(); $lime.Dispose(); $dark.Dispose(); $graphics.Dispose(); $canvas.Dispose()
}
