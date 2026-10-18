$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security
$inputObject = [Console]::In.ReadToEnd() | ConvertFrom-Json
$key = [Convert]::FromBase64String($inputObject.key)
if ($key.Length -ne 32) { throw 'Token key must be 32 bytes' }
$hash = [System.Security.Cryptography.SHA256]::Create()
$encMaterial = New-Object byte[] ($key.Length + 3)
$macMaterial = New-Object byte[] ($key.Length + 3)
[Array]::Copy($key, 0, $encMaterial, 0, $key.Length)
[Array]::Copy($key, 0, $macMaterial, 0, $key.Length)
[Array]::Copy([Text.Encoding]::ASCII.GetBytes('enc'), 0, $encMaterial, $key.Length, 3)
[Array]::Copy([Text.Encoding]::ASCII.GetBytes('mac'), 0, $macMaterial, $key.Length, 3)
$encKey = $hash.ComputeHash($encMaterial)
$macKey = $hash.ComputeHash($macMaterial)
$aes = New-Object System.Security.Cryptography.AesManaged
$aes.KeySize = 256
$aes.Mode = [System.Security.Cryptography.CipherMode]::CBC
$aes.Padding = [System.Security.Cryptography.PaddingMode]::PKCS7
$aes.Key = $encKey
$hmac = New-Object System.Security.Cryptography.HMACSHA256
$hmac.Key = $macKey
try {
  if ($inputObject.mode -eq 'encrypt') {
    $aes.GenerateIV()
    $clear = [Text.Encoding]::UTF8.GetBytes($inputObject.payload)
    $transform = $aes.CreateEncryptor()
    $cipher = $transform.TransformFinalBlock($clear, 0, $clear.Length)
    $combined = New-Object byte[] ($aes.IV.Length + $cipher.Length)
    [Array]::Copy($aes.IV, 0, $combined, 0, $aes.IV.Length)
    [Array]::Copy($cipher, 0, $combined, $aes.IV.Length, $cipher.Length)
    $mac = $hmac.ComputeHash($combined)
    $output = New-Object byte[] ($combined.Length + $mac.Length)
    [Array]::Copy($combined, 0, $output, 0, $combined.Length)
    [Array]::Copy($mac, 0, $output, $combined.Length, $mac.Length)
    [Console]::Out.Write([Convert]::ToBase64String($output))
  } elseif ($inputObject.mode -eq 'decrypt') {
    $raw = [Convert]::FromBase64String($inputObject.payload)
    if ($raw.Length -lt 64) { throw 'Invalid encrypted token' }
    $combined = New-Object byte[] ($raw.Length - 32)
    $mac = New-Object byte[] 32
    [Array]::Copy($raw, 0, $combined, 0, $combined.Length)
    [Array]::Copy($raw, $combined.Length, $mac, 0, 32)
    $actual = $hmac.ComputeHash($combined)
    $match = 0
    for ($i = 0; $i -lt 32; $i++) { $match = $match -bor ($mac[$i] -bxor $actual[$i]) }
    if ($match -ne 0) { throw 'Encrypted token authentication failed' }
    $iv = New-Object byte[] 16
    [Array]::Copy($combined, 0, $iv, 0, 16)
    $aes.IV = $iv
    $cipher = New-Object byte[] ($combined.Length - 16)
    [Array]::Copy($combined, 16, $cipher, 0, $cipher.Length)
    $transform = $aes.CreateDecryptor()
    $clear = $transform.TransformFinalBlock($cipher, 0, $cipher.Length)
    [Console]::Out.Write([Text.Encoding]::UTF8.GetString($clear))
  } else { throw 'Unknown crypto operation' }
} finally {
  $aes.Dispose()
  $hmac.Dispose()
  $hash.Dispose()
}
